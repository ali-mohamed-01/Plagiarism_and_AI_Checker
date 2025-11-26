# backend/database.py
from sqlmodel import SQLModel, create_engine, Session
import os

DB_FILE = os.environ.get("RIS_SQLITE", "ris_demo.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
