from __future__ import annotations

import heapq
from typing import Iterable

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

_analyze = TfidfVectorizer(strip_accents="unicode", lowercase=True).build_analyzer()


def abstract_bm25_scores_vs_reference(
    reference: str,
    candidates: dict[str, str],
) -> dict[str, float]:
    """Okapi BM25 score of each candidate abstract against the reference abstract."""
    ref_tokens = _analyze(reference.strip())
    if not ref_tokens or not candidates:
        return {}

    ids = [wid for wid, text in candidates.items() if text and text.strip()]
    if not ids:
        return {}

    corpus = [_analyze(candidates[wid].strip()) for wid in ids]
    scores = BM25Okapi(corpus).get_scores(ref_tokens)
    return {wid: float(scores[i]) for i, wid in enumerate(ids)}


def _top_k_by_score(scores: dict[str, float], top_k: int) -> list[str]:
    if not scores or top_k <= 0:
        return []
    return [
        wid for wid, _ in heapq.nlargest(top_k, scores.items(), key=lambda item: item[1])
    ]


def top_k_by_bm25(
    reference: str | None,
    candidates: dict[str, str],
    *,
    top_k: int,
    fallback_order: Iterable[str] | None = None,
) -> tuple[list[str], dict[str, float]]:
    """
    Return up to top_k work ids ranked by BM25 score vs reference,
    plus the score map. Unscored ids from fallback_order fill remaining slots.
    """
    if top_k <= 0:
        return [], {}

    scores: dict[str, float] = {}
    if reference and reference.strip() and candidates:
        scores = abstract_bm25_scores_vs_reference(reference, candidates)

    seen: set[str] = set()
    out: list[str] = []
    for wid in _top_k_by_score(scores, top_k):
        if wid in seen:
            continue
        seen.add(wid)
        out.append(wid)
        if len(out) >= top_k:
            return out, scores

    if fallback_order is not None:
        for wid in fallback_order:
            if wid in seen:
                continue
            seen.add(wid)
            out.append(wid)
            if len(out) >= top_k:
                break

    return out, scores
