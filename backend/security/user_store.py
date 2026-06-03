from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User


async def get_user(db: AsyncSession, username: str):
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, username: str, password_hash: str, role: str = "viewer") -> bool:
    existing = await get_user(db, username)
    if existing:
        return False
    user = User(username=username, hashed_password=password_hash, role=role)
    db.add(user)
    await db.commit()
    return True


async def init_default_admin(db: AsyncSession) -> None:
    from backend.security.auth import pwd_context  # lazy import to avoid circular dependency
    from backend.core.config import settings
    import logging
    existing = await get_user(db, "admin")
    if not existing:
        if settings.ADMIN_DEFAULT_PASSWORD == "password":
            logging.getLogger(__name__).warning(
                "SECURITY: admin account seeded with default password 'password'. "
                "Set ADMIN_DEFAULT_PASSWORD in .env before deploying."
            )
        admin = User(
            username="admin",
            hashed_password=pwd_context.hash(settings.ADMIN_DEFAULT_PASSWORD),
            role="admin",
        )
        db.add(admin)
        await db.commit()
