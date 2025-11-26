# backend/models.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, nullable=False, unique=True)
    hashed_password: str
    name: Optional[str] = None
    affiliation: Optional[str] = None
    field_of_study: Optional[str] = None
    role: str = "researcher"  # researcher | admin
    credits: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    submissions: List["Submission"] = Relationship(back_populates="owner")


class Submission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    content_type: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "processing"  # processing | completed | failed
    store_for_future: bool = False
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # simplified: store raw extracted text and report JSON for demo
    extracted_text: Optional[str] = None
    report_json: Optional[str] = None
    raw_bytes_len: Optional[int] = None
    retention_days: int = 30

    owner: Optional[User] = Relationship(back_populates="submissions")
