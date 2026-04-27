from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    sql = """
        SELECT id, title, content, category, related_type, related_id, is_read, created_at
        FROM notifications
        WHERE user_id=%s
    """
    params = [current_user["sub"]]
    if unread_only:
        sql += " AND is_read=0"
    sql += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, tuple(params))
            rows = await cur.fetchall()
            await cur.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0",
                (current_user["sub"],),
            )
            unread_count = (await cur.fetchone())[0]

    return {
        "items": [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2] or "",
                "category": row[3],
                "related_type": row[4],
                "related_id": row[5],
                "is_read": bool(row[6]),
                "created_at": row[7],
            }
            for row in rows
        ],
        "unread_count": unread_count,
    }


@router.patch("/{notification_id}/read")
async def mark_notification_read(notification_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s",
                (notification_id, current_user["sub"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "消息不存在")
    return {"ok": True}


@router.post("/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0",
                (current_user["sub"],),
            )
    return {"ok": True}
