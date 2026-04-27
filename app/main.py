from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import config
from app.config import Config
from app.api import auth_routes, profile
from app.database.database import engine, Base
from app.middleware.logging import log_requests
from app.middleware.rate_limit import setup_rate_limiting
from fastapi.openapi.utils import get_openapi


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Insighta Labs+ API", version='1.0.0')



def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add API version header to all endpoints
    for path in openapi_schema["paths"].values():
        for method in path.values():
            if "parameters" not in method:
                method["parameters"] = []
            method["parameters"].append({
                "name": Config.API_VERSION_HEADER,
                "in": "header",
                "required": True,
                "schema": {
                    "type": "string",
                    "default": Config.API_VERSION,
                    "enum": [Config.API_VERSION]
                },
                "description": "API version header (required)"
            })
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.middleware("http")(log_requests)

setup_rate_limiting(app)

app.include_router(auth_routes.router)
app.include_router(profile.router)

@app.exception_handler


@app.get("/")
def root():
    return {"message": "Name Profiler API", "version": "1.0.0"}
