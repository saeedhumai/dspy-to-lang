from fastapi import APIRouter
from app.schemas.broker_schema import AgentMessage
from app.core.dima_http_client import DimaHttpClient
router = APIRouter(tags=["DIMA"])


@router.post("/dima")
async def dima(request: AgentMessage):
    dima_client = DimaHttpClient()
    return await dima_client.search_medicines(request)

