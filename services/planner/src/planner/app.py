"""FastAPI application factory; dependencies are scoped to this instance."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from planner.api.auth import router as auth_router
from planner.api.errors import install_error_handlers
from planner.api.routes import router as input_router
from planner.db.session import create_db_engine, database_is_ready, migration_heads
from planner.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    engine = create_db_engine(config)
    expected_heads = migration_heads()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="Adaptive Planner", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def private_response_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.state.settings = config
    app.state.engine = engine
    app.state.clock = lambda: datetime.now(UTC)

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"], responses={503: {"description": "Not ready"}})
    def ready() -> JSONResponse:
        is_ready = database_is_ready(engine, expected_heads)
        return JSONResponse(
            {"status": "ready" if is_ready else "not_ready"},
            status_code=200 if is_ready else 503,
        )

    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(input_router)
    return app
