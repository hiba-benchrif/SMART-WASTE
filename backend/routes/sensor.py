"""
routes/sensor.py — Route d'ingestion des données du Raspberry Pi

Ce fichier gère la réception des mesures envoyées par le capteur HC-SR04
connecté au Raspberry Pi. L'authentification se fait via une clé API
(X-API-KEY) et non par JWT, car le Pi n'a pas d'interface de connexion.

Sécurité :
  - La clé API est stockée sous forme de hash SHA-256 dans le .env
  - La comparaison utilise hmac.compare_digest() pour éviter les timing attacks
  - Si fill_percentage >= 80% et aucune alerte active → création automatique d'alerte
"""

import hashlib
import hmac
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from models import db, Bin, BinLevel, Alert
from utils.validators import require_fields, validate_fill_level
from utils.helpers import calculate_status, generate_alert_message
from utils.constants import ALERT_THRESHOLD
from middleware.role_middleware import roles_required

sensor_bp = Blueprint("sensor", __name__, url_prefix="/api")


def verify_pi_api_key(key: str) -> bool:
    """
    Vérifie la clé API du Raspberry Pi en comparant son hash SHA-256.

    La clé brute n'est jamais stockée côté serveur — uniquement son hash.
    hmac.compare_digest() est utilisé pour éviter les attaques par timing
    (timing attack : comparer caractère par caractère révèle la longueur).

    Args:
        key: Clé API reçue dans l'en-tête X-API-KEY de la requête.

    Returns:
        True si la clé correspond au hash stocké, False sinon.
    """
    stored_hash = current_app.config.get("PI_API_KEY_HASH", "")
    if not stored_hash:
        return False
    # Calcul du hash SHA-256 de la clé reçue
    received_hash = hashlib.sha256(key.encode()).hexdigest()
    # Comparaison sécurisée (résistante aux timing attacks)
    return hmac.compare_digest(received_hash, stored_hash)


@sensor_bp.post("/bin-data")
def ingest_bin_data():
    """
    POST /api/bin-data — Réception d'une mesure du Raspberry Pi.

    Authentification : en-tête X-API-KEY avec la clé secrète du Pi.

    Corps JSON requis :
        {
            "bin_id": 1,
            "fill_percentage": 75.5,
            "distance_cm": 15.0    (optionnel — distance brute du capteur)
        }

    Traitement effectué :
      1. Validation de la clé API
      2. Validation des données reçues
      3. Mise à jour de la poubelle (fill_percentage, status, last_updated)
      4. Enregistrement dans l'historique (BinLevel)
      5. Création d'une alerte si fill >= 80% et pas d'alerte active

    Réponse (200) : état mis à jour de la poubelle.
    """
    # ── Étape 1 : Vérification de la clé API ──────────────────────────────────
    api_key = request.headers.get("X-API-KEY", "")
    if not verify_pi_api_key(api_key):
        return jsonify({"error": "Clé API Raspberry Pi invalide"}), 401

    # ── Étape 2 : Validation des données ──────────────────────────────────────
    data = request.get_json() or {}

    ok, error = require_fields(data, ["bin_id", "fill_percentage"])
    if not ok:
        return jsonify({"error": error}), 400

    fill_ok, fill = validate_fill_level(data["fill_percentage"])
    if not fill_ok:
        return jsonify({"error": fill}), 400

    try:
        bin_id = int(data["bin_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "bin_id doit être un entier"}), 400

    distance_cm = data.get("distance_cm", None)
    if distance_cm is not None:
        try:
            distance_cm = float(distance_cm)
        except (ValueError, TypeError):
            distance_cm = None

    # ── Étape 3 : Récupération et mise à jour de la poubelle ──────────────────
    bin_item = db.session.get(Bin, bin_id)
    if not bin_item:
        return jsonify({"error": f"Poubelle ID {bin_id} introuvable"}), 404

    bin_item.fill_percentage = fill
    bin_item.status = calculate_status(fill)
    bin_item.last_updated = datetime.utcnow()

    # ── Étape 4 : Enregistrement dans l'historique BinLevel ───────────────────
    level_record = BinLevel(
        bin_id=bin_id,
        fill_percentage=fill,
        distance_cm=distance_cm,
    )
    db.session.add(level_record)

    # ── Étape 5 : Alerte automatique si seuil critique atteint ────────────────
    alert_created = False
    if fill >= ALERT_THRESHOLD:
        # Vérifier qu'il n'existe pas déjà une alerte active pour cette poubelle
        existing_alert = Alert.query.filter_by(
            bin_id=bin_id, status="active"
        ).first()

        if not existing_alert:
            # Créer une nouvelle alerte avec un message descriptif
            alert_msg = generate_alert_message(bin_item.name, fill)
            new_alert = Alert(bin_id=bin_id, message=alert_msg)
            db.session.add(new_alert)
            alert_created = True

    db.session.commit()

    return jsonify({
        "message": "Données reçues et enregistrées",
        "bin": bin_item.to_dict(),
        "alert_created": alert_created,
    })


@sensor_bp.get("/bin-data/<int:bin_id>")
@roles_required("admin", "driver")
def get_bin_history(bin_id: int):
    """
    GET /api/bin-data/<bin_id>?limit=50 — Historique des mesures d'une poubelle.

    Retourne les dernières mesures de remplissage enregistrées pour une poubelle.
    Utilisé par les graphiques de l'interface admin.

    Paramètres query :
        limit (int) : Nombre de mesures à retourner (défaut : 50, max : 500)
    """
    bin_item = db.session.get(Bin, bin_id)
    if not bin_item:
        return jsonify({"error": "Poubelle introuvable"}), 404

    limit = min(int(request.args.get("limit", 50)), 500)

    levels = (
        BinLevel.query
        .filter_by(bin_id=bin_id)
        .order_by(BinLevel.timestamp.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        "bin": bin_item.to_dict(),
        "history": [lvl.to_dict() for lvl in reversed(levels)],
        "count": len(levels),
    })
