import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_pool
from app.routers.auth import get_current_user
from app.routers.settings import get_dispatch_config_from_db
from app.services.notifications import create_notification

router = APIRouter()


def _normalize_audio_url(value: str | None) -> str | None:
    if not value:
        return value
    normalized = str(value).strip().replace("\\", "/")
    if normalized.startswith(("http://", "https://", "/uploads/")):
        return normalized
    file_name = Path(normalized).name
    if not file_name:
        return None
    return f"/uploads/{quote(file_name)}"


def _normalize_meeting_name(value: str | None) -> str:
    name = str(value or "").strip()
    if not name:
        raise HTTPException(400, "会议名称不能为空")
    if len(name) > 255:
        raise HTTPException(400, "会议名称不能超过 255 个字符")
    return name


def _parse_legacy_speaker(text: str) -> tuple[str, str]:
    value = str(text or "")
    if value.startswith("[") and "]" in value:
        speaker, content = value[1:].split("]", 1)
        speaker = speaker.strip() or "SPEAKER_00"
        content = content.strip()
        if speaker.upper().startswith("SPEAKER_"):
            return speaker, content
    return "SPEAKER_00", value


async def _fetch_meeting(cur, meeting_id: str, user_id: str):
    await cur.execute("SELECT id, name FROM contacts WHERE username=%s LIMIT 1", (user_id,))
    contact_row = await cur.fetchone()
    current_contact_id = contact_row[0] if contact_row else None
    current_contact_name = contact_row[1] if contact_row else ""

    await cur.execute(
        """
        SELECT id,name,date,duration_sec,task_count,status,audio_url,summary,decisions,template_minutes,
               CASE WHEN user_id=%s THEN 1 ELSE 0 END AS can_edit
        FROM meetings
        WHERE id=%s AND is_deleted=0
          AND (
            user_id=%s
            OR EXISTS (
                SELECT 1
                FROM action_items ai
                WHERE ai.meeting_id = meetings.id
                  AND (
                    ai.owner_name = %s
                    OR (%s IS NOT NULL AND ai.owner_id = %s)
                  )
            )
          )
        LIMIT 1
        """,
        (user_id, meeting_id, user_id, current_contact_name, current_contact_id, current_contact_id),
    )
    row = await cur.fetchone()
    if not row:
        return None

    meeting = {
        "id": row[0],
        "name": row[1],
        "date": row[2],
        "duration_sec": row[3],
        "task_count": row[4],
        "status": row[5],
        "audio_url": _normalize_audio_url(row[6]),
        "summary": row[7],
        "decisions": json.loads(row[8]) if row[8] else [],
        "template_minutes": row[9] or "",
        "can_edit": bool(row[10]),
    }

    await cur.execute(
        "SELECT id,start_ms,end_ms,text,speaker,confidence,segment_no FROM transcripts WHERE meeting_id=%s ORDER BY start_ms, segment_no, id",
        (meeting_id,),
    )
    transcript_rows = await cur.fetchall()
    meeting["transcript"] = []
    for row in transcript_rows:
        legacy_speaker, text = _parse_legacy_speaker(row[3])
        meeting["transcript"].append(
            {
                "id": row[0],
                "start_ms": row[1],
                "end_ms": row[2],
                "text": text,
                "speaker": row[4] or legacy_speaker,
                "confidence": row[5],
                "segment_no": row[6] or 0,
            }
        )

    await cur.execute(
        """
        SELECT id,owner_id,owner_name,content,due_date,status,updated_after_dispatch,last_dispatched_at,progress_note
        FROM action_items
        WHERE meeting_id=%s
        ORDER BY id
        """,
        (meeting_id,),
    )
    meeting["action_items"] = [
        {
            "id": r[0],
            "owner_id": r[1],
            "owner_name": r[2],
            "content": r[3],
            "due_date": r[4],
            "status": r[5],
            "updated_after_dispatch": bool(r[6]),
            "last_dispatched_at": r[7],
            "progress_note": r[8],
        }
        for r in await cur.fetchall()
    ]
    return meeting


async def _send_grouped_task_emails(
    owner_items: dict[str, dict[str, Any]],
    meeting_name: str,
    summary: str,
    decisions: list[str],
    subject_prefix: str,
) -> int:
    if not (settings.smtp_user and settings.smtp_pass and owner_items):
        return 0

    decisions_text = "\n".join([f"- {item}" for item in decisions]) if decisions else "无"
    emails_sent = 0
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()
    server.login(settings.smtp_user, settings.smtp_pass)

    for email, data in owner_items.items():
        msg = EmailMessage()
        msg["Subject"] = f"[AI会议助手 {subject_prefix}] {meeting_name}"
        msg["From"] = settings.smtp_from
        msg["To"] = email
        body = f"你好，{data['name']}\n\n"
        body += f"以下是会议《{meeting_name}》的最新行动项，请以此版本为准。\n\n"
        body += "【你的任务】\n" + "\n".join(data["tasks"]) + "\n\n"
        body += "【会议摘要】\n" + (summary or "无") + "\n\n"
        body += "【核心决议】\n" + decisions_text + "\n"
        msg.set_content(body)
        server.send_message(msg)
        emails_sent += 1

    server.quit()
    return emails_sent


def _normalize_due_date(value):
    return "" if value in (None, "None") else str(value)


def _item_changed(existing_row, payload_item):
    return any(
        [
            str(existing_row[1] or "") != str(payload_item.get("owner_id", "") or ""),
            str(existing_row[2] or "") != str(payload_item.get("owner_name", "") or ""),
            str(existing_row[3] or "") != str(payload_item.get("content", "") or ""),
            _normalize_due_date(existing_row[4]) != _normalize_due_date(payload_item.get("due_date", "")),
            str(existing_row[5] or "pending") != str(payload_item.get("status", "pending") or "pending"),
            str(existing_row[8] or "") != str(payload_item.get("progress_note", "") or ""),
        ]
    )


def _build_dispatch_targets(rows) -> tuple[dict[str, dict[str, Any]], list[int]]:
    owner_items: dict[str, dict[str, Any]] = {}
    synced_ids: list[int] = []

    for row in rows:
        item_id, meeting_id, content, due_date, owner_name, owner_email = row[:6]
        task_text = f"{content} (截止: {due_date or '待定'})"
        if owner_email:
            if owner_email not in owner_items:
                owner_items[owner_email] = {"name": owner_name, "tasks": []}
            owner_items[owner_email]["tasks"].append(task_text)
        synced_ids.append(int(item_id))

    return owner_items, synced_ids


@router.get("")
async def list_meetings(page: int = 1, size: int = 10, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM meetings WHERE user_id=%s AND is_deleted=0", (current_user["sub"],))
            total = (await cur.fetchone())[0]
            offset = (page - 1) * size
            await cur.execute(
                """
                SELECT id,name,date,duration_sec,task_count,status
                FROM meetings
                WHERE user_id=%s AND is_deleted=0
                ORDER BY date DESC
                LIMIT %s OFFSET %s
                """,
                (current_user["sub"], size, offset),
            )
            rows = await cur.fetchall()
    items = [{"id": r[0], "name": r[1], "date": r[2], "duration_sec": r[3], "task_count": r[4], "status": r[5]} for r in rows]
    return {"items": items, "total": total, "page": page}


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            meeting = await _fetch_meeting(cur, meeting_id, current_user["sub"])
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    return meeting


class ConfirmPayload(BaseModel):
    name: Optional[str] = None
    summary: Optional[str] = None
    decisions: Optional[List[str]] = None
    action_items: Optional[List[dict]] = None
    template_minutes: Optional[str] = None


class UpdateMeetingPayload(BaseModel):
    name: Optional[str] = None
    template_minutes: Optional[str] = None


class UpdateTranscriptSpeakerPayload(BaseModel):
    speaker: str


class BulkUpdateTranscriptSpeakersPayload(BaseModel):
    mappings: dict[str, str]


@router.put("/{meeting_id}/transcripts/{transcript_id}/speaker")
async def update_transcript_speaker(
    meeting_id: str,
    transcript_id: int,
    payload: UpdateTranscriptSpeakerPayload,
    current_user: dict = Depends(get_current_user),
):
    speaker = str(payload.speaker or "").strip()
    if not speaker:
        raise HTTPException(400, "Speaker name is required")
    if len(speaker) > 64:
        raise HTTPException(400, "Speaker name is too long")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM meetings WHERE id=%s AND user_id=%s AND is_deleted=0",
                (meeting_id, current_user["sub"]),
            )
            meeting_row = await cur.fetchone()
            if not meeting_row:
                raise HTTPException(404, "Meeting not found")

            await cur.execute(
                "SELECT id FROM transcripts WHERE id=%s AND meeting_id=%s LIMIT 1",
                (transcript_id, meeting_id),
            )
            transcript_row = await cur.fetchone()
            if not transcript_row:
                raise HTTPException(404, "Transcript not found")

            await cur.execute(
                "UPDATE transcripts SET speaker=%s WHERE id=%s AND meeting_id=%s",
                (speaker, transcript_id, meeting_id),
            )
    return {"ok": True, "speaker": speaker}


@router.put("/{meeting_id}/transcripts/speakers")
async def bulk_update_transcript_speakers(
    meeting_id: str,
    payload: BulkUpdateTranscriptSpeakersPayload,
    current_user: dict = Depends(get_current_user),
):
    raw_mappings = payload.mappings or {}
    mappings = {
        str(source or "").strip(): str(target or "").strip()
        for source, target in raw_mappings.items()
        if str(source or "").strip() and str(target or "").strip()
    }
    if not mappings:
        raise HTTPException(400, "At least one speaker mapping is required")
    if any(len(target) > 64 for target in mappings.values()):
        raise HTTPException(400, "Speaker name is too long")

    pool = await get_pool()
    updated = 0
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM meetings WHERE id=%s AND user_id=%s AND is_deleted=0",
                (meeting_id, current_user["sub"]),
            )
            meeting_row = await cur.fetchone()
            if not meeting_row:
                raise HTTPException(404, "Meeting not found")

            for source, target in mappings.items():
                if source == target:
                    continue
                await cur.execute(
                    "UPDATE transcripts SET speaker=%s WHERE meeting_id=%s AND speaker=%s",
                    (target, meeting_id, source),
                )
                updated += cur.rowcount or 0
    return {"ok": True, "updated": updated}


@router.post("/{meeting_id}/confirm")
async def confirm_meeting(meeting_id: str, payload: ConfirmPayload, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id,status FROM meetings WHERE id=%s AND user_id=%s AND is_deleted=0",
                (meeting_id, current_user["sub"]),
            )
            meeting_row = await cur.fetchone()
            if not meeting_row:
                raise HTTPException(404, "Meeting not found")
            meeting_status = meeting_row[1]

            if payload.name is not None:
                await cur.execute(
                    "UPDATE meetings SET name=%s WHERE id=%s",
                    (_normalize_meeting_name(payload.name), meeting_id),
                )
            if payload.summary is not None:
                await cur.execute("UPDATE meetings SET summary=%s WHERE id=%s", (payload.summary, meeting_id))
            if payload.decisions is not None:
                await cur.execute("UPDATE meetings SET decisions=%s WHERE id=%s", (json.dumps(payload.decisions, ensure_ascii=False), meeting_id))
            if payload.template_minutes is not None:
                await cur.execute("UPDATE meetings SET template_minutes=%s WHERE id=%s", (payload.template_minutes, meeting_id))
            if payload.action_items is not None:
                await cur.execute(
                    """
                    SELECT id,owner_id,owner_name,content,due_date,status,updated_after_dispatch,last_dispatched_at,progress_note
                    FROM action_items
                    WHERE meeting_id=%s
                    """,
                    (meeting_id,),
                )
                existing_rows = await cur.fetchall()
                existing_map = {str(row[0]): row for row in existing_rows}
                seen_ids = set()

                for item in payload.action_items:
                    item_id = str(item.get("id", "") or "")
                    owner_id = item.get("owner_id", "")
                    owner_name = item.get("owner_name", "")
                    content = item.get("content", "")
                    due_date = item.get("due_date", "")
                    status = item.get("status", "pending")
                    progress_note = item.get("progress_note", "")

                    if item_id and item_id in existing_map:
                        existing = existing_map[item_id]
                        seen_ids.add(item_id)
                        changed = _item_changed(existing, item)
                        updated_after_dispatch = 1 if meeting_status == "dispatched" and changed else int(existing[6] or 0)
                        await cur.execute(
                            """
                            UPDATE action_items
                            SET owner_id=%s, owner_name=%s, content=%s, due_date=%s, status=%s, progress_note=%s, updated_after_dispatch=%s
                            WHERE id=%s AND meeting_id=%s
                            """,
                            (owner_id, owner_name, content, due_date, status, progress_note, updated_after_dispatch, int(item_id), meeting_id),
                        )
                    else:
                        await cur.execute(
                            """
                            INSERT INTO action_items(meeting_id,owner_id,owner_name,content,due_date,status,progress_note,updated_after_dispatch,last_dispatched_at)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                                meeting_id,
                                owner_id,
                                owner_name,
                                content,
                                due_date,
                                status,
                                progress_note,
                                1 if meeting_status == "dispatched" else 0,
                                None,
                            ),
                        )

                for existing_id in existing_map.keys():
                    if existing_id not in seen_ids:
                        await cur.execute("DELETE FROM action_items WHERE id=%s AND meeting_id=%s", (int(existing_id), meeting_id))
    return {"ok": True}


@router.patch("/{meeting_id}")
async def update_meeting(meeting_id: str, payload: UpdateMeetingPayload, current_user: dict = Depends(get_current_user)):
    updates = []
    params = []
    if payload.name is not None:
        updates.append("name=%s")
        params.append(_normalize_meeting_name(payload.name))
    if payload.template_minutes is not None:
        updates.append("template_minutes=%s")
        params.append(payload.template_minutes)
    if not updates:
        raise HTTPException(400, "没有可更新的会议字段")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"UPDATE meetings SET {', '.join(updates)} WHERE id=%s AND user_id=%s AND is_deleted=0",
                tuple(params + [meeting_id, current_user["sub"]]),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Meeting not found")

    return {"ok": True}


@router.post("/{meeting_id}/dispatch")
async def dispatch_meeting(meeting_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    emails_sent = 0
    meeting_name = ""
    rows = []

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT name,date,summary,decisions FROM meetings WHERE id=%s AND user_id=%s AND is_deleted=0",
                (meeting_id, current_user["sub"]),
            )
            meeting_row = await cur.fetchone()
            if not meeting_row:
                raise HTTPException(status_code=404, detail="Meeting not found")

            meeting_name, _meeting_date, meeting_summary, meeting_decisions_json = meeting_row
            try:
                meeting_decisions = json.loads(meeting_decisions_json) if meeting_decisions_json else []
            except Exception:
                meeting_decisions = []

            dispatch_config = await get_dispatch_config_from_db()

            await cur.execute(
                """
                SELECT a.id, a.meeting_id, a.content, a.due_date, c.name, COALESCE(c.email, '')
                FROM action_items a
                LEFT JOIN contacts c ON a.owner_id = c.id
                WHERE a.meeting_id=%s
                """,
                (meeting_id,),
            )
            rows = await cur.fetchall()
            owner_items, synced_ids = _build_dispatch_targets(rows)

            if dispatch_config.get("email_enabled"):
                try:
                    emails_sent = await _send_grouped_task_emails(
                        owner_items,
                        meeting_name,
                        meeting_summary,
                        meeting_decisions,
                        "待办任务",
                    )
                except Exception as error:
                    raise HTTPException(status_code=500, detail=f"邮件发送失败: {str(error)}")

            await cur.execute("UPDATE meetings SET status='dispatched' WHERE id=%s", (meeting_id,))
            if synced_ids:
                placeholders = ",".join(["%s"] * len(synced_ids))
                dispatched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                await cur.execute(
                    f"UPDATE action_items SET updated_after_dispatch=0, last_dispatched_at=%s WHERE id IN ({placeholders})",
                    tuple([dispatched_at] + synced_ids),
                )

    await create_notification(
        user_id=current_user["sub"],
        title="行动项已分发",
        content=f"《{meeting_name}》已完成任务分发，涉及 {len(rows)} 条行动项，邮件 {emails_sent} 封。",
        category="dispatch",
        related_type="meeting",
        related_id=meeting_id,
    )
    return {"ok": True, "dispatched_count": len(rows), "emails_sent": emails_sent}


@router.post("/{meeting_id}/resync")
async def resync_meeting_changes(meeting_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    emails_sent = 0
    changed_count = 0
    meeting_name = ""

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT name,summary,decisions,status FROM meetings WHERE id=%s AND user_id=%s AND is_deleted=0",
                (meeting_id, current_user["sub"]),
            )
            meeting_row = await cur.fetchone()
            if not meeting_row:
                raise HTTPException(404, "Meeting not found")

            meeting_name, meeting_summary, meeting_decisions_json, meeting_status = meeting_row
            if meeting_status != "dispatched":
                raise HTTPException(400, "Meeting has not been dispatched yet")

            try:
                meeting_decisions = json.loads(meeting_decisions_json) if meeting_decisions_json else []
            except Exception:
                meeting_decisions = []

            dispatch_config = await get_dispatch_config_from_db()

            await cur.execute(
                """
                SELECT a.id, a.meeting_id, a.content, a.due_date, c.name, COALESCE(c.email, '')
                FROM action_items a
                LEFT JOIN contacts c ON a.owner_id = c.id
                WHERE a.meeting_id=%s AND a.updated_after_dispatch=1
                """,
                (meeting_id,),
            )
            rows = await cur.fetchall()
            changed_count = len(rows)
            if changed_count == 0:
                return {"ok": True, "emails_sent": 0, "changed_count": 0}

            owner_items, synced_ids = _build_dispatch_targets(rows)

            if dispatch_config.get("email_enabled"):
                try:
                    emails_sent = await _send_grouped_task_emails(
                        owner_items,
                        meeting_name,
                        meeting_summary,
                        meeting_decisions,
                        "任务变更同步",
                    )
                except Exception as error:
                    raise HTTPException(status_code=500, detail=f"变更邮件发送失败: {str(error)}")

            if synced_ids:
                placeholders = ",".join(["%s"] * len(synced_ids))
                dispatched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                await cur.execute(
                    f"UPDATE action_items SET updated_after_dispatch=0, last_dispatched_at=%s WHERE id IN ({placeholders})",
                    tuple([dispatched_at] + synced_ids),
                )

    await create_notification(
        user_id=current_user["sub"],
        title="行动项变更已同步",
        content=f"《{meeting_name}》已同步 {changed_count} 条变更任务，邮件 {emails_sent} 封。",
        category="dispatch",
        related_type="meeting",
        related_id=meeting_id,
    )
    return {"ok": True, "emails_sent": emails_sent, "changed_count": changed_count}


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE meetings SET is_deleted=1, deleted_at=NOW() WHERE id=%s AND user_id=%s AND is_deleted=0",
                (meeting_id, current_user["sub"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Meeting not found")
    return {"ok": True}
