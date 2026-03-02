"""FastAPI dependency injection."""

from fastapi import Request

from app.sessions.manager import SessionManager
from app.services.auth_service import AuthService
from app.services.group_service import GroupService


def get_session_manager(request: Request) -> SessionManager:
    """Return the session manager from app state (set in lifespan)."""
    return request.app.state.session_manager


def get_auth_service(request: Request) -> AuthService:
    """Return AuthService using session manager from app state."""
    return AuthService(request.app.state.session_manager)


def get_group_service() -> GroupService:
    """Return GroupService (stateless)."""
    return GroupService()
