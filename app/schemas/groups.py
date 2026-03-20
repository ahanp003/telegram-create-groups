"""Group creation request and response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class UserInRequest(BaseModel):
    """User to add to the group, with optional full admin promotion."""

    user_name: str = Field(..., description="Username (with or without @)")
    transfer_ownership: bool = Field(
        False, description="Promote user to full admin with all privileges"
    )

    @field_validator("user_name")
    @classmethod
    def validate_user_name(cls, v: str) -> str:
        if not v:
            raise ValueError("User name cannot be empty")
        return v.lstrip("@")


class UserAddResult(BaseModel):
    """Result of adding a user to the group."""

    username: str = Field(..., description="Username")
    added: bool = Field(..., description="Whether user was added")
    promoted: bool = Field(False, description="Whether user was promoted to full admin")
    error: Optional[str] = Field(None, description="Error if any")


class BotAddResult(BaseModel):
    """Result of adding a bot to the group."""

    username: str = Field(..., description="Bot username")
    added: bool = Field(..., description="Whether bot was added")
    promoted: bool = Field(False, description="Whether bot was promoted to admin")
    error: Optional[str] = Field(None, description="Error if any")


class GroupCreationRequest(BaseModel):
    """Request to create a group."""

    session_id: str = Field(..., description="Which account to use (session_id from auth)")
    group_name: str = Field(..., min_length=1, max_length=255, description="Group name")
    bot_username: Optional[str] = Field(
        None,
        description="Legacy single bot username (with or without @). "
        "Use bot_usernames for multiple bots.",
    )
    bot_usernames: List[str] = Field(
        default_factory=list,
        description="List of bot usernames (with or without @)",
    )
    users: List[UserInRequest] = Field(
        default_factory=list, description="List of users to add (with optional transfer_ownership)"
    )
    leave_after: bool = Field(False, description="Leave group after creation")
    photo_url: Optional[str] = Field(
        None,
        description="URL of image to set as group avatar (e.g. https://example.com/image.png)",
    )

    @staticmethod
    def _normalize_username(value: str, field_name: str) -> str:
        value = value.strip().lstrip("@")
        if not value:
            raise ValueError(f"{field_name} cannot be empty")
        return value

    @field_validator("bot_username")
    @classmethod
    def validate_bot_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return cls._normalize_username(v, "Bot username")

    @field_validator("bot_usernames")
    @classmethod
    def validate_bot_usernames(cls, values: List[str]) -> List[str]:
        return [cls._normalize_username(v, "Bot username") for v in values]

    @model_validator(mode="after")
    def normalize_bots(self) -> "GroupCreationRequest":
        combined = [*self.bot_usernames]
        if self.bot_username:
            combined.append(self.bot_username)

        unique: list[str] = []
        seen: set[str] = set()
        for username in combined:
            if username not in seen:
                seen.add(username)
                unique.append(username)

        if not unique:
            raise ValueError("At least one bot username is required")

        self.bot_usernames = unique
        self.bot_username = unique[0]
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "group_name": "My New Group",
                "bot_usernames": ["@bot_1", "@bot_2"],
                "users": [
                {"user_name": "@user1", "transfer_ownership": False},
                {"user_name": "@user2", "transfer_ownership": True}
            ],
                "leave_after": False,
                "photo_url": "https://example.com/group-avatar.png",
            }
        }
    }


class GroupCreationResponse(BaseModel):
    """Response after group creation."""

    success: bool = Field(..., description="Whether group was created successfully")
    group_id: Optional[int] = Field(None, description="Created group ID")
    group_name: Optional[str] = Field(None, description="Group name")
    invite_link: Optional[str] = Field(None, description="Invite link")
    bot: Optional[BotAddResult] = Field(
        None, description="Legacy: first bot add result (for backward compatibility)"
    )
    bots: List[BotAddResult] = Field(default_factory=list, description="Bot add results")
    users: List[UserAddResult] = Field(default_factory=list, description="User add results")
    error: Optional[str] = Field(None, description="Overall error")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "group_id": -1002200104615,
                "group_name": "My New Group",
                "invite_link": "https://t.me/+AbCdEfGhIjKlMnO",
                "bot": {"username": "bot_1", "added": True, "promoted": True, "error": None},
                "bots": [
                    {"username": "bot_1", "added": True, "promoted": True, "error": None},
                    {"username": "bot_2", "added": True, "promoted": True, "error": None}
                ],
                "users": [
                    {"username": "user1", "added": True, "promoted": True, "error": None}
                ],
                "error": None,
                "timestamp": "2024-01-01T12:00:00",
            }
        }
    }
