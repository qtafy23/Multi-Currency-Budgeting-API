from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    """
    Application settings - manages both environment variables and config files.
    Priority: environment variables > .env file > defaults
    """
    
    # App Settings
    app_name: str = Field(default="Multi-Currency Budgeting API", env="APP_NAME")
    env: str = Field(default="development", env="ENV")
    debug: bool = Field(default=True, env="DEBUG")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # Database Settings
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/mcb_dev", env="DATABASE_URL")
    db_echo: bool = Field(default=False, env="DB_ECHO")
    
    # Redis Settings
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Security Settings
    secret_key: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # CORS Settings
    cors_origins: list = Field(default=["http://localhost:3000", "http://localhost:8000"], env="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, env="CORS_CREDENTIALS")
    cors_methods: list = Field(default=["*"], env="CORS_METHODS")
    cors_headers: list = Field(default=["*"], env="CORS_HEADERS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Load settings
settings = Settings()

# Print active settings (only in development)
if settings.env == "development":
    print(f"[Config] Environment: {settings.env}")
    print(f"[Config] Debug: {settings.debug}")
    print(f"[Config] Database: {settings.database_url}")
