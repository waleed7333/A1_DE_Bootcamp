# PROJECTHUB/backend/schemas/project.py

from pydantic import BaseModel
from typing import Optional, List
from schemas.task import TaskResponse


class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    owner_id: int


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int
    tasks: List[TaskResponse] = []

    class Config:
        from_attributes = True