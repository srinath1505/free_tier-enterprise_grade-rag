from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from backend.core.config import settings

# --- Configuration ---
# In a real app, these should be in settings/env
SECRET_KEY = "super-secret-key-change-this-in-prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class User(BaseModel):
    username: str
    role: str # 'admin' or 'viewer'

class UserInDB(User):
    hashed_password: str

# --- Security Utils ---
# Using pbkdf2_sha256 to avoid bcrypt/Windows binary issues in this environment
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- In-Memory User Store (for Zero-Cost/No-DB setup) ---
# Default password is "password" for simplicity in this demo
# Hash generated via pwd_context.hash("password")
fake_users_db = {
    "admin": {
        "username": "admin",
        "role": "admin",
        "hashed_password": "$pbkdf2-sha256$29000$QygF4JxTau09x1jL2ZsTYg$b.J.wPTCbfgymXOfFVUsGKxbn4G1gJbmh0gZPNxIZYw"
    },
    "viewer": {
        "username": "viewer",
        "role": "viewer",
        "hashed_password": "$pbkdf2-sha256$29000$QygF4JxTau09x1jL2ZsTYg$b.J.wPTCbfgymXOfFVUsGKxbn4G1gJbmh0gZPNxIZYw"
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
    
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user
