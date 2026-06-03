from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from jose import jwt, JWTError
from backend.core.config import settings


def _get_user_or_ip(request: Request) -> str:
    """Use JWT username as rate-limit key for authenticated requests, IP for everything else."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(
                auth.split(" ")[1],
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            username = payload.get("sub")
            if username:
                return username
        except JWTError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip, default_limits=[])
