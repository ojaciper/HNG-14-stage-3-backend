import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from jose import jwt as jose_jwt
from jose.exceptions import JWTError
from app.config import Config


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jose_jwt.encode(to_encode, Config.SECRET_KEY, algorithm=Config.ALGORITHM)


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=Config.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    secret_key = Config.SECRET_KEY.encode('utf-8')
    return jose_jwt.encode(to_encode, secret_key, algorithm=Config.ALGORITHM)


def verify_token(token: str):
    try:
        secret_key = Config.SECRET_KEY.encode('utf-8')
        payload = jose_jwt.decode(token, secret_key, algorithms=[Config.ALGORITHM]) # Debugging log
        print("Decoded Payload:", payload)
        return payload
    except JWTError as e:
        print("Token verification error:", str(e))  # Debugging log
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
