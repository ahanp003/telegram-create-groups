"""Group creation request and response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


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
    bot_username: str = Field(..., description="Bot username (with or without @)")
    users: List[UserInRequest] = Field(
        default_factory=list, description="List of users to add (with optional transfer_ownership)"
    )
    leave_after: bool = Field(False, description="Leave group after creation")

    @field_validator("bot_username")
    @classmethod
    def validate_bot_username(cls, v: str) -> str:
        if not v:
            raise ValueError("Bot username cannot be empty")
        return v.lstrip("@")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "group_name": "My New Group",
                "bot_username": "@test_chat_all_bot",
                "users": ["@user1", "@user2"],
                "leave_after": False,
            }
        }
    }


class GroupCreationResponse(BaseModel):
    """Response after group creation."""

    success: bool = Field(..., description="Whether group was created successfully")
    group_id: Optional[int] = Field(None, description="Created group ID")
    group_name: Optional[str] = Field(None, description="Group name")
    invite_link: Optional[str] = Field(None, description="Invite link")
    bot: Optional[BotAddResult] = Field(None, description="Bot add result")
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
                "bot": {"username": "test_chat_all_bot", "added": True, "promoted": True, "error": None},
                "users": [
                    {"username": "user1", "added": True, "promoted": True, "error": None}
                ],
                "error": None,
                "timestamp": "2024-01-01T12:00:00",
            }
        }
    }
