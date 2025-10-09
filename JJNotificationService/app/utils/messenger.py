import os
import requests
from dotenv import load_dotenv

load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
ENABLE_MESSENGER_SEND = os.getenv("ENABLE_MESSENGER_SEND", "true").lower() == "true"

print("PAGE_ACCESS_TOKEN", PAGE_ACCESS_TOKEN)
print("ENABLE_MESSENGER_SEND", ENABLE_MESSENGER_SEND)


def send_message(messenger_id: str, message: str) -> dict:
    """
    Send a Messenger message if ENABLE_MESSENGER_SEND is true.
    Returns {"skipped": True} if sending is disabled.
    """
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
