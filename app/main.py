from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.socket_manager import socket_manager
from app.services.ayla_service import AylaService
from config.settings import Settings
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
    ayla_service = AylaService(db, settings)
    
    @socket_manager.sio.on('connect')
    async def handle_connect(sid, environ):
        query = environ.get('QUERY_STRING', '')
        params = dict(param.split('=') for param in query.split('&') if param and '=' in param)
        user_id = params.get('user_id')
        if user_id and user_id != 'undefined':
            await socket_manager.connect(sid, user_id)
    
    @socket_manager.sio.on('chat_message')
    async def handle_message(sid, data):
        await ayla_service.handle_message(
            user_id=data['user_id'],
            message=data['message'],
            provider=data.get('provider', 'openai')
        )
    
    app.mount("/", socket_manager.app)
    yield
    await socket_manager.sio.disconnect()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)