from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.user_service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=True)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)
INACTIVE_USER_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="This account is inactive.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except TokenError as exc:
        raise CREDENTIALS_EXCEPTION from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise CREDENTIALS_EXCEPTION

    subject = payload.get("sub")
    if subject is None:
        raise CREDENTIALS_EXCEPTION

    user = await get_user_by_id(db, subject)
    if user is None:
        raise CREDENTIALS_EXCEPTION

    if user.status != "Active":
        raise INACTIVE_USER_EXCEPTION

    return user
