from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
import os
import requests

from app.database import SessionLocal
from app import models, schemas
from app.websocket_manager import manager
from app.utils.billing import (
    handle_paid_client,
    handle_unpaid_client,
)
from app.utils.messenger import send_message
from app.models import BillingStatus

router = APIRouter()

FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v23.0"
ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")


# -------------------------------
# Dependency for DB session
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🚀 Create a new client
@router.post("/", response_model=schemas.ClientResponse)
def create_client(client: schemas.ClientCreate, db: Session = Depends(get_db)):
    db_client = models.Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


# 🚀 Get all clients
@router.get("/", response_model=List[schemas.ClientResponse])
def get_clients(db: Session = Depends(get_db)):
    return db.query(models.Client).all()


# 🚀 Get a client by ID
@router.get("/{client_id}", response_model=schemas.ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# 🚀 Update a client
@router.put("/{client_id}", response_model=schemas.ClientResponse)
async def update_client(client_id: int, client: schemas.ClientUpdate, db: Session = Depends(get_db)):
    db_client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    for key, value in client.dict(exclude_unset=True).items():
        setattr(db_client, key, value)

    db.commit()
    db.refresh(db_client)

    await manager.broadcast({"id": db_client.id})
    return db_client


# 🚀 Delete a client
@router.delete("/{client_id}", response_model=dict)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    db_client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    db.delete(db_client)
    db.commit()
    return {"message": "Client deleted successfully"}


# 🚀 Bulk delete clients
@router.delete("/", response_model=dict)
def delete_clients(client_ids: List[int] = Query(...), db: Session = Depends(get_db)):
    if not client_ids:
        raise HTTPException(status_code=400, detail="No client IDs provided")

    deleted = db.query(models.Client).filter(models.Client.id.in_(client_ids)).delete(synchronize_session=False)
    db.commit()
    return {"message": f"✅ Deleted {deleted} client(s)"}


# ✅ Sync clients from Facebook Graph API
@router.post("/sync", response_model=dict, status_code=status.HTTP_200_OK)
def sync_clients(db: Session = Depends(get_db)):
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Missing Facebook access token")

    url = f"{FACEBOOK_GRAPH_URL}/me/conversations"
    params = {"fields": "participants", "access_token": ACCESS_TOKEN}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", [])
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Facebook API error: {str(e)}")

    if not data:
        return {"message": "⚠️ No conversations found"}

    synced = 0
    for convo in data:
        participants = convo.get("participants", {}).get("data", [])
        if not participants:
            continue

        for p in participants:
            if PAGE_ID and p.get("id") == PAGE_ID:
                continue
            if not p.get("id"):
                continue

            existing = db.query(models.Client).filter(models.Client.messenger_id == p["id"]).first()
            if not existing:
                db_client = models.Client(
                    name=p.get("name") or "Unknown",
                    messenger_id=p["id"],
                    group_name="G1",
                    state="UNKNOWN",
                    billing_date=None,
                    status=BillingStatus.PAID.value,
                    speed_limit="Unlimited",
                    amt_monthly=0,
                )
                db.add(db_client)
                synced += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"message": f"✅ Synced {synced} new client(s) from Facebook"}


# 🚀 Single Set Paid
@router.post("/{client_id}/set_paid", response_model=dict)
async def set_paid(client_id: int, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 🧩 Save the old status before updating
    prev_status = client.status
    # Update to PAID
    client.status = BillingStatus.PAID
    handle_paid_client(db, client)

    # 🧩 Send message if connected to Messenger
    if client.messenger_id:
        if prev_status in [BillingStatus.LIMITED, BillingStatus.CUTOFF]:
            msg = (
                f"Hi {client.name}, we received your payment of {client.amt_monthly}.\n"
                "Your connection will be fully restored shortly. ✅ Thank you!"
            )
        else:
            msg = (
                f"Hi {client.name}, we received your payment of {client.amt_monthly}.\n"
                "Thank you!"
            )

        send_message(client.messenger_id, msg)

    await manager.broadcast({
        "event": "billing_update",
        "client_id": client.id,
        "status": client.status.value,
    })

    return {"message": f"Client {client.id} marked as PAID and restored"}


# 🚀 Bulk Set Paid
@router.post("/set_paid_bulk", response_model=dict)
async def set_paid_bulk(client_ids: List[int], db: Session = Depends(get_db)):
    clients = db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()
    if not clients:
        raise HTTPException(status_code=404, detail="No clients found")

    for client in clients:
        prev_status = client.status
        client.status = BillingStatus.PAID
        handle_paid_client(db, client)

        if client.messenger_id:
            if prev_status in [BillingStatus.LIMITED, BillingStatus.CUTOFF]:
                msg = (
                    f"Hi {client.name}, we received your payment of {client.amt_monthly}.\n"
                    "Your connection will be fully restored shortly. ✅ Thank you!"
                )
            else:
                msg = (
                    f"Hi {client.name}, we received your payment of {client.amt_monthly}.\n"
                    "Thank you!"
                )

            send_message(client.messenger_id, msg)

    await manager.broadcast({
        "event": "billing_update_bulk",
        "client_ids": [c.id for c in clients],
        "status": BillingStatus.PAID.value,
    })

    return {"message": f"{len(clients)} clients marked as PAID"}



# 🚀 Single Set Unpaid
@router.post("/{client_id}/set_unpaid", response_model=dict)
async def set_unpaid(client_id: int, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.status = BillingStatus.UNPAID
    handle_unpaid_client(db, client)

    await manager.broadcast({
        "event": "billing_update",
        "client_id": client.id,
        "status": client.status.value,
    })

    return {"message": f"Client {client.id} marked as UNPAID"}


# 🚀 Bulk Set Unpaid
@router.post("/set_unpaid_bulk", response_model=dict)
async def set_unpaid_bulk(client_ids: List[int], db: Session = Depends(get_db)):
    clients = db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()
    if not clients:
        raise HTTPException(status_code=404, detail="No clients found")

    for client in clients:
        client.status = BillingStatus.UNPAID
        handle_unpaid_client(db, client, "enforce")

    await manager.broadcast({
        "event": "billing_update_bulk",
        "client_ids": [c.id for c in clients],
        "status": BillingStatus.UNPAID.value,
    })

    return {"message": f"{len(clients)} clients marked as UNPAID"}
