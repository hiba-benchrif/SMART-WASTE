from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
import hashlib
import hmac
from models import db, User, Alert, Bin
from services.auth_service import register_user, login_user
from services.bin_service import list_bins, create_bin, update_bin, delete_bin, ingest_pi_data, collection_route, bins_grouped_by_street
from services.analytics_service import dashboard_stats, fill_history, predict_full_time
from middleware.role_middleware import roles_required

api = Blueprint("api", __name__, url_prefix="/api")

@api.get("/health")
def health():
    return jsonify({"status": "ok", "message": "SmartWaste API is running"})

@api.post("/auth/register")
def register():
    user, error = register_user(request.get_json() or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(user.to_dict()), 201

@api.post("/auth/login")
def login():
    result, error = login_user(request.get_json() or {})
    if error:
        return jsonify({"error": error}), 401
    return jsonify(result)

@api.get("/bins")
def bins_index():
    return jsonify(list_bins())

@api.get("/bins/streets")
def bins_by_street():
    return jsonify(bins_grouped_by_street())

@api.post("/bins")
@roles_required("admin")
def bins_create():
    bin_item, error = create_bin(request.get_json() or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(bin_item.to_dict()), 201

@api.put("/bins/<int:bin_id>")
@roles_required("admin", "driver")
def bins_update(bin_id):
    bin_item, error = update_bin(bin_id, request.get_json() or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(bin_item.to_dict())

@api.delete("/bins/<int:bin_id>")
@roles_required("admin")
def bins_delete(bin_id):
    if not delete_bin(bin_id):
        return jsonify({"error": "Bin not found"}), 404
    return jsonify({"message": "Bin deleted"})

@api.get("/driver/route")
@roles_required("driver", "admin")
def driver_route():
    origin_lat = float(request.args.get("lat", 33.5731))
    origin_lng = float(request.args.get("lng", -7.5898))
    return jsonify(collection_route(origin_lat, origin_lng))

@api.get("/alerts")
@jwt_required(optional=True)
def alerts_index():
    alerts = Alert.query.order_by(Alert.created_at.desc()).all()
    return jsonify([alert.to_dict() for alert in alerts])

@api.patch("/alerts/<int:alert_id>/resolve")
@roles_required("admin", "driver")
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = "resolved"
    db.session.commit()
    return jsonify(alert.to_dict())

@api.get("/analytics/stats")
@roles_required("admin")
def stats():
    return jsonify(dashboard_stats())

@api.get("/analytics/history")
@roles_required("admin")
def history():
    bin_id = request.args.get("bin_id", type=int)
    return jsonify(fill_history(bin_id))

@api.get("/analytics/predict/<int:bin_id>")
@roles_required("admin", "driver")
def predict(bin_id):
    return jsonify(predict_full_time(bin_id))

@api.post("/pi/ingest")
def pi_ingest():
    key = request.headers.get("X-API-KEY", "")
    key_hash = current_app.config.get("PI_API_KEY_HASH", "")
    if not key_hash or not hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), key_hash):
        return jsonify({"error": "Invalid Raspberry Pi API key"}), 401
    bin_item, error = ingest_pi_data(request.get_json() or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(bin_item.to_dict())

@api.post("/seed")
def seed_demo_data():
    if User.query.filter_by(email="admin@smartwaste.local").first():
        update_demo_streets()
        return jsonify({"message": "Demo data already exists. Street data updated."})
    admin = User(name="Admin SmartWaste", email="admin@smartwaste.local", role="admin")
    admin.set_password("admin12345")
    driver = User(name="Driver SmartWaste", email="driver@smartwaste.local", role="driver")
    driver.set_password("driver12345")
    citizen = User(name="Citizen SmartWaste", email="citizen@smartwaste.local", role="citizen")
    citizen.set_password("citizen12345")
    db.session.add_all([admin, driver, citizen])
    db.session.commit()
    demo_bins = [
        {"name": "Poubelle Rue Ibnou Sina 1", "street": "Rue Ibnou Sina", "zone": "Maarif", "latitude": 33.5866, "longitude": -7.6315, "fill_level": 25},
        {"name": "Poubelle Rue Ibnou Sina 2", "street": "Rue Ibnou Sina", "zone": "Maarif", "latitude": 33.5872, "longitude": -7.6306, "fill_level": 55},
        {"name": "Poubelle Boulevard Zerktouni 1", "street": "Boulevard Zerktouni", "zone": "Maarif", "latitude": 33.5892, "longitude": -7.6254, "fill_level": 62},
        {"name": "Poubelle Avenue Hassan II 1", "street": "Avenue Hassan II", "zone": "Centre-ville", "latitude": 33.5948, "longitude": -7.6186, "fill_level": 88},
        {"name": "Poubelle Boulevard de la Corniche 1", "street": "Boulevard de la Corniche", "zone": "Ain Diab", "latitude": 33.5920, "longitude": -7.6892, "fill_level": 78},
    ]
    for item in demo_bins:
        create_bin(item)
    return jsonify({"message": "Demo data created"}), 201

def update_demo_streets():
    demo_updates = {
        "Bin Maarif": {"name": "Poubelle Rue Ibnou Sina 1", "street": "Rue Ibnou Sina", "zone": "Maarif"},
        "Bin Hassan II": {"name": "Poubelle Avenue Hassan II 1", "street": "Avenue Hassan II", "zone": "Centre-ville"},
        "Bin Casa Port": {"name": "Poubelle Boulevard des Almohades 1", "street": "Boulevard des Almohades", "zone": "Casa Port"},
        "Bin Ain Diab": {"name": "Poubelle Boulevard de la Corniche 1", "street": "Boulevard de la Corniche", "zone": "Ain Diab"},
    }
    for old_name, values in demo_updates.items():
        bin_item = Bin.query.filter_by(name=old_name).first()
        if bin_item:
            bin_item.name = values["name"]
            bin_item.street = values["street"]
            bin_item.zone = values["zone"]
    for bin_item in Bin.query.filter_by(street="Rue non definie").all():
        bin_item.street = "Rue non definie"
        bin_item.zone = "Zone non definie"
    db.session.commit()
