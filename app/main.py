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

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     settings = Settings()
#     db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
#     socket_manager = initialize_socket_manager(db)
#     ayla_agent = get_ayla_agent(db)
    
#     # Start the Ozil socket connection in the background and store the task
#     ozil_socket_task = asyncio.create_task(ayla_agent.ozil_client.initialize_socket())
    
#     # Wait briefly for initial connection
#     try:
#         await asyncio.wait_for(ayla_agent.ozil_client.wait_for_connection(), timeout=5.0)
#     except asyncio.TimeoutError:
#         logger.warning("Initial Ozil connection timed out, continuing startup anyway")
    
#     # Mount socket manager
#     app.mount("/", socket_manager.app)
    
#     yield
    
#     # Cleanup
#     if ozil_socket_task and not ozil_socket_task.done():
#         ozil_socket_task.cancel()
#         try:
#             await ozil_socket_task
#         except asyncio.CancelledError:
#             pass
    
#     # Disconnect Ozil socket if connected
#     if ayla_agent.ozil_client.ozil_socket and ayla_agent.ozil_client.ozil_socket.connected:
#         await ayla_agent.ozil_client.ozil_socket.disconnect()

# Create FastAPI application
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

settings = Settings()
db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
socket_manager = initialize_socket_manager(db)
ozil_client = OzilClient(settings, socket_manager)
asyncio.create_task(ozil_client.maintain_connection())

app.mount("/", socket_manager.app)