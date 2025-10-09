from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import SessionLocal

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ Get all message logs
@router.get("/", response_model=List[schemas.MessageLogResponse])
def get_message_logs(db: Session = Depends(get_db)):
    logs = db.query(models.MessageLog).all()
    return logs


# ✅ Delete all logs — placed BEFORE /{log_id} to prevent 422 error
@router.delete("/all", response_model=dict)
def delete_all_message_logs(db: Session = Depends(get_db)):
    total_logs = db.query(models.MessageLog).count()
    if total_logs == 0:
        raise HTTPException(status_code=404, detail="No logs found to delete")

    db.query(models.MessageLog).delete()
    db.commit()
    return {"message": f"Deleted all ({total_logs}) message logs successfully"}


# ✅ Bulk delete logs (using query param IDs)
@router.delete("/", response_model=dict)
def delete_message_logs(
    log_ids: List[int] = Query(..., description="IDs of logs to delete"),
    db: Session = Depends(get_db),
):
    logs = db.query(models.MessageLog).filter(models.MessageLog.id.in_(log_ids)).all()
    if not logs:
        raise HTTPException(status_code=404, detail="No logs found to delete")

    for log in logs:
        db.delete(log)
    db.commit()
    return {"message": f"Deleted {len(logs)} logs successfully"}


# ✅ Get single message log
@router.get("/{log_id}", response_model=schemas.MessageLogResponse)
def get_message_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.MessageLog).filter(models.MessageLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Message log not found")
    return log


# ✅ Delete single message log
@router.delete("/{log_id}", response_model=dict)
def delete_message_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.MessageLog).filter(models.MessageLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Message log not found")

    db.delete(log)
    db.commit()
    return {"message": f"Message log {log_id} deleted successfully"}
