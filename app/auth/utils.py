import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from jose import jwt, JWTError

# import jwt

from app.config import Config


def create_acces_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, Config.SECRET_KEY, algorithm=Config.ALGORITHMs)


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=Config.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, Config.SECRET_KEY, algorithm=Config.ALGORITHM)


def verify_token(token: str):
    try:
        payload = jwt.decode(token=Config.SECRET_KEY, algorithms=[Config.ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_pkce():
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    )
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return code_verifier, code_challenge


def generate_state():
    return secrets.token_urlsafe(32)
