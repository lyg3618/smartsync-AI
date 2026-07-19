import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_pool
from app.routers.auth import get_current_user
from app.security import hash_password


router = APIRouter()


class ContactCreate(BaseModel):
    name: str
    email: str = ""
    username: str | None = None


class ContactUpdate(BaseModel):
    name: str
    email: str = ""


def _require_admin(current_user: dict | None) -> dict:
    if not current_user:
        raise HTTPException(status_code=401, detail="未授权")
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Requires admin privilege")
    return current_user


@router.get("")
async def list_contacts(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="未授权")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, COALESCE(email, '') FROM contacts ORDER BY name"
            )
            rows = await cur.fetchall()
    return [{"id": row[0], "name": row[1], "email": row[2]} for row in rows]


@router.post("")
async def create_contact(contact: ContactCreate, current_user: dict = Depends(get_current_user)):
    current_user = _require_admin(current_user)

    contact_id = uuid.uuid4().hex
    name = contact.name.strip()
    email = contact.email.strip()
    username = (contact.username or (email.split("@")[0] if email else name) or f"user_{contact_id[:8]}").strip()
    if not name:
        raise HTTPException(status_code=400, detail="成员姓名不能为空")
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    pool = await get_pool()
    hashed_password = hash_password("123456")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO contacts (id, name, email, user_id, username, hashed_password, role)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (contact_id, name, email, current_user["sub"], username, hashed_password, "user"),
                )
            except Exception:
                raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    return {"id": contact_id, "name": name, "email": email, "username": username}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
    return {"ok": True}


@router.put("/{contact_id}")
async def update_contact(contact_id: str, contact: ContactUpdate, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)

    name = contact.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="成员姓名不能为空")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "UPDATE contacts SET name = %s, email = %s WHERE id = %s",
                    (name, contact.email.strip(), contact_id),
                )
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Contact not found")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="Failed to update contact")

    return {"id": contact_id, "name": name, "email": contact.email.strip()}
