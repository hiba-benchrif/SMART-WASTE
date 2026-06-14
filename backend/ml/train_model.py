"""
ml/train_model.py — Entraînement des modèles Machine Learning SmartWaste

Ce fichier entraîne et sauvegarde les modèles ML utilisés pour :
  1. Prédire le taux de remplissage (Linear Regression)
     → Entrée  : heure de la journée, jour de la semaine, heures écoulées
     → Sortie  : niveau de remplissage prédit (%)
  2. Détecter le pic hebdomadaire (analyse statistique)
     → Identifier le jour de la semaine où les poubelles se remplissent le plus vite

Les modèles sont sauvegardés au format .pkl (pickle) via joblib.
Ils sont rechargés automatiquement lors des prédictions sans réentraînement.

Usage :
    python ml/train_model.py

Ou automatiquement au démarrage de l'app si aucun modèle n'existe.
"""

import os
import random
import numpy as np
import joblib
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Chemin vers le dossier de sauvegarde des modèles
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
FILL_MODEL_PATH = os.path.join(MODELS_DIR, "fill_predictor.pkl")


def generate_synthetic_data(num_bins: int = 10, days: int = 30) -> list:
    """
    Génère des données synthétiques réalistes pour entraîner le modèle.

    Simule le comportement de remplissage d'une poubelle :
    - Remplissage plus rapide les jours de marché (vendredi/samedi)
    - Variations diurnes (plus de déchets en journée)
    - Bruit aléatoire pour simuler la réalité

    Args:
        num_bins: Nombre de poubelles simulées.
        days: Nombre de jours d'historique à générer.

    Returns:
        Liste de tuples (heure, jour_semaine, heures_écoulées, fill_percentage).
    """
    data = []
    now = datetime.utcnow()

    for bin_num in range(num_bins):
        # Chaque poubelle a un taux de base différent (2 à 8% par heure)
        base_rate = random.uniform(2.0, 8.0)
        fill = random.uniform(0, 30)  # Niveau de départ aléatoire

        for hour_offset in range(days * 24):
            ts = now - timedelta(hours=(days * 24) - hour_offset)
            hour_of_day = ts.hour
            day_of_week = ts.weekday()

            # Multiplicateur journalier :
            # Vendredi (4) et Samedi (5) → +30% de déchets (marché, weekend)
            day_multiplier = 1.3 if day_of_week in (4, 5) else 1.0

            # Multiplicateur horaire : plus de déchets entre 7h et 20h
            if 7 <= hour_of_day <= 20:
                hour_multiplier = 1.5
            elif hour_of_day <= 6:
                hour_multiplier = 0.3
            else:
                hour_multiplier = 0.8

            # Incrément de remplissage pour cette heure
            increment = base_rate * day_multiplier * hour_multiplier / 24
            increment += random.uniform(-0.5, 1.0)  # Bruit aléatoire
            fill = min(100, fill + max(0, increment))

            # Simulation d'une collecte (remise à 0) quand la poubelle est pleine
            if fill >= 95:
                fill = random.uniform(0, 10)

            data.append((hour_of_day, day_of_week, hour_offset, round(fill, 1)))

    return data


def train_fill_predictor() -> Pipeline:
    """
    Entraîne un modèle de régression linéaire pour prédire le remplissage.

    Caractéristiques (features) :
      - hour_of_day   : heure de la journée (0-23)
      - day_of_week   : jour de la semaine (0=Lundi, 6=Dimanche)
      - hours_elapsed : nombre d'heures écoulées depuis le début

    Cible (target) :
      - fill_percentage : niveau de remplissage (0-100%)

    Le modèle est encapsulé dans un Pipeline scikit-learn avec
    un StandardScaler pour normaliser les features.

    Returns:
        Pipeline sklearn entraîné (StandardScaler + LinearRegression).
    """
    print("📊 Génération des données d'entraînement...")
    raw_data = generate_synthetic_data(num_bins=20, days=60)

    # Séparation features / target
    X = np.array([[h, d, e] for h, d, e, _ in raw_data])
    y = np.array([fill for _, _, _, fill in raw_data])

    print(f"   → {len(X)} échantillons générés")

    # Pipeline : normalisation + régression linéaire
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", LinearRegression()),
    ])

    model.fit(X, y)

    # Qualité du modèle
    score = model.score(X, y)
    print(f"   → Score R² du modèle : {score:.4f}")

    return model


def save_models(fill_model: Pipeline) -> None:
    """
    Sauvegarde les modèles entraînés au format .pkl avec joblib.

    joblib est préféré à pickle pour les objets numpy/sklearn
    car il est plus efficace pour les grands tableaux.

    Args:
        fill_model: Pipeline sklearn entraîné.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(fill_model, FILL_MODEL_PATH)
    print(f"✅ Modèle sauvegardé : {FILL_MODEL_PATH}")


def main():
    """
    Pipeline complet d'entraînement des modèles ML.

    Étapes :
      1. Génération des données synthétiques
      2. Entraînement du modèle de régression
      3. Sauvegarde des modèles
    """
    print("🤖 Démarrage de l'entraînement des modèles SmartWaste ML...")
    print("=" * 55)

    # Entraînement du prédicteur de remplissage
    fill_model = train_fill_predictor()

    # Sauvegarde
    save_models(fill_model)

    print("=" * 55)
    print("✅ Entraînement terminé avec succès !")
    print(f"   Modèles sauvegardés dans : {MODELS_DIR}/")


if __name__ == "__main__":
    main()
