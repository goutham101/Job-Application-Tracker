from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from fastapi import HTTPException

from app.auth import hash_password, verify_password, create_access_token, get_current_user

app = FastAPI()

@app.patch("/applications/{application_id}", response_model=schemas.ApplicationResponse)
def update_status(
    application_id: int,
    status_update: schemas.StatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    application = db.query(models.Application).filter(
        models.Application.id == application_id,
        models.Application.user_id == current_user.id
    ).first()
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
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    application = db.query(models.Application).filter(
        models.Application.id == application_id,
        models.Application.user_id == current_user.id
    ).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db.delete(application)
    db.commit()

    return None 

@app.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        email=user.email,
        hashed_password=hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=schemas.Token)
def login(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/applications", response_model=schemas.ApplicationResponse)
def create_application(
    application: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_app = models.Application(**application.model_dump(), user_id=current_user.id)
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
def list_applications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Application).filter(models.Application.user_id == current_user.id).all()