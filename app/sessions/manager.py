"""Session manager: multi-account Telegram clients and pending auth with TTL."""

import asyncio
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pyrogram import Client

from app.config import get_settings
from app.core.exceptions import SessionNotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)

PENDING_AUTH_TTL_SEC = 300  # 5 minutes
SESSION_LOAD_TIMEOUT_SEC = 20  # не ждать дольше при загрузке (избегаем зависания на "Enter phone")


def normalize_phone(phone: str) -> str:
    """Normalize phone to digits only (for session key and file names)."""
    return re.sub(r"\D", "", phone.strip()) or phone


@dataclass
class PendingAuth:
    """Temporary state for a client waiting for verification code."""

    client: Client
    phone_number: str
    phone_code_hash: str
    created_at: float = field(default_factory=time.monotonic)

    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > PENDING_AUTH_TTL_SEC


class SessionManager:
    """
    Manages multiple Telegram client sessions.
    - active_clients: connected, authorized clients (key = normalized phone, internal)
    - session_id <-> phone mapping for API (persisted in session_ids.json)
    - pending_auth: clients in sign-in flow (key = phone_code_hash / session_id), TTL 5 min
    """

    SESSION_IDS_FILENAME = "session_ids.json"

    def __init__(self) -> None:
        self._active: dict[str, Client] = {}
        self._pending: dict[str, PendingAuth] = {}
        self._session_id_to_phone: dict[str, str] = {}
        self._phone_to_session_id: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._load_session_ids()

    @property
    def settings(self):
        return get_settings()

    def _session_path(self) -> Path:
        path = Path(self.settings.sessions_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _session_ids_file(self) -> Path:
        return self._session_path() / self.SESSION_IDS_FILENAME

    def _load_session_ids(self) -> None:
        """Load phone -> session_id mapping from disk."""
        path = self._session_ids_file()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._phone_to_session_id = {k: str(v) for k, v in data.items()}
                self._session_id_to_phone = {v: k for k, v in self._phone_to_session_id.items()}
        except Exception as e:
            logger.warning("Could not load session_ids.json: %s", e)

    def _save_session_ids(self) -> None:
        """Persist phone -> session_id mapping to disk."""
        path = self._session_ids_file()
        try:
            path.write_text(json.dumps(self._phone_to_session_id, indent=0), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not save session_ids.json: %s", e)

    def _session_name(self, phone: str) -> str:
        return normalize_phone(phone)

    def _remove_session_files(self, name: str) -> None:
        """Удалить файлы сессии по имени (при невалидной/просроченной сессии)."""
        workdir = self._session_path()
        for ext in ("", "-journal"):
            p = workdir / f"{name}.session{ext}"
            if p.exists():
                try:
                    p.unlink()
                    logger.info("Removed invalid session file %s", p.name)
                except OSError as e:
                    logger.warning("Could not remove %s: %s", p, e)

    async def start_all(self) -> None:
        """Load all existing .session files from sessions_dir and start clients.
        Невалидные/просроченные сессии удаляются, чтобы не зависать на запросе ввода.
        """
        workdir = self._session_path()
        session_files = list(workdir.glob("*.session"))
        if not session_files:
            logger.info("No existing sessions found in %s", workdir)
            return

        # Pyrogram при невалидной сессии печатает "Enter phone number..." и вызывает input().
        # На время start() подменяем stdin/stdout на devnull — не блокируем и не засоряем консоль.
        old_stdin, old_stdout = sys.stdin, sys.stdout
        devnull_r = open(os.devnull, encoding="utf-8")
        devnull_w = open(os.devnull, "w", encoding="utf-8")

        for path in session_files:
            name = path.stem
            if not name or name.startswith("."):
                continue
            client = None
            try:
                client = Client(
                    name=name,
                    api_id=self.settings.api_id,
                    api_hash=self.settings.api_hash,
                    workdir=str(workdir),
                    test_mode=self.settings.test_mode,
                    no_updates=True,
                )
                try:
                    sys.stdin, sys.stdout = devnull_r, devnull_w
                    await asyncio.wait_for(client.start(), timeout=SESSION_LOAD_TIMEOUT_SEC)
                finally:
                    sys.stdin, sys.stdout = old_stdin, old_stdout
                me = await client.get_me()
                self._active[name] = client
                if name not in self._phone_to_session_id:
                    session_id = str(uuid.uuid4())
                    self._phone_to_session_id[name] = session_id
                    self._session_id_to_phone[session_id] = name
                    self._save_session_ids()
                logger.info("Loaded session for %s (%s)", me.phone_number or name, me.first_name)
            except asyncio.TimeoutError:
                sys.stdin, sys.stdout = old_stdin, old_stdout
                logger.warning("Session %s: load timeout (removing file to avoid hang on next start)", name)
                self._remove_session_files(name)
                if client and client.is_connected:
                    try:
                        await client.stop()
                    except Exception:
                        pass
            except Exception as e:
                sys.stdin, sys.stdout = old_stdin, old_stdout
                logger.warning("Failed to load session %s: %s (removing invalid session file)", name, e)
                self._remove_session_files(name)
                if client and client.is_connected:
                    try:
                        await client.stop()
                    except Exception:
                        pass
        devnull_r.close()
        devnull_w.close()

        if self.settings.test_mode:
            logger.warning("Test mode is enabled")

    async def stop_all(self) -> None:
        """Disconnect all active and pending clients."""
        async with self._lock:
            for key, client in list(self._active.items()):
                try:
                    if client.is_connected:
                        await client.stop()
                    logger.info("Stopped session %s", key)
                except Exception as e:
                    logger.error("Error stopping session %s: %s", key, e)
            self._active.clear()

            for key, pending in list(self._pending.items()):
                try:
                    if pending.client.is_connected:
                        await pending.client.disconnect()
                    logger.info("Discarded pending auth %s", key)
                except Exception as e:
                    logger.error("Error disconnecting pending %s: %s", key, e)
            self._pending.clear()

    def _clean_expired_pending(self) -> None:
        """Remove expired pending auth entries (caller should hold lock if needed)."""
        expired = [k for k, p in self._pending.items() if p.is_expired()]
        for k in expired:
            self._pending.pop(k, None)
            logger.debug("Removed expired pending auth %s", k)

    async def get_client(self, session_id: str) -> Client:
        """Return active client for the given session_id. Raises SessionNotFoundError if not found."""
        self._clean_expired_pending()
        phone = self._session_id_to_phone.get(session_id)
        if phone is None:
            raise SessionNotFoundError(f"No active session for session_id: {session_id}")
        client = self._active.get(phone)
        if client is None or not client.is_connected:
            raise SessionNotFoundError(f"No active session for session_id: {session_id}")
        return client

    def get_client_sync(self, session_id: str) -> Optional[Client]:
        """Return active client for the given session_id or None (for sync use in same thread)."""
        phone = self._session_id_to_phone.get(session_id)
        if phone is None:
            return None
        return self._active.get(phone)

    def list_accounts(self) -> list[tuple[str, bool]]:
        """Return list of (session_id, connected) for all active sessions."""
        self._clean_expired_pending()
        return [
            (self._phone_to_session_id[phone], c.is_connected)
            for phone, c in self._active.items()
            if phone in self._phone_to_session_id
        ]

    def add_pending(self, phone: str, client: Client, phone_code_hash: str) -> None:
        """Register a client in pending auth (awaiting verification code). Key = phone_code_hash (session_id)."""
        key = phone_code_hash
        self._pending[key] = PendingAuth(
            client=client, phone_number=normalize_phone(phone), phone_code_hash=phone_code_hash
        )
        logger.info("Pending auth added for session_id %s", key)

    def get_pending(self, session_id: str) -> Optional[PendingAuth]:
        """Get pending auth by session_id (phone_code_hash); remove and return None if expired."""
        self._clean_expired_pending()
        pending = self._pending.get(session_id)
        if pending is None or pending.is_expired():
            if pending and pending.is_expired():
                self._pending.pop(session_id, None)
            return None
        return pending

    def pop_pending(self, session_id: str) -> Optional[PendingAuth]:
        """Remove and return pending auth by session_id (phone_code_hash)."""
        return self._pending.pop(session_id, None)

    def add_active(self, phone: str, client: Client) -> str:
        """Register an authorized client as active. Returns session_id for API."""
        key = normalize_phone(phone)
        self._active[key] = client
        if key not in self._phone_to_session_id:
            session_id = str(uuid.uuid4())
            self._phone_to_session_id[key] = session_id
            self._session_id_to_phone[session_id] = key
            self._save_session_ids()
        session_id = self._phone_to_session_id[key]
        logger.info("Active session added for session_id %s", session_id)
        return session_id

    async def remove_account(self, session_id: str) -> bool:
        """Log out and remove session for the given session_id. Returns True if removed."""
        phone = self._session_id_to_phone.pop(session_id, None)
        if phone is None:
            return False
        self._phone_to_session_id.pop(phone, None)
        client = self._active.pop(phone, None)
        if client is None:
            return False
        try:
            await client.log_out()
        except Exception as e:
            logger.warning("log_out failed for session_id %s: %s", session_id, e)
        try:
            if client.is_connected:
                await client.stop()
        except Exception as e:
            logger.warning("stop failed for session_id %s: %s", session_id, e)
        session_path = self._session_path() / f"{phone}.session"
        if session_path.exists():
            try:
                session_path.unlink()
                for ext in (".session-journal",):
                    p = self._session_path() / f"{phone}{ext}"
                    if p.exists():
                        p.unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Could not delete session file %s: %s", session_path, e)
        self._save_session_ids()
        return True
