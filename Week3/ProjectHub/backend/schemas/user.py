# PROJECTHUB/backend/schemas/user.py

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from schemas.project import ProjectResponse
from schemas.task import TaskResponse


class UserBase(BaseModel):
    username: str
    email: EmailStr



class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    projects: List[ProjectResponse] = []
    tasks: List[TaskResponse] = []

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"