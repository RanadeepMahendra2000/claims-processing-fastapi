from passlib.context import CryptContext
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SESSION_USER_KEY = "user_id"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:

    return pwd_context.verify(password, password_hash)


def login_user(request: Request, user: User) -> None:
  
    request.session[SESSION_USER_KEY] = user.id


def logout_user(request: Request) -> None:

    request.session.pop(SESSION_USER_KEY, None)


def get_current_user(request: Request, db: Session) -> User:

    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    return user


def require_roles(user: User, allowed_roles: set[str]) -> None:
 
    if user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
