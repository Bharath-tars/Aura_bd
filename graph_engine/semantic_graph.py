"""
In-memory semantic wellness knowledge graph.
Rebuilt from SQLite data on startup / on-demand.
Provides O(1) node lookup and cosine similarity semantic search.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any
import numpy as np


@dataclass
class GraphNode:
    id: str
    type: str      # "mood" | "journal" | "theme" | "emotion" | "factor" | "activity"
    properties: dict[str, Any] = field(default_factory=dict)
    embedding: np.ndarray | None = None


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str  # "EXPRESSED","INFLUENCED_BY","CONTAINS_THEME","CORRELATES_WITH","TRIGGERS","IMPROVES"
    weight: float = 1.0
    timestamp: str | None = None


class WellnessSemanticGraph:
    """
    Typed property graph for wellness data.
    All mutation is synchronous (call from async code with run_in_executor if needed).
    """

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.adj: dict[str, list[GraphEdge]] = defaultdict(list)
        self.rev: dict[str, list[GraphEdge]] = defaultdict(list)

    # ─── Mutation ──────────────────────────────────────────────────────────────

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.adj[edge.source_id].append(edge)
        self.rev[edge.target_id].append(edge)

    def upsert_node(self, node: GraphNode) -> None:
        existing = self.nodes.get(node.id)
        if existing:
            existing.properties.update(node.properties)
            if node.embedding is not None:
                existing.embedding = node.embedding
        else:
            self.nodes[node.id] = node

    # ─── Queries ───────────────────────────────────────────────────────────────

    def neighbors(self, node_id: str, relation: str | None = None) -> list[GraphNode]:
        edges = self.adj.get(node_id, [])
        if relation:
            edges = [e for e in edges if e.relation == relation]
        return [self.nodes[e.target_id] for e in edges if e.target_id in self.nodes]

    def get_nodes_by_type(self, node_type: str) -> list[GraphNode]:
        return [n for n in self.nodes.values() if n.type == node_type]

    def semantic_search(self, query_emb: np.ndarray, node_type: str, top_k: int = 5) -> list[GraphNode]:
        candidates = [n for n in self.nodes.values() if n.type == node_type and n.embedding is not None]
        if not candidates:
            return []
        matrix = np.stack([c.embedding for c in candidates])
        q = query_emb / (np.linalg.norm(query_emb) + 1e-9)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
        scores = (matrix / norms) @ q
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [candidates[i] for i in top_idx]

    # ─── Analytics ─────────────────────────────────────────────────────────────

    def get_mood_trend(self) -> dict:
        mood_nodes = sorted(
            self.get_nodes_by_type("mood"),
            key=lambda n: n.properties.get("created_at", ""),
        )
        if not mood_nodes:
            return {"avg": 0.0, "trend": "insufficient_data", "weekly_avgs": []}
        scores = [n.properties["score"] for n in mood_nodes]
        avg = float(np.mean(scores))

        # Weekly buckets (last 4 weeks)
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        weekly_avgs: list[float] = []
        for offset in range(3, -1, -1):
            start = now - timedelta(weeks=offset + 1)
            end = now - timedelta(weeks=offset)
            week_scores = [
                n.properties["score"] for n in mood_nodes
                if start.isoformat() <= n.properties.get("created_at", "") < end.isoformat()
            ]
            weekly_avgs.append(round(float(np.mean(week_scores)), 1) if week_scores else 0.0)

        non_zero = [x for x in weekly_avgs if x > 0]
        if len(non_zero) >= 2:
            delta = non_zero[-1] - non_zero[0]
            trend = "rising" if delta > 0.5 else "falling" if delta < -0.5 else "stable"
        else:
            trend = "insufficient_data"

        return {"avg": round(avg, 1), "trend": trend, "weekly_avgs": weekly_avgs}

    def get_emotion_freq(self) -> dict[str, int]:
        freq: dict[str, int] = defaultdict(int)
        for edge in sum(self.adj.values(), []):
            if edge.relation == "EXPRESSED":
                freq[edge.target_id] += 1
        return dict(sorted(freq.items(), key=lambda x: -x[1])[:15])

    def get_factor_impact(self, factor_name: str) -> float:
        """Mean mood delta when factor present vs absent."""
        with_f, without_f = [], []
        for node in self.get_nodes_by_type("mood"):
            score = node.properties.get("score", 5)
            factors = node.properties.get("factors", [])
            if factor_name in factors:
                with_f.append(score)
            else:
                without_f.append(score)
        if not with_f or not without_f:
            return 0.0
        return round(float(np.mean(with_f)) - float(np.mean(without_f)), 2)

    def find_positive_levers(self, top_n: int = 5) -> list[dict]:
        all_factors: set[str] = set()
        for node in self.get_nodes_by_type("mood"):
            all_factors.update(node.properties.get("factors", []))
        impacts = [(f, self.get_factor_impact(f)) for f in all_factors]
        positive = sorted([(f, d) for f, d in impacts if d > 0], key=lambda x: -x[1])
        return [{"factor": f, "delta": d} for f, d in positive[:top_n]]

    def get_top_themes(self, top_n: int = 5) -> list[str]:
        freq: dict[str, int] = defaultdict(int)
        for edge in sum(self.adj.values(), []):
            if edge.relation == "CONTAINS_THEME":
                freq[edge.target_id] += 1
        sorted_themes = sorted(freq.items(), key=lambda x: -x[1])
        return [t for t, _ in sorted_themes[:top_n]]


_graph_instance: WellnessSemanticGraph | None = None


def get_graph() -> WellnessSemanticGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = WellnessSemanticGraph()
    return _graph_instance


async def rebuild_graph(db) -> WellnessSemanticGraph:
    """Rebuild graph from SQLite for the current user."""
    from sqlalchemy import select
    from ..models.mood import MoodEntry
    from ..models.journal import JournalEntry

    graph = WellnessSemanticGraph()

    mood_result = await db.execute(select(MoodEntry))
    for entry in mood_result.scalars().all():
        node = GraphNode(
            id=f"mood_{entry.id}", type="mood",
            properties={"score": entry.score, "factors": entry.factors or [],
                        "emotions": entry.emotions or [], "created_at": entry.created_at.isoformat()},
        )
        graph.add_node(node)
        for emotion in (entry.emotions or []):
            emotion_node = GraphNode(id=emotion, type="emotion", properties={"name": emotion})
            graph.upsert_node(emotion_node)
            graph.add_edge(GraphEdge(f"mood_{entry.id}", emotion, "EXPRESSED", weight=1.0))
        for factor in (entry.factors or []):
            factor_node = GraphNode(id=factor, type="factor", properties={"name": factor})
            graph.upsert_node(factor_node)
            graph.add_edge(GraphEdge(f"mood_{entry.id}", factor, "INFLUENCED_BY", weight=1.0))

    journal_result = await db.execute(select(JournalEntry))
    for entry in journal_result.scalars().all():
        node = GraphNode(
            id=f"journal_{entry.id}", type="journal",
            properties={"title": entry.title, "themes": entry.themes or [],
                        "sentiment": entry.sentiment_score, "created_at": entry.created_at.isoformat()},
        )
        graph.add_node(node)
        for theme in (entry.themes or []):
            theme_node = GraphNode(id=f"theme_{theme}", type="theme", properties={"name": theme})
            graph.upsert_node(theme_node)
            graph.add_edge(GraphEdge(f"journal_{entry.id}", f"theme_{theme}", "CONTAINS_THEME", weight=1.0))

    return graph
