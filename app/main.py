# app/main.py
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from configs.settings import Settings
from contextlib import asynccontextmanager
from app.socket_manger.socket_manager_utils import initialize_socket_manager
from app.core.ayla_document_processor import AylaDocumentProcessor
from app.core.dima_http_client import DimaHttpClient
from app.core.diana_http_client import DianaHttpClient
from app.services.ayla.ayla_agent import AylaAgentService
from contextlib import asynccontextmanager
from app.dependencies.depends import get_audio_processor
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI application first
app = FastAPI()

# Add CORS middleware with specific configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Add your frontend origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize all required services
    settings = Settings()
    db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
    # Initialize socket manager
    socket_manager = initialize_socket_manager(db)
    
    # Initialize other required services
    document_processor = AylaDocumentProcessor()
    audio_processor = get_audio_processor(settings)
    dima_client = DimaHttpClient(settings)
    diana_client = DianaHttpClient(settings)
    
    # Create AylaAgentService instance
    ayla_agent = AylaAgentService(
        db=db,
        document_processor=document_processor,
        audio_processor=audio_processor,
        socket_manager=socket_manager,
        dima_client=dima_client,
        diana_client=diana_client,
        settings=settings
    )
    
    # Initialize Ozil connection
    await ayla_agent.initialize_ozil_socket()
    
    # Store instances in app state
    app.state.socket_manager = socket_manager
    app.state.ayla_agent = ayla_agent
    yield
    
    if hasattr(app.state, 'ayla_agent') and app.state.ayla_agent.ozil_socket:
        await app.state.ayla_agent.ozil_socket.disconnect()

# Set the lifespan
app.router.lifespan_context = lifespan

# Include routers
from app.api import ayla_agent_route, dima_enpoint, clear_table_routes
app.include_router(ayla_agent_route.router)
app.include_router(dima_enpoint.router)
app.include_router(clear_table_routes.router)

# Initialize socket manager immediately for mounting
settings = Settings()
db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
socket_manager = initialize_socket_manager(db)

# Mount socket manager at a specific path instead of root
app.mount("/ws", socket_manager.app)