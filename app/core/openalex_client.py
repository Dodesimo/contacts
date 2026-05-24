from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import Settings
from app.core.graph_store import normalize_openalex_work_id

PER_PAGE = 25


def reconstruct_abstract_from_inverted_index(inv: dict[str, list[int]] | None) -> str | None:
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((int(i), word))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)


def normalize_work(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable work document for graph nodes."""
    wid = normalize_openalex_work_id(raw.get("id"))
    abstract = raw.get("abstract")
    if not abstract:
        inv = raw.get("abstract_inverted_index")
        if isinstance(inv, dict):
            abstract = reconstruct_abstract_from_inverted_index(inv)  # type: ignore[arg-type]

    refs = raw.get("referenced_works")
    referenced_works = refs
    referenced_works_truncated = False
    if isinstance(refs, list) and len(refs) > 400:
        referenced_works = refs[:400]
        referenced_works_truncated = True

    return {
        "openalex_id": wid,
        "id": raw.get("id"),
        "doi": raw.get("doi"),
        "title": raw.get("display_name") or raw.get("title"),
        "publication_year": raw.get("publication_year"),
        "type": raw.get("type"),
        "language": raw.get("language"),
        "cited_by_count": raw.get("cited_by_count"),
        "is_oa": raw.get("is_oa"),
        "abstract": abstract,
        "primary_location": raw.get("primary_location"),
        "concepts": raw.get("concepts"),
        "authorships": raw.get("authorships"),
        "related_works": raw.get("related_works"),
        "referenced_works_count": raw.get("referenced_works_count"),
        "referenced_works": referenced_works,
        "referenced_works_truncated": referenced_works_truncated,
        "summary": None,
        "key_findings": None,
    }


class OpenAlexClient:
    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self._settings = settings
        self._client = client
        self._delay_s = settings.openalex_request_delay_s

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": f"OpenAlexResearchGraph/0.1 (mailto:{self._settings.openalex_mailto})"}

    def _base_params(self) -> dict[str, str]:
        return {"api_key": self._settings.openalex_api_key}

    def _throttle(self) -> None:
        if self._delay_s > 0:
            time.sleep(self._delay_s)

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()
        url = f"{self._settings.openalex_base_url.rstrip('/')}/{path.lstrip('/')}"
        query: dict[str, Any] = dict[str, Any](self._base_params())
        if params:
            query.update({k: v for k, v in params.items() if v is not None})
        response = self._client.get(url, params=query, headers=self._headers(), timeout=60.0)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("OpenAlex returned non-object JSON")
        return data

    def search_works(self, term: str, *, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        while len(results) < max_results:
            data = self.get_json(
                "works",
                params={
                    "search": term,
                    "per_page": min(PER_PAGE, max_results - len(results)),
                    "page": page,
                },
            )
            batch = data.get("results") or []
            if not batch:
                break
            results.extend(batch)
            if len(batch) < PER_PAGE:
                break
            page += 1
        return results[:max_results]

    def get_work(self, work_id: str) -> dict[str, Any] | None:
        wid = normalize_openalex_work_id(work_id) or work_id
        try:
            return self.get_json(f"works/{wid}")
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            raise

    def get_works_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        normalized = [normalize_openalex_work_id(i) or i for i in ids if i]
        if not normalized:
            return []
        out: list[dict[str, Any]] = []
        chunk_size = 50
        for offset in range(0, len(normalized), chunk_size):
            chunk = normalized[offset : offset + chunk_size]
            filt = "|".join(chunk)
            data = self.get_json(
                "works",
                params={"filter": f"ids.openalex:{filt}", "per_page": min(len(chunk), 50)},
            )
            out.extend(data.get("results") or [])
        return out

    def list_works_filter(self, filter_expr: str, *, max_results: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 1
        while len(out) < max_results:
            data = self.get_json(
                "works",
                params={
                    "filter": filter_expr,
                    "per_page": min(PER_PAGE, max_results - len(out)),
                    "page": page,
                },
            )
            batch = data.get("results") or []
            if not batch:
                break
            out.extend(batch)
            if len(batch) < PER_PAGE:
                break
            page += 1
        return out[:max_results]

    def citing_works(self, work_id: str, *, max_results: int) -> list[dict[str, Any]]:
        wid = normalize_openalex_work_id(work_id) or work_id
        return self.list_works_filter(f"cites:{wid}", max_results=max_results)

    def cited_by_works(self, work_id: str, *, max_results: int) -> list[dict[str, Any]]:
        wid = normalize_openalex_work_id(work_id) or work_id
        return self.list_works_filter(f"cited_by:{wid}", max_results=max_results)

    def related_work_objects(self, raw_work: dict[str, Any], *, max_results: int) -> list[dict[str, Any]]:
        rel = raw_work.get("related_works") or []
        ids: list[str] = []
        for url in rel:
            if isinstance(url, str):
                wid = normalize_openalex_work_id(url)
                if wid:
                    ids.append(wid)
        return self.get_works_by_ids(ids[:max_results])
