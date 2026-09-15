from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timesheet import Timesheet
from app.services import timesheet_service


async def get_timesheet_or_404(db: AsyncSession, timesheet_id: str) -> Timesheet:
    timesheet = await timesheet_service.get_timesheet_by_id(db, timesheet_id)
    if timesheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet entry not found.")
    return timesheet
