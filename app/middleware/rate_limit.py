from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request, HTTPException

def get_rate_limit_key(request: Request):
    # Use the original client IP behind proxies to avoid all traffic collapsing into one shared IP.
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
        return f"{client_ip}:{request.url.path}"
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return f"{real_ip}:{request.url.path}"
    return f"{get_remote_address(request)}:{request.url.path}"

limiter = Limiter(key_func=get_rate_limit_key, default_limits=["100/minute"])

def setup_rate_limiting(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Kept for compatibility if imported elsewhere.
def get_user_rate_limit_key(request: Request):
    if hasattr(request.state, "user") and request.state.user:
        return f"user_{request.state.user.id}"
    return get_rate_limit_key(request)