from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()

VALID_STATUSES = {"pending", "in_progress", "done"}


@router.get("")
async def list_todos(owner_name: str = "", status: str = "", current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name FROM contacts WHERE username=%s LIMIT 1",
                (current_user["sub"],),
            )
            contact_row = await cur.fetchone()
            current_contact_id = contact_row[0] if contact_row else None
            current_contact_name = contact_row[1] if contact_row else current_user.get("name", "")

            sql = """
                SELECT ai.id, ai.meeting_id, m.name as meeting_name,
                       ai.owner_id, ai.owner_name, ai.content,
                       ai.due_date, ai.status, ai.is_viewed, ai.viewed_at, ai.completed_at, ai.progress_note
                FROM action_items ai
                JOIN meetings m ON ai.meeting_id = m.id
                WHERE m.is_deleted=0
                  AND (
                    ai.owner_name = %s
                    OR (%s IS NOT NULL AND ai.owner_id = %s)
                  )
            """
            params = [current_contact_name, current_contact_id, current_contact_id]
            if owner_name:
                sql += " AND ai.owner_name = %s"
                params.append(owner_name)
            if status:
                sql += " AND ai.status = %s"
                params.append(status)
            sql += " ORDER BY ai.due_date ASC"
            await cur.execute(sql, params)
            rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "meeting_id": r[1],
            "meeting_name": r[2],
            "owner_id": r[3],
            "owner_name": r[4],
            "content": r[5],
            "due_date": r[6],
            "status": r[7],
            "is_viewed": bool(r[8]),
            "viewed_at": r[9],
            "completed_at": r[10],
            "progress_note": r[11],
        }
        for r in rows
    ]


class StatusUpdate(BaseModel):
    status: str | None = None
    viewed: bool | None = None
    progress_note: str | None = None


@router.patch("/{item_id}")
async def update_todo(item_id: int, payload: StatusUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name FROM contacts WHERE username=%s LIMIT 1",
                (current_user["sub"],),
            )
            contact_row = await cur.fetchone()
            current_contact_id = contact_row[0] if contact_row else None
            current_contact_name = contact_row[1] if contact_row else current_user.get("name", "")

            await cur.execute(
                """
                SELECT ai.id, ai.status, ai.is_viewed
                FROM action_items ai
                JOIN meetings m ON m.id = ai.meeting_id
                LEFT JOIN contacts c ON c.id = ai.owner_id
                WHERE ai.id=%s
                  AND m.is_deleted=0
                  AND (
                    ai.owner_name = %s
                    OR (%s IS NOT NULL AND ai.owner_id = %s)
                  )
                LIMIT 1
                """,
                (item_id, current_contact_name, current_contact_id, current_contact_id),
            )
            item_row = await cur.fetchone()
            if not item_row:
                raise HTTPException(404, "Item not found")

            updates = []
            params = []

            if payload.viewed is True and not bool(item_row[2]):
                updates.extend(["is_viewed=1", "viewed_at=NOW()"])

            if payload.status is not None:
                if payload.status not in VALID_STATUSES:
                    raise HTTPException(400, "Invalid status")
                updates.append("status=%s")
                params.append(payload.status)
                if payload.status == "in_progress":
                    updates.append("is_viewed=1")
                    updates.append("viewed_at=COALESCE(viewed_at, NOW())")
                    updates.append("completed_at=NULL")
                elif payload.status == "done":
                    updates.append("is_viewed=1")
                    updates.append("viewed_at=COALESCE(viewed_at, NOW())")
                    updates.append("completed_at=NOW()")
                elif payload.status == "pending":
                    updates.append("completed_at=NULL")

            if payload.progress_note is not None:
                updates.append("progress_note=%s")
                params.append(payload.progress_note.strip() or None)

            if not updates:
                return {"ok": True}

            await cur.execute(
                f"""
                UPDATE action_items
                SET {', '.join(updates)}
                WHERE id=%s
                """,
                tuple(params + [item_id]),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Item not found")

    return {"ok": True}
