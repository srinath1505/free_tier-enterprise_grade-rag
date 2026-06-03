from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.security.auth import get_current_user, User
from backend.models.conversation import Conversation
from backend.models.user import User as DBUser

router = APIRouter()


class MessageOut(BaseModel):
    role: str
    content: str
    timestamp: datetime

    model_config = {"from_attributes": True}


async def save_message(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    role: str,
    content: str,
) -> None:
    db.add(Conversation(user_id=user_id, session_id=session_id, role=role, content=content))
    await db.commit()


@router.get("/{session_id}", response_model=List[MessageOut])
async def get_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if session_id != current_user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(select(DBUser).where(DBUser.username == session_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        return []

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == db_user.id)
        .order_by(Conversation.timestamp)
    )
    rows = result.scalars().all()
    return [MessageOut(role=r.role, content=r.content, timestamp=r.timestamp) for r in rows]
