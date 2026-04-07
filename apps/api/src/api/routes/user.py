"""REST API handler for current user APIs."""

from fastapi import APIRouter, status

from api.models.user import User
from api.security.session_auth import CurrentUser

router = APIRouter()


@router.get(
    '/current',
    response_description='Logged in user information',
    status_code=status.HTTP_200_OK,
    response_model=User,
    include_in_schema=False,
)
async def get_current_user(current_user: CurrentUser) -> User:
    """Authenticate the user and return the user information."""
    return current_user
