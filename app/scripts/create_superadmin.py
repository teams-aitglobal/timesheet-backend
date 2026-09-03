"""Bootstraps the first SUPER_ADMIN account.

There is no public HTTP registration endpoint in this application - the very
first administrator must be created out-of-band, by someone with shell access
to the backend (e.g. during initial deployment). This script is that
mechanism. It is NOT importable by any API route and must never be wired up
to an HTTP endpoint.

Usage:
    python -m app.scripts.create_superadmin
    python -m app.scripts.create_superadmin --email a@b.com --first-name A --last-name B
    python -m app.scripts.create_superadmin --force   # allow creating another SUPER_ADMIN
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.role import SUPER_ADMIN, Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.audit_service import AuditAction, create_audit_log
from app.services.user_service import next_employee_id


def _prompt_email() -> str:
    while True:
        email = input("Email: ").strip()
        if "@" in email and "." in email.split("@")[-1]:
            return email
        print("Please enter a valid email address.")


def _prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} cannot be empty.")


def _prompt_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Try again.")
            continue
        return password


async def create_superadmin(
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    force: bool,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Role).where(Role.name == SUPER_ADMIN))
        super_admin_role = result.scalar_one_or_none()
        if super_admin_role is None:
            print(
                "ERROR: The SUPER_ADMIN role does not exist. Start the app once (schema and "
                "seed data are applied on startup), or run `python -m app.scripts.seed_data` "
                "manually, first.",
                file=sys.stderr,
            )
            sys.exit(1)

        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            print(f"ERROR: A user with email '{email}' already exists.", file=sys.stderr)
            sys.exit(1)

        if not force:
            result = await db.execute(
                select(UserRole).where(UserRole.role_id == super_admin_role.id).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                print(
                    "ERROR: A SUPER_ADMIN already exists. Re-run with --force to create another one.",
                    file=sys.stderr,
                )
                sys.exit(1)

        user = User(
            employee_id=await next_employee_id(db),
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            is_verified=True,
            must_change_password=False,
        )
        db.add(user)
        await db.flush()

        db.add(UserRole(user_id=user.employee_id, role_id=super_admin_role.id))

        await create_audit_log(
            db,
            action=AuditAction.SUPERADMIN_BOOTSTRAPPED,
            changed_by=user.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"email": user.email},
        )

        await db.commit()
        print(f"SUPER_ADMIN created: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the first SUPER_ADMIN account.")
    parser.add_argument("--email")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow creating a SUPER_ADMIN even if one already exists.",
    )
    args = parser.parse_args()

    email = args.email or _prompt_email()
    first_name = args.first_name or _prompt_non_empty("First name")
    last_name = args.last_name or _prompt_non_empty("Last name")
    password = _prompt_password()

    asyncio.run(create_superadmin(email, first_name, last_name, password, args.force))


if __name__ == "__main__":
    main()
