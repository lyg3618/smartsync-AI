from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()


class LlmConfigPayload(BaseModel):
    name: str
    model: str
    base_url: str
    api_key: str = ""
    is_active: bool = False


class LlmConfigUpdatePayload(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


def _serialize_row(row):
    return {
        "id": row[0],
        "name": row[1],
        "model": row[2],
        "base_url": row[3],
        "api_key": row[4],
        "is_active": bool(row[5]),
        "created_at": row[6],
        "updated_at": row[7],
    }


async def _fetch_config(cur, config_id: int, user_id: str):
    await cur.execute(
        """
        SELECT id, name, model, base_url, api_key, is_active, created_at, updated_at
        FROM llm_connection_configs
        WHERE id=%s AND user_id=%s
        """,
        (config_id, user_id),
    )
    return await cur.fetchone()


@router.get("")
async def list_llm_configs(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, model, base_url, api_key, is_active, created_at, updated_at
                FROM llm_connection_configs
                WHERE user_id=%s
                ORDER BY is_active DESC, updated_at DESC, id DESC
                """,
                (current_user["sub"],),
            )
            rows = await cur.fetchall()
    return [_serialize_row(row) for row in rows]


@router.get("/active")
async def get_active_llm_config(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, model, base_url, api_key, is_active, created_at, updated_at
                FROM llm_connection_configs
                WHERE user_id=%s AND is_active=1
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (current_user["sub"],),
            )
            row = await cur.fetchone()
    return _serialize_row(row) if row else None


@router.post("")
async def create_llm_config(payload: LlmConfigPayload, current_user: dict = Depends(get_current_user)):
    if not payload.name.strip() or not payload.model.strip() or not payload.base_url.strip():
        raise HTTPException(400, "Name, model and base_url are required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if payload.is_active:
                await cur.execute(
                    "UPDATE llm_connection_configs SET is_active=0 WHERE user_id=%s",
                    (current_user["sub"],),
                )
            await cur.execute(
                """
                INSERT INTO llm_connection_configs(user_id, name, model, base_url, api_key, is_active)
                VALUES(%s, %s, %s, %s, %s, %s)
                """,
                (
                    current_user["sub"],
                    payload.name.strip(),
                    payload.model.strip(),
                    payload.base_url.strip(),
                    payload.api_key.strip() if payload.api_key else "",
                    int(payload.is_active),
                ),
            )
            config_id = cur.lastrowid
            row = await _fetch_config(cur, config_id, current_user["sub"])
    return _serialize_row(row)


@router.put("/{config_id}")
async def update_llm_config(config_id: int, payload: LlmConfigUpdatePayload, current_user: dict = Depends(get_current_user)):
    updates = []
    params = []

    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(400, "Name cannot be empty")
        updates.append("name=%s")
        params.append(payload.name.strip())

    if payload.model is not None:
        if not payload.model.strip():
            raise HTTPException(400, "Model cannot be empty")
        updates.append("model=%s")
        params.append(payload.model.strip())

    if payload.base_url is not None:
        if not payload.base_url.strip():
            raise HTTPException(400, "Base URL cannot be empty")
        updates.append("base_url=%s")
        params.append(payload.base_url.strip())

    if payload.api_key is not None:
        updates.append("api_key=%s")
        params.append(payload.api_key.strip() if payload.api_key else "")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            existing = await _fetch_config(cur, config_id, current_user["sub"])
            if not existing:
                raise HTTPException(404, "LLM config not found")

            if payload.is_active is not None:
                if payload.is_active:
                    await cur.execute(
                        "UPDATE llm_connection_configs SET is_active=0 WHERE user_id=%s",
                        (current_user["sub"],),
                    )
                updates.append("is_active=%s")
                params.append(int(payload.is_active))

            if updates:
                params.extend([config_id, current_user["sub"]])
                await cur.execute(
                    f"UPDATE llm_connection_configs SET {', '.join(updates)} WHERE id=%s AND user_id=%s",
                    tuple(params),
                )

            row = await _fetch_config(cur, config_id, current_user["sub"])
    return _serialize_row(row)


@router.delete("/{config_id}")
async def delete_llm_config(config_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM llm_connection_configs WHERE id=%s AND user_id=%s",
                (config_id, current_user["sub"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "LLM config not found")
    return {"ok": True}
