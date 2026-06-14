from models import db, Bin, FillHistory, Alert
from utils.helpers import calculate_status, distance_score
from utils.validators import require_fields, validate_coordinates, validate_fill_level
from utils.constants import CRITICAL_FILL_LEVEL

def list_bins():
    return [bin_item.to_dict() for bin_item in Bin.query.order_by(Bin.id.asc()).all()]

def create_bin(data):
    ok, error = require_fields(data, ["name", "street", "latitude", "longitude"])
    if not ok:
        return None, error
    coords_ok, coords = validate_coordinates(data["latitude"], data["longitude"])
    if not coords_ok:
        return None, coords
    fill_ok, fill_value = validate_fill_level(data.get("fill_level", 0))
    if not fill_ok:
        return None, fill_value
    bin_item = Bin(
        name=data["name"],
        street=data["street"],
        zone=data.get("zone", "Zone non definie"),
        latitude=coords[0],
        longitude=coords[1],
        fill_level=fill_value,
        status=calculate_status(fill_value),
        is_simulated=bool(data.get("is_simulated", True)),
    )
    db.session.add(bin_item)
    db.session.commit()
    add_history_and_alert(bin_item)
    return bin_item, None

def update_bin(bin_id, data):
    bin_item = Bin.query.get(bin_id)
    if not bin_item:
        return None, "Bin not found"
    if "name" in data:
        bin_item.name = data["name"]
    if "street" in data:
        bin_item.street = data["street"]
    if "zone" in data:
        bin_item.zone = data["zone"]
    if "latitude" in data or "longitude" in data:
        coords_ok, coords = validate_coordinates(data.get("latitude", bin_item.latitude), data.get("longitude", bin_item.longitude))
        if not coords_ok:
            return None, coords
        bin_item.latitude, bin_item.longitude = coords
    if "fill_level" in data:
        fill_ok, fill_value = validate_fill_level(data["fill_level"])
        if not fill_ok:
            return None, fill_value
        bin_item.fill_level = fill_value
        bin_item.status = calculate_status(fill_value)
    if "is_simulated" in data:
        bin_item.is_simulated = bool(data["is_simulated"])
    db.session.commit()
    add_history_and_alert(bin_item)
    return bin_item, None

def delete_bin(bin_id):
    bin_item = Bin.query.get(bin_id)
    if not bin_item:
        return False
    db.session.delete(bin_item)
    db.session.commit()
    return True

def ingest_pi_data(data):
    ok, error = require_fields(data, ["bin_id", "fill_level"])
    if not ok:
        return None, error
    return update_bin(int(data["bin_id"]), {"fill_level": data["fill_level"], "is_simulated": False})

def add_history_and_alert(bin_item):
    db.session.add(FillHistory(bin_id=bin_item.id, fill_level=bin_item.fill_level))
    if bin_item.fill_level >= CRITICAL_FILL_LEVEL:
        active_alert = Alert.query.filter_by(bin_id=bin_item.id, status="active").first()
        if not active_alert:
            db.session.add(Alert(bin_id=bin_item.id, message=f"{bin_item.name} is almost full"))
    db.session.commit()

def collection_route(origin_lat=33.5731, origin_lng=-7.5898):
    bins = Bin.query.filter(Bin.fill_level >= 70).all()
    sorted_bins = sorted(bins, key=lambda item: distance_score(origin_lat, origin_lng, item))
    return [item.to_dict() for item in sorted_bins]

def bins_grouped_by_street():
    grouped = {}
    for bin_item in Bin.query.order_by(Bin.street.asc(), Bin.id.asc()).all():
        grouped.setdefault(bin_item.street, []).append(bin_item.to_dict())
    return [{"street": street, "bins": bins, "count": len(bins)} for street, bins in grouped.items()]
