from fastapi import APIRouter, Depends, Request
from app.auth.dependencies import get_current_user, verify_api_version
from app.database.model import User
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me")
@limiter.limit("60/minute")
async def get_me(
    request: Request,
    api_version: bool = Depends(verify_api_version),
    current_user: User = Depends(get_current_user),
):
    return {
        "status": "success",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "avatar_url": current_user.avatar_url,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat()
            if current_user.created_at
            else None,
        },
    }
