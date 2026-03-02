"""Group creation endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import verify_api_key
from app.core.exceptions import SessionNotFoundError
from app.dependencies import get_session_manager, get_group_service
from app.schemas.groups import GroupCreationRequest, GroupCreationResponse
from app.sessions.manager import SessionManager
from app.services.group_service import GroupService

router = APIRouter(prefix="/api/v1/groups", tags=["groups"], dependencies=[Depends(verify_api_key)])


@router.post("/create", response_model=GroupCreationResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: GroupCreationRequest,
    manager: SessionManager = Depends(get_session_manager),
    group_service: GroupService = Depends(get_group_service),
) -> GroupCreationResponse:
    """
    Create a Telegram group with bot and users.
    Uses the account identified by session_id (must be registered via auth flow).
    """
    try:
        client = await manager.get_client(request.session_id)
    except SessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from e
    response = await group_service.create_group(client, request)
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=response.error or "Unknown error creating group",
        )
    return response
