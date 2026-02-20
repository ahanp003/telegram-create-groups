"""
Telegram Group Creator API

FastAPI сервис для автоматического создания Telegram групп с добавлением ботов и пользователей.
Поддерживает тестовые и продакшн серверы Telegram.
"""

import os
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import ChatPrivileges
from pyrogram.raw.functions.channels import CreateChannel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() == 'true'

# Глобальный Telegram клиент
telegram_client: Optional[Client] = None


# ============================================================================
# Pydantic Models
# ============================================================================

class UserAddResult(BaseModel):
    """Результат добавления пользователя в группу"""
    username: str = Field(..., description="Username пользователя")
    added: bool = Field(..., description="Успешно ли добавлен пользователь")
    error: Optional[str] = Field(None, description="Ошибка при добавлении")


class BotAddResult(BaseModel):
    """Результат добавления бота в группу"""
    username: str = Field(..., description="Username бота")
    added: bool = Field(..., description="Успешно ли добавлен бот")
    promoted: bool = Field(False, description="Назначен ли администратором")
    error: Optional[str] = Field(None, description="Ошибка при добавлении")


class GroupCreationRequest(BaseModel):
    """Запрос на создание группы"""
    group_name: str = Field(..., min_length=1, max_length=255, description="Название группы")
    bot_username: str = Field(..., description="Username бота (с @ или без)")
    users: List[str] = Field(default_factory=list, description="Список username пользователей")
    leave_after: bool = Field(False, description="Выйти из группы после создания")
    
    @field_validator('bot_username')
    @classmethod
    def validate_bot_username(cls, v: str) -> str:
        """Валидация username бота"""
        if not v:
            raise ValueError("Bot username не может быть пустым")
        return v.lstrip('@')
    
    @field_validator('users')
    @classmethod
    def validate_users(cls, v: List[str]) -> List[str]:
        """Валидация списка пользователей"""
        return [user.lstrip('@') for user in v if user]
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "group_name": "Моя новая группа",
                "bot_username": "@test_chat_all_bot",
                "users": ["@meteor2000"],
                "leave_after": False
            }
        }
    }


class GroupCreationResponse(BaseModel):
    """Ответ на создание группы"""
    success: bool = Field(..., description="Успешно ли создана группа")
    group_id: Optional[int] = Field(None, description="ID созданной группы")
    group_name: Optional[str] = Field(None, description="Название группы")
    invite_link: Optional[str] = Field(None, description="Бессрочная ссылка-приглашение")
    bot: Optional[BotAddResult] = Field(None, description="Результат добавления бота")
    users: List[UserAddResult] = Field(default_factory=list, description="Результаты добавления пользователей")
    error: Optional[str] = Field(None, description="Общая ошибка")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время создания")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "group_id": -1002200104615,
                "group_name": "Моя новая группа",
                "invite_link": "https://t.me/+AbCdEfGhIjKlMnO",
                "bot": {
                    "username": "test_chat_all_bot",
                    "added": True,
                    "promoted": True,
                    "error": None
                },
                "users": [
                    {
                        "username": "meteor2000",
                        "added": True,
                        "error": None
                    }
                ],
                "error": None,
                "timestamp": "2024-01-01T12:00:00"
            }
        }
    }


# ============================================================================
# Telegram Client Management
# ============================================================================

async def initialize_telegram_client() -> Client:
    """
    Инициализирует и запускает Telegram клиент.
    
    Returns:
        Инициализированный Telegram клиент
        
    Raises:
        Exception: При ошибке инициализации
    """
    session_name = "session_name_test" if TEST_MODE else "session_name"
    
    client = Client(
        session_name,
        api_id=int(API_ID) if API_ID else None,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        test_mode=TEST_MODE,
        workdir=".",
        no_updates=True
    )
    
    logger.info("Инициализация Telegram клиента...")
    if TEST_MODE:
        logger.warning("⚠️  Режим тестовых серверов включен")
    
    await client.start()
    me = await client.get_me()
    logger.info(f"✅ Подключение к Telegram успешно! Пользователь: {me.first_name}")
    
    return client


async def stop_telegram_client(client: Client) -> None:
    """
    Останавливает Telegram клиент.
    
    Args:
        client: Telegram клиент для остановки
    """
    if client and client.is_connected:
        await client.stop()
        logger.info("Telegram клиент остановлен")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Инициализирует и останавливает Telegram клиент.
    """
    global telegram_client
    
    # Startup
    try:
        telegram_client = await initialize_telegram_client()
        logger.info("FastAPI приложение запущено")
        yield
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")
        raise
    finally:
        # Shutdown
        if telegram_client:
            await stop_telegram_client(telegram_client)
        logger.info("FastAPI приложение остановлено")


# ============================================================================
# Core Business Logic
# ============================================================================

async def create_supergroup(
    client: Client,
    group_name: str
) -> tuple[int, str]:
    """
    Создает супергруппу (мегагруппу) в Telegram.
    
    Args:
        client: Telegram клиент
        group_name: Название группы
        
    Returns:
        Tuple (chat_id, chat_title)
        
    Raises:
        Exception: При ошибке создания группы
    """
    logger.info(f"Создание группы '{group_name}'...")
    
    result = await client.invoke(
        CreateChannel(
            title=group_name,
            about="Группа создана автоматически через API",
            megagroup=True
        )
    )
    
    if not result.chats or len(result.chats) == 0:
        raise Exception("Результат создания группы не содержит информации о чате")
    
    created_chat = result.chats[0]
    chat_id_raw = created_chat.id
    
    # Для супергрупп используется формат: -100{chat_id}
    chat_id = int(f"-100{chat_id_raw}") if chat_id_raw > 0 else chat_id_raw
    
    # Задержка для обработки Telegram
    await asyncio.sleep(2)
    
    # Получение информации о чате
    chat_title = group_name
    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
        logger.info(f"✅ Группа создана: {chat_title} (ID: {chat_id})")
    except Exception as e:
        logger.warning(f"Не удалось получить информацию о чате: {e}")
        logger.info(f"✅ Группа создана: {chat_title} (ID: {chat_id})")
    
    return chat_id, chat_title


async def create_invite_link(
    client: Client,
    chat_id: int
) -> Optional[str]:
    """
    Создает бессрочную ссылку-приглашение для группы.
    
    Args:
        client: Telegram клиент
        chat_id: ID группы
        
    Returns:
        Ссылка-приглашение или None при ошибке
    """
    try:
        # Создаем бессрочную ссылку без ограничений
        invite_link = await client.create_chat_invite_link(
            chat_id=chat_id,
            name="API Generated Link",
            creates_join_request=False  # Прямое вступление без запроса
        )
        logger.info(f"✅ Создана ссылка-приглашение: {invite_link.invite_link}")
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Ошибка при создании ссылки-приглашения: {e}")
        # Пытаемся получить основную ссылку группы
        try:
            chat = await client.get_chat(chat_id)
            if hasattr(chat, 'invite_link') and chat.invite_link:
                return chat.invite_link
        except:
            pass
        return None


async def add_bot_to_group(
    client: Client,
    chat_id: int,
    bot_username: str
) -> BotAddResult:
    """
    Добавляет бота в группу и назначает его администратором.
    
    Args:
        client: Telegram клиент
        chat_id: ID группы
        bot_username: Username бота (без @)
        
    Returns:
        Результат добавления бота
    """
    result = BotAddResult(username=bot_username, added=False, promoted=False)
    
    try:
        # Добавление бота
        logger.info(f"Добавление бота @{bot_username} в группу...")
        await client.add_chat_members(chat_id, bot_username)
        result.added = True
        logger.info(f"✅ Бот @{bot_username} добавлен в группу")
        
        # Назначение администратором
        try:
            logger.info(f"Назначение бота @{bot_username} администратором...")
            
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
                can_promote_members=False
            )
            
            await client.promote_chat_member(
                chat_id=chat_id,
                user_id=bot_username,
                privileges=privileges
            )
            
            # Установка титула
            try:
                await client.set_administrator_title(chat_id, bot_username, "Bot Admin")
            except Exception:
                pass
            
            result.promoted = True
            logger.info(f"✅ Бот @{bot_username} назначен администратором")
            
        except Exception as e:
            error_msg = f"Ошибка при назначении администратором: {str(e)}"
            logger.error(error_msg)
            result.error = error_msg
            
    except Exception as e:
        error_msg = f"Ошибка при добавлении бота: {str(e)}"
        logger.error(error_msg)
        result.error = error_msg
    
    return result


async def add_user_to_group(
    client: Client,
    chat_id: int,
    username: str
) -> UserAddResult:
    """
    Добавляет пользователя в группу.
    
    Args:
        client: Telegram клиент
        chat_id: ID группы
        username: Username пользователя (без @)
        
    Returns:
        Результат добавления пользователя
    """
    result = UserAddResult(username=username, added=False)
    
    try:
        await client.add_chat_members(chat_id, username)
        result.added = True
        logger.info(f"✅ Пользователь @{username} добавлен в группу")
        
        # Небольшая задержка для избежания rate-limit
        await asyncio.sleep(2)
        
    except FloodWait as e:
        wait_time = e.value
        error_msg = f"Rate limit: нужно подождать {wait_time} секунд"
        logger.warning(error_msg)
        result.error = error_msg
        await asyncio.sleep(wait_time)
        
    except Exception as e:
        error_msg = str(e)
        
        # Детальная обработка ошибок
        if "USER_PRIVACY" in error_msg or "privacy" in error_msg.lower():
            result.error = "Настройки приватности не позволяют добавить пользователя"
        elif "USER_NOT_MUTUAL_CONTACT" in error_msg:
            result.error = "Пользователь не в взаимных контактах"
        elif "USER_ALREADY_PARTICIPANT" in error_msg:
            result.added = True
            result.error = "Пользователь уже в группе"
        else:
            result.error = error_msg
        
        logger.error(f"❌ Ошибка при добавлении @{username}: {result.error}")
    
    return result


async def leave_group(
    client: Client,
    chat_id: int
) -> bool:
    """
    Выходит из группы.
    
    Args:
        client: Telegram клиент
        chat_id: ID группы
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        await client.leave_chat(chat_id)
        logger.info("✅ Успешно вышли из группы")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выходе из группы: {e}")
        return False


async def create_telegram_group(
    request: GroupCreationRequest
) -> GroupCreationResponse:
    """
    Главная функция создания группы со всеми участниками.
    
    Args:
        request: Запрос на создание группы
        
    Returns:
        Результат создания группы
        
    Raises:
        Exception: При критических ошибках
    """
    if not telegram_client or not telegram_client.is_connected:
        raise Exception("Telegram клиент не инициализирован")
    
    response = GroupCreationResponse(success=False)
    
    try:
        # 1. Создание группы
        chat_id, chat_title = await create_supergroup(
            telegram_client,
            request.group_name
        )
        response.group_id = chat_id
        response.group_name = chat_title
        
        # 2. Создание ссылки-приглашения
        invite_link = await create_invite_link(telegram_client, chat_id)
        response.invite_link = invite_link
        
        # 3. Добавление бота
        bot_result = await add_bot_to_group(
            telegram_client,
            chat_id,
            request.bot_username
        )
        response.bot = bot_result
        
        # 4. Добавление пользователей
        user_results = []
        for username in request.users:
            user_result = await add_user_to_group(
                telegram_client,
                chat_id,
                username
            )
            user_results.append(user_result)
        response.users = user_results
        
        # 5. Выход из группы (если требуется)
        if request.leave_after:
            await leave_group(telegram_client, chat_id)
        
        # Проверка успешности
        all_added = (
            bot_result.added and
            all(user.added for user in user_results)
        )
        
        response.success = True
        
        if not all_added:
            logger.warning("⚠️  Группа создана, но не все участники добавлены")
        else:
            logger.info("🎉 Группа успешно создана со всеми участниками!")
        
    except Exception as e:
        error_msg = f"Критическая ошибка при создании группы: {str(e)}"
        logger.error(error_msg)
        response.error = error_msg
        response.success = False
    
    return response


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Telegram Group Creator API",
    description="API для автоматического создания Telegram групп с добавлением ботов и пользователей",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работы API"""
    return {
        "service": "Telegram Group Creator API",
        "version": "1.0.0",
        "status": "running",
        "test_mode": TEST_MODE
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    client_connected = telegram_client and telegram_client.is_connected
    
    return {
        "status": "healthy" if client_connected else "unhealthy",
        "telegram_connected": client_connected,
        "test_mode": TEST_MODE
    }


@app.post(
    "/api/v1/create-group",
    response_model=GroupCreationResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_group_endpoint(request: GroupCreationRequest) -> GroupCreationResponse:
    """
    Создает Telegram группу с ботом и пользователями.
    
    - Создает супергруппу с указанным названием
    - Добавляет бота и назначает его администратором
    - Добавляет указанных пользователей
    - Создает бессрочную ссылку-приглашение
    - Опционально выходит из группы после создания
    
    Returns:
        Результат создания группы с деталями о добавленных участниках
    """
    try:
        logger.info(f"Получен запрос на создание группы: {request.group_name}")
        response = await create_telegram_group(request)
        
        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=response.error or "Неизвестная ошибка при создании группы"
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Проверка наличия необходимых переменных окружения
    if not API_ID or not API_HASH:
        logger.error("❌ API_ID и API_HASH должны быть установлены в .env файле")
        exit(1)
    
    logger.info("🚀 Запуск Telegram Group Creator API...")
    logger.info(f"📡 Сервер будет доступен на http://localhost:3579")
    logger.info(f"📚 Документация API: http://localhost:3579/docs")
    
    uvicorn.run(
        "telegram_group_creator_api:app",
        host="0.0.0.0",
        port=3579,
        reload=True,
        log_level="info"
    )

