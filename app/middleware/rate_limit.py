from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request, HTTPException

limiter = Limiter(key_func=get_remote_address)

def setup_rate_limiting(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def get_rate_limit_key(request: Request):
    # For authenticated users, use user ID
    if hasattr(request.state, "user") and request.state.user:
        return f"user_{request.state.user.id}"
    return get_remote_address(request)