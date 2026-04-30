from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.utils import verify_token
from app.config import config
from app.database.database import get_db
from app.database.model import User


security = HTTPBearer(auto_error=False)


def verify_api_version(request: Request):
    path = request.url.path
    if (
        path.startswith("/auth")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
        or path == "/"
        or path == "/health"
    ):
        return True

    api_version = request.headers.get(config.API_VERSION_HEADER)
    if not api_version:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "API version header required"},
        )
    if api_version != config.API_VERSION:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"Unsupported API Version. Expected {config.API_VERSION}",
            },
        )
    return True


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = None
    # payload = verify_token(token)
    if credentials:
        token = credentials.credentials
        print(f"[DEBUG] Token from Authorization header: {token[:50]}...")

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        token = request.query_params.get("access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Authentication required"}
        )

    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Invalid or expired token"}
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Invalid token type"}
        )

    user = db.query(User).filter(User.id == payload["sub"]).first()

    if not user:
        raise HTTPException(
            status_code=401, detail={"status": "error", "message": "User not found"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "message": "Account is deactivated"},
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "message": "Admin access required"},
        )
    return current_user


def require_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "message": "Account is deactivated"},
        )
    return current_user


async def require_analyst(current_user: User = Depends(get_current_user)):
    """Require at least analyst role"""
    if current_user.role not in ["admin", "analyst"]:
        raise HTTPException(
            status_code=403, detail={"status": "error", "message": "Access denied"}
        )
    return current_user
