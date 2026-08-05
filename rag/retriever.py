"""
retriever.py — Numpy cosine-similarity retrieval over precomputed embeddings.

No ChromaDB. Loads data/extracted/precomputed_embeddings.json (built by
ingest/embed_and_index.py) and does cosine similarity in numpy.

Three retrieval modes:
  retrieve()               — semantic search with per-case diversity cap
  retrieve_all_overviews() — one overview chunk per case for summary queries
  retrieve_for_case()      — all chunks for a specific case study ID
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EMBED_MODEL = "all-MiniLM-L6-v2"
PRECOMPUTED_PATH = Path("data/extracted/precomputed_embeddings.json")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "their", "this",
    "to", "what", "when", "where", "which", "who", "why", "with", "worked",
}

# Module-level cache — loaded once per process
_store = None
_embeddings_np = None


def _load_store():
    global _store, _embeddings_np
    if _store is None:
        if not PRECOMPUTED_PATH.exists():
            raise FileNotFoundError(
                f"Precomputed embeddings not found at {PRECOMPUTED_PATH}. "
                "Run: python ingest/embed_and_index.py"
            )
        data = json.loads(PRECOMPUTED_PATH.read_text())
        if "texts" not in data or "metadatas" not in data:
            raise ValueError(
                "precomputed_embeddings.json is missing 'texts'/'metadatas'. "
                "Re-run: python ingest/embed_and_index.py"
            )
        _store = data
        emb = np.array(data["embeddings"], dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        _embeddings_np = emb / norms
    return _store


def _cosine_scores(query_vec):
    _load_store()
    if _embeddings_np is None or len(_embeddings_np) == 0:
        return np.array([])
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    return _embeddings_np @ q


def _tokens(text):
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", text.lower())
        if token not in STOPWORDS
    ]


class MRRetriever:
    def __init__(self, n_results=8):
        self.model = None
        self.n_results = n_results

    def _get_model(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(EMBED_MODEL)
        return self.model

    def retrieve(self, query, filters=None, max_per_case=2):
        store = _load_store()
        if not store.get("ids"):
            return []

        if os.getenv("RAG_RETRIEVAL_MODE", "lexical").lower() != "semantic":
            return self._retrieve_lexical(query, filters=filters, max_per_case=max_per_case)

        q_vec = self._get_model().encode(query, convert_to_numpy=True)
        scores = _cosine_scores(q_vec)
        ranked = np.argsort(-scores)

        seen = {}
        output = []
        for idx in ranked:
            m = store["metadatas"][idx]
            if filters and not all(m.get(k) == str(v) for k, v in filters.items()):
                continue
            cid = m.get("case_id", "unknown")
            if seen.get(cid, 0) < max_per_case:
                seen[cid] = seen.get(cid, 0) + 1
                output.append({"text": store["texts"][idx], "metadata": m})
            if len(output) >= self.n_results:
                break
        return output

    def _retrieve_lexical(self, query, filters=None, max_per_case=2):
        store = _load_store()
        query_terms = _tokens(query)
        if not query_terms:
            return []

        query_counts = Counter(query_terms)
        ranked = []
        for idx, (text, metadata) in enumerate(zip(store.get("texts", []), store.get("metadatas", []))):
            if filters and not all(metadata.get(k) == str(v) for k, v in filters.items()):
                continue
            text_l = text.lower()
            text_terms = Counter(_tokens(text_l))
            score = 0.0
            for term, count in query_counts.items():
                if term in text_terms:
                    score += min(text_terms[term], 4) * count
                if term in text_l:
                    score += 0.75
            if score:
                ranked.append((score, idx))

        ranked.sort(reverse=True)
        seen = {}
        output = []
        for _, idx in ranked:
            metadata = store["metadatas"][idx]
            cid = metadata.get("case_id", "unknown")
            if seen.get(cid, 0) < max_per_case:
                seen[cid] = seen.get(cid, 0) + 1
                output.append({"text": store["texts"][idx], "metadata": metadata})
            if len(output) >= self.n_results:
                break
        return output

    def retrieve_all_overviews(self):
        """Return one overview/summary chunk per case for broad summary queries."""
        store = _load_store()
        return [
            {"text": t, "metadata": m}
            for t, m in zip(store.get("texts", []), store.get("metadatas", []))
            if m.get("section") == "overview_summary"
        ]

    def retrieve_for_case(self, case_id):
        """Return all chunks for a specific case study ID."""
        store = _load_store()
        return [
            {"text": t, "metadata": m}
            for t, m in zip(store.get("texts", []), store.get("metadatas", []))
            if m.get("case_id") == case_id
        ]
