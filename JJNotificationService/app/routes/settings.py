from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json

router = APIRouter()

SETTINGS_FILE = "app/config/settings.json"

# Ensure settings file exists
if not os.path.exists(SETTINGS_FILE):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"ENABLE_MESSENGER_SEND": True}, f)

def load_settings():
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

class SettingsUpdate(BaseModel):
    ENABLE_MESSENGER_SEND: bool

@router.get("/settings/messenger")
def get_messenger_setting():
    settings = load_settings()
    return {"ENABLE_MESSENGER_SEND": settings.get("ENABLE_MESSENGER_SEND", True)}

@router.post("/settings/messenger")
def update_messenger_setting(payload: SettingsUpdate):
    settings = load_settings()
    settings["ENABLE_MESSENGER_SEND"] = payload.ENABLE_MESSENGER_SEND
    save_settings(settings)
    return {"success": True, "ENABLE_MESSENGER_SEND": payload.ENABLE_MESSENGER_SEND}
