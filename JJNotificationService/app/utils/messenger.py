import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

# Path to the settings file
SETTINGS_FILE = "app/config/settings.json"

def is_messenger_enabled() -> bool:
    """
    Check dynamically if Messenger sending is enabled.
    Falls back to .env if settings.json does not exist.
    """
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return data.get("ENABLE_MESSENGER_SEND", True)
    except FileNotFoundError:
        # fallback to .env value for backward compatibility
        return os.getenv("ENABLE_MESSENGER_SEND", "true").lower() == "true"


def send_message(messenger_id: str, message: str) -> dict:
    """
    Send a Messenger message if ENABLE_MESSENGER_SEND is true.
    Returns {"skipped": True} if sending is disabled.
    """
    ENABLE_MESSENGER_SEND = is_messenger_enabled()

    if not ENABLE_MESSENGER_SEND:
        return {"skipped": True, "messenger_id": messenger_id, "message": message}

    if not PAGE_ACCESS_TOKEN:
        return {"error": "Missing PAGE_ACCESS_TOKEN"}

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": messenger_id},
        "message": {"text": message},
        "tag": "CONFIRMED_EVENT_UPDATE"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except requests.RequestException as e:
        return {"error": str(e)}
