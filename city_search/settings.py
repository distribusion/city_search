"""
Settings module for specifying configurable parameters with environment variables
"""
import logging
from typing import List, Optional

from pydantic import BaseSettings, SecretStr


class AppSettings(BaseSettings):
    """
    These settings populated with environment variables
    """

    debug: bool = False
    title: str = "City-Search"
    version: str = "0.1.0"
    api_root_path: str = "/"

    allow_credentials: bool = True
    allowed_hosts: List[str] = ["*"]
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]

    api_prefix: str = "/api/v1"
    secret_key: SecretStr = SecretStr("test_secret")

    logging_level: int = logging.DEBUG

    db_url: str = "sqlite://db.sqlite"
    db_migrations_location: str = "migrations"

    bq_project: str = "distribusion-bq"
    bq_location: str = "europe-west3"
    gs_account_key: Optional[str] = None

    class Config:
        validate_assignment = True


settings = AppSettings()

# Also used for aerich migrations
TORTOISE_ORM = {
    "connections": {"default": settings.db_url},
    "apps": {
        "models": {
            "models": ["city_search.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
