"""
app.py — Point d'entrée principal de l'application Flask SmartWaste

Ce fichier crée et configure l'application Flask via le pattern Factory.
Le pattern Factory permet de créer plusieurs instances de l'app (dev, test, prod)
avec des configurations différentes sans modifier le code.

Composants initialisés :
  - SQLAlchemy : ORM pour PostgreSQL
  - JWTManager : gestion des tokens d'authentification
  - Flask-CORS  : autorisation des requêtes cross-origin depuis le frontend
  - Flask-Limiter : limitation du débit de requêtes (anti-abus)
  - 4 Blueprints : auth, bins, sensor, alerts, analytics

Démarrage :
  - Via Docker : gunicorn --bind 0.0.0.0:5000 app:app
  - En local    : python app.py
"""

import logging
import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from models import db


def create_app(config_class=Config) -> Flask:
    """
    Factory Function Flask — Crée et configure l'application SmartWaste.

    L'utilisation d'une factory function est une bonne pratique Flask qui :
    - Facilite les tests unitaires (une app par test)
    - Évite les imports circulaires
    - Permet différentes configurations (dev/prod/test)

    Args:
        config_class: Classe de configuration à utiliser (défaut: Config).

    Returns:
        Application Flask configurée et prête à être démarrée.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Logging ───────────────────────────────────────────────────────────────
    # Configuration du système de logs pour suivre les requêtes et erreurs
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename="logs/app.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger(__name__).info("SmartWaste API démarrage...")

    # ── Base de données ───────────────────────────────────────────────────────
    # Connexion à PostgreSQL via SQLAlchemy
    db.init_app(app)

    # ── Authentification JWT ──────────────────────────────────────────────────
    # Initialise la gestion des tokens JWT signés
    JWTManager(app)

    # ── CORS (Cross-Origin Resource Sharing) ─────────────────────────────────
    # Autorise le frontend (localhost:8080) à appeler l'API
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # Limite le nombre de requêtes par IP pour prévenir les abus
    Limiter(
        get_remote_address,
        app=app,
        default_limits=[app.config["RATE_LIMIT"]],
        storage_uri="memory://",
    )

    # ── Enregistrement des Blueprints (routes) ────────────────────────────────
    # Chaque blueprint gère un groupe de routes liées
    from routes.auth import auth_bp
    from routes.bins import bins_bp
    from routes.sensor import sensor_bp
    from routes.alerts import alerts_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp)      # /api/login, /api/register, /api/me
    app.register_blueprint(bins_bp)      # /api/bins, /api/nearby-bins, /api/collect
    app.register_blueprint(sensor_bp)    # /api/bin-data
    app.register_blueprint(alerts_bp)    # /api/alerts
    app.register_blueprint(analytics_bp) # /api/stats, /api/prediction, /api/seed

    # ── Service du frontend statique ─────────────────────────────────────────
    # Permet de servir le site web HTML/CSS/JS directement depuis Flask.
    # Indispensable pour le déploiement sur Hugging Face Spaces.
    from flask import send_from_directory

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
        if path != "" and os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    # ── Initialisation du contexte applicatif ────────────────────────────────
    with app.app_context():
        # Créer toutes les tables si elles n'existent pas encore
        db.create_all()

        # S'assurer que le dossier des modèles ML existe
        models_path = app.config.get("ML_MODELS_PATH", "ml/models")
        os.makedirs(models_path, exist_ok=True)

    return app


# Création de l'instance globale de l'application
# Cette instance est utilisée par Gunicorn : `gunicorn app:app`
app = create_app()


if __name__ == "__main__":
    # Lancement en mode développement avec rechargement automatique
    # NE PAS utiliser debug=True en production !
    app.run(host="0.0.0.0", port=5000, debug=True)
