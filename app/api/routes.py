from fastapi import APIRouter, Depends

from app.api.schemas import SearchGraphMetadata, SearchGraphRequest, SearchGraphResponse
from app.core.config import Settings, get_settings

router = APIRouter()


@router.post("/search-graph", response_model=SearchGraphResponse)
def search_graph(
    body: SearchGraphRequest,
    _settings: Settings = Depends(get_settings),
) -> SearchGraphResponse:
    """
    Search graph (skeleton). Wire to orchestrator in a later todo.
    """
    return SearchGraphResponse(
        nodes=[],
        meta=SearchGraphMetadata(
            term=body.term,
            timings_s={},
            counts={"nodes": 0},
            adjacency_truncated=False,
            errors=[],
        ),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
