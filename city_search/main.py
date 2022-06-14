"""
Server entrypoint with FastAPI app defined
"""

import os
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

app = FastAPI(root_path=os.environ.get("API_ROOT_PATH", "/"))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["health"])  # type: ignore
async def health() -> str:
    """Checks health of application, uncluding database and all systems"""
    return "OK"


@app.get("/")  # type: ignore
async def index() -> Dict[str, str]:
    return {
        "message": (
            f"Hello World."
            f" Test environment variable is: {os.getenv('TEST_ENV_VAR')}"
        )
    }


@app.get("/say_hello")  # type: ignore
async def say_hello(name: str) -> Dict[str, str]:
    """My method"""
    return {"message": f"Hello, {name}"}


# We need to specify custom openapi to add app.root_path to servers
def custom_openapi() -> Any:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="DataHub Authentication service",
        version="0.1.0",
        description="Authenticates users",
        routes=app.routes,
    )
    openapi_schema["servers"] = [{"url": app.root_path}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # noqa
