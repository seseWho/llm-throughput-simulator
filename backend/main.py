from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import router, worker_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop background queue workers with the application."""
    worker_manager.start()
    try:
        yield
    finally:
        await worker_manager.stop()


app = FastAPI(title="llm-load-mvp", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


app.include_router(router)
