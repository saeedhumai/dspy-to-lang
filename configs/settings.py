from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""
    MONGODB_URL: str
    MONGODB_DB: str
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    OZIL_SERVICE_URL: str

    class Config:
        case_sensitive = True
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()