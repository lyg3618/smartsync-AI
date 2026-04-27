from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()


class TemplatePayload(BaseModel):
    name: str
    content: str
    is_default: bool = False


class TemplateUpdatePayload(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    is_default: Optional[bool] = None


@router.get("")
async def list_templates(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, content, is_default, created_at, updated_at
                FROM meeting_minutes_templates
                WHERE user_id=%s
                ORDER BY is_default DESC, updated_at DESC, id DESC
                """,
                (current_user["sub"],),
            )
            rows = await cur.fetchall()
    return [
        {
            "id": row[0],
            "name": row[1],
            "content": row[2],
            "is_default": bool(row[3]),
            "created_at": row[4],
            "updated_at": row[5],
        }
        for row in rows
    ]


@router.post("")
async def create_template(payload: TemplatePayload, current_user: dict = Depends(get_current_user)):
    if not payload.name.strip() or not payload.content.strip():
        raise HTTPException(400, "Template name and content are required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if payload.is_default:
                await cur.execute(
                    "UPDATE meeting_minutes_templates SET is_default=0 WHERE user_id=%s",
                    (current_user["sub"],),
                )
            await cur.execute(
                """
                INSERT INTO meeting_minutes_templates(user_id, name, content, is_default)
                VALUES(%s, %s, %s, %s)
                """,
                (current_user["sub"], payload.name.strip(), payload.content, int(payload.is_default)),
            )
            template_id = cur.lastrowid
            await cur.execute(
                "SELECT id, name, content, is_default, created_at, updated_at FROM meeting_minutes_templates WHERE id=%s AND user_id=%s",
                (template_id, current_user["sub"]),
            )
            row = await cur.fetchone()
    return {
        "id": row[0],
        "name": row[1],
        "content": row[2],
        "is_default": bool(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
    }


@router.put("/{template_id}")
async def update_template(template_id: int, payload: TemplateUpdatePayload, current_user: dict = Depends(get_current_user)):
    updates = []
    params = []

    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(400, "Template name cannot be empty")
        updates.append("name=%s")
        params.append(payload.name.strip())
    if payload.content is not None:
        if not payload.content.strip():
            raise HTTPException(400, "Template content cannot be empty")
        updates.append("content=%s")
        params.append(payload.content)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM meeting_minutes_templates WHERE id=%s AND user_id=%s",
                (template_id, current_user["sub"]),
            )
            if not await cur.fetchone():
                raise HTTPException(404, "Template not found")

            if payload.is_default is not None:
                if payload.is_default:
                    await cur.execute(
                        "UPDATE meeting_minutes_templates SET is_default=0 WHERE user_id=%s",
                        (current_user["sub"],),
                    )
                updates.append("is_default=%s")
                params.append(int(payload.is_default))

            if updates:
                params.extend([template_id, current_user["sub"]])
                await cur.execute(
                    f"UPDATE meeting_minutes_templates SET {', '.join(updates)} WHERE id=%s AND user_id=%s",
                    tuple(params),
                )

            await cur.execute(
                "SELECT id, name, content, is_default, created_at, updated_at FROM meeting_minutes_templates WHERE id=%s AND user_id=%s",
                (template_id, current_user["sub"]),
            )
            row = await cur.fetchone()
    return {
        "id": row[0],
        "name": row[1],
        "content": row[2],
        "is_default": bool(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
    }


@router.delete("/{template_id}")
async def delete_template(template_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM meeting_minutes_templates WHERE id=%s AND user_id=%s",
                (template_id, current_user["sub"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Template not found")
    return {"ok": True}
