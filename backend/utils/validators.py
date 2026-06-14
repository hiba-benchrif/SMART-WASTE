"""
utils/validators.py — Fonctions de validation des données entrantes

Ce fichier centralise la validation de toutes les données reçues par l'API.
Valider les entrées est crucial pour la sécurité et la fiabilité du système.
Chaque fonction retourne un tuple (succès: bool, valeur_ou_erreur).
"""

from .constants import VALID_ROLES


def require_fields(data: dict, fields: list) -> tuple:
    """
    Vérifie que tous les champs requis sont présents et non vides dans le dictionnaire.

    Args:
        data: Dictionnaire JSON reçu dans la requête.
        fields: Liste des noms de champs obligatoires.

    Returns:
        (True, None) si tout est valide.
        (False, "message d'erreur") si des champs manquent.

    Exemple:
        ok, error = require_fields(data, ['email', 'password'])
        if not ok:
            return jsonify({'error': error}), 400
    """
    missing = [
        field for field in fields
        if field not in data or data[field] in (None, "", [])
    ]
    if missing:
        return False, f"Champ(s) manquant(s) : {', '.join(missing)}"
    return True, None


def validate_fill_level(value) -> tuple:
    """
    Valide et convertit un niveau de remplissage.

    Args:
        value: Valeur brute (peut être str, int ou float).

    Returns:
        (True, float) si valide et entre 0 et 100.
        (False, "message d'erreur") sinon.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False, "fill_percentage doit être un nombre"
    if not 0 <= number <= 100:
        return False, "fill_percentage doit être entre 0 et 100"
    return True, number


def validate_coordinates(latitude, longitude) -> tuple:
    """
    Valide des coordonnées GPS (latitude, longitude).

    Args:
        latitude: Latitude brute (doit être entre -90 et 90).
        longitude: Longitude brute (doit être entre -180 et 180).

    Returns:
        (True, (float, float)) si valides.
        (False, "message d'erreur") sinon.
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return False, "latitude et longitude doivent être des nombres"
    if not -90 <= lat <= 90:
        return False, "latitude doit être entre -90 et 90"
    if not -180 <= lng <= 180:
        return False, "longitude doit être entre -180 et 180"
    return True, (lat, lng)


def validate_role(role: str) -> bool:
    """
    Vérifie qu'un rôle est valide pour le système SmartWaste.

    Args:
        role: Chaîne représentant le rôle ('admin' ou 'driver').

    Returns:
        True si le rôle est dans VALID_ROLES, False sinon.
    """
    return role in VALID_ROLES


def validate_radius(value, max_km: float = 10.0) -> tuple:
    """
    Valide un rayon de recherche géographique.

    Args:
        value: Valeur brute du rayon.
        max_km: Rayon maximum autorisé (défaut : 10 km).

    Returns:
        (True, float) si valide.
        (False, "message d'erreur") sinon.
    """
    try:
        radius = float(value)
    except (TypeError, ValueError):
        return False, "radius doit être un nombre"
    if radius <= 0:
        return False, "radius doit être positif"
    if radius > max_km:
        return False, f"radius ne peut pas dépasser {max_km} km"
    return True, radius
