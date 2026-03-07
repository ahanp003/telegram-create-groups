# Telegram Group Creator API

Профессиональный FastAPI сервис для автоматического создания Telegram групп и управления несколькими аккаунтами.

## Возможности

- Создание супергрупп (мегагрупп) в Telegram
- Автоматическое добавление ботов с правами администратора
- Приглашение пользователей в группу
- Генерация бессрочных ссылок-приглашений
- **Мультиаккаунт** — несколько Telegram-аккаунтов, выбор аккаунта при создании группы
- **Регистрация аккаунтов через API** — send-code → verify-code → (при необходимости) verify-2fa
- Защита API ключом (заголовок `X-API-Key`)
- Поддержка тестовых серверов Telegram
- Продакшн-структура: разнесённые роутеры, сервисы, сессии, конфиг

## Установка

### 1. Зависимости

```bash
pip install -r requirements.txt
```

### 2. Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
API_ID=ваш_api_id          # https://my.telegram.org/apps
API_HASH=ваш_api_hash
API_KEY=секретный_ключ     # для заголовка X-API-Key
TEST_MODE=False
SESSIONS_DIR=sessions_data
HOST=0.0.0.0
PORT=3579
LOG_LEVEL=INFO
```

### 3. Регистрация первого аккаунта

Аккаунты регистрируются через API (интерактивный ввод кода не нужен):

1. **Отправить код на телефон**
   ```http
   POST /api/v1/auth/send-code
   X-API-Key: ваш_api_key
   Content-Type: application/json

   {"phone_number": "+79001234567"}
   ```
   В ответе — `phone_code_hash` и `session_id`.

2. **Ввести код из Telegram**
   ```http
   POST /api/v1/auth/verify-code
   X-API-Key: ваш_api_key
   Content-Type: application/json

   {
     "phone_number": "+79001234567",
     "phone_code_hash": "<из send-code>",
     "code": "12345"
   }
   ```
   Если включена 2FA, в ответе будет `requires_2fa: true`.

3. **При 2FA — отправить пароль**
   ```http
   POST /api/v1/auth/verify-2fa
   X-API-Key: ваш_api_key
   Content-Type: application/json

   {"phone_number": "+79001234567", "password": "ваш_2fa_пароль"}
   ```

После успешной регистрации сессия сохраняется в `sessions_data/`.

## Запуск

```bash
python run.py
```

Сервер: **http://localhost:3579**  
Документация: **http://localhost:3579/docs**

### Доступ с интернета через туннель

#### Localtunnel

1. Установить (нужен Node.js): `npm install -g localtunnel`
2. Запустить приложение: `python run.py`
3. В другом терминале:
   ```bash
   lt --port 3579
   ```
   Если туннель «висит» или не открывается, укажите хост явно:
   ```bash
   lt --port 3579 --host https://server.loca.lt
   ```

**Важно:** при открытии URL в браузере localtunnel показывает страницу «напоминания». Чтобы запросы доходили до вашего API, добавляйте заголовок **`Bypass-Tunnel-Reminder: true`** (в Postman, curl, скриптах):

```bash
# Bash / cmd (на Windows лучше вызвать curl.exe)
curl.exe -H "Bypass-Tunnel-Reminder: true" https://ваш-поддомен.loca.lt/health
```

```powershell
# PowerShell
Invoke-WebRequest -Uri "https://ваш-поддомен.loca.lt/health" -Headers @{"Bypass-Tunnel-Reminder"="true"}
```

Без этого заголовка браузер или клиент получает HTML-страницу localtunnel, а не ответ вашего приложения — из-за этого кажется, что «не загружается».

**Если видите «503 - Tunnel Unavailable»:** туннель оборвался или не запущен. Убедитесь, что в отдельном терминале всё ещё работает `lt --port 3579` (окно не закрыто), приложение `python run.py` слушает порт 3579, затем перезапустите `lt`. Публичные серверы localtunnel часто роняют соединение; для стабильной работы лучше использовать ngrok ниже.

#### Альтернатива: ngrok

Стабильнее для постоянного доступа (нужна бесплатная регистрация на [ngrok.com](https://ngrok.com)):

```bash
ngrok http 3579
```

Публичный URL будет в выводе; страницы-посредника нет, API доступен сразу.

## API (кратко)

Эндпоинты без ключа (для проверки и health-check):

- `GET /` — статус сервиса
- `GET /health` — здоровье (telegram_connected, accounts_count)
- `GET /accounts` — список зарегистрированных аккаунтов (без ключа)

Эндпоинты с заголовком **X-API-Key**:

- `POST /api/v1/auth/send-code` — отправить код на телефон
- `POST /api/v1/auth/verify-code` — подтвердить код
- `POST /api/v1/auth/verify-2fa` — ввести 2FA-пароль
- `GET /api/v1/auth/accounts` — список аккаунтов
- `DELETE /api/v1/auth/accounts/{phone}` — удалить аккаунт
- `POST /api/v1/groups/create` — создать группу (указать `phone_number` аккаунта)

### Создание группы

```http
POST /api/v1/groups/create
X-API-Key: ваш_api_key
Content-Type: application/json
```

```json
{
  "phone_number": "+79001234567",
  "group_name": "Моя новая группа",
  "bot_username": "@test_chat_all_bot",
  "users": [
    {"user_name": "@user1", "transfer_ownership": false},
    {"user_name": "@user2", "transfer_ownership": true}
  ],
  "leave_after": false
}
```

Успешный ответ (201): `success`, `group_id`, `group_name`, `invite_link`, `bot`, `users`, `timestamp`.

## Структура проекта

```
app/
├── main.py           # FastAPI, lifespan, роутеры
├── config.py         # pydantic-settings
├── dependencies.py   # DI (session_manager, auth_service, group_service)
├── core/
│   ├── logging.py
│   ├── security.py   # проверка X-API-Key
│   └── exceptions.py
├── schemas/          # Pydantic (auth, groups, common)
├── routers/          # health, auth, groups
├── services/         # auth_service, group_service
└── sessions/
    └── manager.py    # мультиаккаунт, pending_auth с TTL
run.py                # точка входа (uvicorn)
```

## Безопасность

- Не коммитьте `.session`, `sessions_data/` и `.env`
- API ключ обязателен для `/api/v1/*` (кроме перечисленных выше)
- В продакшене: HTTPS, ограничение доступа по сети, мониторинг

## Ошибки при добавлении пользователей

| Ошибка | Решение |
|--------|---------|
| USER_PRIVACY | Пользователь должен разрешить добавление или добавить вас в контакты |
| USER_NOT_MUTUAL_CONTACT | Добавьте друг друга в контакты |
| USER_ALREADY_PARTICIPANT | Уже в группе (успех) |
| FloodWait | API ждёт и повторяет запрос |

## Тестовые серверы

В `.env`: `TEST_MODE=True`. Сессии тестовых аккаунтов хранятся в том же `sessions_data/` с отдельными именами.

## Стек

- FastAPI, Uvicorn, Pydantic, pydantic-settings
- Pyrogram, TgCrypto
- Python 3.10+
