"""
utils/helpers.py — Fonctions utilitaires partagées dans SmartWaste

Ce fichier contient des fonctions réutilisables qui ne dépendent d'aucun
modèle de base de données. Elles sont utilisées dans les services et les routes.
"""

from datetime import datetime
from .constants import EMPTY_STATUS, MEDIUM_STATUS, FULL_STATUS, EMPTY_THRESHOLD, MEDIUM_THRESHOLD


def calculate_status(fill_percentage: float) -> str:
    """
    Convertit un pourcentage de remplissage en statut lisible.

    Règles :
      - 0 à 49%  → 'empty'  (poubelle disponible)
      - 50 à 79% → 'medium' (poubelle à mi-capacité)
      - 80 à 100% → 'full'  (poubelle à collecter)

    Args:
        fill_percentage: Valeur entre 0 et 100.

    Returns:
        Chaîne de statut : 'empty', 'medium' ou 'full'.
    """
    if fill_percentage >= MEDIUM_THRESHOLD:
        return FULL_STATUS
    if fill_percentage >= EMPTY_THRESHOLD:
        return MEDIUM_STATUS
    return EMPTY_STATUS


def generate_alert_message(bin_name: str, fill_percentage: float) -> str:
    """
    Génère un message d'alerte formaté pour une poubelle trop pleine.

    Args:
        bin_name: Nom de la poubelle (ex: 'Poubelle Maarif 1').
        fill_percentage: Niveau de remplissage actuel.

    Returns:
        Message d'alerte lisible pour les chauffeurs et admins.
    """
    level = round(fill_percentage, 1)
    urgency = "URGENT" if fill_percentage >= 90 else "Intervention requise"
    return f"{bin_name} est à {level}% — {urgency}"


def format_prediction_response(
    bin_id: int,
    current_fill: float,
    fill_speed: float,
    hours_until_full: float,
    confidence: str = "medium"
) -> dict:
    """
    Formate la réponse de prédiction ML en dictionnaire JSON-compatible.

    Args:
        bin_id: Identifiant de la poubelle.
        current_fill: Niveau de remplissage actuel (%).
        fill_speed: Vitesse de remplissage (% par heure).
        hours_until_full: Heures estimées avant d'atteindre 100%.
        confidence: Niveau de confiance : 'high', 'medium' ou 'low'.

    Returns:
        Dictionnaire prêt à être renvoyé en JSON.
    """
    if hours_until_full <= 0 or fill_speed <= 0:
        predicted_at = None
    else:
        from datetime import timezone
        now = datetime.utcnow()
        predicted_seconds = hours_until_full * 3600
        predicted_at = datetime.utcfromtimestamp(
            now.timestamp() + predicted_seconds
        ).isoformat()

    return {
        "bin_id": bin_id,
        "current_fill_percentage": round(current_fill, 1),
        "fill_speed_per_hour": round(fill_speed, 2),
        "hours_until_full": round(hours_until_full, 1) if hours_until_full > 0 else None,
        "predicted_full_at_utc": predicted_at,
        "confidence": confidence,
        "confidence_label_fr": {
            "high": "Élevée (≥20 mesures)",
            "medium": "Moyenne (5-19 mesures)",
            "low": "Faible (<5 mesures)"
        }.get(confidence, "Inconnue"),
    }
