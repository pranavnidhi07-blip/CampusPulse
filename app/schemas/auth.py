from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class OrganizerCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "organizer"


class OrganizerLogin(BaseModel):
    email: EmailStr
    password: str


class OrganizerOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SensorClientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class SensorClientOut(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    api_key: Optional[str] = None  # Plaintext key only shown upon creation

    model_config = {"from_attributes": True}
