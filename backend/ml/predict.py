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
    Prédit le nombre d'heures restantes avant qu'une poubelle soit pleine
    en utilisant VÉRITABLEMENT le modèle Machine Learning (RandomForest).

    Algorithme :
      1. Récupère l'historique et calcule le temps depuis la dernière collecte.
      2. Simule le temps heure par heure dans le futur.
      3. Interroge le modèle ML à chaque itération pour prédire le niveau.
      4. S'arrête quand la prédiction atteint 100% ou après 7 jours max (168h).
    """
    from models import Bin, BinLevel
    from datetime import datetime, timedelta
    import numpy as np

    # Récupération de la poubelle
    bin_item = Bin.query.get(bin_id)
    if not bin_item:
        return {"error": f"Poubelle ID {bin_id} introuvable"}

    current_fill = bin_item.fill_percentage

    # Cas trivial : poubelle déjà pleine
    if current_fill >= 100:
        return format_prediction_response(
            bin_id=bin_id, current_fill=current_fill, fill_speed=0,
            hours_until_full=0, confidence="high"
        )

    # Récupération de l'historique pour déterminer la dernière collecte
    levels = BinLevel.query.filter_by(bin_id=bin_id).order_by(BinLevel.timestamp.asc()).all()
    num_records = len(levels)

    # ── Calcul du niveau de confiance ────────────────────────────────────────
    if num_records >= 20:
        confidence = "high"
    elif num_records >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    # ── Calcul des heures depuis la dernière collecte ────────────────────────
    hours_since_last_collection = 0
    if levels:
        last_lvl = levels[-1]
        last_collect_time = levels[0].timestamp
        # On remonte l'historique pour trouver le dernier vidage (<= 5%)
        for lvl in reversed(levels):
            if lvl.fill_percentage <= 5.0:
                last_collect_time = lvl.timestamp
                break
        hours_since_last_collection = int((last_lvl.timestamp - last_collect_time).total_seconds() / 3600)

    # ── Simulation temporelle avec le modèle ML ──────────────────────────────
    model = load_fill_predictor()
    
    simulated_fill = current_fill
    now = datetime.utcnow()
    hours_ahead = 0
    max_simulation_hours = 168  # Ne pas simuler au-delà d'une semaine

    while simulated_fill < 100.0 and hours_ahead < max_simulation_hours:
        hours_ahead += 1
        future_time = now + timedelta(hours=hours_ahead)
        
        # Le RandomForest attend 4 variables : hour, day_of_week, hours_since, previous_fill
        X_input = np.array([[
            future_time.hour,
            future_time.weekday(),
            hours_since_last_collection + hours_ahead,
            simulated_fill
        ]])
        
        # Le modèle prédit le niveau de remplissage pour l'heure H+1
        predicted_next = model.predict(X_input)[0]
        
        # On s'assure mathématiquement que le niveau ne baisse pas 
        # (le camion ne passera pas tout seul dans la simulation)
        simulated_fill = max(simulated_fill, predicted_next)

    # Si le modèle prévoit qu'elle ne sera pas pleine d'ici 1 semaine
    if hours_ahead >= max_simulation_hours:
        hours_until_full = max_simulation_hours
    else:
        hours_until_full = hours_ahead

    # Calcul d'une "vitesse moyenne" indicative pour l'interface
    fill_speed = (100 - current_fill) / hours_until_full if hours_until_full > 0 else 0

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
