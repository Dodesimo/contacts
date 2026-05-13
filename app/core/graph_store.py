from __future__ import annotations

import re
import threading
from typing import Any

from app.api.schemas import ConsideredNeighbor, GraphNode

_W_RE = re.compile(r"^W\d+$")


def normalize_openalex_work_id(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if s.startswith("https://openalex.org/"):
        s = s.rsplit("/", 1)[-1]
    if _W_RE.match(s):
        return s
    return None


class ResearchGraphStore:
    """Thread-safe store: one node per OpenAlex work id with embedded adjacency."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, dict[str, Any]] = {}

    def upsert_work(self, work_id: str, work: dict[str, Any]) -> str:
        wid = normalize_openalex_work_id(work_id) or work_id
        with self._lock:
            if wid not in self._nodes:
                self._nodes[wid] = {"id": wid, "work": dict[str, Any](work), "adjacency": []}
            else:
                self._nodes[wid]["work"].update(work)
            return wid

    def replace_adjacency(self, work_id: str, adjacency: list[ConsideredNeighbor]) -> str:
        wid = normalize_openalex_work_id(work_id) or work_id
        with self._lock:
            if wid not in self._nodes:
                self._nodes[wid] = {"id": wid, "work": {}, "adjacency": []}
            self._nodes[wid]["adjacency"] = [a.model_dump() for a in adjacency]
            return wid

    def append_adjacency(self, work_id: str, entries: list[ConsideredNeighbor]) -> str:
        if not entries:
            return normalize_openalex_work_id(work_id) or work_id
        wid = normalize_openalex_work_id(work_id) or work_id
        with self._lock:
            if wid not in self._nodes:
                self._nodes[wid] = {"id": wid, "work": {}, "adjacency": []}
            self._nodes[wid]["adjacency"].extend([e.model_dump() for e in entries])
            return wid

    def get_node_ids(self) -> list[str]:
        with self._lock:
            return list(self._nodes.keys())

    def count_nodes(self) -> int:
        with self._lock:
            return len(self._nodes)

    def has_node(self, work_id: str) -> bool:
        wid = normalize_openalex_work_id(work_id) or work_id
        with self._lock:
            return wid in self._nodes

    def snapshot_nodes(self) -> list[GraphNode]:
        """Return a sorted copy suitable for API serialization."""
        with self._lock:
            out: list[GraphNode] = []
            for raw in self._nodes.values():
                adj = [ConsideredNeighbor(**a) for a in raw["adjacency"]]
                out.append(GraphNode(id=raw["id"], work=dict[str, Any](raw["work"]), adjacency=adj))
            out.sort(key=lambda n: n.id)
            return out
