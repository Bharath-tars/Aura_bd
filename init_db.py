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
    print("âœ“ Database tables created")


async def build_centroids():
    """Pre-compute semantic router embedding centroids at startup."""
    try:
        from backend.agents.semantic_router import SemanticRouter
        from backend.config import get_settings
        from google import genai as google_genai

        settings = get_settings()
        if not settings.gemini_api_key:
            print("âš   GEMINI_API_KEY not set â€” skipping centroid build")
            return

        gclient = google_genai.Client(api_key=settings.gemini_api_key)

        async def embed(text: str):
            import numpy as np
            result = gclient.models.embed_content(model="models/text-embedding-004", contents=text)
            return np.array(result.embeddings[0].values, dtype=np.float32)

        router = SemanticRouter(embedding_fn=embed)
        await router.build_centroids()
        router.save_centroids("centroids.npy")
        print("âœ“ Semantic router centroids built and saved")
    except Exception as e:
        print(f"âš   Centroid build skipped: {e}")


async def main():
    print("Initialising Aura database...")
    await create_tables()
    await build_centroids()
    print("\nâœ“ Aura is ready. Run: uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(main())

