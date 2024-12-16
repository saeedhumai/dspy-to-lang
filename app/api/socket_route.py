# routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/ws")
# The socket handling is now done in SocketManager