"""Auth endpoints: send-code, verify-code, verify-2fa, accounts list, delete account."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.security import verify_api_key
from app.core.exceptions import AuthFlowError
from app.dependencies import get_auth_service, get_session_manager
from app.schemas.auth import (
    AccountsListResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
    Verify2FARequest,
    Verify2FAResponse,
)
from app.schemas.common import AccountInfo
from app.sessions.manager import SessionManager
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(verify_api_key)])


@router.post("/send-code", response_model=SendCodeResponse)
async def send_code(
    body: SendCodeRequest,
    auth: AuthService = Depends(get_auth_service),
) -> SendCodeResponse:
    """Send verification code to phone. Use session_id in verify-code."""
    try:
        return await auth.send_code(body.phone_number)
    except AuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(
    body: VerifyCodeRequest,
    auth: AuthService = Depends(get_auth_service),
) -> VerifyCodeResponse:
    """Verify code from Telegram. If requires_2fa, call verify-2fa next."""
    try:
        return await auth.verify_code(body.session_id, body.code)
    except AuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/verify-2fa", response_model=Verify2FAResponse)
async def verify_2fa(
    body: Verify2FARequest,
    auth: AuthService = Depends(get_auth_service),
) -> Verify2FAResponse:
    """Complete 2FA with password (after verify-code returned requires_2fa)."""
    try:
        return await auth.verify_2fa(body.session_id, body.password)
    except AuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get("/accounts", response_model=AccountsListResponse)
async def list_accounts(manager: SessionManager = Depends(get_session_manager)) -> AccountsListResponse:
    """List registered Telegram accounts."""
    accounts = manager.list_accounts()
    return AccountsListResponse(
        accounts=[AccountInfo(session_id=session_id, connected=connected) for session_id, connected in accounts]
    )


@router.delete("/accounts/{session_id:path}")
async def delete_account(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """Remove account: logout and delete session file."""
    removed = await manager.remove_account(session_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {"success": True, "message": "Account removed"}
