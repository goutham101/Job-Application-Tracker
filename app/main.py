from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from fastapi import HTTPException

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



@app.patch("/applications/{application_id}", response_model=schemas.ApplicationResponse)
def update_status(application_id: int, status_update: schemas.StatusUpdate, db: Session = Depends(get_db)):
    application = db.query(models.Application).filter(models.Application.id == application_id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    application.current_status = status_update.current_status

    history_entry = models.StatusHistory(
        application_id=application.id,
        status=status_update.current_status
    )
    db.add(history_entry)
    db.commit()
    db.refresh(application)

    return application

@app.delete("/applications/{application_id}", status_code = 204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    application = db.query(models.Application).filter(models.Application.id == application_id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db.delete(application)
    db.commit
    
    return None 