"""
routes/auth.py — Routes d'authentification JWT pour SmartWaste

Ce fichier gère toute l'authentification de l'application :
  - Connexion (login) : retourne un token JWT signé
  - Création de compte (register) : réservé aux admins
  - Informations de l'utilisateur connecté (me)
  - Health check de l'API

Sécurité :
  - Les mots de passe sont vérifiés via Werkzeug (hash PBKDF2)
  - Les tokens JWT sont signés avec une clé secrète
  - L'enregistrement de nouveaux utilisateurs requiert un rôle admin
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User
from utils.validators import require_fields, validate_role
from middleware.role_middleware import get_current_user, roles_required

# Blueprint Flask — toutes les routes de ce fichier auront le préfixe /api
auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.get("/health")
def health():
    """
    GET /api/health — Vérification que l'API est en ligne.
    Utilisé par Docker et les outils de monitoring pour tester la disponibilité.
    """
    return jsonify({"status": "ok", "message": "SmartWaste API opérationnelle ✅"})


@auth_bp.post("/login")
def login():
    """
    POST /api/login — Connexion d'un utilisateur.

    Corps de la requête (JSON) :
        {
            "email_or_username": "admin@smartwaste.local",
            "password": "admin12345"
        }

    Réponse (200) :
        {
            "access_token": "eyJ...",
            "user": {"id": 1, "username": "admin", "role": "admin", ...}
        }

    Erreurs :
        400 — Champs manquants
        401 — Email/username ou mot de passe incorrect
        403 — Compte désactivé
    """
    data = request.get_json() or {}

    # Validation des champs obligatoires
    ok, error = require_fields(data, ["email_or_username", "password"])
    if not ok:
        return jsonify({"error": error}), 400

    identifier = data["email_or_username"].strip().lower()
    password = data["password"]

    # Recherche de l'utilisateur par email OU par nom d'utilisateur
    user = (
        User.query.filter_by(email=identifier).first()
        or User.query.filter_by(username=identifier).first()
    )

    # Vérification du mot de passe (Werkzeug compare le hash)
    if not user or not user.check_password(password):
        return jsonify({"error": "Identifiants incorrects"}), 401

    # Vérification que le compte est actif
    if not user.is_active:
        return jsonify({"error": "Ce compte a été désactivé"}), 403

    # Création du token JWT signé (durée définie dans Config)
    # L'identité est l'ID de l'utilisateur sous forme de chaîne
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "username": user.username}
    )

    return jsonify({
        "access_token": access_token,
        "user": user.to_dict()
    })


@auth_bp.post("/register")
@roles_required("admin")
def register():
    """
    POST /api/register — Création d'un nouveau compte (admin uniquement).

    Seul un administrateur connecté peut créer de nouveaux comptes.
    Les citoyens n'ont pas de compte dans le système.

    Corps de la requête (JSON) :
        {
            "username": "nouveau_driver",
            "email": "driver2@smartwaste.local",
            "password": "motdepasse123",
            "role": "driver"
        }

    Réponse (201) :
        { "id": 3, "username": "nouveau_driver", "role": "driver", ... }

    Erreurs :
        400 — Champs manquants, rôle invalide, email/username déjà utilisé
    """
    data = request.get_json() or {}

    ok, error = require_fields(data, ["username", "email", "password", "role"])
    if not ok:
        return jsonify({"error": error}), 400

    # Validation du rôle (seuls 'admin' et 'driver' sont autorisés)
    if not validate_role(data["role"]):
        return jsonify({"error": "Rôle invalide. Valeurs acceptées : admin, driver"}), 400

    # Vérification de l'unicité de l'email
    if User.query.filter_by(email=data["email"].lower()).first():
        return jsonify({"error": "Cet email est déjà utilisé"}), 400

    # Vérification de l'unicité du nom d'utilisateur
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Ce nom d'utilisateur est déjà pris"}), 400

    # Création du nouvel utilisateur
    user = User(
        username=data["username"].strip(),
        email=data["email"].strip().lower(),
        role=data["role"]
    )
    # Le mot de passe est hashé automatiquement via Werkzeug
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.get("/me")
@jwt_required()
def me():
    """
    GET /api/me — Retourne les informations de l'utilisateur connecté.

    Nécessite un token JWT valide dans l'en-tête Authorization.

    Réponse (200) :
        { "id": 1, "username": "admin", "email": "...", "role": "admin", ... }

    Erreurs :
        401 — Token manquant ou expiré
        404 — Utilisateur non trouvé
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    return jsonify(user.to_dict())
