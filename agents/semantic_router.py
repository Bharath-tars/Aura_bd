"""
Semantic intent router using Gemini text embeddings + cosine similarity.
Pre-computes centroids at startup. <50ms on the hot path (no LLM call).
"""
from __future__ import annotations
import numpy as np
from pathlib import Path
from typing import Callable, Awaitable

INTENT_EXAMPLES: dict[str, list[str]] = {
    "coach": [
        "I'm feeling overwhelmed today",
        "how do I deal with anxiety",
        "I need someone to talk to",
        "help me feel better",
        "I'm struggling with my thoughts",
        "feeling really stressed out",
        "I don't know what to do",
        "just having a hard time lately",
    ],
    "mood_analysis": [
        "analyze my mood patterns",
        "what are my mood trends",
        "when am I happiest",
        "show me my emotional history",
        "why is my mood low this week",
        "what emotions am I feeling most",
        "how has my mood changed",
    ],
    "journal_insights": [
        "analyze my journal",
        "what themes appear in my writing",
        "find patterns in my entries",
        "what am I thinking about most",
        "summarize my recent reflections",
        "what does my journal say about me",
    ],
    "plan_generation": [
        "create a wellness plan for me",
        "help me build healthy habits",
        "generate a self-care routine",
        "I want to improve my sleep",
        "make me a mental health plan",
        "help me reduce stress with a plan",
        "build me a 4 week wellness program",
    ],
    "crisis": [
        "I don't want to be here anymore",
        "I'm having thoughts of hurting myself",
        "I feel hopeless about everything",
        "nothing matters anymore",
        "I can't take this anymore",
        "I've been thinking about ending it",
        "everyone would be better off without me",
    ],
}

EmbedFn = Callable[[str], Awaitable[np.ndarray]]


class SemanticRouter:
    def __init__(self, embedding_fn: EmbedFn, threshold: float = 0.72, crisis_threshold: float = 0.65):
        self.embedding_fn = embedding_fn
        self.threshold = threshold
        self.crisis_threshold = crisis_threshold
        self.centroids: dict[str, np.ndarray] = {}

    async def build_centroids(self) -> None:
        for intent, examples in INTENT_EXAMPLES.items():
            embeddings = [await self.embedding_fn(ex) for ex in examples]
            self.centroids[intent] = np.mean(embeddings, axis=0).astype(np.float32)

    def save_centroids(self, path: str = "centroids.npy") -> None:
        data = {k: v for k, v in self.centroids.items()}
        np.save(path, data)  # type: ignore

    def load_centroids(self, path: str = "centroids.npy") -> None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        data = np.load(path, allow_pickle=True).item()
        self.centroids = {k: np.array(v, dtype=np.float32) for k, v in data.items()}

    async def route(self, message: str) -> tuple[str, float]:
        """Returns (intent, confidence). Target: <50ms."""
        if not self.centroids:
            return "coach", 0.5  # fallback if not initialised

        query_emb = await self.embedding_fn(message)
        query_emb = query_emb.astype(np.float32)
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)

        scores: dict[str, float] = {}
        for intent, centroid in self.centroids.items():
            c_norm = centroid / (np.linalg.norm(centroid) + 1e-9)
            scores[intent] = float(c_norm @ query_norm)

        # Safety check first — always overrides
        if scores.get("crisis", 0) >= self.crisis_threshold:
            return "crisis", scores["crisis"]

        best_intent = max(scores, key=scores.__getitem__)
        confidence = scores[best_intent]

        if confidence < self.threshold:
            return "coach", confidence  # safe fallback

        return best_intent, confidence


# ── Module-level singleton (set by main.py lifespan) ──────────────────────────
_router_instance: "SemanticRouter | None" = None


def get_router() -> "SemanticRouter | None":
    return _router_instance


def set_router(r: "SemanticRouter") -> None:
    global _router_instance
    _router_instance = r
