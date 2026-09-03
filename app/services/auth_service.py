from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_temporary_password,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.audit_service import AuditAction, create_audit_log
from app.services.user_service import get_user_by_email, get_user_by_id

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password."
)
INACTIVE_USER = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is inactive.")
INVALID_REFRESH_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token."
)


async def _issue_tokens(
    db: AsyncSession, user: User, *, ip_address: str | None, user_agent: str | None
) -> tuple[str, str]:
    access_token = create_access_token(user.employee_id)
    raw_refresh_token = generate_refresh_token()

    db.add(
        RefreshToken(
            user_id=user.employee_id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=refresh_token_expiry(),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    await db.flush()
    return access_token, raw_refresh_token


async def login(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str, str]:
    user = await get_user_by_email(db, email)

    if user is None:
        raise INVALID_CREDENTIALS

    if user.password_hash is None or not verify_password(password, user.password_hash):
        await create_audit_log(
            db,
            action=AuditAction.LOGIN_FAILED,
            changed_by=user.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"email": email},
        )
        await db.commit()
        raise INVALID_CREDENTIALS

    if user.status != "Active":
        await create_audit_log(
            db,
            action=AuditAction.LOGIN_FAILED,
            changed_by=user.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"reason": "inactive_user"},
        )
        await db.commit()
        raise INACTIVE_USER

    access_token, refresh_token = await _issue_tokens(db, user, ip_address=ip_address, user_agent=user_agent)

    await create_audit_log(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        changed_by=user.employee_id,
        entity_type="user",
        entity_id=user.employee_id,
    )
    await db.commit()
    user = await get_user_by_id(db, user.employee_id)
    return user, access_token, refresh_token


async def refresh_session(
    db: AsyncSession,
    raw_refresh_token: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str]:
    token_hash = hash_refresh_token(raw_refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        raise INVALID_REFRESH_TOKEN

    now = _now()
    if stored_token.revoked_at is not None or stored_token.expires_at < now:
        raise INVALID_REFRESH_TOKEN

    user = await get_user_by_id(db, stored_token.user_id)
    if user is None or user.status != "Active":
        raise INVALID_REFRESH_TOKEN

    # Rotate: revoke the presented token and issue a brand new pair.
    stored_token.revoked_at = now
    new_access_token, new_refresh_token = await _issue_tokens(
        db, user, ip_address=ip_address, user_agent=user_agent
    )

    await db.commit()
    return new_access_token, new_refresh_token


async def logout(
    db: AsyncSession,
    raw_refresh_token: str,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored_token = result.scalar_one_or_none()

    if stored_token is not None and stored_token.revoked_at is None:
        stored_token.revoked_at = _now()
        await create_audit_log(
            db,
            action=AuditAction.LOGOUT,
            changed_by=actor.employee_id,
            entity_type="refresh_token",
            entity_id=stored_token.id,
        )
        await db.commit()


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    if user.password_hash is None or not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False

    # A changed password should invalidate any session issued under the old one -
    # otherwise a stolen-and-then-rotated password leaves old refresh tokens (up to
    # REFRESH_TOKEN_EXPIRE_DAYS) still usable elsewhere.
    revoke_result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.employee_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )

    await create_audit_log(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        changed_by=user.employee_id,
        entity_type="user",
        entity_id=user.employee_id,
    )
    if revoke_result.rowcount:
        await create_audit_log(
            db,
            action=AuditAction.REFRESH_TOKEN_REVOKED,
            changed_by=user.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"reason": "password_changed", "revoked_count": revoke_result.rowcount},
        )

    await db.commit()
    user = await get_user_by_id(db, user.employee_id)
    return user


async def admin_reset_password(
    db: AsyncSession,
    user: User,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    temporary_password = generate_temporary_password()
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.updated_by = actor.employee_id

    # Same rationale as change_password: a reset password should invalidate any
    # session issued under the old one.
    revoke_result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.employee_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )

    await create_audit_log(
        db,
        action=AuditAction.PASSWORD_RESET,
        changed_by=actor.employee_id,
        entity_type="user",
        entity_id=user.employee_id,
    )
    if revoke_result.rowcount:
        await create_audit_log(
            db,
            action=AuditAction.REFRESH_TOKEN_REVOKED,
            changed_by=actor.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"reason": "password_reset", "revoked_count": revoke_result.rowcount},
        )

    await db.commit()
    user = await get_user_by_id(db, user.employee_id)
    return user, temporary_password


def _now() -> datetime:
    return datetime.now(timezone.utc)
