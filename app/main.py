from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from configs.settings import Settings
from contextlib import asynccontextmanager
from app.socket_manger.socket_manager_utils import initialize_socket_manager
from app.dependencies.depends import get_ayla_agent
from fastapi.middleware.cors import CORSMiddleware
from app.api import clear_table_routes
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = Settings()
    db = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGODB_DB]
    socket_manager = initialize_socket_manager(db)
    ayla_agent = get_ayla_agent(db)
    
    # Start the Ozil socket connection in the background
    asyncio.create_task(ayla_agent.initialize_ozil_socket())
    
    # Mount socket manager
    app.mount("/", socket_manager.app)
    
    yield
    
    # Cleanup (if needed)
    # Add any cleanup code here

# Create FastAPI application
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

# Include routers
app.include_router(clear_table_routes.router)