import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Template


def get_template(db: Session, group: str, connection_name: str, state: str) -> Template:

    if not group:
      raise HTTPException(status_code=404, detail="Group not found")

    if not connection_name:
      raise HTTPException(status_code=404, detail="Connect name not found")

    key  = f"{group}-{connection_name}-{state}"

    logging.info(f"Getting template for '{key}'")

    template = db.query(Template).filter(Template.title == key).first()

    if not template:
      raise HTTPException(status_code=404, detail=" No Template found")

    return template

