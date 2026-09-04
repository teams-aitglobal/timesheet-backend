import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog

logger = get_logger(__name__)


class AuditAction:
    """Generic verbs, reusable across any entity_type. A new module (e.g.
    Project, Timesheet) should reuse these rather than adding its own
    entity-prefixed constants — entity_type already identifies what changed.
    """

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    ACTIVATED = "ACTIVATED"
    DEACTIVATED = "DEACTIVATED"
    DELETED = "DELETED"

    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    REFRESH_TOKEN_REVOKED = "REFRESH_TOKEN_REVOKED"

    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET = "PASSWORD_RESET"

    SUPERADMIN_BOOTSTRAPPED = "SUPERADMIN_BOOTSTRAPPED"


async def create_audit_log(
    db: AsyncSession,
    *,
    action: str,
    changed_by: str,
    entity_type: str,
    entity_id: uuid.UUID | str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    """Writes one audit event. Never pass passwords, password hashes, JWTs, refresh
    tokens, or refresh-token hashes in old_value/new_value.
    """
    log = AuditLog(
        changed_by=changed_by,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_value=old_value,
        new_value=new_value,
    )
    db.add(log)
    await db.flush()

    log_level = logger.warning if action == "LOGIN_FAILED" else logger.info
    log_level("%s %s %s by %s", action, entity_type, entity_id, changed_by)

    return log

