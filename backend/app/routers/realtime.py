import asyncio
import json
import logging
import time
import uuid
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings
from app.database import get_pool
from app.routers.auth import get_current_user
from app.services.notifications import create_notification
from app.services.tingwu_realtime import (
    RealtimeWavRecorder,
    TingwuRealtimeClient,
    TingwuRealtimeError,
    create_realtime_task,
    normalize_realtime_event,
    stop_realtime_task,
)

router = APIRouter()
logger = logging.getLogger("uvicorn.error")
_active_users: set[str] = set()
_active_users_lock = asyncio.Lock()
_SUPPORTED_LANGUAGES = {"cn", "en", "yue", "ja", "ko", "multilingual"}
_SUPPORTED_HINTS = {"cn", "en", "yue", "ja", "ko", "de", "fr", "ru"}
_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_available() -> None:
    if not settings.transcription_enabled:
        raise HTTPException(503, "当前部署已关闭转写功能。")
    if not settings.tingwu_enabled:
        raise HTTPException(503, "实时转写需要启用 TINGWU_ENABLED。")
    if not settings.tingwu_access_key_id or not settings.tingwu_access_key_secret or not settings.tingwu_app_key:
        raise HTTPException(503, "实时转写缺少听悟 AccessKey 或 AppKey 配置。")


@router.post("/ticket")
async def create_realtime_ticket(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(401, "未授权")
    _ensure_available()
    expires_at = datetime.utcnow() + timedelta(minutes=2)
    ticket = jwt.encode(
        {"sub": current_user["sub"], "scope": "tingwu_realtime", "exp": expires_at},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return {"ticket": ticket, "expires_in": 120}


def _decode_ticket(ticket: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(ticket, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("scope") != "tingwu_realtime" or not payload.get("sub"):
        return None
    return payload


def _parse_start_message(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("启动消息必须是 JSON。") from exc
    if not isinstance(payload, dict) or payload.get("type") != "start":
        raise ValueError("首条消息必须是 start。")

    meeting_name = str(payload.get("name") or "").strip()
    if not meeting_name:
        meeting_name = f"实时会议 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    meeting_name = meeting_name[:255]

    source_language = str(payload.get("source_language") or "cn").strip().lower()
    if source_language not in _SUPPORTED_LANGUAGES:
        raise ValueError("不支持的识别语言。")

    raw_hints = payload.get("language_hints")
    language_hints = []
    if isinstance(raw_hints, list):
        language_hints = [str(item).lower() for item in raw_hints if str(item).lower() in _SUPPORTED_HINTS]
    if source_language == "multilingual" and not language_hints:
        language_hints = ["cn", "en"]

    try:
        speaker_count = int(payload.get("speaker_count", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("说话人数必须是整数。") from exc
    if speaker_count < 0 or speaker_count > 100:
        raise ValueError("说话人数必须在 0 到 100 之间。")

    return {
        "meeting_name": meeting_name,
        "source_language": source_language,
        "language_hints": language_hints,
        "speaker_count": speaker_count,
    }


async def _create_meeting(meeting_id: str, meeting_name: str, user_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO meetings(id, name, date, duration_sec, task_count, status, audio_url, summary, decisions, user_id)
                VALUES(%s, %s, %s, 0, 0, 'processing', NULL, %s, '[]', %s)
                """,
                (
                    meeting_id,
                    meeting_name,
                    date.today().strftime("%Y-%m-%d"),
                    "实时记录进行中，结束后可查看完整逐字稿。",
                    user_id,
                ),
            )


async def _persist_final_segment(meeting_id: str, event: dict[str, Any]) -> None:
    text = str(event.get("text") or "").strip()
    if not text:
        return
    index = int(event.get("index") or 0)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM transcripts WHERE meeting_id=%s AND segment_no=%s LIMIT 1",
                (meeting_id, index),
            )
            row = await cur.fetchone()
            values = (
                int(event.get("start_ms") or 0),
                int(event.get("end_ms") or 0),
                str(event.get("speaker") or "SPEAKER_00")[:64],
                text,
            )
            if row:
                await cur.execute(
                    """
                    UPDATE transcripts
                    SET start_ms=%s, end_ms=%s, speaker=%s, text=%s
                    WHERE id=%s
                    """,
                    (*values, row[0]),
                )
            else:
                await cur.execute(
                    """
                    INSERT INTO transcripts(meeting_id, start_ms, end_ms, speaker, confidence, segment_no, text)
                    VALUES(%s, %s, %s, %s, NULL, %s, %s)
                    """,
                    (meeting_id, values[0], values[1], values[2], index, values[3]),
                )


async def _finish_meeting(
    meeting_id: str,
    user_id: str,
    meeting_name: str,
    *,
    audio_url: str | None = None,
    audio_duration_ms: int = 0,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COALESCE(MAX(end_ms), 0), COUNT(*) FROM transcripts WHERE meeting_id=%s",
                (meeting_id,),
            )
            max_end_ms, segment_count = await cur.fetchone()
            duration_ms = max(int(max_end_ms or 0), max(0, int(audio_duration_ms)))
            summary = (
                "实时转写已完成，请点击 AI 分析生成会议摘要。"
                if segment_count
                else "实时记录已结束，未识别到有效语音内容。"
            )
            await cur.execute(
                """
                UPDATE meetings
                SET duration_sec=%s, status='ready_for_review', summary=%s,
                    audio_url=COALESCE(%s, audio_url)
                WHERE id=%s AND user_id=%s
                """,
                ((duration_ms + 999) // 1000, summary, audio_url, meeting_id, user_id),
            )
    await create_notification(
        user_id=user_id,
        title="实时转写已完成",
        content=f"《{meeting_name}》已生成实时逐字稿，可以进入会议详情继续整理。",
        category="meeting",
        related_type="meeting",
        related_id=meeting_id,
    )


@router.websocket("/ws")
async def realtime_transcription_socket(websocket: WebSocket):
    ticket_payload = _decode_ticket(websocket.query_params.get("ticket", ""))
    if not ticket_payload:
        await websocket.close(code=4401, reason="实时转写凭证无效或已过期")
        return

    user_id = str(ticket_payload["sub"])
    await websocket.accept()

    try:
        _ensure_available()
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "message": str(exc.detail)})
        await websocket.close(code=1011)
        return

    async with _active_users_lock:
        if user_id in _active_users:
            await websocket.send_json({"type": "error", "message": "你已有一场实时记录正在进行。"})
            await websocket.close(code=4409)
            return
        _active_users.add(user_id)

    sdk_client: TingwuRealtimeClient | None = None
    task_id = ""
    meeting_id = ""
    meeting_name = ""
    cloud_created = False
    meeting_created = False
    stopped_cleanly = False
    event_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    forward_task: asyncio.Task | None = None
    audio_recorder: RealtimeWavRecorder | None = None
    audio_url: str | None = None
    audio_duration_ms = 0
    started_at = time.monotonic()
    loop = asyncio.get_running_loop()

    def emit(kind: str, message: str) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, (kind, message))

    async def forward_events() -> None:
        while True:
            kind, raw_message = await event_queue.get()
            try:
                event = normalize_realtime_event(kind, raw_message)
                if kind == "final" and meeting_id:
                    try:
                        await _persist_final_segment(meeting_id, event)
                    except Exception:
                        logger.exception("[TINGWU_REALTIME] failed to persist segment meeting_id=%s", meeting_id)
                try:
                    await websocket.send_json(event)
                except (RuntimeError, WebSocketDisconnect):
                    pass
            finally:
                event_queue.task_done()

    try:
        first_message = await asyncio.wait_for(websocket.receive_text(), timeout=15)
        options = _parse_start_message(first_message)
        meeting_name = options["meeting_name"]

        realtime_task = await asyncio.to_thread(
            create_realtime_task,
            source_language=options["source_language"],
            language_hints=options["language_hints"],
            speaker_count=options["speaker_count"],
        )
        task_id = realtime_task.task_id
        cloud_created = True

        sdk_client = TingwuRealtimeClient(realtime_task.meeting_join_url, emit)
        await asyncio.to_thread(sdk_client.start)

        meeting_id = str(uuid.uuid4())[:8]
        await _create_meeting(meeting_id, meeting_name, user_id)
        meeting_created = True
        audio_path = _UPLOAD_DIR / f"realtime_{meeting_id}.wav"
        audio_recorder = RealtimeWavRecorder(audio_path)
        audio_url = f"/uploads/{audio_path.name}"
        forward_task = asyncio.create_task(forward_events())
        await websocket.send_json(
            {
                "type": "ready",
                "meeting_id": meeting_id,
                "sample_rate": 16000,
                "format": "pcm_s16le",
            }
        )

        while True:
            message = await websocket.receive()
            message_type = message.get("type")
            if message_type == "websocket.disconnect":
                break
            audio = message.get("bytes")
            if audio is not None:
                if len(audio) > 128 * 1024:
                    await websocket.send_json({"type": "warning", "message": "音频帧过大，已忽略。"})
                    continue
                audio_recorder.write(audio)
                sdk_client.send_audio(audio)
                continue

            text_message = message.get("text")
            if not text_message:
                continue
            try:
                command = json.loads(text_message)
            except json.JSONDecodeError:
                continue
            if command.get("type") == "stop":
                await asyncio.to_thread(sdk_client.stop)
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(event_queue.join(), timeout=3)
                stopped_cleanly = True
                break
            if command.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except (ValueError, TingwuRealtimeError, asyncio.TimeoutError) as exc:
        logger.warning("[TINGWU_REALTIME] session rejected user=%s error=%s", user_id, exc)
        with suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(exc)})
    except Exception as exc:
        logger.exception("[TINGWU_REALTIME] unexpected session error user=%s", user_id)
        with suppress(Exception):
            await websocket.send_json({"type": "error", "message": f"实时转写异常：{exc}"})
    finally:
        if sdk_client and not stopped_cleanly:
            with suppress(Exception):
                await asyncio.to_thread(sdk_client.stop)
        if sdk_client:
            sdk_client.shutdown()
        if cloud_created and task_id:
            try:
                await asyncio.to_thread(stop_realtime_task, task_id)
            except Exception:
                logger.exception("[TINGWU_REALTIME] failed to stop cloud task task_id=%s", task_id)
        if forward_task:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(event_queue.join(), timeout=3)
            forward_task.cancel()
            with suppress(asyncio.CancelledError):
                await forward_task
        if audio_recorder:
            audio_duration_ms = audio_recorder.duration_ms
            try:
                audio_recorder.close()
            except Exception:
                audio_url = None
                logger.exception("[TINGWU_REALTIME] failed to finalize audio meeting_id=%s", meeting_id)
        if meeting_created and meeting_id:
            try:
                await _finish_meeting(
                    meeting_id,
                    user_id,
                    meeting_name,
                    audio_url=audio_url if audio_duration_ms > 0 else None,
                    audio_duration_ms=audio_duration_ms,
                )
                with suppress(Exception):
                    await websocket.send_json(
                        {
                            "type": "session_completed",
                            "meeting_id": meeting_id,
                            "duration_sec": max(0, int(time.monotonic() - started_at)),
                        }
                    )
            except Exception:
                logger.exception("[TINGWU_REALTIME] failed to finalize meeting_id=%s", meeting_id)
        with suppress(Exception):
            await websocket.close()
        async with _active_users_lock:
            _active_users.discard(user_id)
