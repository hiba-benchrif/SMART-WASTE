"""
routes/analytics.py — Statistiques, prédictions ML et seed des données de démo

Ce fichier expose les routes analytiques avancées :
  - Statistiques globales du tableau de bord admin
  - Prédictions ML du temps avant remplissage complet
  - Détection du pic hebdomadaire (jour le plus chargé)
  - Historique de remplissage pour les graphiques Chart.js
  - Seeding des données de démonstration
"""

import random
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from models import db, Bin, BinLevel, Alert, User
from utils.helpers import calculate_status, generate_alert_message
from utils.constants import FRENCH_DAYS, ALERT_THRESHOLD
from middleware.role_middleware import roles_required
from ml.predict import predict_hours_until_full, detect_weekly_peak

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api")


@analytics_bp.get("/stats")
@roles_required("admin")
def dashboard_stats():
    """
    GET /api/stats — Statistiques globales pour le tableau de bord admin.

    Réponse :
        {
            "total_bins": 8,
            "active_bins": 8,
            "full_bins": 3,
            "average_fill": 58.4,
            "active_alerts_count": 3,
            "recently_updated": [...5 dernières poubelles mises à jour]
        }
    """
    all_bins = Bin.query.filter_by(is_active=True).all()
    total = len(all_bins)
    full_count = sum(1 for b in all_bins if b.fill_percentage >= ALERT_THRESHOLD)
    avg_fill = round(sum(b.fill_percentage for b in all_bins) / total, 1) if total else 0
    active_alerts = Alert.query.filter_by(status="active").count()

    # 5 dernières poubelles mises à jour (triées par last_updated desc)
    recently = sorted(
        [b for b in all_bins if b.last_updated],
        key=lambda b: b.last_updated,
        reverse=True
    )[:5]

    return jsonify({
        "total_bins": total,
        "active_bins": total,
        "full_bins": full_count,
        "average_fill": avg_fill,
        "active_alerts_count": active_alerts,
        "recently_updated": [b.to_dict() for b in recently],
    })


@analytics_bp.get("/prediction/<int:bin_id>")
@roles_required("admin", "driver")
def prediction(bin_id: int):
    """
    GET /api/prediction/<bin_id> — Prédiction ML : heures avant remplissage complet.

    Utilise l'historique BinLevel pour calculer la vitesse de remplissage
    et estimer le temps restant avant d'atteindre 100%.

    Réponse :
        {
            "bin_id": 3,
            "current_fill_percentage": 82.0,
            "fill_speed_per_hour": 4.5,
            "hours_until_full": 4.0,
            "predicted_full_at_utc": "2024-06-06T10:30:00",
            "confidence": "high"
        }
    """
    bin_item = db.session.get(Bin, bin_id)
    if not bin_item:
        return jsonify({"error": "Poubelle introuvable"}), 404

    result = predict_hours_until_full(bin_id)
    return jsonify(result)


@analytics_bp.get("/weekly-peak")
@roles_required("admin")
def weekly_peak():
    """
    GET /api/weekly-peak — Détecte le jour de la semaine avec le plus fort remplissage.

    Analyse l'historique BinLevel pour trouver quel jour les poubelles
    se remplissent le plus vite. Utile pour planifier les collectes.

    Réponse :
        {
            "peak_day": 4,
            "peak_day_name_fr": "Vendredi",
            "day_stats": [
                { "day": 0, "day_name_fr": "Lundi", "avg_increase": 8.2, "avg_fill": 45.0 },
                ...
            ]
        }
    """
    result = detect_weekly_peak()
    return jsonify(result)


@analytics_bp.get("/history")
@roles_required("admin")
def fill_history():
    """
    GET /api/history?bin_id=&days=7 — Historique de remplissage pour les graphiques.

    Si bin_id est fourni : retourne les mesures de cette poubelle spécifique.
    Sinon : retourne la moyenne journalière de toutes les poubelles.

    Paramètres query :
        bin_id (int, optionnel) : ID de la poubelle
        days   (int, optionnel) : Nombre de jours d'historique (défaut : 7)

    Réponse pour average globale :
        [
            { "date": "2024-06-01", "average_fill": 42.3, "count": 45 },
            ...
        ]
    """
    bin_id = request.args.get("bin_id", type=int)
    days = min(int(request.args.get("days", 7)), 90)  # max 90 jours
    since = datetime.utcnow() - timedelta(days=days)

    if bin_id:
        # Historique d'une poubelle spécifique
        levels = (
            BinLevel.query
            .filter(BinLevel.bin_id == bin_id, BinLevel.timestamp >= since)
            .order_by(BinLevel.timestamp.asc())
            .limit(500)
            .all()
        )
        return jsonify([lvl.to_dict() for lvl in levels])

    # Moyenne journalière globale de toutes les poubelles
    levels = (
        BinLevel.query
        .filter(BinLevel.timestamp >= since)
        .order_by(BinLevel.timestamp.asc())
        .all()
    )

    # Regroupement par date
    daily = {}
    for lvl in levels:
        date_key = lvl.timestamp.strftime("%Y-%m-%d")
        if date_key not in daily:
            daily[date_key] = {"fills": [], "count": 0}
        daily[date_key]["fills"].append(lvl.fill_percentage)
        daily[date_key]["count"] += 1

    result = [
        {
            "date": date,
            "average_fill": round(sum(d["fills"]) / len(d["fills"]), 1),
            "count": d["count"],
        }
        for date, d in sorted(daily.items())
    ]
    return jsonify(result)


@analytics_bp.post("/seed")
def seed_demo_data():
    """
    POST /api/seed — Initialise la base de données avec des données de démonstration.

    Opération idempotente : si les données existent déjà, elles ne sont pas recréées.

    Crée :
      - 2 utilisateurs (admin + driver)
      - 8 poubelles à Casablanca
      - ~100 mesures d'historique par poubelle (7 jours simulés)
      - Alertes pour les poubelles ≥ 80%
    """
    # Vérification : si l'admin existe déjà, les données sont déjà créées
    if User.query.filter_by(email="admin@smartwaste.local").first():
        return jsonify({"message": "Les données de démonstration existent déjà ✅"})

    # ── Création des utilisateurs ────────────────────────────────────────────
    admin = User(username="admin", email="admin@smartwaste.local", role="admin")
    admin.set_password("admin12345")

    driver = User(username="driver", email="driver@smartwaste.local", role="driver")
    driver.set_password("driver12345")

    db.session.add_all([admin, driver])

    # ── Création des poubelles de démonstration ──────────────────────────────
    demo_bins_data = [
        {"name": "Poubelle Maarif 1",       "address": "Rue Ibnou Sina, Maarif, Casablanca",           "lat": 33.5866, "lng": -7.6315, "fill": 25},
        {"name": "Poubelle Maarif 2",       "address": "Rue Ibnou Sina 12, Maarif, Casablanca",        "lat": 33.5872, "lng": -7.6306, "fill": 55},
        {"name": "Poubelle Zerktouni 1",    "address": "Boulevard Zerktouni, Maarif, Casablanca",      "lat": 33.5892, "lng": -7.6254, "fill": 82},
        {"name": "Poubelle Hassan II 1",    "address": "Avenue Hassan II, Centre-ville, Casablanca",   "lat": 33.5948, "lng": -7.6186, "fill": 91},
        {"name": "Poubelle Corniche 1",     "address": "Boulevard de la Corniche, Ain Diab, Casablanca","lat": 33.5920, "lng": -7.6892, "fill": 45},
        {"name": "Poubelle Hay Mohammadi",  "address": "Rue Principale, Hay Mohammadi, Casablanca",   "lat": 33.5730, "lng": -7.5808, "fill": 73},
        {"name": "Poubelle Anfa",           "address": "Boulevard d'Anfa, Anfa, Casablanca",           "lat": 33.5952, "lng": -7.6491, "fill": 38},
        {"name": "Poubelle Sidi Moumen",    "address": "Rue Principale, Sidi Moumen, Casablanca",     "lat": 33.5690, "lng": -7.4985, "fill": 67},
    ]

    created_bins = []
    for item in demo_bins_data:
        bin_obj = Bin(
            name=item["name"],
            address=item["address"],
            latitude=item["lat"],
            longitude=item["lng"],
            fill_percentage=item["fill"],
            status=calculate_status(item["fill"]),
            capacity_cm=60.0,
        )
        db.session.add(bin_obj)
        created_bins.append((bin_obj, item["fill"]))

    db.session.flush()  # Obtenir les IDs sans commit

    # ── Génération de l'historique simulé (7 jours) ──────────────────────────
    now = datetime.utcnow()
    for bin_obj, final_fill in created_bins:
        start_fill = max(0, final_fill - random.uniform(30, 60))

        # Environ 100 mesures réparties sur 7 jours (toutes les ~100 minutes)
        num_records = 100
        interval_minutes = (7 * 24 * 60) / num_records

        for i in range(num_records):
            progress = i / num_records
            # Remplissage simulé avec bruit aléatoire
            simulated_fill = start_fill + (final_fill - start_fill) * progress
            simulated_fill += random.uniform(-2, 2)
            simulated_fill = max(0, min(100, simulated_fill))

            ts = now - timedelta(minutes=(num_records - i) * interval_minutes)
            db.session.add(BinLevel(
                bin_id=bin_obj.id,
                fill_percentage=round(simulated_fill, 1),
                distance_cm=round(60 * (1 - simulated_fill / 100), 1),
                timestamp=ts,
            ))

    # ── Création des alertes pour les poubelles critiques ────────────────────
    db.session.flush()
    for bin_obj, final_fill in created_bins:
        if final_fill >= ALERT_THRESHOLD:
            db.session.add(Alert(
                bin_id=bin_obj.id,
                message=generate_alert_message(bin_obj.name, final_fill),
                status="active",
            ))

    db.session.commit()

    return jsonify({
        "message": "Données de démonstration créées avec succès 🎉",
        "created": {
            "users": 2,
            "bins": len(created_bins),
            "history_records": len(created_bins) * 100,
            "alerts": sum(1 for _, f in created_bins if f >= ALERT_THRESHOLD),
        }
    }), 201
