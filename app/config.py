import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CampusPulse"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./campuspulse.db"
    DB_POOL_MIN_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 50
    
    # Security
    JWT_SECRET: str = "campuspulse-secret-key-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Ingestion constraints
    MAX_BATCH_SIZE: int = 1000
    MAX_FUTURE_SKEW_SECONDS: int = 600  # 10 minutes
    MAX_PAST_SKEW_SECONDS: int = 86400 * 7  # 7 days
    
    # Worker
    WORKER_POLL_INTERVAL_SECONDS: float = 0.5
    WORKER_BATCH_SIZE: int = 100
    JOB_LOCK_TIMEOUT_SECONDS: int = 30
    
    # Supported metric types whitelist
    SUPPORTED_METRIC_TYPES: list[str] = [
        "temperature",
        "humidity",
        "air_quality",
        "co2",
        "occupancy",
        "noise_level",
        "light_level",
        "power_consumption"
    ]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
