from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.database import SessionLocal
from app import models
from app.schemas import SendRequest
from app.utils.messengerV2 import send_message
from datetime import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/send")
def send_to_clients(payload: SendRequest, db: Session = Depends(get_db)):
    title = payload.title
    if not title:
        return {"error": "Title is empty"}

    message = payload.message
    if not message:
        return {"error": "Message is empty"}

    results = []
    for cid in payload.client_ids:
        client = db.query(models.Client).filter(models.Client.id == cid).first()
        if client:
            resp = send_message(db, client.messenger_id, title, message)

            results.append({"client": client.name, "status": resp})

    return {"results": results}
