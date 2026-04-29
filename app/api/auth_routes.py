from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.auth.utils import generate_pkce, generate_state
from app.config import config
from app.database.database import get_db
from app.auth.oauth import (
    GitHubOAuth,
    create_or_update_user,
    create_user_tokens,
    refresh_tokens,
    revoke_refresh_token,
    
)
from app.auth.dependencies import get_current_user
from app.database.model import User
from app.middleware.rate_limit import limiter
from app.schama.token import LogoutRequest, RefreshRequest

router = APIRouter(prefix="/api/auth", tags=["authentication"])
temp_states = {}


@router.get("/github")
@limiter.limit("10/minute")
async def github_login(request: Request, is_cli: str = "false"):
    """Redirect to GitHub OAuth with PKCE and state"""

    # Generate PKCE parameters
    state = generate_state()
    code_verifier, code_challenge = generate_pkce()

    # Store state and verifier for callback validation
    temp_states[state] = {
        "code_verifier": code_verifier,
        "is_cli": is_cli.lower() == "true",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Clean up old states (older than 10 minutes)
    now = datetime.now(timezone.utc)
    expired = [
        s
        for s, data in temp_states.items()
        if datetime.fromisoformat(data["created_at"]) < now - timedelta(minutes=10)
    ]
    for s in expired:
        temp_states.pop(s, None)

    # Determine redirect URI
    redirect_uri = config.GITHUB_REDIRECT_URI
    if is_cli.lower() == "true":
        redirect_uri = config.CLI_CALLBACK_URL

    # Build GitHub authorization URL with PKCE
    github_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={config.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&scope=user:email"
    )

    # Return redirect with CORS headers
    response = RedirectResponse(url=github_url, status_code=302)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, X-API-Version"
    )

    return response


@router.get("/github/callback")
@limiter.limit("10/minute")
async def github_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    """Handle GitHub OAuth callback with PKCE validation"""

    # Handle error from GitHub
    if error:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": f"GitHub OAuth error: {error}"},
        )

    # Validate required parameters
    if not code:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Missing authorization code"},
        )

    if not state:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Missing state parameter"},
        )

    # Validate state
    stored = temp_states.pop(state, None)
    if not stored:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Invalid or expired state parameter"},
        )

    code_verifier = stored.get("code_verifier")
    is_cli = stored.get("is_cli", False)

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": config.GITHUB_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )

        token_data = token_response.json()

        if "access_token" not in token_data:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Failed to exchange code for token",
                },
            )

        github_token = token_data["access_token"]

        # Get user info
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {github_token}"},
        )
        github_user = user_response.json()

        # Get user email
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {github_token}"},
        )
        emails = email_response.json()
        primary_email = None
        if emails and isinstance(emails, list):
            for email in emails:
                if email.get("primary"):
                    primary_email = email.get("email")
                    break
            if not primary_email and emails:
                primary_email = emails[0].get("email")

        if primary_email:
            github_user["email"] = primary_email

    # Create or update user
    user = await create_or_update_user(github_user, db)

    # Create JWT tokens
    access_token, refresh_token = create_user_tokens(user.id, db)

    # Return response based on client type
    if is_cli:
        return {
            "status": "success",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {"id": user.id, "username": user.username, "role": user.role},
        }
    else:
        # For web, return JSON for frontend to handle
        return {
            "status": "success",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {"id": user.id, "username": user.username, "role": user.role},
        }


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh_token(
    request: Request, refresh_req: RefreshRequest, db: Session = Depends(get_db)
):
    """Refresh access token"""

    if not refresh_req.refresh_token:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Refresh token required"},
        )

    result = refresh_tokens(refresh_req.refresh_token, db)

    if not result:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Invalid or expired refresh token"},
        )

    access_token, refresh_token = result

    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(
    request: Request, logout_req: LogoutRequest, db: Session = Depends(get_db)
):
    """Logout - invalidate refresh token"""

    if not logout_req.refresh_token:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Refresh token required"},
        )

    revoke_refresh_token(logout_req.refresh_token, db)

    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user info"""
    return {
        "status": "success",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "avatar_url": current_user.avatar_url,
            "role": current_user.role,
            "is_active": current_user.is_active,
        },
    }
