from fastapi import Depends
from typing import Annotated
from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis
from configs.settings import Settings, get_settings
from langchain_openai import ChatOpenAI
from app.services.ayla.ayla_agent import AylaAgentService
from app.core.ayla_document_processor import AylaDocumentProcessor
from app.core.image_processor import ImageProcessor
from app.core.diana_http_client import DianaHttpClient
from app.core.dima_http_client import DimaHttpClient
from app.core.ayla_voice_processor import AudioProcessor
from app.socket_manger.socket_manager_utils import get_socket_manager

# ################################################### MUHAMMAD SHAH START ###################################################
async def get_db(
    settings: Annotated[Settings, Depends(get_settings)]
):
    return AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]

async def get_redis(
        settings: Annotated[Settings, Depends(get_settings)]
) ->Redis:
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True
    )
def get_audio_processor(
    settings: Annotated[Settings, Depends(get_settings)]
) -> AudioProcessor:
    return AudioProcessor(settings.GOOGLE_APPLICATION_CREDENTIALS)

def get_streaming_llm(
    settings: Annotated[Settings, Depends(get_settings)],
    model: str = "gpt-4o"
) -> ChatOpenAI:
    """Get streaming-enabled LLM instance"""
    return ChatOpenAI(
        temperature=0.7,
        model=model,
        streaming=True,
        api_key=settings.OPENAI_API_KEY
    )

def get_llm(
    settings: Annotated[Settings, Depends(get_settings)],
    model: str = "gpt-4o"
) -> ChatOpenAI:
    return ChatOpenAI(
        temperature=0.7,
        model=model,
        api_key=settings.OPENAI_API_KEY
    )

openai_client = ChatOpenAI(api_key=get_settings().OPENAI_API_KEY, model="gpt-4o")

async def get_redis_url(
    settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    return f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}"

def get_image_processor(
) -> ImageProcessor:
    return ImageProcessor(openai_client)

def get_document_processor(
) -> AylaDocumentProcessor:
    return AylaDocumentProcessor()

def get_dima_client(
    settings: Annotated[Settings, Depends(get_settings)]
) -> DimaHttpClient:
    return DimaHttpClient(
        settings=settings
)

def get_diana_client(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncIOMotorClient, Depends(get_db)],
) -> DianaHttpClient:
    return DianaHttpClient(
        settings=settings,
        db=db
    )




def get_ayla_agent(db: Annotated[AsyncIOMotorClient, Depends(get_db)]) -> AylaAgentService:
    return AylaAgentService(
        db=db,
        document_processor=get_document_processor(),
        audio_processor=get_audio_processor(settings=get_settings()),
        socket_manager=get_socket_manager(),  # Use get_socket_manager instead
        dima_client=get_dima_client(settings=get_settings()),
        diana_client=get_diana_client(settings=get_settings(), db=db),
        settings=get_settings()
    )

# ################################################### MUHAMMAD SHAH END ###################################################
