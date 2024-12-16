from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""
    # Database
    MONGODB_URL: str
    MONGODB_DB: str

    DIMA_SERVICE_URL: str
    DIMA_REQUEST_TIMEOUT: str
    
    # Pinecone
    PINECONE_API_KEY: str
    PINECONE_INDEX: str

    REDIS_HOST: str
    REDIS_PORT: str
    REDIS_PASSWORD: str
    
    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str
    
    # OpenAI
    OPENAI_API_KEY: str
    DIANA_SERVICE_URL: str
    OZIL_SERVICE_URL: str
    
    # Gemini
    GOOGLE_API_KEY: str
    GOOGLE_APPLICATION_CREDENTIALS: str

    # Claude
    ANTHROPIC_API_KEY: str

    # WhatsApp
    WHATSAPP_APP_SECRET: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    
    class Config:
        case_sensitive = True
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()