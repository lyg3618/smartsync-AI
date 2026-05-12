import aiomysql
from app.config import settings

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            db=settings.mysql_db,
            charset='utf8mb4',
            autocommit=True,
            minsize=2,
            maxsize=10,
        )
    return _pool


async def ensure_runtime_tables():
    from app.services.notifications import ensure_notifications_table

    await ensure_notifications_table()
    await ensure_action_item_tracking_columns()
    await ensure_transcript_columns()
    await ensure_contact_columns()
    await ensure_system_settings_table()


async def ensure_action_item_tracking_columns():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute("ALTER TABLE action_items MODIFY COLUMN status ENUM('pending','in_progress','done') NOT NULL DEFAULT 'pending'")
            except Exception:
                pass

            await cur.execute(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='action_items'
                """,
                (settings.mysql_db,)
            )
            existing_columns = {row[0] for row in await cur.fetchall()}

            column_statements = {
                "is_viewed": "ALTER TABLE action_items ADD COLUMN is_viewed TINYINT(1) NOT NULL DEFAULT 0",
                "viewed_at": "ALTER TABLE action_items ADD COLUMN viewed_at DATETIME NULL",
                "completed_at": "ALTER TABLE action_items ADD COLUMN completed_at DATETIME NULL",
                "progress_note": "ALTER TABLE action_items ADD COLUMN progress_note TEXT NULL",
                "collab_message_target_id": "ALTER TABLE action_items ADD COLUMN collab_message_target_id VARCHAR(255) NULL",
                "collab_message_login_id": "ALTER TABLE action_items ADD COLUMN collab_message_login_id VARCHAR(100) NULL",
                "collab_message_title": "ALTER TABLE action_items ADD COLUMN collab_message_title VARCHAR(255) NULL",
                "collab_message_context": "ALTER TABLE action_items ADD COLUMN collab_message_context TEXT NULL",
                "collab_message_sent_at": "ALTER TABLE action_items ADD COLUMN collab_message_sent_at DATETIME NULL",
                "collab_message_deleted_at": "ALTER TABLE action_items ADD COLUMN collab_message_deleted_at DATETIME NULL",
            }

            for column_name, statement in column_statements.items():
                if column_name in existing_columns:
                    continue
                try:
                    await cur.execute(statement)
                except Exception:
                    pass

            for statement in (
                "CREATE INDEX idx_transcripts_meeting_start ON transcripts(meeting_id, start_ms)",
                "CREATE INDEX idx_transcripts_meeting_speaker ON transcripts(meeting_id, speaker)",
            ):
                try:
                    await cur.execute(statement)
                except Exception:
                    pass


async def ensure_transcript_columns():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='transcripts'
                """,
                (settings.mysql_db,)
            )
            existing_columns = {row[0] for row in await cur.fetchall()}

            column_statements = {
                "speaker": "ALTER TABLE transcripts ADD COLUMN speaker VARCHAR(64) NOT NULL DEFAULT 'SPEAKER_00'",
                "confidence": "ALTER TABLE transcripts ADD COLUMN confidence FLOAT NULL",
                "segment_no": "ALTER TABLE transcripts ADD COLUMN segment_no INT NOT NULL DEFAULT 0",
            }
            for column_name, statement in column_statements.items():
                if column_name in existing_columns:
                    continue
                try:
                    await cur.execute(statement)
                except Exception:
                    pass


async def ensure_contact_columns():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='contacts'
                """,
                (settings.mysql_db,)
            )
            existing_columns = {row[0] for row in await cur.fetchall()}

            column_statements = {
                "collab_no": "ALTER TABLE contacts ADD COLUMN collab_no VARCHAR(100) NULL",
            }

            for column_name, statement in column_statements.items():
                if column_name in existing_columns:
                    continue
                try:
                    await cur.execute(statement)
                except Exception:
                    pass


async def ensure_system_settings_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    `key` VARCHAR(100) PRIMARY KEY,
                    `value` JSON NULL,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """
            )

async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
