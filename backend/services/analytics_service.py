from datetime import datetime
from models import Bin, FillHistory, Alert

def dashboard_stats():
    bins = Bin.query.all()
    total = len(bins)
    full = len([item for item in bins if item.fill_level >= 80])
    average = round(sum(item.fill_level for item in bins) / total, 2) if total else 0
    return {
        "total_bins": total,
        "full_bins": full,
        "average_fill_level": average,
        "recently_updated": [item.to_dict() for item in sorted(bins, key=lambda item: item.updated_at, reverse=True)[:5]],
        "active_alerts": [alert.to_dict() for alert in Alert.query.filter_by(status="active").order_by(Alert.created_at.desc()).all()],
    }

def fill_history(bin_id=None):
    query = FillHistory.query
    if bin_id:
        query = query.filter_by(bin_id=bin_id)
    return [item.to_dict() for item in query.order_by(FillHistory.created_at.asc()).limit(100).all()]

def predict_full_time(bin_id):
    history = FillHistory.query.filter_by(bin_id=bin_id).order_by(FillHistory.created_at.asc()).all()
    if len(history) < 2:
        return {"message": "Not enough history to predict yet"}
    first = history[0]
    last = history[-1]
    hours = (last.created_at - first.created_at).total_seconds() / 3600
    if hours <= 0:
        return {"message": "Prediction needs measurements at different times"}
    speed = (last.fill_level - first.fill_level) / hours
    if speed <= 0:
        return {"message": "Fill level is stable or decreasing", "fill_speed_per_hour": round(speed, 2)}
    remaining = max(0, 100 - last.fill_level)
    hours_until_full = remaining / speed
    predicted_timestamp = datetime.utcnow().timestamp() + hours_until_full * 3600
    return {"bin_id": bin_id, "current_fill_level": round(last.fill_level, 2), "fill_speed_per_hour": round(speed, 2), "hours_until_full": round(hours_until_full, 2), "predicted_full_at_utc": datetime.utcfromtimestamp(predicted_timestamp).isoformat()}
