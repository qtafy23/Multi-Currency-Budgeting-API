from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings - manages both environment
    variables and config files.
    Priority: environment variables > .env file > defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    # App Settings
    app_name: str = "Multi-Currency Budgeting API"
    env: str = "development"
    debug: bool = False

    # Server Settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=1)

    # Database Settings
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/mcb_dev"
    )
    db_echo: bool = False

    # Redis Settings
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Exchange Rate Settings
    exchange_rate_update_interval_minutes: int = Field(default=1440)

    # Security Settings
    secret_key: str = Field(default="your-secret-key-change-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    # CORS Settings
    cors_origins: list = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    cors_credentials: bool = Field(default=True)
    cors_methods: list = Field(default=["*"])
    cors_headers: list = Field(default=["*"])

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.env.strip().lower() != "production":
            return self

        if self.debug:
            raise ValueError("DEBUG must be False in production")

        placeholder_keys = {
            "secret",
            "changeme",
            "your-secret-key",
            "your-secret-key-change-in-production",
            "dev-secret-key",
        }

        if (len(self.secret_key) < 32 or self.secret_key.lower() in placeholder_keys):
            raise ValueError(
                "SECRET_KEY must be a strong key of at least 32 characters "
                "in production"
            )

        return self


# Load settings
settings = Settings()

# Print active settings (only in development)
if settings.env == "development":
    print(f"[Config] Environment: {settings.env}")
    print(f"[Config] Debug: {settings.debug}")
