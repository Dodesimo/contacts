from __future__ import annotations

import time
from typing import Any

import httpx

from app.api.schemas import (
    MAX_LAYERS,
    ConsideredNeighbor,
    SearchGraphMetadata,
    SearchGraphRequest,
    SearchGraphResponse,
)
from app.core.config import Settings
from app.core.graph_store import ResearchGraphStore, normalize_openalex_work_id
from app.core.openalex_client import OpenAlexClient, normalize_work


def _rank_score(rank: int) -> float:
    return 1.0 / (1.0 + rank)


def _add_work(
    store: ResearchGraphStore,
    raw: dict[str, Any],
    cache: dict[str, dict[str, Any]],
) -> str | None:
    wid = normalize_openalex_work_id(raw.get("id"))
    if not wid:
        return None
    cache[wid] = raw
    store.upsert_work(wid, normalize_work(raw))
    return wid


def _expand_seed(
    oa: OpenAlexClient,
    seed_id: str,
    raw_seed: dict[str, Any] | None,
    *,
    max_neighbors: int,
    per_page: int,
) -> list[tuple[str, dict[str, Any]]]:
    """Return deduped (subtype, raw_work) pairs from citing, cited_by, and related."""
    if raw_seed is None:
        raw_seed = oa.get_work(seed_id)
    if raw_seed is None:
        return []

    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def add_batch(subtype: str, works: list[dict[str, Any]]) -> None:
        for raw in works:
            wid = normalize_openalex_work_id(raw.get("id"))
            if not wid or wid in seen:
                continue
            seen.add(wid)
            out.append((subtype, raw))
            if len(out) >= max_neighbors:
                return

    per_type = max(1, max_neighbors // 3)
    add_batch("citing", oa.citing_works(seed_id, per_page=per_page, max_results=per_type))
    if len(out) < max_neighbors:
        add_batch("cited_by", oa.cited_by_works(seed_id, per_page=per_page, max_results=per_type))
    if len(out) < max_neighbors and raw_seed is not None:
        add_batch("related", oa.related_work_objects(raw_seed, max_results=per_type))

    return out[:max_neighbors]


def run_search_graph(request: SearchGraphRequest, settings: Settings) -> SearchGraphResponse:
    store = ResearchGraphStore()
    raw_cache: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    timings: dict[str, float] = {}
    layers_completed = 0

    seen: set[str] = set()
    frontier: list[str] = []

    t0 = time.perf_counter()
    with httpx.Client() as http_client:
        oa = OpenAlexClient(settings, http_client)

        try:
            initial = oa.search_works(
                request.term,
                max_results=request.max_initial_works,
                per_page=request.per_page,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"search:{exc}")
            initial = []

        for raw in initial:
            wid = _add_work(store, raw, raw_cache)
            if wid and wid not in seen:
                seen.add(wid)
                frontier.append(wid)

        layers_completed = 1 if frontier else 0

        for layer in range(1, MAX_LAYERS):
            if not frontier:
                break

            next_frontier: list[str] = []

            for seed_id in frontier:
                if store.count_nodes() >= request.max_total_works:
                    break

                try:
                    neighbors = _expand_seed(
                        oa,
                        seed_id,
                        raw_cache.get(seed_id),
                        max_neighbors=request.max_neighbors_per_seed,
                        per_page=request.per_page,
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"expand:{seed_id}:{exc}")
                    continue

                adjacency: list[ConsideredNeighbor] = []
                for rank, (subtype, raw) in enumerate(neighbors):
                    wid = normalize_openalex_work_id(raw.get("id"))
                    if not wid:
                        continue

                    if not store.has_node(wid) and store.count_nodes() >= request.max_total_works:
                        adjacency.append(
                            ConsideredNeighbor(
                                work_id=wid,
                                relevancy_score=_rank_score(rank),
                                continued=False,
                                context="expansion",
                                expansion_subtype=subtype,
                            )
                        )
                        continue

                    _add_work(store, raw, raw_cache)
                    continued = wid not in seen
                    if continued:
                        seen.add(wid)
                        next_frontier.append(wid)

                    adjacency.append(
                        ConsideredNeighbor(
                            work_id=wid,
                            relevancy_score=_rank_score(rank),
                            continued=continued,
                            context="expansion",
                            expansion_subtype=subtype,
                        )
                    )

                if adjacency:
                    store.append_adjacency(seed_id, adjacency)

            frontier = next_frontier
            layers_completed = layer + 1

    timings["total"] = time.perf_counter() - t0

    return SearchGraphResponse(
        nodes=store.snapshot_nodes(),
        meta=SearchGraphMetadata(
            term=request.term,
            layers_completed=layers_completed,
            max_layers=MAX_LAYERS,
            timings_s=timings,
            counts={"nodes": store.count_nodes()},
            errors=errors,
        ),
    )
