"""Custom exceptions for the application."""


class AppError(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class SessionNotFoundError(AppError):
    """Raised when no session exists for the given phone number."""

    pass


class AuthFlowError(AppError):
    """Raised when authentication flow fails (invalid code, expired hash, etc.)."""

    pass


class TelegramError(AppError):
    """Raised when a Telegram API operation fails."""

    pass
