from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.security.auth import get_current_user, User
from backend.models.memory import Memory
from backend.models.user import User as DBUser

router = APIRouter()


class MemoryOut(BaseModel):
    id: int
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=List[MemoryOut])
async def list_memory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DBUser).where(DBUser.username == current_user.username))
    db_user = result.scalar_one_or_none()
    if not db_user:
        return []

    result = await db.execute(
        select(Memory).where(Memory.user_id == db_user.id).order_by(Memory.created_at.desc())
    )
    return [MemoryOut.model_validate(m) for m in result.scalars().all()]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DBUser).where(DBUser.username == current_user.username))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == db_user.id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    await db.execute(delete(Memory).where(Memory.id == memory_id))
    await db.commit()
