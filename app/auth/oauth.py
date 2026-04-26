from datetime import datetime, timedelta, timezone
import uuid

import httpx
from sqlalchemy.orm import Session

from app.auth.utils import create_access_token, create_refresh_token, verify_token
from app.config import Config
from app.database.model import RefreshToken, User


class GitHubOAuth:
    @staticmethod
    async def get_github_user(code: str):
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": Config.GITHUB_CLIENT_ID,
                    "client_secret": Config.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": Config.GITHUB_REDIRECT_URL,
                },
            )
            token_data = token_response.json()
            access_token = token_data["access_token"]
            if "access_token" not in token_data:
                return None
            user_response = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return user_response.json()

    @staticmethod
    async def get_user_email(access_token: str):
        async with httpx.AsyncClient() as client:
            email_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            emails = email_response.json()
            if emails and isinstance(emails, list):
                primary_email = next((e for e in emails if e.get("primary")), emails[0])
                return primary_email.get("email")
            return None


async def create_or_update_user(github_data: dict, db: Session):
    user = db.query(User).filter(User.github_id == str(github_data["id"])).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            github_id=str(github_data["id"]),
            username=github_data["login"],
            email=github_data.get("email"),
            avatar_url=github_data.get("avatar_url"),
            role="analyst",
            is_active=True,
        )
        db.add(user)
    else:
        user.username = github_data["login"]
        user.avatar_url = github_data.get("avatar_url")
        user.last_login_at = datetime.now(timezone.utc)


def create_user_tokens(user_id: str, db: Session):
    access_token = create_access_token({"sub": user_id, "role": "user"})
    refresh_token = create_refresh_token({"sub": user_id})

    token_record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=Config.REFRESH_TOKEN_EXPIRE_MINUTES),
    )
    db.add(token_record)
    db.commit()
    return access_token, refresh_token


def revoke_refresh_token(token: str, db: Session):
    token_record = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if token_record:
        token_record.is_revoked = True
        db.commit()
        return True
    return False


def refresh_access_token(refresh_token: str, db: Session):
    payload = verify_token(refresh_access_token)
    if not payload or payload.get("type") != "refresh":
        return None

    token_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == refresh_token, RefreshToken.is_revoked == False)
        .first()
    )

    if not token_record or token_record.expires_at < datetime.now(timezone.utc):
        return None
    token_record.is_revoked = True
    db.commit()

    new_access_token = create_access_token({"sub": payload["sub"]})
    new_refresh_token = create_refresh_token({"sub": payload["sub"]})

    new_token_record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=payload["sub"],
        token=new_access_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=Config.REFRESH_TOKEN_EXPIRE_MINUTES),
    )
    db.add(new_token_record)
    db.commit()
    return new_access_token, new_refresh_token
