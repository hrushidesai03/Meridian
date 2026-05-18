"""
Configuration management for Meridian backend.
Loads settings from environment variables with defaults.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

# Load .env file first
load_dotenv()


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    
    # App metadata
    app_name: str = "Meridian"
    app_version: str = "1.0.0"
    
    # Database
    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/meridian")
    mongodb_db: str = os.getenv("MONGODB_DB", "meridian")
    
    # VideoDB
    videodb_api_key: str = os.getenv("VIDEODB_API_KEY", "")
    videodb_api_endpoint: str = os.getenv("VIDEODB_API_ENDPOINT", "https://api.videodb.io")
    videodb_webhook_secret: str = os.getenv("VIDEODB_WEBHOOK_SECRET", "")
    videodb_callback_url: str = os.getenv("VIDEODB_CALLBACK_URL", "http://localhost:8000/webhooks")
    
    # Anthropic Claude
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Groq
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    
    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # CORS
    cors_origins: list = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]
    
    # WebSocket
    ws_heartbeat_interval: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    
    # VideoDB Callbacks
    callback_base_url: str = os.getenv("CALLBACK_BASE_URL", "http://localhost:8000")
    
    # Processing
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
    transcript_batch_timeout_seconds: int = int(os.getenv("TRANSCRIPT_BATCH_TIMEOUT_SECONDS", "5"))


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
