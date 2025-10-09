from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.database import SessionLocal
from app import models
from app.utils.messenger import send_message
from datetime import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SendRequest(BaseModel):
    template_id: int
    client_ids: List[int]

@router.post("/send")
def send_to_clients(payload: SendRequest, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == payload.template_id).first()
    if not template:
        return {"error": "Template not found"}

    results = []
    for cid in payload.client_ids:
        client = db.query(models.Client).filter(models.Client.id == cid).first()
        if client:
            resp = send_message(client.messenger_id, template.content)

            log = models.MessageLog(
                client_id=client.id,
                template_id=template.id,
                status=resp.get("message_id", "failed"),
                sent_at=datetime.utcnow()  # <-- set when sending
            )
            db.add(log)
            db.commit()

            results.append({"client": client.name, "status": resp})

    return {"results": results}
