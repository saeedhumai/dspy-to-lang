from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from configs.settings import Settings
from contextlib import asynccontextmanager
from app.socket_manger.socket_manager_utils import initialize_socket_manager
from app.dependencies.depends import get_ayla_agent
from fastapi.middleware.cors import CORSMiddleware
from app.api import clear_table_routes
import asyncio
from configs.logger import logger
from app.core.ozil_client import OzilClient
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = Settings()
    db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
    socket_manager = initialize_socket_manager(db)
    ozil_client = OzilClient(settings, socket_manager)
    
    # Start the Ozil socket connection maintenance task
    maintenance_task = asyncio.create_task(ozil_client.maintain_connection())
    
    # Mount socket manager
    app.mount("/", socket_manager.app)
    
    yield
    
    # Cleanup
    # Cancel the maintenance task
    if maintenance_task and not maintenance_task.done():
        maintenance_task.cancel()
        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass
    
    # Cleanup Ozil socket connection
    if ozil_client.ozil_socket and ozil_client.ozil_socket.connected:
        await ozil_client.ozil_socket.disconnect()
        ozil_client.ozil_socket = None
    
    # Cleanup Socket.IO server
    await socket_manager.sio.disconnect()

# Create FastAPI application with lifespan
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# settings = Settings()
# db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
# socket_manager = initialize_socket_manager(db)
# ozil_client = OzilClient(settings, socket_manager)
# asyncio.create_task(ozil_client.maintain_connection())

# app.mount("/", socket_manager.app)