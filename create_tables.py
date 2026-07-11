from app.database import Base, engine
from app.models import Application, StatusHistory

Base.metadata.create_all(bind=engine)
print("Tables created.")