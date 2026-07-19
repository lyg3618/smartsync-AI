from typing import Optional


CREATE_NOTIFICATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    category VARCHAR(50) NOT NULL DEFAULT 'system',
    related_type VARCHAR(50) NULL,
    related_id VARCHAR(100) NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_notifications_user_created (user_id, created_at DESC),
    INDEX idx_notifications_user_read (user_id, is_read, created_at DESC)
)
"""


async def ensure_notifications_table() -> None:
    from app.database import get_pool
    from app.config import settings

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='notifications'
                LIMIT 1
                """,
                (settings.mysql_db,),
            )
            if await cur.fetchone():
                return

            await cur.execute(CREATE_NOTIFICATIONS_TABLE_SQL)


async def create_notification(
    *,
    user_id: str,
    title: str,
    content: str,
    category: str = "system",
    related_type: Optional[str] = None,
    related_id: Optional[str] = None,
) -> None:
    if not user_id or not title:
        return

    from app.database import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO notifications(user_id, title, content, category, related_type, related_id)
                VALUES(%s, %s, %s, %s, %s, %s)
                """,
                (user_id, title.strip(), (content or "").strip(), category.strip() or "system", related_type, related_id),
            )
