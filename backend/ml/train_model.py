"""
ml/train_model.py — Entraînement des modèles Machine Learning SmartWaste

Ce fichier entraîne et sauvegarde le modèle ML utilisé pour prédire le niveau 
de remplissage des poubelles.

Objectifs et améliorations :
  1. Génération de données synthétiques réalistes (pas de remise à zéro aléatoire, 
     utilisation de l'historique récent).
  2. Entraînement d'un modèle RandomForestRegressor, particulièrement performant 
     pour capturer les relations non-linéaires temporelles.
  3. Découpage strict des données (Train/Test Split) pour une évaluation honnête.
  4. Calcul et affichage des métriques R², MAE et RMSE.

Le modèle est sauvegardé au format .pkl (pickle) via joblib.
"""

import os
import random
import numpy as np
import joblib
from datetime import datetime, timezone, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import math

# Chemin vers le dossier de sauvegarde des modèles
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
FILL_MODEL_PATH = os.path.join(MODELS_DIR, "fill_predictor.pkl")


def generate_synthetic_data(num_bins: int = 10, days: int = 30) -> list:
    """
    Génère des données synthétiques réalistes pour entraîner le modèle.

    Améliorations par rapport à la version précédente :
    - Ajout de la variable `hours_since_last_collection`.
    - Ajout de la variable `previous_fill_level`.
    - Remise à zéro stricte lors de la collecte (au lieu d'une valeur aléatoire).
    
    Args:
        num_bins: Nombre de poubelles simulées.
        days: Nombre de jours d'historique à générer.

    Returns:
        Liste de tuples (heure, jour_semaine, heures_depuis_collecte, niveau_precedent, remplissage_actuel).
    """
    data = []
    # Utilisation de datetime.now(timezone.utc) recommandé dans les versions modernes de Python
    now = datetime.now(timezone.utc)

    for bin_num in range(num_bins):
        # Taux de remplissage de base (entre 1% et 5% par heure)
        base_rate = random.uniform(1.0, 5.0)
        
        # État initial
        current_fill = 0.0
        hours_since_last_collection = 0

        # On itère chronologiquement du passé vers le présent
        total_hours = days * 24
        for hour_offset in range(total_hours, 0, -1):
            ts = now - timedelta(hours=hour_offset)
            hour_of_day = ts.hour
            day_of_week = ts.weekday()

            # Mémorisation du niveau de l'heure précédente
            previous_fill_level = current_fill

            # Multiplicateur journalier (Vendredi/Samedi = plus de déchets)
            day_multiplier = 1.3 if day_of_week in (4, 5) else 1.0

            # Multiplicateur horaire (journée = plus actif, nuit = calme)
            if 7 <= hour_of_day <= 20:
                hour_multiplier = 1.5
            elif hour_of_day <= 6:
                hour_multiplier = 0.2
            else:
                hour_multiplier = 0.8

            # Calcul du nouveau niveau avec une légère composante aléatoire (bruit)
            increment = base_rate * day_multiplier * hour_multiplier
            increment += random.uniform(-0.5, 0.5)
            
            # Mise à jour de l'état
            current_fill = previous_fill_level + max(0, increment)
            hours_since_last_collection += 1

            # Simulation d'une collecte stricte si la poubelle dépasse 95%
            if current_fill >= 95.0:
                current_fill = 0.0
                hours_since_last_collection = 0

            # On s'assure que le niveau ne dépasse jamais 100%
            current_fill = min(100.0, current_fill)

            # Ajout de l'échantillon au dataset
            data.append((
                hour_of_day, 
                day_of_week, 
                hours_since_last_collection, 
                round(previous_fill_level, 1), 
                round(current_fill, 1)
            ))

    return data


def train_fill_predictor() -> Pipeline:
    """
    Entraîne un modèle Random Forest pour prédire le remplissage.

    Caractéristiques (features X) :
      - hour_of_day                 : Heure de la journée (0-23)
      - day_of_week                 : Jour de la semaine (0-6)
      - hours_since_last_collection : Heures écoulées depuis le dernier vidage
      - previous_fill_level         : Niveau de remplissage à t-1

    Cible (target y) :
      - current_fill                : Niveau de remplissage à t

    Returns:
        Pipeline sklearn entraîné.
    """
    print("📊 Génération des données d'entraînement...")
    raw_data = generate_synthetic_data(num_bins=20, days=60)

    # Séparation features (X) / target (y)
    X = np.array([[h, d, hs, p] for h, d, hs, p, _ in raw_data])
    y = np.array([current_fill for _, _, _, _, current_fill in raw_data])

    print(f"   → {len(X)} échantillons générés")

    # Découpage strict : 80% Entraînement, 20% Test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Pipeline : Normalisation + Random Forest Regressor
    # Random Forest est excellent pour capturer les ruptures brutales (remises à 0)
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
    ])

    print("🧠 Entraînement du modèle RandomForestRegressor en cours...")
    model.fit(X_train, y_train)

    # Prédictions sur l'ensemble de TEST (jamais vu par le modèle pendant l'entraînement)
    y_pred = model.predict(X_test)

    # Calcul des métriques de performance
    score_r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = math.sqrt(mean_squared_error(y_test, y_pred))

    print("\n📈 RÉSULTATS DE L'ÉVALUATION (SUR ENSEMBLE DE TEST) :")
    print("-" * 55)
    print(f"   → Score R²  : {score_r2:.4f}")
    print(f"   → MAE       : {mae:.2f} % (Erreur Absolue Moyenne)")
    print(f"   → RMSE      : {rmse:.2f} % (Racine Erreur Quadratique Moyenne)")
    print("-" * 55)

    return model


def save_models(fill_model: Pipeline) -> None:
    """
    Sauvegarde les modèles entraînés au format .pkl avec joblib.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(fill_model, FILL_MODEL_PATH)
    print(f"✅ Modèle sauvegardé avec succès : {FILL_MODEL_PATH}")


def main():
    """
    Pipeline complet d'entraînement des modèles ML.
    """
    print("🤖 Démarrage du pipeline SmartWaste ML...")
    print("=" * 55)

    # Entraînement du modèle de remplissage
    fill_model = train_fill_predictor()

    # Sauvegarde
    save_models(fill_model)

    print("=" * 55)
    print("🚀 Processus terminé avec succès !")


if __name__ == "__main__":
    main()
