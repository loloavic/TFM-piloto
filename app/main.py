from contextlib import asynccontextmanager

from app.core.config import settings

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.routes import rag, router


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    rag.sessions.start(settings.session_cleanup_interval_seconds)
    try:
        yield
    finally:
        rag.sessions.close()


app = FastAPI(
    lifespan=lifespan,
    title="Asistente Consular DNI",
    description="API del piloto experimental del TFM",
    version="0.1.0",
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "Asistente Consular DNI",
        "status": "operativo",
    }


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        service="asistente-consular-dni",
        version="0.1.0",
    )
