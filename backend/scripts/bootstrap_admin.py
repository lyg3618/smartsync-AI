from __future__ import annotations

import asyncio
import os
import sys
import uuid

import aiomysql

from app.config import settings
from app.security import hash_password


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set for Docker deployment.")
    return value


async def bootstrap_admin() -> None:
    username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    password = _required_env("ADMIN_PASSWORD")
    display_name = os.getenv("ADMIN_NAME", "Administrator").strip() or "Administrator"
    email = os.getenv("ADMIN_EMAIL", "").strip()

    if len(password) < 8:
        raise RuntimeError("ADMIN_PASSWORD must contain at least 8 characters.")

    connection = await aiomysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_db,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT id FROM contacts WHERE username=%s LIMIT 1",
                (username,),
            )
            if await cursor.fetchone():
                print(f"[BOOTSTRAP] Administrator '{username}' already exists.")
                return

            await cursor.execute(
                """
                INSERT INTO contacts
                    (id, name, email, user_id, username, hashed_password, role)
                VALUES (%s, %s, %s, %s, %s, %s, 'admin')
                """,
                (
                    uuid.uuid4().hex,
                    display_name,
                    email,
                    username,
                    username,
                    hash_password(password),
                ),
            )
            print(f"[BOOTSTRAP] Administrator '{username}' created.")
    except aiomysql.ProgrammingError as exc:
        if exc.args and exc.args[0] == 1146:
            raise RuntimeError(
                "Database schema is missing. Start with an empty MySQL volume or import a valid backup."
            ) from exc
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        asyncio.run(bootstrap_admin())
    except Exception as exc:
        print(f"[BOOTSTRAP] Failed: {exc}", file=sys.stderr)
        raise
