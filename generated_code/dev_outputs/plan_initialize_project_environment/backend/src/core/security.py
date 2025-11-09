from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext

from src.config.settings import get_settings
from src.core.exceptions import UnauthorizedException

settings = get_settings()

# Configure bcrypt rounds for CryptContext.
# This allows for a lower rounds value in testing environments to prevent timeouts,
# while maintaining a secure default for production.
# The default for bcrypt in passlib is typically 12.
bcrypt_rounds = getattr(settings, "BCRYPT_ROUNDS", 12)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=bcrypt_rounds)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hashes a plain password.
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Creates a JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes a JWT access token.
    Raises UnauthorizedException if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise UnauthorizedException(detail="Could not validate credentials")

# Placeholder for dependency injection for current user
# def get_current_user(token: str = Depends(oauth2_scheme)):
#     payload = decode_access_token(token)
#     username: str = payload.get("sub")
#     if username is None:
#         raise UnauthorizedException()
#     # In a real app, you would fetch the user from the database here
#     # user = get_user(username)
#     # if user is None:
#     #     raise UnauthorizedException()
#     # return user
#     return {"username": username} # Placeholder