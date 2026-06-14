"""
utils/constants.py — Constantes globales de l'application SmartWaste

Ce fichier centralise toutes les valeurs constantes utilisées dans le projet.
L'avantage de les regrouper ici est de n'avoir qu'un seul endroit à modifier
si les seuils ou valeurs changent (principe DRY — Don't Repeat Yourself).
"""

# ─── Rôles utilisateurs ───────────────────────────────────────────────────────
# Ensemble des rôles valides (les citoyens n'ont pas de compte)
VALID_ROLES = {"admin", "driver"}

# ─── Statuts des poubelles ────────────────────────────────────────────────────
# Valeurs de statut stockées en base de données
EMPTY_STATUS = "empty"     # Poubelle disponible (0-49%)
MEDIUM_STATUS = "medium"   # Poubelle à surveiller (50-79%)
FULL_STATUS = "full"       # Poubelle à collecter (80-100%)

# ─── Seuils de remplissage (en pourcentage) ───────────────────────────────────
# En dessous de ce seuil → statut 'empty'
EMPTY_THRESHOLD = 50
# En dessous de ce seuil → statut 'medium' ; au-dessus → statut 'full'
MEDIUM_THRESHOLD = 80
# Seuil déclenchant une alerte automatique
ALERT_THRESHOLD = 80

# ─── Géolocalisation ──────────────────────────────────────────────────────────
# Rayon de recherche par défaut pour les poubelles proches (en km)
DEFAULT_RADIUS_KM = 2.0
# Rayon maximum autorisé (évite les requêtes trop larges)
MAX_RADIUS_KM = 10.0

# ─── Raspberry Pi / Capteur ───────────────────────────────────────────────────
# Hauteur par défaut de la poubelle en cm (mesurée par HC-SR04)
DEFAULT_BIN_HEIGHT_CM = 60.0

# ─── Machine Learning ─────────────────────────────────────────────────────────
# Vitesse de remplissage par défaut si pas assez d'historique (% par heure)
DEFAULT_FILL_RATE_PER_HOUR = 5.0
# Nombre minimal de mesures pour une prédiction fiable
MIN_RECORDS_FOR_PREDICTION = 2

# ─── Jours de la semaine en français ──────────────────────────────────────────
# Index 0 = Lundi (standard Python weekday())
FRENCH_DAYS = [
    "Lundi", "Mardi", "Mercredi", "Jeudi",
    "Vendredi", "Samedi", "Dimanche"
]
