"""
Run once to initialise the database and pre-build semantic router centroids.
Usage: python init_db.py  (from the backend/ directory)
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, Base
from backend.models import User, MoodEntry, JournalEntry, WellnessPlan, ChatSession, ChatMessage, StreakTracking  # noqa: F401


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created")


async def build_centroids():
    """Pre-compute semantic router embedding centroids at startup."""
    try:
        from backend.agents.semantic_router import SemanticRouter
        from backend.config import get_settings
        import google.generativeai as genai

        settings = get_settings()
        if not settings.gemini_api_key:
            print("⚠  GEMINI_API_KEY not set — skipping centroid build")
            return

        genai.configure(api_key=settings.gemini_api_key)

        async def embed(text: str):
            import numpy as np
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="SEMANTIC_SIMILARITY",
            )
            return np.array(result["embedding"], dtype=np.float32)

        router = SemanticRouter(embedding_fn=embed)
        await router.build_centroids()
        router.save_centroids("centroids.npy")
        print("✓ Semantic router centroids built and saved")
    except Exception as e:
        print(f"⚠  Centroid build skipped: {e}")


async def main():
    print("Initialising Aura database...")
    await create_tables()
    await build_centroids()
    print("\n✓ Aura is ready. Run: uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
