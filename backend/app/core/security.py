from datetime import datetime, timedelta, timezone
from typing import Any, Union

from jose import jwt
import base64
import hashlib
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import get_settings

settings = get_settings()

password_hash = PasswordHash((BcryptHasher(),))


def _pre_hash(password: str) -> str:
    """
    Pre-hash the password with SHA-256 and encode in base64.
    This safely bypasses bcrypt's 72-byte limit without truncating passwords.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def hash_password(password: str) -> str:
    return password_hash.hash(_pre_hash(password))


def verify_password(plain_password: str, hashed_pwd: str) -> bool:
    return password_hash.verify(_pre_hash(plain_password), hashed_pwd)



def _create_token(subject: Union[str, Any], expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        "type": token_type
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_access_token(subject: Union[str, Any]) -> str:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(
        subject=subject,
        expires_delta=expires_delta,
        token_type="access"
    )


def create_refresh_token(subject: Union[str, Any]) -> str:
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(
        subject=subject,
        expires_delta=expires_delta,
        token_type="refresh"
    )


def decode_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    return payload
