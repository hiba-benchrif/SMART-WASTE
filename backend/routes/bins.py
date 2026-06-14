"""
routes/bins.py — Routes CRUD des poubelles + géolocalisation

Ce fichier gère toutes les opérations sur les poubelles :
  - Lister toutes les poubelles (public)
  - Trouver les poubelles proches via Haversine (public)
  - Créer / modifier / supprimer une poubelle (admin)
  - Marquer une poubelle comme collectée (chauffeur/admin)

La géolocalisation utilise la formule de Haversine (utils/geo.py)
pour calculer la distance réelle entre la position de l'utilisateur
et chaque poubelle.
"""

from datetime import datetime
from flask import Blueprint, jsonify, request
from models import db, Bin, Alert
from utils.validators import require_fields, validate_fill_level, validate_coordinates, validate_radius
from utils.helpers import calculate_status, generate_alert_message
from utils.geo import find_nearby_bins
from utils.constants import DEFAULT_RADIUS_KM, ALERT_THRESHOLD
from middleware.role_middleware import roles_required

bins_bp = Blueprint("bins", __name__, url_prefix="/api")


@bins_bp.get("/bins")
def list_bins():
    """
    GET /api/bins — Liste toutes les poubelles actives.

    Accessible sans authentification (citoyens + chauffeurs + admins).

    Réponse (200) : liste de poubelles triées par ID croissant.
    """
    bins = Bin.query.filter_by(is_active=True).order_by(Bin.id.asc()).all()
    return jsonify([b.to_dict() for b in bins])


@bins_bp.get("/nearby-bins")
def nearby_bins():
    """
    GET /api/nearby-bins?lat=&lng=&radius=2 — Poubelles dans un rayon donné.

    Utilise la formule de Haversine pour calculer la distance réelle.
    Résultats triés par distance croissante.

    Paramètres query string :
        lat    (float, requis) : Latitude de l'utilisateur
        lng    (float, requis) : Longitude de l'utilisateur
        radius (float, optionnel) : Rayon en km (défaut : 2, max : 10)

    Réponse (200) :
        [
          { ...bin, "distance_km": 0.45 },
          { ...bin, "distance_km": 1.2 },
        ]
    """
    # Lecture et validation des paramètres
    lat_raw = request.args.get("lat")
    lng_raw = request.args.get("lng")
    radius_raw = request.args.get("radius", DEFAULT_RADIUS_KM)

    if not lat_raw or not lng_raw:
        return jsonify({"error": "Paramètres lat et lng requis"}), 400

    coords_ok, coords = validate_coordinates(lat_raw, lng_raw)
    if not coords_ok:
        return jsonify({"error": coords}), 400

    radius_ok, radius = validate_radius(radius_raw)
    if not radius_ok:
        return jsonify({"error": radius}), 400

    user_lat, user_lng = coords

    # Récupération des poubelles actives
    active_bins = Bin.query.filter_by(is_active=True).all()

    # Filtrage et tri par distance Haversine
    nearby = find_nearby_bins(active_bins, user_lat, user_lng, radius)

    return jsonify(nearby)


@bins_bp.post("/bins")
@roles_required("admin")
def create_bin():
    """
    POST /api/bins — Crée une nouvelle poubelle (admin uniquement).

    Corps JSON requis :
        {
            "name": "Poubelle Maarif 3",
            "address": "Rue Ibnou Sina 15, Maarif, Casablanca",
            "latitude": 33.5870,
            "longitude": -7.6310,
            "capacity_cm": 60,
            "fill_percentage": 0
        }

    Réponse (201) : Poubelle créée.
    """
    data = request.get_json() or {}

    ok, error = require_fields(data, ["name", "latitude", "longitude"])
    if not ok:
        return jsonify({"error": error}), 400

    coords_ok, coords = validate_coordinates(data["latitude"], data["longitude"])
    if not coords_ok:
        return jsonify({"error": coords}), 400

    fill_ok, fill = validate_fill_level(data.get("fill_percentage", 0))
    if not fill_ok:
        return jsonify({"error": fill}), 400

    bin_item = Bin(
        name=data["name"].strip(),
        address=data.get("address", "Adresse non définie").strip(),
        latitude=coords[0],
        longitude=coords[1],
        capacity_cm=float(data.get("capacity_cm", 60.0)),
        fill_percentage=fill,
        status=calculate_status(fill),
    )
    db.session.add(bin_item)
    db.session.commit()

    return jsonify(bin_item.to_dict()), 201


@bins_bp.put("/bins/<int:bin_id>")
@roles_required("admin")
def update_bin(bin_id: int):
    """
    PUT /api/bins/<bin_id> — Met à jour une poubelle existante (admin uniquement).

    Tous les champs sont optionnels — seuls les champs fournis sont modifiés.
    """
    bin_item = db.session.get(Bin, bin_id)
    if not bin_item:
        return jsonify({"error": "Poubelle introuvable"}), 404

    data = request.get_json() or {}

    if "name" in data:
        bin_item.name = data["name"].strip()
    if "address" in data:
        bin_item.address = data["address"].strip()
    if "latitude" in data or "longitude" in data:
        lat = data.get("latitude", bin_item.latitude)
        lng = data.get("longitude", bin_item.longitude)
        coords_ok, coords = validate_coordinates(lat, lng)
        if not coords_ok:
            return jsonify({"error": coords}), 400
        bin_item.latitude, bin_item.longitude = coords
    if "capacity_cm" in data:
        bin_item.capacity_cm = float(data["capacity_cm"])
    if "fill_percentage" in data:
        fill_ok, fill = validate_fill_level(data["fill_percentage"])
        if not fill_ok:
            return jsonify({"error": fill}), 400
        bin_item.fill_percentage = fill
        bin_item.status = calculate_status(fill)

    bin_item.last_updated = datetime.utcnow()
    db.session.commit()

    return jsonify(bin_item.to_dict())


@bins_bp.delete("/bins/<int:bin_id>")
@roles_required("admin")
def delete_bin(bin_id: int):
    """
    DELETE /api/bins/<bin_id> — Suppression douce (soft delete) d'une poubelle.

    La poubelle n'est pas réellement supprimée de la base — elle est désactivée
    (is_active = False). Cela préserve l'historique des mesures.
    """
    bin_item = db.session.get(Bin, bin_id)
    if not bin_item:
        return jsonify({"error": "Poubelle introuvable"}), 404

    bin_item.is_active = False
    db.session.commit()

    return jsonify({"message": f"Poubelle '{bin_item.name}' désactivée avec succès"})


@bins_bp.post("/collect/<int:bin_id>")
@roles_required("admin", "driver")
def collect_bin(bin_id: int):
    """
    POST /api/collect/<bin_id> — Marque une poubelle comme collectée.

    Actions effectuées :
      1. Remet le niveau de remplissage à 0%
      2. Met le statut à 'empty'
      3. Résout toutes les alertes actives de cette poubelle
      4. Enregistre une mesure à 0% dans l'historique

    Accessible aux chauffeurs et aux admins.
    """
    from models import BinLevel

    bin_item = db.session.get(Bin, bin_id)
    if not bin_item:
        return jsonify({"error": "Poubelle introuvable"}), 404

    # 1. Remise à zéro du niveau de remplissage
    bin_item.fill_percentage = 0.0
    bin_item.status = "empty"
    bin_item.last_updated = datetime.utcnow()

    # 2. Résolution de toutes les alertes actives pour cette poubelle
    active_alerts = Alert.query.filter_by(bin_id=bin_id, status="active").all()
    for alert in active_alerts:
        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()

    # 3. Enregistrement de la collecte dans l'historique
    db.session.add(BinLevel(bin_id=bin_id, fill_percentage=0.0, distance_cm=None))

    db.session.commit()

    return jsonify({
        "message": f"Poubelle '{bin_item.name}' marquée comme collectée ✅",
        "bin": bin_item.to_dict(),
        "alerts_resolved": len(active_alerts)
    })
