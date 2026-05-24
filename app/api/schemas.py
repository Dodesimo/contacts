from typing import Any, Literal

from pydantic import BaseModel, Field


MAX_LAYERS = 5


class SearchGraphRequest(BaseModel):
    term: str = Field(min_length=1, max_length=512)
    max_initial_works: int = Field(default=25, ge=1, le=200)
    max_neighbors_per_seed: int = Field(default=25, ge=1, le=100)
    max_total_works: int = Field(default=500, ge=1, le=5000)
    per_page: int = Field(default=25, ge=1, le=200)


class ConsideredNeighbor(BaseModel):
    work_id: str
    relevancy_score: float | None = None
    continued: bool = False
    context: Literal["search", "expansion"] = "expansion"
    expansion_subtype: str | None = None


class GraphNode(BaseModel):
    id: str
    work: dict[str, Any]
    adjacency: list[ConsideredNeighbor] = Field(default_factory=list)


class SearchGraphMetadata(BaseModel):
    term: str
    layers_completed: int = 0
    max_layers: int = MAX_LAYERS
    timings_s: dict[str, float] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class SearchGraphResponse(BaseModel):
    nodes: list[GraphNode]
    meta: SearchGraphMetadata
