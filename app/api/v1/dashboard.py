from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.dashboard import AdminDashboardOut, EmployeeDashboardOut, ManagerDashboardOut
from app.services.dashboard import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DashboardOut = Annotated[
    AdminDashboardOut | ManagerDashboardOut | EmployeeDashboardOut, Field(discriminator="role")
]


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardOut | ManagerDashboardOut | EmployeeDashboardOut:
    return await dashboard_service.get_dashboard(db, current_user)
