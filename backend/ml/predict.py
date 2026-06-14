"""
ml/predict.py — Fonctions de prédiction Machine Learning SmartWaste

Ce fichier charge les modèles ML entraînés et fournit deux fonctions principales :

1. predict_hours_until_full(bin_id)
   → Prédit combien d'heures il reste avant que la poubelle soit pleine (100%)
   → Basé sur la vitesse de remplissage calculée depuis l'historique BinLevel

2. detect_weekly_peak()
   → Identifie le jour de la semaine où les poubelles se remplissent le plus vite
   → Analyse l'historique BinLevel groupé par jour de la semaine

Ces fonctions sont appelées par les routes de analytics.py.
"""

import os
import joblib
from datetime import datetime
from utils.constants import FRENCH_DAYS, DEFAULT_FILL_RATE_PER_HOUR, MIN_RECORDS_FOR_PREDICTION
from utils.helpers import format_prediction_response

# Chemin du modèle sauvegardé
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
FILL_MODEL_PATH = os.path.join(MODELS_DIR, "fill_predictor.pkl")

# Cache en mémoire du modèle (chargé une seule fois au démarrage)
_fill_model = None


def load_fill_predictor():
    """
    Charge le modèle de prédiction depuis le fichier .pkl.

    Si le modèle n'existe pas encore, il l'entraîne automatiquement.
    Le modèle est mis en cache (_fill_model) pour éviter de recharger
    le fichier à chaque requête.

    Returns:
        Pipeline sklearn chargé.
    """
    global _fill_model
    if _fill_model is not None:
        return _fill_model

    if not os.path.exists(FILL_MODEL_PATH):
        # Entraînement automatique si le modèle n'existe pas encore
        print("🤖 Modèle ML absent — entraînement automatique...")
        from ml.train_model import train_fill_predictor, save_models
        model = train_fill_predictor()
        save_models(model)
        _fill_model = model
    else:
        _fill_model = joblib.load(FILL_MODEL_PATH)
        print(f"✅ Modèle ML chargé depuis {FILL_MODEL_PATH}")

    return _fill_model


def predict_hours_until_full(bin_id: int) -> dict:
    """
    Prédit le nombre d'heures restantes avant qu'une poubelle soit pleine.

    Algorithme :
      1. Récupère les 50 dernières mesures BinLevel de la poubelle
      2. Calcule la vitesse de remplissage (% par heure) entre la 1ère et dernière mesure
      3. Si pas assez de données, utilise un taux par défaut (DEFAULT_FILL_RATE_PER_HOUR)
      4. Calcule : heures_restantes = (100 - fill_actuel) / vitesse
      5. Retourne la prédiction formatée avec un niveau de confiance

    Niveaux de confiance :
      - 'high'   : ≥ 20 mesures disponibles
      - 'medium' : 5 à 19 mesures
      - 'low'    : < 5 mesures (estimation peu fiable)

    Args:
        bin_id: Identifiant de la poubelle à analyser.

    Returns:
        Dictionnaire de prédiction (voir format_prediction_response).
    """
    # Import ici pour éviter les imports circulaires avec Flask
    from models import Bin, BinLevel

    # Récupération de la poubelle
    bin_item = Bin.query.get(bin_id)
    if not bin_item:
        return {"error": f"Poubelle ID {bin_id} introuvable"}

    current_fill = bin_item.fill_percentage

    # Cas trivial : poubelle déjà pleine
    if current_fill >= 100:
        return {
            "bin_id": bin_id,
            "current_fill_percentage": current_fill,
            "fill_speed_per_hour": 0,
            "hours_until_full": 0,
            "predicted_full_at_utc": None,
            "confidence": "high",
            "message": "La poubelle est déjà pleine — collecte requise immédiatement",
        }

    # Récupération des 50 dernières mesures
    levels = (
        BinLevel.query
        .filter_by(bin_id=bin_id)
        .order_by(BinLevel.timestamp.asc())
        .limit(50)
        .all()
    )

    num_records = len(levels)

    # ── Calcul du niveau de confiance ────────────────────────────────────────
    if num_records >= 20:
        confidence = "high"
    elif num_records >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    # ── Calcul de la vitesse de remplissage ───────────────────────────────────
    if num_records >= MIN_RECORDS_FOR_PREDICTION:
        first = levels[0]
        last = levels[-1]

        # Durée entre la première et dernière mesure (en heures)
        time_delta = (last.timestamp - first.timestamp).total_seconds() / 3600

        if time_delta > 0:
            # Vitesse moyenne de remplissage (% par heure)
            fill_delta = last.fill_percentage - first.fill_percentage
            fill_speed = fill_delta / time_delta
        else:
            fill_speed = DEFAULT_FILL_RATE_PER_HOUR
    else:
        # Pas assez de données → utiliser le taux par défaut
        fill_speed = DEFAULT_FILL_RATE_PER_HOUR

    # La vitesse ne peut pas être négative pour une prédiction de remplissage
    if fill_speed <= 0:
        return {
            "bin_id": bin_id,
            "current_fill_percentage": current_fill,
            "fill_speed_per_hour": round(fill_speed, 2),
            "hours_until_full": None,
            "predicted_full_at_utc": None,
            "confidence": confidence,
            "message": "Le niveau de remplissage est stable ou en baisse",
        }

    # ── Calcul des heures restantes ───────────────────────────────────────────
    remaining_fill = 100 - current_fill
    hours_until_full = remaining_fill / fill_speed

    return format_prediction_response(
        bin_id=bin_id,
        current_fill=current_fill,
        fill_speed=fill_speed,
        hours_until_full=hours_until_full,
        confidence=confidence,
    )


def detect_weekly_peak() -> dict:
    """
    Détecte le jour de la semaine avec le plus fort remplissage moyen.

    Algorithme :
      1. Récupère tous les enregistrements BinLevel des 30 derniers jours
      2. Groupe les mesures par jour de la semaine (0=Lundi, 6=Dimanche)
      3. Calcule le remplissage moyen par jour
      4. Identifie le jour avec le niveau moyen le plus élevé (peak day)

    Returns:
        {
            "peak_day": 4,
            "peak_day_name_fr": "Vendredi",
            "day_stats": [
                { "day": 0, "day_name_fr": "Lundi", "avg_fill": 42.5, "avg_increase": 3.2 },
                ...
            ]
        }
    """
    from models import BinLevel
    from datetime import timedelta

    # Analyse sur les 30 derniers jours
    since = datetime.utcnow() - timedelta(days=30)
    levels = (
        BinLevel.query
        .filter(BinLevel.timestamp >= since)
        .order_by(BinLevel.timestamp.asc())
        .all()
    )

    # Cas où pas assez de données
    if len(levels) < 14:
        return {
            "peak_day": 4,
            "peak_day_name_fr": "Vendredi",
            "message": "Données insuffisantes — résultat estimé",
            "day_stats": [
                {"day": i, "day_name_fr": FRENCH_DAYS[i], "avg_fill": 0, "avg_increase": 0}
                for i in range(7)
            ],
        }

    # ── Regroupement par jour de la semaine ───────────────────────────────────
    day_fills = {i: [] for i in range(7)}  # 0=Lundi ... 6=Dimanche

    for lvl in levels:
        day_of_week = lvl.timestamp.weekday()
        day_fills[day_of_week].append(lvl.fill_percentage)

    # ── Calcul des statistiques par jour ──────────────────────────────────────
    day_stats = []
    for day_idx in range(7):
        fills = day_fills[day_idx]
        if fills:
            avg_fill = round(sum(fills) / len(fills), 1)
            # L'augmentation moyenne = écart entre max et min des mesures du jour
            avg_increase = round(max(fills) - min(fills), 1) if len(fills) > 1 else 0
        else:
            avg_fill = 0
            avg_increase = 0

        day_stats.append({
            "day": day_idx,
            "day_name_fr": FRENCH_DAYS[day_idx],
            "avg_fill": avg_fill,
            "avg_increase": avg_increase,
        })

    # ── Identification du jour peak ───────────────────────────────────────────
    peak = max(day_stats, key=lambda d: d["avg_fill"])

    return {
        "peak_day": peak["day"],
        "peak_day_name_fr": peak["day_name_fr"],
        "day_stats": day_stats,
    }
