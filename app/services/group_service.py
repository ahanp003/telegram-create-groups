"""Group creation business logic (migrated from legacy API)."""

import asyncio
import urllib.request
from io import BytesIO
from typing import Optional

from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import ChatPrivileges
from pyrogram.raw.functions.channels import CreateChannel

from app.schemas.groups import (
    BotAddResult,
    GroupCreationRequest,
    GroupCreationResponse,
    UserAddResult,
    UserInRequest,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class GroupService:
    """Creates Telegram groups and adds bot/users. Requires an active Client."""

    async def create_supergroup(self, client: Client, group_name: str) -> tuple[int, str]:
        """Create a supergroup (megagroup). Returns (chat_id, chat_title)."""
        logger.info("Создание группы '%s'...", group_name)
        result = await client.invoke(
            CreateChannel(
                title=group_name,
                about="Группа создана автоматически через API",
                megagroup=True,
            )
        )
        if not result.chats or len(result.chats) == 0:
            raise Exception("Результат создания группы не содержит информации о чате")

        created_chat = result.chats[0]
        chat_id_raw = created_chat.id
        chat_id = int(f"-100{chat_id_raw}") if chat_id_raw > 0 else chat_id_raw
        await asyncio.sleep(2)

        chat_title = group_name
        try:
            chat = await client.get_chat(chat_id)
            chat_title = chat.title
            logger.info("Группа создана: %s (ID: %s)", chat_title, chat_id)
        except Exception as e:
            logger.warning("Не удалось получить информацию о чате: %s", e)
        return chat_id, chat_title

    async def _set_chat_photo_from_url(
        self, client: Client, chat_id: int, photo_url: str
    ) -> bool:
        """Download image from URL and set as group chat photo. Returns True on success."""
        try:
            def _download() -> bytes:
                req = urllib.request.Request(photo_url, headers={"User-Agent": "TelegramClient/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()

            data = await asyncio.to_thread(_download)
            if not data or len(data) > 10 * 1024 * 1024:  # 10 MB limit
                logger.warning("Фото по URL пустое или слишком большое")
                return False
            buf = BytesIO(data)
            buf.name = "photo.png"
            await client.set_chat_photo(chat_id=chat_id, photo=buf)
            logger.info("Аватар группы установлен из URL: %s", photo_url)
            return True
        except Exception as e:
            logger.warning("Не удалось установить аватар группы из URL %s: %s", photo_url, e)
            return False

    async def create_invite_link(self, client: Client, chat_id: int) -> Optional[str]:
        """Create a permanent invite link for the group."""
        try:
            invite_link = await client.create_chat_invite_link(
                chat_id=chat_id,
                name="API Generated Link",
                creates_join_request=False,
            )
            logger.info("Создана ссылка-приглашение: %s", invite_link.invite_link)
            return invite_link.invite_link
        except Exception as e:
            logger.error("Ошибка при создании ссылки-приглашения: %s", e)
            try:
                chat = await client.get_chat(chat_id)
                if hasattr(chat, "invite_link") and chat.invite_link:
                    return chat.invite_link
            except Exception:
                pass
            return None

    async def add_bot_to_group(
        self, client: Client, chat_id: int, bot_username: str
    ) -> BotAddResult:
        """Add bot to group and promote to admin."""
        result = BotAddResult(username=bot_username, added=False, promoted=False)
        try:
            logger.info("Добавление бота @%s в группу...", bot_username)
            await client.add_chat_members(chat_id, bot_username)
            result.added = True
            logger.info("Бот @%s добавлен в группу", bot_username)
            try:
                privileges = ChatPrivileges(
                    can_invite_users=True,
                    can_change_info=True,
                    can_delete_messages=True,
                    can_restrict_members=True,
                    can_pin_messages=True,
                    can_manage_video_chats=True,
                    can_manage_chat=False,
                    can_post_messages=False,
                    can_edit_messages=False,
                    can_promote_members=False,
                )
                await client.promote_chat_member(
                    chat_id=chat_id, user_id=bot_username, privileges=privileges
                )
                try:
                    await client.set_administrator_title(chat_id, bot_username, "Bot Admin")
                except Exception:
                    pass
                result.promoted = True
                logger.info("Бот @%s назначен администратором", bot_username)
            except Exception as e:
                result.error = f"Ошибка при назначении администратором: {str(e)}"
                logger.error(result.error)
        except Exception as e:
            result.error = f"Ошибка при добавлении бота: {str(e)}"
            logger.error(result.error)
        return result

    async def promote_user_to_full_admin(
        self, client: Client, chat_id: int, username: str
    ) -> bool:
        """Promote user to full admin with all privileges. Returns True on success."""
        try:
            privileges = ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_post_messages=False,
                can_edit_messages=False,
            )
            await client.promote_chat_member(
                chat_id=chat_id, user_id=username, privileges=privileges
            )
            logger.info("Пользователь @%s назначен администратором с полными правами", username)
            return True
        except Exception as e:
            logger.error("Ошибка при назначении @%s администратором: %s", username, e)
            return False

    async def add_user_to_group(
        self, client: Client, chat_id: int, user_spec: UserInRequest
    ) -> UserAddResult:
        """Add user to group; optionally promote to full admin if transfer_ownership=True."""
        username = user_spec.user_name
        result = UserAddResult(username=username, added=False, promoted=False)
        try:
            await client.add_chat_members(chat_id, username)
            result.added = True
            logger.info("Пользователь @%s добавлен в группу", username)
            await asyncio.sleep(2)
            if user_spec.transfer_ownership:
                result.promoted = await self.promote_user_to_full_admin(
                    client, chat_id, username
                )
        except FloodWait as e:
            result.error = f"Rate limit: нужно подождать {e.value} секунд"
            logger.warning(result.error)
            await asyncio.sleep(e.value)
        except Exception as e:
            msg = str(e)
            if "USER_PRIVACY" in msg or "privacy" in msg.lower():
                result.error = "Настройки приватности не позволяют добавить пользователя"
            elif "USER_NOT_MUTUAL_CONTACT" in msg:
                result.error = "Пользователь не в взаимных контактах"
            elif "USER_ALREADY_PARTICIPANT" in msg:
                result.added = True
                result.error = "Пользователь уже в группе"
            else:
                result.error = msg
            logger.error("Ошибка при добавлении @%s: %s", username, result.error)
        return result

    async def leave_group(self, client: Client, chat_id: int) -> bool:
        """Leave the chat."""
        try:
            await client.leave_chat(chat_id)
            logger.info("Успешно вышли из группы")
            return True
        except Exception as e:
            logger.error("Ошибка при выходе из группы: %s", e)
            return False

    async def create_group(
        self, client: Client, request: GroupCreationRequest
    ) -> GroupCreationResponse:
        """Create group with bots and users. Client must be connected."""
        response = GroupCreationResponse(success=False)
        try:
            chat_id, chat_title = await self.create_supergroup(client, request.group_name)
            response.group_id = chat_id
            response.group_name = chat_title
            if request.photo_url:
                await self._set_chat_photo_from_url(client, chat_id, request.photo_url)
            response.invite_link = await self.create_invite_link(client, chat_id)
            bot_results = []
            for bot_username in request.bot_usernames:
                bot_results.append(
                    await self.add_bot_to_group(client, chat_id, bot_username)
                )
            response.bots = bot_results
            response.bot = bot_results[0] if bot_results else None
            user_results = []
            for user_spec in request.users:
                user_results.append(
                    await self.add_user_to_group(client, chat_id, user_spec)
                )
            response.users = user_results
            if request.leave_after:
                await self.leave_group(client, chat_id)
            response.success = True
            if not (
                all(b.added for b in bot_results)
                and all(u.added for u in user_results)
            ):
                logger.warning("Группа создана, но не все участники добавлены")
            else:
                logger.info("Группа успешно создана со всеми участниками")
        except Exception as e:
            response.error = f"Критическая ошибка при создании группы: {str(e)}"
            logger.error(response.error)
        return response
