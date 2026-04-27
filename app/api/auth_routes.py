from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.config import Config
from app.database.database import get_db
from app.auth.oauth import (
    GitHubOAuth,
    create_or_update_user,
    create_user_tokens,
    revoke_refresh_token,
    refresh_access_token,
)
from app.auth.dependencies import get_current_user
from app.middleware.rate_limit import limiter
from app.schama.token import RefreshRequest

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/github")
@limiter.limit("10/minute")
async def github_login(request: Request, is_cli: bool = False):
    """Redirect to GitHub OAuth"""
    client_id = Config.GITHUB_CLIENT_ID  # From env
    # redirect_uri = "http://localhost:8000/auth/github/callback"
    redirect_uri = Config.GITHUB_REDIRECT_URI
    

    github_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=user:email"
    return RedirectResponse(url=github_url)


@router.get("/github/callback")
@limiter.limit("10/minute")
async def github_callback(request: Request, code: str, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    # Get user info from GitHub
    github_user = await GitHubOAuth.get_github_user(code)

    if not github_user:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Failed to authenticate with GitHub"},
        )

    # Get user email
    # Note: In production, you'd need the access token from the exchange
    # For now, we'll use the email from github_user if available

    # Create or update user in database
    user = await create_or_update_user(github_user, db)

    # Create tokens
    access_token, refresh_token = create_user_tokens(user.id, db)

    # Return tokens (for web, you'd set HTTP-only cookies)
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
    result = refresh_access_token(refresh_req.refresh_token, db)
    print("Refresh token result:", result)  # Debugging log

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
async def logout(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    """Logout - invalidate refresh token"""
    revoke_refresh_token(refresh_token, db)
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
