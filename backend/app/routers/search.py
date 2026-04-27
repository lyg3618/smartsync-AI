from fastapi import APIRouter, Depends, Query

from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()


def _parse_legacy_speaker(text: str) -> tuple[str, str]:
    value = str(text or "")
    if value.startswith("[") and "]" in value:
        speaker, content = value[1:].split("]", 1)
        speaker = speaker.strip() or "SPEAKER_00"
        content = content.strip()
        if speaker.upper().startswith("SPEAKER_"):
            return speaker, content
    return "SPEAKER_00", value


@router.get("")
async def global_search(
    q: str = Query("", min_length=0),
    limit: int = Query(8, ge=1, le=30),
    current_user: dict = Depends(get_current_user),
):
    keyword = (q or "").strip()
    if not keyword:
        return {
            "keyword": "",
            "meetings": [],
            "transcripts": [],
            "actions": [],
            "total": 0,
        }

    like_value = f"%{keyword}%"
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, date, status, summary
                FROM meetings
                WHERE user_id=%s AND is_deleted=0
                  AND (name LIKE %s OR IFNULL(summary, '') LIKE %s OR IFNULL(decisions, '') LIKE %s)
                ORDER BY date DESC, id DESC
                LIMIT %s
                """,
                (current_user["sub"], like_value, like_value, like_value, limit),
            )
            meeting_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT t.meeting_id, m.name, t.start_ms, t.end_ms, t.text, t.speaker
                FROM transcripts t
                JOIN meetings m ON m.id = t.meeting_id
                WHERE m.user_id=%s AND m.is_deleted=0 AND t.text LIKE %s
                ORDER BY m.date DESC, t.start_ms ASC
                LIMIT %s
                """,
                (current_user["sub"], like_value, limit),
            )
            transcript_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT a.id, a.meeting_id, m.name, a.owner_name, a.content, a.due_date, a.status
                FROM action_items a
                JOIN meetings m ON m.id = a.meeting_id
                WHERE m.user_id=%s AND m.is_deleted=0
                  AND (a.content LIKE %s OR IFNULL(a.owner_name, '') LIKE %s)
                ORDER BY m.date DESC, a.id DESC
                LIMIT %s
                """,
                (current_user["sub"], like_value, like_value, limit),
            )
            action_rows = await cur.fetchall()

    meetings = [
        {
            "id": row[0],
            "name": row[1],
            "date": row[2],
            "status": row[3],
            "summary": row[4] or "",
        }
        for row in meeting_rows
    ]
    transcripts = []
    for row in transcript_rows:
        legacy_speaker, text = _parse_legacy_speaker(row[4])
        transcripts.append(
            {
                "meeting_id": row[0],
                "meeting_name": row[1],
                "start_ms": row[2],
                "end_ms": row[3],
                "text": text,
                "speaker": row[5] or legacy_speaker,
            }
        )
    actions = [
        {
            "id": row[0],
            "meeting_id": row[1],
            "meeting_name": row[2],
            "owner_name": row[3] or "未分配",
            "content": row[4] or "",
            "due_date": row[5],
            "status": row[6],
        }
        for row in action_rows
    ]

    return {
        "keyword": keyword,
        "meetings": meetings,
        "transcripts": transcripts,
        "actions": actions,
        "total": len(meetings) + len(transcripts) + len(actions),
    }
