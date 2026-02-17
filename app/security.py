from functools import wraps
from datetime import datetime
import hashlib
from flask import abort, g, request, jsonify
from flask_login import current_user
from .extensions import db
from .models import ApiToken


def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def authenticate_api_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    raw_token = auth_header.split(" ", 1)[1].strip()
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)
    token = ApiToken.query.filter_by(token_hash=token_hash, is_active=True).first()
    if not token:
        return None
    token.last_used_at = datetime.utcnow()
    db.session.commit()
    return token.user


def require_api_user():
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = authenticate_api_token()
            if not user:
                return jsonify({"error": "unauthorized"}), 401
            g.api_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_api_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = authenticate_api_token()
            if not user:
                return jsonify({"error": "unauthorized"}), 401
            if roles and user.role not in roles:
                return jsonify({"error": "forbidden"}), 403
            g.api_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def hash_api_token(raw_token):
    return _hash_token(raw_token)
