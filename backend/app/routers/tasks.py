from fastapi import APIRouter, Depends
from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT status, progress, meeting_id FROM upload_tasks WHERE id=%s",
                (task_id,)
            )
            row = await cur.fetchone()
    if not row:
        return {"status": "not_found", "progress": 0}
    return {"status": row[0], "progress": row[1], "meeting_id": row[2]}