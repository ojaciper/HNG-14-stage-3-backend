import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # GITHUB AUTH
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URL = os.getenv("GITHUB_REDIRECT_URL")
    
    # jwt
    SECRET_KEY = os.getenv("SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES =3
    REFRESH_TOKEN_EXPIRE_MINUTES =5
    ALGORITHM = "HS256"
    
    #API
    API_VERSION = "1"
    API_VERSION_HEADER = "X-API_VERSION"
    
    #EXTERNAL APIS
    GENDERIZE_API = "https://api.genderize.io"
    AGIFY_API = "https://api.agify.io"
    NATIONALIZE_API = "https://api.nationalize.io"
    
    #RATE LIMITING
    RATE_LIMITING_AUTH ="10/minute"
    RATE_LIMITING_DEFAULT ="60/MINUTE"