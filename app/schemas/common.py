"""Common response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Root / status response."""

    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
    status: str = Field(..., description="Running status")
    test_mode: bool = Field(..., description="Whether test servers are used")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="healthy or unhealthy")
    telegram_connected: bool = Field(..., description="Whether any Telegram client is connected")
    test_mode: bool = Field(..., description="Whether test servers are used")
    accounts_count: int = Field(0, description="Number of registered accounts")


class AccountInfo(BaseModel):
    """Minimal account info for listing."""

    session_id: str = Field(..., description="Session identifier for this account")
    connected: bool = Field(..., description="Whether client is connected")
