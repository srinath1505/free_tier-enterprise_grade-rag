from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class QueryCacheEntry(Base):
    __tablename__ = "query_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str] = mapped_column(Text)   # JSON-encoded list[float]
    answer: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text)     # JSON-encoded list[dict]
    confidence: Mapped[int] = mapped_column(Integer)
    warning: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
