"""
utils/geo.py — Calculs géographiques pour SmartWaste

Ce fichier implémente la formule de Haversine pour calculer les distances
entre coordonnées GPS. C'est la formule standard utilisée en navigation
pour calculer la distance sur une sphère (la Terre).

La formule de Haversine donne la distance en km entre deux points GPS
en tenant compte de la courbure de la Terre.
"""

import math
from typing import List

# Rayon moyen de la Terre en kilomètres (valeur standard WGS-84)
EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcule la distance en kilomètres entre deux points GPS.

    Formule de Haversine :
      a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlng/2)
      c = 2 × arcsin(√a)
      distance = R × c

    Args:
        lat1, lng1: Coordonnées du premier point (degrés décimaux).
        lat2, lng2: Coordonnées du second point (degrés décimaux).

    Returns:
        Distance en kilomètres (arrondie à 3 décimales).

    Exemple:
        # Distance Casablanca centre → Ain Diab
        dist = haversine(33.5731, -7.5898, 33.5920, -7.6892)
        # → environ 8.5 km
    """
    # Conversion des degrés en radians (obligatoire pour les fonctions math)
    lat1_r, lng1_r, lat2_r, lng2_r = map(math.radians, [lat1, lng1, lat2, lng2])

    # Différences de coordonnées
    delta_lat = lat2_r - lat1_r
    delta_lng = lng2_r - lng1_r

    # Calcul du terme intermédiaire 'a'
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lng / 2) ** 2
    )

    # Angle central en radians
    c = 2 * math.asin(math.sqrt(a))

    return round(EARTH_RADIUS_KM * c, 3)


def find_nearby_bins(bins: list, user_lat: float, user_lng: float, radius_km: float = 2.0) -> List[dict]:
    """
    Retourne les poubelles situées dans un rayon donné autour d'une position GPS.

    Utilise la formule de Haversine pour calculer la distance entre
    la position de l'utilisateur et chaque poubelle.

    Args:
        bins: Liste d'objets Bin SQLAlchemy.
        user_lat: Latitude de l'utilisateur.
        user_lng: Longitude de l'utilisateur.
        radius_km: Rayon de recherche en km (défaut : 2 km).

    Returns:
        Liste de dictionnaires de poubelles, avec le champ 'distance_km' ajouté,
        triée par distance croissante (la plus proche en premier).

    Exemple réponse :
        [
          {"id": 3, "name": "Poubelle Maarif 1", ..., "distance_km": 0.45},
          {"id": 7, "name": "Poubelle Zerktouni", ..., "distance_km": 1.2},
        ]
    """
    nearby = []

    for bin_item in bins:
        # Calcul de la distance entre l'utilisateur et cette poubelle
        distance = haversine(user_lat, user_lng, bin_item.latitude, bin_item.longitude)

        # Inclure uniquement si dans le rayon de recherche
        if distance <= radius_km:
            bin_dict = bin_item.to_dict()
            bin_dict["distance_km"] = distance
            nearby.append(bin_dict)

    # Tri par distance croissante (poubelle la plus proche en premier)
    return sorted(nearby, key=lambda x: x["distance_km"])


def get_google_maps_url(latitude: float, longitude: float) -> str:
    """
    Génère l'URL Google Maps pour naviguer vers une position GPS.

    Args:
        latitude: Latitude de la destination.
        longitude: Longitude de la destination.

    Returns:
        URL Google Maps prête à ouvrir dans un navigateur ou l'app mobile.
    """
    return f"https://maps.google.com/?q={latitude},{longitude}"
