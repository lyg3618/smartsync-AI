"""Realtime transcription support for Alibaba Cloud Tingwu.

The OpenAPI calls create and stop the realtime record. Audio streaming itself is
handled by the official ``nls.NlsRealtimeMeeting`` SDK, using the
``MeetingJoinUrl`` returned by CreateTask.
"""

from __future__ import annotations

import json
import logging
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx

from app.config import settings
from app.services.tingwu import (
    TINGWU_ENDPOINT,
    TingwuError,
    _get_credentials,
    _sign_request,
)

logger = logging.getLogger("uvicorn.error")


class TingwuRealtimeError(TingwuError):
    pass


class RealtimeWavRecorder:
    """Persist the exact PCM stream sent to Tingwu as a browser-playable WAV."""

    def __init__(
        self,
        path: str | Path,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        self.path = Path(path)
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.bytes_written = 0
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = wave.open(str(self.path), "wb")
        self._writer.setnchannels(channels)
        self._writer.setsampwidth(sample_width)
        self._writer.setframerate(sample_rate)

    @property
    def duration_ms(self) -> int:
        bytes_per_second = self.sample_rate * self.channels * self.sample_width
        if bytes_per_second <= 0:
            return 0
        return self.bytes_written * 1000 // bytes_per_second

    def write(self, data: bytes) -> None:
        if self._closed:
            raise TingwuRealtimeError("实时录音文件已经关闭。")
        if not data:
            return
        frame_width = self.channels * self.sample_width
        if len(data) % frame_width:
            raise TingwuRealtimeError("收到的 PCM 音频帧不完整，无法保存原录音。")
        self._writer.writeframesraw(data)
        self.bytes_written += len(data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._writer.close()


@dataclass(frozen=True)
class RealtimeTask:
    task_id: str
    meeting_join_url: str


def build_realtime_task_body(
    *,
    source_language: str = "cn",
    language_hints: list[str] | None = None,
    speaker_count: int = 0,
) -> dict[str, Any]:
    _, _, app_key = _get_credentials()
    input_data: dict[str, Any] = {
        "Format": "pcm",
        "SampleRate": 16000,
        "SourceLanguage": source_language,
        "TaskKey": uuid4().hex,
    }
    if source_language == "multilingual" and language_hints:
        input_data["LanguageHints"] = language_hints

    return {
        "AppKey": app_key,
        "Input": input_data,
        "Parameters": {
            "Transcription": {
                "OutputLevel": 2,
                "DiarizationEnabled": True,
                "Diarization": {"SpeakerCount": speaker_count},
            },
            "AutoChaptersEnabled": False,
            "MeetingAssistanceEnabled": False,
            "SummarizationEnabled": False,
            "TextPolishEnabled": False,
        },
    }


def create_realtime_task(
    *,
    source_language: str = "cn",
    language_hints: list[str] | None = None,
    speaker_count: int = 0,
) -> RealtimeTask:
    ak, sk, _ = _get_credentials()
    body = build_realtime_task_body(
        source_language=source_language,
        language_hints=language_hints,
        speaker_count=speaker_count,
    )
    query = {"type": "realtime"}
    headers, body_bytes, _ = _sign_request(
        method="PUT",
        path="/openapi/tingwu/v2/tasks",
        query_params=query,
        body=body,
        ak=ak,
        sk=sk,
        action="CreateTask",
    )

    try:
        with httpx.Client(timeout=30) as client:
            response = client.put(
                f"{TINGWU_ENDPOINT}/openapi/tingwu/v2/tasks?type=realtime",
                content=body_bytes,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise TingwuRealtimeError(f"创建实时记录失败：{exc}") from exc

    try:
        payload = response.json()
    except Exception as exc:
        raise TingwuRealtimeError(f"听悟返回了无法解析的响应：{response.text[:400]}") from exc

    if response.status_code >= 400:
        raise TingwuRealtimeError(
            f"创建实时记录失败（HTTP {response.status_code}）："
            f"{payload.get('Message', payload)}"
        )

    data = payload.get("Data") or {}
    task_id = str(data.get("TaskId") or "").strip()
    meeting_join_url = str(data.get("MeetingJoinUrl") or "").strip()
    if not task_id or not meeting_join_url.startswith("wss://"):
        raise TingwuRealtimeError(f"听悟响应缺少 TaskId 或 MeetingJoinUrl：{payload}")
    return RealtimeTask(task_id=task_id, meeting_join_url=meeting_join_url)


def stop_realtime_task(task_id: str) -> None:
    ak, sk, _ = _get_credentials()
    body = {"Input": {"TaskId": task_id}}
    query = {"operation": "stop", "type": "realtime"}
    headers, body_bytes, _ = _sign_request(
        method="PUT",
        path="/openapi/tingwu/v2/tasks",
        query_params=query,
        body=body,
        ak=ak,
        sk=sk,
        action="CreateTask",
    )

    try:
        with httpx.Client(timeout=30) as client:
            response = client.put(
                f"{TINGWU_ENDPOINT}/openapi/tingwu/v2/tasks?operation=stop&type=realtime",
                content=body_bytes,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise TingwuRealtimeError(f"结束实时记录失败：{exc}") from exc

    try:
        payload = response.json()
    except Exception as exc:
        raise TingwuRealtimeError(f"结束实时记录时收到无法解析的响应：{response.text[:400]}") from exc
    if response.status_code >= 400:
        raise TingwuRealtimeError(
            f"结束实时记录失败（HTTP {response.status_code}）："
            f"{payload.get('Message', payload)}"
        )


def _number(payload: dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return default


def _speaker_label(payload: dict[str, Any]) -> str:
    raw = next(
        (
            payload.get(key)
            for key in ("speaker_id", "speakerId", "speaker", "SpeakerId")
            if payload.get(key) not in (None, "")
        ),
        "00",
    )
    value = str(raw).strip() or "00"
    if re.match(r"^SPEAKER_", value, re.I):
        return value.upper()
    return f"SPEAKER_{value.zfill(2)}"


def _stash_text(payload: dict[str, Any]) -> str:
    stash = payload.get("stash_result") or payload.get("stashResult") or payload.get("stash_result_text")
    if isinstance(stash, dict):
        stash = stash.get("text") or stash.get("result")
    return str(stash or "").strip()


def normalize_realtime_event(kind: str, message: str | dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(message) if isinstance(message, str) else message
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    header = data.get("header") if isinstance(data.get("header"), dict) else {}
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

    base = {
        "type": kind,
        "name": header.get("name") or kind,
        "status": header.get("status"),
        "status_text": header.get("status_text") or "",
    }
    if kind not in {"partial", "final"}:
        return base

    result = str(payload.get("result") or payload.get("text") or "").strip()
    stash = _stash_text(payload)
    if stash and stash not in result:
        result = f"{result}{stash}"

    words = payload.get("words") if isinstance(payload.get("words"), list) else []
    word_start = 0
    word_end = 0
    if words:
        first = words[0] if isinstance(words[0], dict) else {}
        last = words[-1] if isinstance(words[-1], dict) else {}
        word_start = _number(first, "startTime", "start_time", "start")
        word_end = _number(last, "endTime", "end_time", "end")

    end_ms = _number(payload, "time", "end_time", "endTime", default=word_end)
    start_ms = _number(
        payload,
        "begin_time",
        "sentence_begin_time",
        "beginTime",
        default=word_start,
    )
    if end_ms < start_ms:
        end_ms = start_ms

    return {
        **base,
        "index": _number(payload, "index", default=0),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "speaker": _speaker_label(payload),
        "text": result,
        "words": words,
    }


class TingwuRealtimeClient:
    """Small adapter around the official SDK with normalized callback names."""

    def __init__(self, meeting_join_url: str, emit: Callable[[str, str], None]):
        try:
            import nls
        except ImportError as exc:
            raise TingwuRealtimeError(
                "缺少阿里云 nls 实时转写 SDK，请安装 requirements 中的 nls 1.1.0。"
            ) from exc

        self._client = nls.NlsRealtimeMeeting(
            url=meeting_join_url,
            on_start=lambda message, *_: emit("started", message),
            on_sentence_begin=lambda message, *_: emit("sentence_begin", message),
            on_sentence_end=lambda message, *_: emit("final", message),
            on_result_changed=lambda message, *_: emit("partial", message),
            on_result_translated=lambda message, *_: emit("translated", message),
            on_completed=lambda message, *_: emit("completed", message),
            on_error=lambda message, *_: emit("error", message),
            on_close=lambda *_: emit("closed", "{}"),
        )

    def start(self) -> None:
        self._client.start(timeout=15, ping_interval=8)

    def send_audio(self, data: bytes) -> None:
        self._client.send_audio(data)

    def stop(self) -> None:
        self._client.stop(timeout=15)

    def shutdown(self) -> None:
        try:
            self._client.shutdown()
        except Exception:
            logger.debug("Tingwu realtime SDK shutdown ignored", exc_info=True)
