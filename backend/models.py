"""
models.py — Modèles de base de données SQLAlchemy pour SmartWaste

Ce fichier définit la structure de toutes les tables de la base de données.
Chaque classe Python correspond à une table PostgreSQL.
SQLAlchemy gère automatiquement la création des tables et les requêtes SQL.

Tables définies :
  - User       : comptes admin et chauffeur
  - Bin        : poubelles physiques avec leur position GPS
  - BinLevel   : historique des mesures de remplissage
  - Alert      : alertes générées quand une poubelle dépasse 80%
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Instance SQLAlchemy partagée entre tous les modules.
# Initialisée dans app.py via db.init_app(app)
db = SQLAlchemy()


class User(db.Model):
    """
    Utilisateur de l'application (Admin ou Chauffeur).
    Les citoyens n'ont pas de compte — ils utilisent l'interface publique.

    Sécurité : le mot de passe n'est JAMAIS stocké en clair.
    On stocke uniquement son hash PBKDF2 généré par Werkzeug.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Rôles possibles : 'admin' (accès total) ou 'driver' (chauffeur)
    role = db.Column(db.String(20), nullable=False, default="driver")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        """Hash le mot de passe et le stocke de façon sécurisée."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Vérifie si le mot de passe fourni correspond au hash stocké."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Sérialise l'utilisateur en dictionnaire (sans le hash du mot de passe)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class Bin(db.Model):
    """
    Poubelle intelligente connectée au système SmartWaste.

    Chaque poubelle a :
    - Des coordonnées GPS (latitude/longitude) pour la géolocalisation
    - Un niveau de remplissage actuel (fill_percentage 0-100)
    - Un statut calculé automatiquement (empty/medium/full)
    - Un historique complet des mesures (relation vers BinLevel)
    """
    __tablename__ = "bins"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False, default="Adresse non définie")
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    # Hauteur physique de la poubelle en cm (utilisée par le capteur HC-SR04)
    capacity_cm = db.Column(db.Float, nullable=False, default=60.0)
    # Niveau de remplissage actuel en pourcentage (0 = vide, 100 = pleine)
    fill_percentage = db.Column(db.Float, nullable=False, default=0.0)
    # Statut calculé : 'empty' (0-49%), 'medium' (50-79%), 'full' (80-100%)
    status = db.Column(db.String(20), nullable=False, default="empty")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relations : une poubelle a plusieurs mesures et plusieurs alertes
    levels = db.relationship(
        "BinLevel", backref="bin", lazy=True, cascade="all, delete-orphan"
    )
    alerts = db.relationship(
        "Alert", backref="bin", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Sérialise la poubelle en dictionnaire JSON-compatible."""
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "capacity_cm": self.capacity_cm,
            "fill_percentage": round(self.fill_percentage, 1),
            "status": self.status,
            "is_active": self.is_active,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Bin {self.name} ({self.fill_percentage}%)>"


class BinLevel(db.Model):
    """
    Enregistrement d'une mesure de remplissage par le capteur HC-SR04.

    Chaque envoi du Raspberry Pi crée un enregistrement ici.
    Ces données sont utilisées par le module ML pour :
    - Calculer la vitesse de remplissage
    - Prédire quand la poubelle sera pleine
    - Détecter le jour peak de la semaine
    """
    __tablename__ = "bin_levels"

    id = db.Column(db.Integer, primary_key=True)
    bin_id = db.Column(db.Integer, db.ForeignKey("bins.id"), nullable=False, index=True)
    # Pourcentage de remplissage calculé à partir de la distance mesurée
    fill_percentage = db.Column(db.Float, nullable=False)
    # Distance brute mesurée par le capteur ultrason (optionnel)
    distance_cm = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        """Sérialise la mesure en dictionnaire JSON-compatible."""
        return {
            "id": self.id,
            "bin_id": self.bin_id,
            "fill_percentage": round(self.fill_percentage, 1),
            "distance_cm": self.distance_cm,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<BinLevel bin={self.bin_id} fill={self.fill_percentage}% at {self.timestamp}>"


class Alert(db.Model):
    """
    Alerte générée automatiquement quand une poubelle dépasse le seuil critique (80%).

    Le système crée une alerte dès qu'une poubelle atteint 80% et qu'aucune
    alerte active n'existe déjà pour cette poubelle (évite les doublons).

    L'alerte est résolue quand un chauffeur marque la poubelle comme collectée.
    """
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    bin_id = db.Column(db.Integer, db.ForeignKey("bins.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    # Statut : 'active' (intervention requise) ou 'resolved' (collectée)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    # Timestamp de résolution (null si encore active)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Sérialise l'alerte en dictionnaire JSON-compatible."""
        return {
            "id": self.id,
            "bin_id": self.bin_id,
            "bin_name": self.bin.name if self.bin else None,
            "bin_address": self.bin.address if self.bin else None,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def __repr__(self) -> str:
        return f"<Alert bin={self.bin_id} status={self.status}>"
