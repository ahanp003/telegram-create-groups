"""Auth service: send_code, verify_code, verify_2fa using Pyrogram low-level API."""

import asyncio

from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

from app.schemas.auth import (
    AccountInfoResponse,
    SendCodeResponse,
    VerifyCodeResponse,
    Verify2FAResponse,
)
from app.sessions.manager import SessionManager, normalize_phone
from app.core.exceptions import AuthFlowError
from app.core.logging import get_logger

logger = get_logger(__name__)

SEND_CODE_TIMEOUT_SEC = 30  # не зависать при долгом ответе Telegram


def _user_to_account_info(session_id: str, user) -> AccountInfoResponse:
    return AccountInfoResponse(
        session_id=session_id,
        user_id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name,
        username=user.username,
    )


class AuthService:
    """Handles Telegram account registration (send code, verify code, 2FA)."""

    def __init__(self, manager: SessionManager) -> None:
        self.manager = manager
        self.settings = manager.settings

    async def send_code(self, phone_number: str) -> SendCodeResponse:
        """
        Send verification code to the phone. Puts a temporary client in pending_auth.
        Caller must call verify_code with the code received in Telegram.
        """
        key = normalize_phone(phone_number)
        workdir = self.manager._session_path()
        session_name = self.manager._session_name(phone_number)

        client = Client(
            name=session_name,
            api_id=self.settings.api_id,
            api_hash=self.settings.api_hash,
            workdir=str(workdir),
            test_mode=self.settings.test_mode,
            no_updates=True,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=SEND_CODE_TIMEOUT_SEC)
            sent = await asyncio.wait_for(
                client.send_code(phone_number), timeout=SEND_CODE_TIMEOUT_SEC
            )
            phone_code_hash = sent.phone_code_hash
        except asyncio.TimeoutError:
            if client.is_connected:
                await client.disconnect()
            logger.warning("send_code timeout for %s", key)
            raise AuthFlowError(
                "Telegram did not respond in time. Check network and try again."
            ) from None
        except Exception as e:
            if client.is_connected:
                await client.disconnect()
            logger.warning("send_code failed for %s: %s", key, e)
            raise AuthFlowError(f"Failed to send code: {e}") from e

        self.manager.add_pending(phone_number, client, phone_code_hash)
        return SendCodeResponse(
            success=True,
            session_id=phone_code_hash,
            message="Code sent. Use verify-code with the code from Telegram.",
        )

    async def verify_code(self, session_id: str, code: str) -> VerifyCodeResponse:
        """
        Verify the code. On success moves client to active. If 2FA is required,
        returns requires_2fa=True and leaves client in pending for verify_2fa.
        """
        pending = self.manager.get_pending(session_id)
        if pending is None:
            raise AuthFlowError(
                "No pending auth for this session_id or session expired (code valid 5 min). "
                "Call send-code first and use the session_id from the response in verify-code."
            )

        phone_number = pending.phone_number
        client = pending.client
        try:
            user = await client.sign_in(phone_number, pending.phone_code_hash, code)
        except SessionPasswordNeeded:
            return VerifyCodeResponse(
                success=False,
                requires_2fa=True,
                account=None,
                error="Two-factor authentication required. Call verify-2fa with your password.",
            )
        except Exception as e:
            logger.warning("sign_in failed for session_id %s: %s", session_id, e)
            raise AuthFlowError(f"Verification failed: {e}") from e

        self.manager.pop_pending(session_id)
        active_session_id = self.manager.add_active(phone_number, client)
        return VerifyCodeResponse(
            success=True,
            requires_2fa=False,
            account=_user_to_account_info(active_session_id, user),
            error=None,
        )

    async def verify_2fa(self, session_id: str, password: str) -> Verify2FAResponse:
        """Complete 2FA. Uses the pending client from the previous verify_code (requires_2fa)."""
        pending = self.manager.get_pending(session_id)
        if pending is None:
            raise AuthFlowError(
                "No pending auth for this session_id or session expired. Complete send-code and verify-code first."
            )

        phone_number = pending.phone_number
        client = pending.client
        try:
            user = await client.check_password(password)
        except Exception as e:
            logger.warning("check_password failed for session_id %s: %s", session_id, e)
            return Verify2FAResponse(
                success=False,
                account=None,
                error=f"Invalid 2FA password or error: {e}",
            )

        self.manager.pop_pending(session_id)
        active_session_id = self.manager.add_active(phone_number, client)
        return Verify2FAResponse(
            success=True,
            account=_user_to_account_info(active_session_id, user),
            error=None,
        )
