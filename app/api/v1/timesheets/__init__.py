from fastapi import APIRouter

from app.api.v1.timesheets.approvals import router as approvals_router
from app.api.v1.timesheets.crud import router as crud_router

# `approvals_router` must be included before `crud_router`: it registers the
# static path "/pending-approval", which would otherwise be shadowed by
# crud_router's "/{timesheet_id}" catch-all if that were registered first.
router = APIRouter()
router.include_router(approvals_router)
router.include_router(crud_router)

__all__ = ["router"]
