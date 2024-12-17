# app/main.py
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from configs.settings import Settings
from contextlib import asynccontextmanager
from app.socket_manger.socket_manager_utils import initialize_socket_manager
# from app.dependencies.depends import get_audio_processor, get_document_processor, get_ayla_agent, get_diana_client, get_dima_client
from fastapi.middleware.cors import CORSMiddleware
from app.api import clear_table_routes

# Create FastAPI application first
app = FastAPI()

# Add CORS middleware with specific configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Include routers
# from app.api import ayla_agent_route, dima_enpoint, clear_table_routes
# app.include_router(ayla_agent_route.router)
# app.include_router(dima_enpoint.router)
app.include_router(clear_table_routes.router)

# Initialize socket manager immediately for mounting
settings = Settings()
db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
socket_manager = initialize_socket_manager(db)
# ayla_agent = get_ayla_agent(db)
# Mount socket manager at a specific path instead of root
app.mount("/", socket_manager.app)