"""
config.py — Configuration centrale de l'application SmartWaste

Ce fichier regroupe toutes les variables de configuration lues depuis
les variables d'environnement (fichier .env). Cela permet de ne jamais
écrire de secrets directement dans le code source (bonne pratique de sécurité).
"""

import os
from datetime import timedelta


class Config:
    """
    Classe de configuration principale.
    Toutes les valeurs sensibles sont lues depuis les variables d'environnement.
    Des valeurs par défaut sûres sont fournies pour le développement local.
    """

    # ─── Base de données ──────────────────────────────────────────────────────
    # URI de connexion. Utilise SQLite par défaut en local si aucune variable
    # n'est définie (facilite le déploiement sur Hugging Face Spaces).
    _db_url = os.getenv("DATABASE_URL")
    if not _db_url:
        _db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "smartwaste.db")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{_db_path}"
    else:
        # Corrige le préfixe postgres:// en postgresql:// requis par SQLAlchemy
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _db_url
    
    # Désactive le suivi des modifications SQLAlchemy (économie mémoire)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── JWT (JSON Web Token) ─────────────────────────────────────────────────
    # Clé secrète pour signer les tokens JWT. DOIT être changée en production !
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "smartwaste-change-me-in-production")
    # Durée de validité des tokens (8 heures par défaut)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_EXPIRES_HOURS", "8"))
    )

    # ─── Raspberry Pi API Key ─────────────────────────────────────────────────
    # Le hash SHA-256 de la clé API utilisée par le Raspberry Pi.
    # Le backend stocke le hash, jamais la clé en clair (sécurité).
    PI_API_KEY_HASH = os.getenv("PI_API_KEY_HASH", "")

    # ─── CORS ─────────────────────────────────────────────────────────────────
    # Origines autorisées à appeler l'API depuis un navigateur.
    # Séparer plusieurs origines par des virgules dans le .env.
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8080,http://localhost:3000,http://127.0.0.1:8080"
    ).split(",")

    # ─── Rate Limiting ────────────────────────────────────────────────────────
    # Limite le nombre de requêtes par IP pour prévenir les abus.
    RATE_LIMIT = os.getenv("RATE_LIMIT", "300 per hour")

    # ─── Machine Learning ─────────────────────────────────────────────────────
    # Chemin vers le dossier contenant les modèles ML sauvegardés (.pkl)
    ML_MODELS_PATH = os.getenv("ML_MODELS_PATH", "ml/models")
