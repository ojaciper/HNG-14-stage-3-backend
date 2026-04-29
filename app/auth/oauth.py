from datetime import datetime, timedelta, timezone
import uuid

import httpx
from sqlalchemy.orm import Session

from app.auth.utils import create_access_token, create_refresh_token, verify_token
from app.config import config
from app.database.model import RefreshToken, User


class GitHubOAuth:
    @staticmethod
    async def exchange_code_for_token(code: str, code_verifier: str = None):
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            data = {
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": config.GITHUB_REDIRECT_URI,
            }

            if code_verifier:
                data["code_verifier"] = code_verifier

            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data=data,
            )

            if response.status_code != 200:
                print(f"GitHub token exchange failed: {response.status_code}")
                return None

            return response.json()

    @staticmethod
    async def get_user_info(access_token: str):
        """Get user info from GitHub"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code != 200:
                return None
            return response.json()

    @staticmethod
    async def get_user_emails(access_token: str):
        """Get user emails from GitHub"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code != 200:
                return None
            emails = response.json()
            if emails and isinstance(emails, list):
                primary = next((e for e in emails if e.get("primary")), emails[0])
                return primary.get("email")
            return None


async def create_or_update_user(github_data: dict, db: Session):
    if not github_data or "id" not in github_data:
        raise ValueError("Invalid GitHub user data")

    user = db.query(User).filter(User.github_id == str(github_data["id"])).first()
    is_first_user = db.query(User).count() == 0

    if not user:
        user = User(
            id=str(uuid.uuid4()),
            github_id=str(github_data["id"]),
            username=github_data["login"],
            email=github_data.get("email"),
            avatar_url=github_data.get("avatar_url"),
            role="admin" if is_first_user else "analyst",
            is_active=True,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.username = github_data.get("login", user.username)
        user.avatar_url = github_data.get("avatar_url", user.avatar_url)
        if github_data.get("email"):
            user.email = github_data.get("email")
        user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def create_user_tokens(user_id: str, db: Session):
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    token_record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=config.REFRESH_TOKEN_EXPIRE_MINUTES),
        is_revoked=False,
    )
    db.add(token_record)
    db.commit()
    return access_token, refresh_token


def revoke_refresh_token(refresh_token: str, db: Session):
    """Revoke a refresh token"""
    token_record = (
        db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    )
    if token_record:
        token_record.is_revoked = True
        db.commit()
        return True
    return False


def refresh_tokens(refresh_token: str, db: Session):
    
    payload = verify_token(refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        return None
    
    token_record = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.is_revoked == False
    ).first()
    
    if not token_record or token_record.expires_at < datetime.now(timezone.utc):
        return None
    
    
    token_record.is_revoked = True
    db.commit()
    
    # Create new tokens
    return create_user_tokens(payload["sub"], db)