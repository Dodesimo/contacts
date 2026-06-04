import asyncio

from fastapi import APIRouter, Depends

from app.api.schemas import SearchGraphRequest, SearchGraphResponse
from app.core.config import Settings, get_settings
from app.search import run_search_graph

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "contacts", "docs": "/docs"}


@router.post("/search-graph", response_model=SearchGraphResponse)
async def search_graph(
    body: SearchGraphRequest,
    settings: Settings = Depends(get_settings),
) -> SearchGraphResponse:
    return await asyncio.to_thread(run_search_graph, body, settings)



@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
