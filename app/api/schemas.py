from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AdjacencyMode(str, Enum):
    full_cohort = "full_cohort"
    top_k_only = "top_k_only"


class SearchGraphRequest(BaseModel):
    term: str = Field(min_length=1, max_length=512)
    max_depth: int = Field(default=2, ge=0, le=10)
    top_k: int = Field(default=50, ge=1, le=200)
    max_initial_works: int = Field(default=50, ge=1, le=500)
    max_total_works: int = Field(default=500, ge=1, le=5000)
    adjacency_mode: AdjacencyMode = AdjacencyMode.full_cohort
    adjacency_full_cohort_max_n: int = Field(default=80, ge=10, le=500)
    max_citing_per_seed: int = Field(default=25, ge=0, le=200)
    max_cited_per_seed: int = Field(default=25, ge=0, le=200)
    max_related_per_seed: int = Field(default=15, ge=0, le=100)
    per_page: int = Field(default=25, ge=1, le=200)
    use_llm_enrichment: bool = False
    fetch_author_h_index: bool = True


class ConsideredNeighbor(BaseModel):
    work_id: str
    relevancy_score: float | None = None
    continued: bool = False
    context: Literal["tfidf_cohort", "openalex_expansion"] = "tfidf_cohort"
    expansion_subtype: str | None = None


class GraphNode(BaseModel):
    id: str
    work: dict[str, Any]
    adjacency: list[ConsideredNeighbor] = Field(default_factory=list)


class SearchGraphMetadata(BaseModel):
    term: str
    timings_s: dict[str, float] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    adjacency_truncated: bool = False
    errors: list[str] = Field(default_factory=list)


class SearchGraphResponse(BaseModel):
    nodes: list[GraphNode]
    meta: SearchGraphMetadata