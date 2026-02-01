import json
from flask import current_app
from ..extensions import db
from ..models import Event


def record_event(event_type, payload):
    event = Event(event_type=event_type, payload_json=json.dumps(payload, ensure_ascii=False))
    db.session.add(event)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to record event")
