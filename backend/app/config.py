"""Application configuration loaded from environment variables."""

import os
from typing import List


class Settings:
    """Small dependency-free settings object for the web service."""

    app_name: str = os.getenv("APP_NAME", "CAD Generator API")
    environment: str = os.getenv("ENVIRONMENT", "production")
    log_level: str = os.getenv("LOG_LEVEL", "info")
    max_code_length: int = int(os.getenv("MAX_CODE_LENGTH", "50000"))
    allowed_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    allowed_origin_regex: str = r"https://([a-zA-Z0-9-]+\.)*vercel\.app"


settings = Settings()
