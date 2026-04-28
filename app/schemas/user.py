from pydantic import BaseModel, EmailStr
from typing import Optional

# Shared properties
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    age: Optional[int] = None

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str

# Properties returned by API
class User(UserBase):
    id: int
    xp: int = 0
    streak_days: int = 0

    class Config:
        from_attributes = True # Allows Pydantic to read ORM models
