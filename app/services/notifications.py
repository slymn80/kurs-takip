import json
import requests
from flask import current_app
from .db_events import record_event


def send_whatsapp(message, to_phone):
    provider = current_app.config.get("WHATSAPP_PROVIDER", "disabled")
    if provider == "disabled":
        return {"status": "disabled"}
    if provider == "twilio":
        return _send_twilio(message, to_phone)
    if provider == "meta":
        return _send_meta(message, to_phone)
    return {"status": "unknown_provider"}


def emit_webhook(event_type, payload):
    url = current_app.config.get("N8N_WEBHOOK_URL")
    record_event(event_type, payload)
    if not url:
        return {"status": "no_webhook"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return {"status": "sent", "code": response.status_code}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _send_twilio(message, to_phone):
    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_number = current_app.config.get("TWILIO_WHATSAPP_FROM")
    if not all([sid, token, from_number]):
        return {"status": "missing_twilio_config"}
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {
        "From": f"whatsapp:{from_number}",
        "To": f"whatsapp:{to_phone}",
        "Body": message
    }
    try:
        response = requests.post(url, data=data, auth=(sid, token), timeout=10)
        response.raise_for_status()
        return {"status": "sent", "code": response.status_code}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _send_meta(message, to_phone):
    token = current_app.config.get("META_WHATSAPP_TOKEN")
    phone_id = current_app.config.get("META_WHATSAPP_PHONE_ID")
    base_url = current_app.config.get("META_WHATSAPP_URL")
    if not all([token, phone_id, base_url]):
        return {"status": "missing_meta_config"}
    url = f"{base_url}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message}
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return {"status": "sent", "code": response.status_code}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
