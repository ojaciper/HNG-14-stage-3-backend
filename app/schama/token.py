from pydantic import BaseModel


class RefreshRequest(BaseModel):
    refresh_token: str

class RefreshResponse(BaseModel):
    status: str
    access_token: str
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str