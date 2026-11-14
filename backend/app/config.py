from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "Earth Science Explorer API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/earth_science"
    DATA_CACHE_DIR: str = "data/cache"
    DATA_OUTPUTS_DIR: str = "data/outputs"

    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-production"
    ADMIN_TOKEN: str = "dev-insecure-admin-token-change-in-production"

    # NASA Earthdata credentials (backend only, SPEC 15.2, Scientific Rule 11)
    EARTHDATA_TOKEN: Optional[str] = None
    EARTHDATA_USERNAME: Optional[str] = None
    EARTHDATA_PASSWORD: Optional[str] = None

    TREND_ALPHA: float = 0.05
    TREND_MIN_DATA_POINTS: int = 12

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
