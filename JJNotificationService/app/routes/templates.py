# ===================================
# 🚀 Templates Routes
# ===================================
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models, schemas

router = APIRouter()

# -------------------------------
# Dependency for DB session
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🚀 Create template
@router.post("/", response_model=schemas.TemplateResponse)
def create_template(template: schemas.TemplateCreate, db: Session = Depends(get_db)):
    db_template = models.Template(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


# 🚀 List all templates
@router.get("/", response_model=List[schemas.TemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return db.query(models.Template).all()


# 🚀 Get single template
@router.get("/{template_id}", response_model=schemas.TemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# 🚀 Update template
@router.put("/{template_id}", response_model=schemas.TemplateResponse)
def update_template(template_id: int, template: schemas.TemplateUpdate, db: Session = Depends(get_db)):
    db_template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    for key, value in template.dict(exclude_unset=True).items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)
    return db_template


# 🚀 Delete single template
@router.delete("/{template_id}", response_model=dict)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    db_template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(db_template)
    db.commit()
    return {"message": f"Template {template_id} deleted successfully"}


# 🚀 Bulk delete templates
@router.delete("/", response_model=dict)
def delete_templates(
    template_ids: List[int] = Query(..., description="IDs of templates to delete"),
    db: Session = Depends(get_db),
):
    templates_to_delete = db.query(models.Template).filter(models.Template.id.in_(template_ids)).all()
    if not templates_to_delete:
        raise HTTPException(status_code=404, detail="No templates found to delete")

    for template in templates_to_delete:
        db.delete(template)
    db.commit()

    return {"message": f"Deleted {len(templates_to_delete)} templates successfully"}
