import os
import uuid
import logging
from pathlib import Path
from urllib.parse import quote
from datetime import date
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.config import settings
from app.database import get_pool
from app.routers.auth import get_current_user
from app.services.local_asr import LocalTranscriptionError
from app.services.notifications import create_notification
from app.services.transcription import run_transcription
from app.services.transcription_types import TranscriptSegment

router = APIRouter()
logger = logging.getLogger("uvicorn.error")
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _build_public_upload_url(file_path: Path) -> str:
    return f"/uploads/{quote(file_path.name)}"


async def _update_task(task_id: str, status: str, progress: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE upload_tasks SET status=%s, progress=%s WHERE id=%s",
                (status, progress, task_id),
            )


async def _persist_transcription_result(
    meeting_id: str,
    meeting_name: str,
    segments: list[TranscriptSegment],
    user_id: str,
    audio_url: str,
) -> None:
    today = date.today().strftime("%Y-%m-%d")
    duration_sec = int(max((seg.end_ms for seg in segments), default=0) / 1000)
    summary = "转写已完成，请点击 AI 分析生成会议摘要。"

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO meetings(id, name, date, duration_sec, task_count, status, audio_url, summary, decisions, user_id)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (meeting_id, meeting_name, today, duration_sec, 0, "ready_for_review", audio_url, summary, "[]", user_id),
            )

            for seg in segments:
                await cur.execute(
                    """
                    INSERT INTO transcripts(meeting_id, start_ms, end_ms, speaker, confidence, segment_no, text)
                    VALUES(%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (meeting_id, seg.start_ms, seg.end_ms, seg.speaker, seg.confidence, seg.segment_no, seg.text),
                )


async def _process_transcription(
    task_id: str,
    meeting_id: str,
    meeting_name: str,
    audio_source: str,
    source_kind: str,
    audio_url: str,
    user_id: str,
) -> None:
    try:
        logger.info(
            "[TRANSCRIPTION_JOB] start provider=%s task_id=%s meeting_id=%s meeting_name=%s",
            settings.asr_provider,
            task_id,
            meeting_id,
            meeting_name,
        )
        await _update_task(task_id, "queued", 20)

        async def _on_status(task_status: str) -> None:
            progress_map = {
                "PREPARING": 25,
                "TRANSCRIBING": 45,
                "EMBEDDING": 65,
                "CLUSTERING": 75,
                "MERGING": 85,
                "PENDING": 30,
                "PROCESSING": 60,
                "COMPLETED": 85,
                "SUCCESS": 85,
                "FAILED": 100,
                "CANCELED": 100,
                "TIME_EXPIRED": 100,
                "INVALID": 100,
            }
            await _update_task(task_id, task_status, progress_map.get(task_status, 50))

        segments = await run_transcription(
            audio_source=audio_source,
            source_kind=source_kind,
            file_name=meeting_name,
            on_status=_on_status,
        )
        await _update_task(task_id, "persisting", 90)
        await _persist_transcription_result(
            meeting_id=meeting_id,
            meeting_name=meeting_name,
            segments=segments,
            user_id=user_id,
            audio_url=audio_url,
        )
        await _update_task(task_id, "ready_for_review", 100)
        await create_notification(
            user_id=user_id,
            title="会议转写完成",
            content=f"《{meeting_name}》已完成转写并可进入确认。",
            category="meeting",
            related_type="meeting",
            related_id=meeting_id,
        )
        logger.info("[TRANSCRIPTION_JOB] success task_id=%s segments=%s", task_id, len(segments))
    except LocalTranscriptionError as exc:
        logger.exception("[TRANSCRIPTION_JOB] local_error task_id=%s", task_id)
        await _update_task(task_id, "failed", 100)
        await create_notification(
            user_id=user_id,
            title="会议转写失败",
            content=f"《{meeting_name}》本地转写失败：{exc}",
            category="warning",
            related_type="meeting",
            related_id=meeting_id,
        )
    except Exception as exc:
        logger.exception("[TRANSCRIPTION_JOB] unexpected_error task_id=%s", task_id)
        await _update_task(task_id, "failed", 100)
        await create_notification(
            user_id=user_id,
            title="会议处理异常",
            content=f"《{meeting_name}》处理异常：{exc}",
            category="warning",
            related_type="meeting",
            related_id=meeting_id,
        )


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    if not settings.transcription_enabled:
        raise HTTPException(503, "Transcription is disabled in this deployment.")
    if not file and not url:
        raise HTTPException(400, "Provide either file or url.")
    if file and url:
        raise HTTPException(400, "Provide file or url, not both.")
    if settings.asr_provider == "tingwu" and not settings.tingwu_enabled:
        raise HTTPException(400, "TINGWU is disabled. Set `ASR_PROVIDER=local` or enable Tingwu in backend .env")

    task_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())[:8]

    audio_source = ""
    source_kind = "file"
    meeting_name = (name or "").strip()
    audio_url = ""

    if file:
        meeting_name = meeting_name or file.filename or "local-audio"
        save_path = UPLOAD_DIR / f"{task_id}_{file.filename}"
        async with aiofiles.open(save_path, "wb") as f_out:
            await f_out.write(await file.read())
        audio_source = str(save_path)
        audio_url = _build_public_upload_url(save_path)
    else:
        meeting_name = meeting_name or "online-audio"
        audio_source = (url or "").strip()
        audio_url = audio_source
        source_kind = "url"

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO upload_tasks(id,meeting_id,status,progress) VALUES(%s,%s,%s,%s)",
                (task_id, meeting_id, "uploading", 10),
            )

    background_tasks.add_task(
        _process_transcription,
        task_id,
        meeting_id,
        meeting_name,
        audio_source,
        source_kind,
        audio_url,
        current_user["sub"],
    )
    return {"task_id": task_id, "meeting_id": meeting_id}
