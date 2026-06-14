# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Image Docker pour le backend SmartWaste (Flask + Gunicorn)
#
# Ce Dockerfile crée une image légère basée sur Python 3.11-slim.
# Gunicorn est utilisé comme serveur WSGI de production (plus performant
# que le serveur de développement intégré à Flask).
# ─────────────────────────────────────────────────────────────────────────────

# Image de base : Python 3.11 version slim (minimise la taille de l'image)
FROM python:3.11-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier uniquement requirements.txt en premier pour profiter du cache Docker
# (si requirements.txt ne change pas, pip install n'est pas réexécuté)
COPY requirements.txt .

# Installation des dépendances Python sans cache (réduit la taille de l'image)
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code source dans le conteneur
COPY . .

# Créer les dossiers nécessaires au démarrage
RUN mkdir -p logs ml/models

# Port exposé par Gunicorn
EXPOSE 5000

# Commande de démarrage :
# - 2 workers Gunicorn pour gérer les requêtes en parallèle
# - timeout 120s pour les opérations ML qui peuvent prendre du temps
# - bind sur toutes les interfaces (0.0.0.0) pour être accessible depuis Docker
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
