# 🐳 Dockerfile pour Hugging Face Spaces
# Compile et lance le serveur Flask unifié (API + Frontend) sur le port 7860

FROM python:3.11-slim

# Configuration des variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copie et installation des dépendances backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source backend et des fichiers statiques frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Déplacement dans le répertoire du backend pour l'exécution
WORKDIR /app/backend

# Création des dossiers requis pour les logs et les modèles ML
RUN mkdir -p logs ml/models

# Port obligatoire exposé par Hugging Face Spaces
EXPOSE 7860

# Lancement de Gunicorn sur le port 7860
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "120", "app:app"]
