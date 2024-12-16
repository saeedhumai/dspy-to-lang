from motor.motor_asyncio import AsyncIOMotorClient
from app.socket_manger.socket_manager import SocketManager
socket_manager = None

def initialize_socket_manager(db: AsyncIOMotorClient):
    global socket_manager
    if socket_manager is None:
        socket_manager = SocketManager(db=db)
    return socket_manager

def get_socket_manager():
    if socket_manager is None:
        raise RuntimeError("Socket manager not initialized")
    return socket_manager