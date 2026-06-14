"""
middleware/role_middleware.py — Décorateur de contrôle d'accès basé sur les rôles (RBAC)

Ce fichier implémente le contrôle d'accès basé sur les rôles (Role-Based Access Control).
Le décorateur @roles_required protège les routes API en vérifiant que l'utilisateur
connecté a bien l'un des rôles autorisés pour accéder à la ressource.

Fonctionnement :
  1. Vérifie la présence et la validité du token JWT dans l'en-tête Authorization
  2. Extrait l'identité de l'utilisateur depuis le token
  3. Charge l'utilisateur depuis la base de données
  4. Vérifie que son rôle est dans la liste des rôles autorisés
  5. Bloque avec 403 Forbidden si le rôle n'est pas autorisé
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models import User


def roles_required(*roles):
    """
    Décorateur qui protège une route Flask en exigeant un ou plusieurs rôles.

    Usage dans une route :
        @api.post('/bins')
        @roles_required('admin')
        def create_bin():
            ...

        @api.get('/alerts')
        @roles_required('admin', 'driver')
        def list_alerts():
            ...

    Args:
        *roles: Un ou plusieurs rôles autorisés ('admin', 'driver').

    Returns:
        La fonction décorée qui vérifie le rôle avant d'exécuter la route.

    Raises:
        401 si aucun token JWT valide n'est fourni.
        403 si l'utilisateur n'a pas le rôle requis.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Étape 1 : Vérifier la présence et validité du token JWT
            # Lève une exception automatiquement si le token manque ou est expiré
            verify_jwt_in_request()

            # Étape 2 : Récupérer l'ID de l'utilisateur depuis le token JWT
            user_id = get_jwt_identity()

            # Étape 3 : Charger l'utilisateur depuis la base de données
            user = db_get_user(user_id)

            # Étape 4 : Vérifier que l'utilisateur existe et est actif
            if not user or not user.is_active:
                return jsonify({"error": "Utilisateur introuvable ou désactivé"}), 403

            # Étape 5 : Vérifier que le rôle de l'utilisateur est autorisé
            if user.role not in roles:
                return jsonify({
                    "error": f"Accès refusé — Rôle requis : {', '.join(roles)}"
                }), 403

            # Accès accordé : exécuter la route
            return fn(*args, **kwargs)

        return wrapper
    return decorator


def db_get_user(user_id: str):
    """
    Charge un utilisateur depuis la base de données par son ID JWT.

    Le JWT contient l'ID sous forme de chaîne, on le convertit en entier.

    Args:
        user_id: Identifiant de l'utilisateur (str depuis JWT).

    Returns:
        Objet User ou None si non trouvé.
    """
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None


def get_current_user():
    """
    Retourne l'utilisateur actuellement connecté depuis le contexte JWT.

    À utiliser à l'intérieur d'une route protégée (après @roles_required).

    Returns:
        Objet User correspondant au token JWT actif.
    """
    user_id = get_jwt_identity()
    return db_get_user(user_id)
