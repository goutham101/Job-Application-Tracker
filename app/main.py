from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

app = FastAPI()

@app.post("/applications", response_model=schemas.ApplicationResponse)
def create_application(application: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    new_app = models.Application(**application.model_dump())
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    history_entry = models.StatusHistory(
        application_id=new_app.id,
        status=new_app.current_status
    )
    db.add(history_entry)
    db.commit()
    db.refresh(new_app)

    return new_app

@app.get("/applications", response_model=List[schemas.ApplicationResponse])
def list_applications(db: Session = Depends(get_db)):
    return db.query(models.Application).all()