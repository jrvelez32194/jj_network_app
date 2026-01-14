import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy.orm import Session

from app import models

load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
SETTINGS_FILE = "app/config/settings.json"


def is_messenger_enabled() -> bool:
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return data.get("ENABLE_MESSENGER_SEND", True)
    except FileNotFoundError:
        return os.getenv("ENABLE_MESSENGER_SEND", "true").lower() == "true"


def send_message(
    db: Session,
    messenger_id: str,
    title: str,
    message: str,
) -> dict:
    """
    Sends a Messenger message and logs the attempt.
    """

    ENABLE_MESSENGER_SEND = is_messenger_enabled()

    # 🚫 Sending disabled (still log)
    if not ENABLE_MESSENGER_SEND:
        log = models.MessageLog(
            title=title,
            message=message,
            status="skipped",
            sent_at=None,
        )
        db.add(log)
        db.commit()

        return {
            "skipped": True,
            "messenger_id": messenger_id,
        }

    if not PAGE_ACCESS_TOKEN:
        log = models.MessageLog(
            title=title,
            message=message,
            status="failed",
            sent_at=None,
        )
        db.add(log)
        db.commit()

        return {"error": "Missing PAGE_ACCESS_TOKEN"}

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": messenger_id},
        "message": {"text": message},
        "tag": "CONFIRMED_EVENT_UPDATE",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        is_sent = bool(data.get("message_id"))

        log = models.MessageLog(
            title=title,
            message=message,
            status="sent" if is_sent else "failed",
            sent_at=datetime.utcnow() if is_sent else None,
        )

        db.add(log)
        db.commit()

        return data

    except requests.RequestException as e:
        log = models.MessageLog(
            title=title,
            message=message,
            status="failed",
            sent_at=None,
        )
        db.add(log)
        db.commit()

        return {"error": str(e)}
