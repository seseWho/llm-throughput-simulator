from fastapi import FastAPI

from backend.api.routes import router

app = FastAPI(title="llm-load-mvp")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


app.include_router(router)
