import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_pool
from app.routers.auth import get_current_user


router = APIRouter()

DISPATCH_SETTING_KEY = "dispatch_channels"
DEFAULT_DISPATCH_CONFIG = {
    "email_enabled": True,
    "message_enabled": False,
    "message_api_url": "http://tcmp.btsteel.com/services/ServiceMessageCustom",
    "message_code": "2906",
    "message_creator_collab_no": "",
    "message_link_url": "",
    "message_mobile_link_url": "",
}


class ProfileUpdatePayload(BaseModel):
    name: str
    email: str = ""
    collab_no: str = ""


class DispatchConfigPayload(BaseModel):
    email_enabled: bool = True
    message_enabled: bool = False
    message_api_url: str = "http://tcmp.btsteel.com/services/ServiceMessageCustom"
    message_code: str = "2906"
    message_creator_collab_no: str = ""
    message_link_url: str = ""
    message_mobile_link_url: str = ""
    notifications: list[bool] = Field(default_factory=list)


def _require_login(current_user: dict | None) -> dict:
    if not current_user:
        raise HTTPException(status_code=401, detail="未授权")
    return current_user


def _require_admin(current_user: dict | None) -> dict:
    user = _require_login(current_user)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Requires admin privilege")
    return user


async def _load_dispatch_config(cur) -> dict[str, Any]:
    await cur.execute("SELECT `value` FROM system_settings WHERE `key`=%s LIMIT 1", (DISPATCH_SETTING_KEY,))
    row = await cur.fetchone()
    if not row:
        return dict(DEFAULT_DISPATCH_CONFIG)

    value = row[0]
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = {}

    config = dict(DEFAULT_DISPATCH_CONFIG)
    if isinstance(value, dict):
        config.update(value)
    return config


async def get_dispatch_config_from_db() -> dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            return await _load_dispatch_config(cur)


@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    user = _require_login(current_user)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, username, name, role, COALESCE(email, ''), COALESCE(collab_no, '')
                FROM contacts
                WHERE username=%s
                LIMIT 1
                """,
                (user["sub"],),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "id": row[0],
        "username": row[1],
        "name": row[2],
        "role": row[3],
        "email": row[4],
        "collab_no": row[5],
    }


@router.put("/profile")
async def update_profile(payload: ProfileUpdatePayload, current_user: dict = Depends(get_current_user)):
    user = _require_login(current_user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="显示名称不能为空")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE contacts
                SET name=%s, email=%s, collab_no=%s
                WHERE username=%s
                """,
                (name, payload.email.strip(), payload.collab_no.strip(), user["sub"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="用户不存在")

            await cur.execute(
                """
                SELECT id, username, name, role, COALESCE(email, ''), COALESCE(collab_no, '')
                FROM contacts
                WHERE username=%s
                LIMIT 1
                """,
                (user["sub"],),
            )
            row = await cur.fetchone()

    return {
        "id": row[0],
        "username": row[1],
        "name": row[2],
        "role": row[3],
        "email": row[4],
        "collab_no": row[5],
    }


@router.get("/dispatch")
async def get_dispatch_config(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return await get_dispatch_config_from_db()


@router.put("/dispatch")
async def update_dispatch_config(payload: DispatchConfigPayload, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    if not payload.email_enabled and not payload.message_enabled:
        raise HTTPException(status_code=400, detail="邮箱发送和消息发送至少启用一种")
    if payload.message_enabled:
        if not payload.message_api_url.strip():
            raise HTTPException(status_code=400, detail="请填写协同消息接口地址")
        if not payload.message_code.strip():
            raise HTTPException(status_code=400, detail="请填写协同消息来源编码")

    config = {
        "email_enabled": payload.email_enabled,
        "message_enabled": payload.message_enabled,
        "message_api_url": payload.message_api_url.strip(),
        "message_code": payload.message_code.strip(),
        "message_creator_collab_no": payload.message_creator_collab_no.strip(),
        "message_link_url": payload.message_link_url.strip(),
        "message_mobile_link_url": payload.message_mobile_link_url.strip(),
    }

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO system_settings(`key`, `value`)
                VALUES(%s, %s)
                ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)
                """,
                (DISPATCH_SETTING_KEY, json.dumps(config, ensure_ascii=False)),
            )

    return config
