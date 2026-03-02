"""FastAPI application: lifespan, routers, exception handlers."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.logging import setup_logging
from app.core.exceptions import AppError, AuthFlowError, SessionNotFoundError
from app.sessions.manager import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init logging, create SessionManager, load sessions. Shutdown: stop all clients."""
    settings = get_settings()
    setup_logging(settings.log_level)
    manager = SessionManager()
    app.state.session_manager = manager
    try:
        await manager.start_all()
        yield
    finally:
        await manager.stop_all()


app = FastAPI(
    title="Telegram Group Creator API",
    description="API для автоматического создания Telegram групп и регистрации аккаунтов",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,  # не сбрасывать ключ при обновлении страницы
    },
)

# CORS: устраняет "Failed to fetch" при вызове API из браузера (в т.ч. Swagger с file:// или другого порта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message},
    )


@app.exception_handler(AuthFlowError)
async def auth_flow_error_handler(request: Request, exc: AuthFlowError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message},
    )


# Routers (health: no API key; auth & groups: require X-API-Key)
from app.routers import health, auth, groups

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(groups.router)
