from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
from sqlalchemy.orm import Session
from app.auth.utils import generate_pkce, generate_state
from app.config import config
from app.database.database import get_db
from app.auth.oauth import (
    create_or_update_user,
    create_user_tokens,
    refresh_tokens,
    revoke_refresh_token,
)
from app.middleware.rate_limit import limiter
from app.schama.token import LogoutRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["authentication"])
temp_states = {}

def _resolve_redirect_uri(request: Request, is_cli: bool) -> str:
    if is_cli and config.CLI_CALLBACK_URL:
        return config.CLI_CALLBACK_URL

    callback_url = str(request.url_for("github_callback"))
    configured = config.GITHUB_REDIRECT_URI
    if not configured:
        return callback_url

    configured_lower = configured.lower()
    callback_lower = callback_url.lower()
    # Avoid using localhost callbacks in deployed environments.
    if callback_lower.startswith("https://") and (
        "127.0.0.1" in configured_lower or "localhost" in configured_lower
    ):
        return callback_url

    return configured


@router.get("/github")
@limiter.limit("10/minute", scope="auth_github")
async def github_login(
    request: Request, is_cli: str = "false", response_mode: str = "redirect"
):
    """Redirect to GitHub OAuth with PKCE and state"""
    is_cli_flow = is_cli.lower() == "true"
    redirect_uri = _resolve_redirect_uri(request, is_cli_flow)

    # Generate PKCE parameters
    state = generate_state()
    code_verifier, code_challenge = generate_pkce()

    # Store state and verifier for callback validation
    temp_states[state] = {
        "code_verifier": code_verifier,
        "is_cli": is_cli_flow,
        "redirect_uri": redirect_uri,
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

    if response_mode.lower() == "json":
        # Swagger "Try it out" uses fetch and cannot complete OAuth redirects to GitHub.
        # This mode returns the authorization URL so it can be opened manually.
        return {
            "status": "success",
            "authorization_url": github_url,
            "state": state,
            "redirect_uri": redirect_uri,
        }

    return RedirectResponse(url=github_url, status_code=302)


@router.get("/github/callback")
@limiter.limit("10/minute", scope="auth_github_callback")
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
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"GitHub OAuth error: {error}"},
        )

    # Validate required parameters
    if not code:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing authorization code"},
        )

    if not state:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing state parameter"},
        )

    # Validate state
    stored = temp_states.pop(state, None)
    if not stored:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Invalid or expired state parameter",
            },
        )

    code_verifier = stored.get("code_verifier")
    is_cli = stored.get("is_cli", False)
    redirect_uri = stored.get("redirect_uri", config.GITHUB_REDIRECT_URI)

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )

        token_data = token_response.json()

        if "access_token" not in token_data:
            return JSONResponse(
                status_code=400,
                content={
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
        if not github_user or "id" not in github_user:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Failed to get user info from GitHub",
                },
            )

        # Get user email
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {github_token}"},
        )

        emails = email_response.json()
        if emails and isinstance(emails, list):
            for email in emails:
                if email.get("primary"):
                    github_user["email"] = email.get("email")
                    break
            if not github_user.get("email") and emails:
                github_user["email"] = emails[0].get("email")

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

    # Create or update user and issue tokens
    user = await create_or_update_user(github_user, db)
    access_token, refresh_token = create_user_tokens(user, db)

    user_data = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
    }

    # Return response based on client type
    if is_cli:
        role_token_key = "admin_token" if user.role == "admin" else "analyst_token"
        return {
            "status": "success",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "github_id": user.github_id,
                "username": user.username,
                "role": user.role,
            },
            "id": user.id,
            "github_id": user.github_id,
            "username": user.username,
            "role": user.role,
            role_token_key: access_token,
        }

    role_token_key = "admin_token" if user.role == "admin" else "analyst_token"
    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user_data,
        "id": user.id,
        "github_id": user.github_id,
        "username": user.username,
        "role": user.role,
        role_token_key: access_token,
    }


@router.post("/refresh")
@limiter.limit("10/minute", scope="auth_refresh")
async def refresh_token(
    request: Request, refresh_req: RefreshRequest, db: Session = Depends(get_db)
):
    """Refresh access token"""

    if not refresh_req.refresh_token:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Refresh token required"},
        )

    result = refresh_tokens(refresh_req.refresh_token, db)

    if not result:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Invalid or expired refresh token"},
        )

    access_token, refresh_token = result

    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post("/logout")
@limiter.limit("10/minute", scope="auth_logout")
async def logout(
    request: Request, logout_req: LogoutRequest, db: Session = Depends(get_db)
):
    """Logout - invalidate refresh token"""

    if not logout_req.refresh_token:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Refresh token required"},
        )

    revoke_refresh_token(logout_req.refresh_token, db)

    return {"status": "success", "message": "Logged out successfully"}


# @router.get("/me")
# @limiter.limit("60/minute")
# async def get_current_user_info(
#     request: Request,
#     db: Session = Depends(get_db)
# ):
#     """Get current user info"""
    
#     print("[DEBUG] /auth/me endpoint called")
#     print(f"[DEBUG] Request headers: {dict(request.headers)}")
    
#     # Try to get token from multiple places
#     token = None
    
#     # Check Authorization header
#     auth_header = request.headers.get("Authorization")
#     print(f"[DEBUG] Authorization header: {auth_header[:50] if auth_header else 'None'}...")
    
#     if auth_header and auth_header.startswith("Bearer "):
#         token = auth_header.replace("Bearer ", "")
#         print(f"[DEBUG] Token from Authorization header: {token[:50]}...")
    
#     # Check cookie
#     if not token:
#         token = request.cookies.get("access_token")
#         print(f"[DEBUG] Token from cookie: {token[:50] if token else 'None'}...")
    
#     # Check query param
#     if not token:
#         token = request.query_params.get("access_token")
#         print(f"[DEBUG] Token from query param: {token[:50] if token else 'None'}...")
    
#     if not token:
#         print("[DEBUG] No token found anywhere")
#         return JSONResponse(
#             status_code=401,
#             content={"status": "error", "message": "Authentication required"}
#         )
    
#     # Verify token
#     payload = verify_token(token)
#     print(f"[DEBUG] Token payload: {payload}")
    
#     if not payload:
#         print("[DEBUG] Invalid token")
#         return JSONResponse(
#             status_code=401,
#             content={"status": "error", "message": "Invalid or expired token"}
#         )
    
#     if payload.get("type") != "access":
#         print(f"[DEBUG] Wrong token type: {payload.get('type')}")
#         return JSONResponse(
#             status_code=401,
#             content={"status": "error", "message": "Invalid token type"}
#         )
    
#     user_id = payload.get("sub")
#     print(f"[DEBUG] User ID from token: {user_id}")
    
#     user = db.query(User).filter(User.id == user_id).first()
    
#     if not user:
#         print(f"[DEBUG] User not found: {user_id}")
#         return JSONResponse(
#             status_code=401,
#             content={"status": "error", "message": "User not found"}
#         )
    
#     if not user.is_active:
#         print(f"[DEBUG] User inactive: {user.username}")
#         return JSONResponse(
#             status_code=403,
#             content={"status": "error", "message": "Account is deactivated"}
#         )
    
#     print(f"[DEBUG] User authenticated: {user.username}")
    
#     return {
#         "status": "success",
#         "user": {
#             "id": user.id,
#             "username": user.username,
#             "email": user.email,
#             "avatar_url": user.avatar_url,
#             "role": user.role,
#             "is_active": user.is_active,
#             "created_at": user.created_at.isoformat() if user.created_at else None
#         }
#     }