from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.query_log import QueryLog
from backend.security.auth import get_current_user, User

router = APIRouter()


@router.get("")
async def get_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    r = await db.execute(
        select(func.count()).select_from(QueryLog).where(
            func.strftime("%Y-%m-%d", QueryLog.timestamp) == today_str
        )
    )
    queries_today = r.scalar() or 0

    r = await db.execute(select(func.count()).select_from(QueryLog))
    total_queries = r.scalar() or 0

    r = await db.execute(
        select(func.avg(QueryLog.response_time_ms))
        .select_from(QueryLog)
        .where(QueryLog.success == True)  # noqa: E712
    )
    avg_ms = round(r.scalar() or 0, 1)

    r = await db.execute(
        select(func.count()).select_from(QueryLog).where(QueryLog.success == False)  # noqa: E712
    )
    failed = r.scalar() or 0

    r = await db.execute(
        select(QueryLog.query, func.count(QueryLog.id).label("cnt"))
        .group_by(QueryLog.query)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_questions = [{"query": row[0][:120], "count": row[1]} for row in r.fetchall()]

    r = await db.execute(
        select(QueryLog).order_by(desc(QueryLog.timestamp)).limit(20)
    )
    recent = [
        {
            "user": row.user,
            "query": row.query[:100],
            "response_time_ms": round(row.response_time_ms, 1),
            "success": row.success,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
        }
        for row in r.scalars().all()
    ]

    return {
        "queries_today": queries_today,
        "total_queries": total_queries,
        "avg_response_ms": avg_ms,
        "failed_queries": failed,
        "top_questions": top_questions,
        "recent_logs": recent,
    }