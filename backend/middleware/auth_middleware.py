"""
middleware/auth_middleware.py — Fonctions d'aide à l'authentification

Ce fichier fournit des fonctions utilitaires pour vérifier
l'authentification JWT dans les routes Flask.
Le décorateur principal est dans role_middleware.py.
"""

from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models import User


def get_current_user():
    """
    Retourne l'utilisateur actuellement connecté depuis le contexte JWT.
    À utiliser à l'intérieur d'une route protégée par @jwt_required().

    Returns:
        Objet User ou None si non trouvé.
    """
    try:
        user_id = get_jwt_identity()
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None


def is_authenticated():
    """
    Vérifie si la requête courante contient un token JWT valide.

    Returns:
        True si authentifié, False sinon.
    """
    try:
        verify_jwt_in_request()
        return True
    except Exception:
        return False
