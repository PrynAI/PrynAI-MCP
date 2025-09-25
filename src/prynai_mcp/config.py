from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ALLOW_ORIGINS: str = "*"

settings = Settings()