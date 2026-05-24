from fastapi import APIRouter, Depends

from app.api.schemas import SearchGraphRequest, SearchGraphResponse
from app.core.config import Settings, get_settings
from app.search import run_search_graph

router = APIRouter()


@router.post("/search-graph", response_model=SearchGraphResponse)
def search_graph(
    body: SearchGraphRequest,
    settings: Settings = Depends(get_settings),
) -> SearchGraphResponse:
    return run_search_graph(body, settings)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
