"""Auth / registration request and response schemas."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import AccountInfo


def _normalize_phone(v: str) -> str:
    """Normalize phone number: digits only, optional + prefix."""
    s = "".join(c for c in v if c.isdigit() or c == "+")
    return s.strip() or v


class SendCodeRequest(BaseModel):
    """Request to send verification code to phone."""

    phone_number: str = Field(..., min_length=10, description="Phone number in international format")

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class SendCodeResponse(BaseModel):
    """Response after sending code: use session_id in verify-code and verify-2fa."""

    success: bool = Field(..., description="Whether code was sent")
    session_id: str = Field(..., description="Identifier for verify-code and verify-2fa")
    message: Optional[str] = Field(None, description="Optional message")


class VerifyCodeRequest(BaseModel):
    """Request to verify code received in Telegram."""

    session_id: str = Field(..., description="From send-code response")
    code: str = Field(..., min_length=5, max_length=6, description="Verification code from Telegram")


class AccountInfoResponse(BaseModel):
    """Account info after successful login."""

    session_id: str = Field(..., description="Session identifier for subsequent API calls")
    user_id: int = Field(..., description="Telegram user ID")
    first_name: str = Field(..., description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    username: Optional[str] = Field(None, description="Username")


class VerifyCodeResponse(BaseModel):
    """Response after verifying code."""

    success: bool = Field(..., description="Whether login succeeded")
    requires_2fa: bool = Field(False, description="If true, caller must call verify-2fa")
    account: Optional[AccountInfoResponse] = Field(None, description="Account info when success")
    error: Optional[str] = Field(None, description="Error message")


class Verify2FARequest(BaseModel):
    """Request to complete 2FA (password)."""

    session_id: str = Field(..., description="From send-code response (same as used in verify-code)")
    password: str = Field(..., min_length=1, description="2FA password")


class Verify2FAResponse(BaseModel):
    """Response after 2FA verification."""

    success: bool = Field(..., description="Whether login succeeded")
    account: Optional[AccountInfoResponse] = Field(None, description="Account info when success")
    error: Optional[str] = Field(None, description="Error message")


class AccountsListResponse(BaseModel):
    """List of registered accounts."""

    accounts: list[AccountInfo] = Field(default_factory=list)
