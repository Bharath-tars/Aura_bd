from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import get_settings
from database import engine, Base
from routers import auth, mood, journal, wellness, chat, analytics, streak


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Build semantic router centroids (uses google-genai SDK)
    settings = get_settings()
    if settings.gemini_api_key:
        try:
            import numpy as np
            from google import genai as google_genai
            from agents.semantic_router import SemanticRouter, set_router

            gclient = google_genai.Client(
                api_key=settings.gemini_api_key,
                http_options={"api_version": "v1"},
            )

            async def embed(text: str):
                result = gclient.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                return np.array(result.embeddings[0].values, dtype=np.float32)

            router_instance = SemanticRouter(embedding_fn=embed)
            try:
                router_instance.load_centroids("centroids.npy")
            except FileNotFoundError:
                await router_instance.build_centroids()
                router_instance.save_centroids("centroids.npy")

            app.state.semantic_router = router_instance
            set_router(router_instance)
        except Exception as e:
            print(f"Warning: semantic router not initialised: {e}")

    yield

    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aura — AI Wellness Platform",
        description="Multi-agent AI health and mental wellness companion",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(auth.router, prefix=prefix)
    app.include_router(mood.router, prefix=prefix)
    app.include_router(journal.router, prefix=prefix)
    app.include_router(wellness.router, prefix=prefix)
    app.include_router(chat.router, prefix=prefix)
    app.include_router(analytics.router, prefix=prefix)
    app.include_router(streak.router, prefix=prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "Aura API"}

    @app.exception_handler(Exception)
    async def global_error(_request, _exc):
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "SERVER_ERROR"})

    return app


app = create_app()
