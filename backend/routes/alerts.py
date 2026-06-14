"""
routes/alerts.py — Gestion des alertes SmartWaste

Ce fichier expose les routes pour consulter et résoudre les alertes.
Une alerte est créée automatiquement quand une poubelle dépasse 80%.
Elle est résolue quand un chauffeur la collecte ou manuellement via cette route.

Accès : chauffeurs ET admins (pas les citoyens)
"""

from datetime import datetime
from flask import Blueprint, jsonify, request
from models import db, Alert
from middleware.role_middleware import roles_required

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api")


@alerts_bp.get("/alerts")
@roles_required("admin", "driver")
def list_alerts():
    """
    GET /api/alerts?status=active — Liste les alertes.

    Paramètre query optionnel :
        status : 'active' (défaut), 'resolved', ou 'all'

    Réponse (200) : liste d'alertes triées par date décroissante.
    """
    status_filter = request.args.get("status", "active")

    query = Alert.query

    # Appliquer le filtre sur le statut si ce n'est pas 'all'
    if status_filter in ("active", "resolved"):
        query = query.filter_by(status=status_filter)

    alerts = query.order_by(Alert.created_at.desc()).all()
    return jsonify([a.to_dict() for a in alerts])


@alerts_bp.get("/alerts/count")
@roles_required("admin", "driver")
def count_alerts():
    """
    GET /api/alerts/count — Nombre d'alertes actives.

    Utile pour afficher un badge/compteur dans la navigation sans charger
    toute la liste des alertes.

    Réponse (200) : { "active_count": 3 }
    """
    count = Alert.query.filter_by(status="active").count()
    return jsonify({"active_count": count})


@alerts_bp.patch("/alerts/<int:alert_id>/resolve")
@roles_required("admin", "driver")
def resolve_alert(alert_id: int):
    """
    PATCH /api/alerts/<alert_id>/resolve — Résout manuellement une alerte.

    Marque une alerte comme résolue et enregistre l'heure de résolution.
    Utilisé quand l'admin ou le chauffeur résout manuellement une situation.

    Réponse (200) : alerte mise à jour.
    Erreur (404) : alerte introuvable.
    """
    alert = db.session.get(Alert, alert_id)
    if not alert:
        return jsonify({"error": "Alerte introuvable"}), 404

    if alert.status == "resolved":
        return jsonify({"error": "Cette alerte est déjà résolue"}), 400

    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "Alerte résolue avec succès",
        "alert": alert.to_dict()
    })
