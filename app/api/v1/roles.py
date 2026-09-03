from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.user import User
from app.schemas.role import RoleOut
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
async def list_roles(
    current_user: User = Depends(require_permission("ROLE_READ")),
    db: AsyncSession = Depends(get_db),
) -> list[RoleOut]:
    roles = await role_service.list_roles(db)
    return [RoleOut.model_validate(role) for role in roles]
