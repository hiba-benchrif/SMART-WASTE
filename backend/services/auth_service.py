from flask_jwt_extended import create_access_token
from models import db, User
from utils.validators import require_fields, validate_role

def register_user(data):
    ok, error = require_fields(data, ["name", "email", "password"])
    if not ok:
        return None, error
    role = data.get("role", "citizen")
    if not validate_role(role):
        return None, "Invalid role"
    if User.query.filter_by(email=data["email"].lower()).first():
        return None, "Email already exists"
    user = User(name=data["name"], email=data["email"].lower(), role=role)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user, None

def login_user(data):
    ok, error = require_fields(data, ["email", "password"])
    if not ok:
        return None, error
    user = User.query.filter_by(email=data["email"].lower()).first()
    if not user or not user.check_password(data["password"]):
        return None, "Invalid email or password"
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"access_token": token, "user": user.to_dict()}, None
