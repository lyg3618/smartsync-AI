import aiomysql
import json
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
    await ensure_meeting_columns()
    await ensure_action_item_tracking_columns()
    await ensure_transcript_columns()
    await ensure_system_settings_table()


async def ensure_meeting_columns():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='meetings'
                """,
                (settings.mysql_db,)
            )
            existing_columns = {row[0] for row in await cur.fetchall()}

            column_statements = {
                "template_minutes": "ALTER TABLE meetings ADD COLUMN template_minutes LONGTEXT NULL",
            }

            for column_name, statement in column_statements.items():
                if column_name in existing_columns:
                    continue
                try:
                    await cur.execute(statement)
                except Exception:
                    pass


async def ensure_action_item_tracking_columns():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='action_items'
                """,
                (settings.mysql_db,)
            )
            column_info = {row[0]: row for row in await cur.fetchall()}
            existing_columns = set(column_info)

            status_info = column_info.get("status")
            if status_info and (
                status_info[1] != "enum('pending','in_progress','done')"
                or status_info[2] != "NO"
                or status_info[3] != "pending"
            ):
                try:
                    await cur.execute("ALTER TABLE action_items MODIFY COLUMN status ENUM('pending','in_progress','done') NOT NULL DEFAULT 'pending'")
                except Exception:
                    pass

            column_statements = {
                "is_viewed": "ALTER TABLE action_items ADD COLUMN is_viewed TINYINT(1) NOT NULL DEFAULT 0",
                "viewed_at": "ALTER TABLE action_items ADD COLUMN viewed_at DATETIME NULL",
                "completed_at": "ALTER TABLE action_items ADD COLUMN completed_at DATETIME NULL",
                "progress_note": "ALTER TABLE action_items ADD COLUMN progress_note TEXT NULL",
            }

            for column_name, statement in column_statements.items():
                if column_name in existing_columns:
                    continue
                try:
                    await cur.execute(statement)
                except Exception:
                    pass

            await cur.execute(
                """
                SELECT INDEX_NAME
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='transcripts'
                """,
                (settings.mysql_db,),
            )
            existing_indexes = {row[0] for row in await cur.fetchall()}

            index_statements = {
                "idx_transcripts_meeting_start": "CREATE INDEX idx_transcripts_meeting_start ON transcripts(meeting_id, start_ms)",
                "idx_transcripts_meeting_speaker": "CREATE INDEX idx_transcripts_meeting_speaker ON transcripts(meeting_id, speaker)",
            }
            for index_name, statement in index_statements.items():
                if index_name in existing_indexes:
                    continue
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


async def ensure_system_settings_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='system_settings'
                LIMIT 1
                """,
                (settings.mysql_db,),
            )
            if not await cur.fetchone():
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_settings (
                        `key` VARCHAR(100) PRIMARY KEY,
                        `value` JSON NULL,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )

            await cur.execute(
                "SELECT `value` FROM system_settings WHERE `key`='dispatch_channels' LIMIT 1"
            )
            row = await cur.fetchone()
            if row:
                value = row[0]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except Exception:
                        value = {}
                await cur.execute(
                    "UPDATE system_settings SET `value`=%s WHERE `key`='dispatch_channels'",
                    (json.dumps({"email_enabled": True}),),
                )

async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
