"""API key verification for protected endpoints."""

from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

# Схема для Swagger UI: появляется кнопка "Authorize" и поле для ввода ключа
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    scheme_name="API Key",
    description="Введите API key из .env (передаётся в заголовке X-API-Key)",
)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> None:
    """Проверяет заголовок X-API-Key. В Swagger UI: нажмите Authorize и введите ключ."""
    settings = get_settings()
    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
