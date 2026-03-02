"""Health and status endpoints (no API key required)."""

from fastapi import APIRouter, Request

from app.schemas.common import AccountInfo, HealthResponse, StatusResponse

router = APIRouter(tags=["health"])


@router.get("/", response_model=StatusResponse)
async def root() -> StatusResponse:
    """Root endpoint: service name and status."""
    from app.config import get_settings
    settings = get_settings()
    return StatusResponse(
        service="Telegram Group Creator API",
        version="1.0.0",
        status="running",
        test_mode=settings.test_mode,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check: telegram connectivity and accounts count."""
    from app.config import get_settings
    from app.sessions.manager import SessionManager
    settings = get_settings()
    manager: SessionManager = request.app.state.session_manager
    accounts = manager.list_accounts()
    any_connected = any(connected for _, connected in accounts)
    return HealthResponse(
        status="healthy" if any_connected else "unhealthy",
        telegram_connected=any_connected,
        test_mode=settings.test_mode,
        accounts_count=len(accounts),
    )


@router.get("/accounts", response_model=list[AccountInfo])
async def list_accounts(request: Request) -> list[AccountInfo]:
    """List registered accounts (session_id and connected status). No API key."""
    from app.sessions.manager import SessionManager
    manager: SessionManager = request.app.state.session_manager
    accounts = manager.list_accounts()
    return [AccountInfo(session_id=session_id, connected=connected) for session_id, connected in accounts]
