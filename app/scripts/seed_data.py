"""Idempotently (re-)applies the role/permission/role-permission seed catalog.

The app's startup lifespan (app.main) already applies this catalog every time
the app boots. This script exists to re-apply it manually without restarting
the app - e.g. after pulling a change to the permission list. The
`apply_seed_data()` function is also reused by the test suite to seed a
freshly created test database.

Usage:
    python -m app.scripts.seed_data
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed_data import PERMISSIONS, ROLE_PERMISSIONS, ROLES
from app.db.session import AsyncSessionLocal
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission


async def apply_seed_data(db: AsyncSession) -> None:
    result = await db.execute(select(Role))
    roles_by_name = {r.name: r for r in result.scalars().all()}

    for role_data in ROLES:
        role = roles_by_name.get(role_data["name"])
        if role is None:
            role = Role(name=role_data["name"], description=role_data["description"])
            db.add(role)
            await db.flush()
            roles_by_name[role.name] = role
        else:
            role.description = role_data["description"]

    result = await db.execute(select(Permission))
    permissions_by_code = {p.code: p for p in result.scalars().all()}

    for module, entries in PERMISSIONS.items():
        for code, name, description in entries:
            permission = permissions_by_code.get(code)
            if permission is None:
                permission = Permission(code=code, name=name, description=description, module=module)
                db.add(permission)
                await db.flush()
                permissions_by_code[code] = permission
            else:
                permission.name = name
                permission.description = description
                permission.module = module

    result = await db.execute(select(RolePermission))
    existing_grants = {(rp.role_id, rp.permission_id) for rp in result.scalars().all()}

    for role_name, codes in ROLE_PERMISSIONS.items():
        role = roles_by_name[role_name]
        for code in codes:
            permission = permissions_by_code[code]
            key = (role.id, permission.id)
            if key not in existing_grants:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
                existing_grants.add(key)

    await db.commit()


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await apply_seed_data(db)
        print("Seed data applied successfully.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
