# Telegram Group Creator API

🚀 Профессиональный FastAPI сервис для автоматического создания Telegram групп с ботами и пользователями.

## 📋 Возможности

- ✅ Создание супергрупп (мегагрупп) в Telegram
- ✅ Автоматическое добавление ботов с правами администратора
- ✅ Приглашение пользователей в группу
- ✅ Генерация бессрочных ссылок-приглашений
- ✅ Поддержка тестовых серверов Telegram
- ✅ Детальные отчеты о результатах
- ✅ Полная типизация и валидация данных
- ✅ Профессиональное логирование

## 🛠️ Установка

### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

### 2. Настройте переменные окружения

Создайте файл `.env`:

```env
API_ID=ваш_api_id
API_HASH=ваш_api_hash
PHONE_NUMBER=ваш_номер_телефона
TEST_MODE=False  # True для тестовых серверов
```

### 3. Первый запуск (авторизация)

При первом запуске потребуется ввести код подтверждения из Telegram:

```bash
python telegram_group_creator_api.py
```

После успешной авторизации сессия сохранится, и код больше не потребуется.

## 🚀 Запуск

```bash
python telegram_group_creator_api.py
```

Сервер запустится на: **http://localhost:3579**

## 📚 Документация API

После запуска сервера документация доступна по адресам:

- **Swagger UI**: http://localhost:3579/docs
- **ReDoc**: http://localhost:3579/redoc

## 🔌 API Эндпоинты

### 1. Проверка работы сервиса

```http
GET /
```

**Ответ:**
```json
{
  "service": "Telegram Group Creator API",
  "version": "1.0.0",
  "status": "running",
  "test_mode": false
}
```

### 2. Проверка здоровья

```http
GET /health
```

**Ответ:**
```json
{
  "status": "healthy",
  "telegram_connected": true,
  "test_mode": false
}
```

### 3. Создание группы

```http
POST /api/v1/create-group
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "group_name": "Моя новая группа",
  "bot_username": "@test_chat_all_bot",
  "users": ["@meteor2000", "@user2"],
  "leave_after": false
}
```

**Успешный ответ (201 Created):**
```json
{
  "success": true,
  "group_id": -1002200104615,
  "group_name": "Моя новая группа",
  "invite_link": "https://t.me/+AbCdEfGhIjKlMnO",
  "bot": {
    "username": "test_chat_all_bot",
    "added": true,
    "promoted": true,
    "error": null
  },
  "users": [
    {
      "username": "meteor2000",
      "added": true,
      "error": null
    }
  ],
  "error": null,
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

**Ответ при ошибке (500):**
```json
{
  "success": false,
  "group_id": null,
  "group_name": null,
  "invite_link": null,
  "bot": null,
  "users": [],
  "error": "Описание ошибки",
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

## 📝 Примеры использования

### Python (requests)

```python
import requests

url = "http://localhost:3579/api/v1/create-group"
data = {
    "group_name": "Test Group",
    "bot_username": "@my_bot",
    "users": ["@user1", "@user2"],
    "leave_after": False
}

response = requests.post(url, json=data)
result = response.json()

print(f"Группа создана: {result['success']}")
print(f"Ссылка-приглашение: {result['invite_link']}")
```

### cURL

```bash
curl -X POST "http://localhost:3579/api/v1/create-group" \
  -H "Content-Type: application/json" \
  -d '{
    "group_name": "Test Group",
    "bot_username": "@my_bot",
    "users": ["@user1", "@user2"],
    "leave_after": false
  }'
```

### JavaScript (fetch)

```javascript
const response = await fetch('http://localhost:3579/api/v1/create-group', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    group_name: 'Test Group',
    bot_username: '@my_bot',
    users: ['@user1', '@user2'],
    leave_after: false
  })
});

const result = await response.json();
console.log('Ссылка-приглашение:', result.invite_link);
```

## 🔒 Безопасность

### ⚠️ ВАЖНО!

1. **Никогда не коммитьте** файлы `.session` в git
2. **Храните в секрете** файл `.env` с API ключами
3. **Не публикуйте** API на публичных серверах без аутентификации
4. **Ограничьте доступ** к API (используйте firewall, VPN, API keys)

### Рекомендации для продакшена

1. Добавьте аутентификацию (API keys, JWT tokens)
2. Используйте HTTPS
3. Настройте rate limiting
4. Используйте Gunicorn вместо Uvicorn
5. Настройте мониторинг и алерты
6. Используйте Docker для изоляции

## 🐛 Обработка ошибок

API возвращает детальную информацию об ошибках:

### Типичные ошибки при добавлении пользователей:

| Ошибка | Описание | Решение |
|--------|----------|---------|
| `USER_PRIVACY` | Настройки приватности пользователя | Пользователь должен изменить настройки или добавить вас в контакты |
| `USER_NOT_MUTUAL_CONTACT` | Не во взаимных контактах | Добавьте друг друга в контакты |
| `USER_ALREADY_PARTICIPANT` | Уже в группе | Не является ошибкой, пользователь уже добавлен |
| `FloodWait` | Rate limit | API автоматически ждет и повторяет запрос |

## 📊 Логирование

Все операции логируются в консоль с timestamp и уровнем важности:

```
2024-01-01 12:00:00 - __main__ - INFO - ✅ Подключение к Telegram успешно!
2024-01-01 12:00:01 - __main__ - INFO - Создание группы 'Test Group'...
2024-01-01 12:00:03 - __main__ - INFO - ✅ Группа создана: Test Group (ID: -1002200104615)
```

## 🧪 Тестовые серверы

Для тестирования установите в `.env`:

```env
TEST_MODE=True
```

**Важно:** На тестовых серверах создается отдельная сессия (`session_name_test.session`), не влияющая на продакшн.

## 🏗️ Архитектура

```
telegram_group_creator_api.py
├── Models (Pydantic)
│   ├── GroupCreationRequest
│   ├── GroupCreationResponse
│   ├── BotAddResult
│   └── UserAddResult
├── Business Logic
│   ├── create_supergroup()
│   ├── create_invite_link()
│   ├── add_bot_to_group()
│   ├── add_user_to_group()
│   └── create_telegram_group()
└── API Endpoints (FastAPI)
    ├── GET /
    ├── GET /health
    └── POST /api/v1/create-group
```

## 🔧 Технологический стек

- **FastAPI** - Современный, быстрый веб-фреймворк
- **Pyrogram** - Элегантная библиотека для Telegram API
- **Pydantic** - Валидация данных и типизация
- **Uvicorn** - ASGI сервер
- **Python 3.10+** - Современный Python с type hints

## 📄 Лицензия

Проект использует библиотеки с открытым исходным кодом:
- Pyrogram: LGPL-3.0
- FastAPI: MIT


