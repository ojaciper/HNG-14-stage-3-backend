from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.utils import verify_token
from app.config import Config
from app.database.database import get_db
from app.database.model import User


security = HTTPBearer()


def verify_api_version(request: Request):
    api_version = request.headers.get(Config.API_VERSION_HEADER)
    if not api_version:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "API version header required"},
        )
    if api_version != Config.API_VERSION:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"Unsupported API Version. Expected {Config.API_VERSION}",
            },
        )
    return True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Invalid or expired token"},
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
