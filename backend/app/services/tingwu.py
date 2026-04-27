"""
Alibaba Cloud Tingwu Audio Transcription Service
Uses ACS3-HMAC-SHA256 signing (v3) manually with httpx – does NOT use
alibabacloud-tea-openapi SDK which generates ACS2 signatures and fails
against the Tingwu endpoint.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

import httpx

from app.config import settings
from app.services.transcription_types import TranscriptSegment

logger = logging.getLogger("uvicorn.error")

TINGWU_HOST = "tingwu.cn-beijing.aliyuncs.com"
TINGWU_ENDPOINT = f"https://{TINGWU_HOST}"


class TingwuError(RuntimeError):
    pass

# ---------------------------------------------------------------------------
# ACS3-HMAC-SHA256 Signer
# ---------------------------------------------------------------------------

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _build_authorization(
    ak: str,
    sk: str,
    method: str,
    canonical_uri: str,
    query_str: str,
    headers: dict,
    body_bytes: bytes,
    date_utc: str,
) -> str:
    """
    Implements Alibaba Cloud ACS3-HMAC-SHA256 request signing:
    https://www.alibabacloud.com/help/en/sdk/developer-reference/request-signature-v3
    """
    # 1. Canonical headers – must be sorted, lower-cased
    signed_header_names = sorted(k.lower() for k in headers)
    canonical_headers = "".join(
        f"{k}:{headers[list(headers.keys())[[kk.lower() for kk in headers.keys()].index(k)]].strip()}\n"
        for k in signed_header_names
    )
    signed_headers_str = ";".join(signed_header_names)

    # 2. Hashed payload
    hashed_payload = _sha256_hex(body_bytes)

    # 3. Canonical request
    canonical_request = "\n".join([
        method.upper(),
        canonical_uri,
        query_str,
        canonical_headers,
        signed_headers_str,
        hashed_payload,
    ])

    # 4. StringToSign
    hashed_canon = _sha256_hex(canonical_request.encode("utf-8"))
    string_to_sign = f"ACS3-HMAC-SHA256\n{hashed_canon}"

    # 5. Signature
    signature = hmac.new(
        sk.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return (
        f"ACS3-HMAC-SHA256 "
        f"Credential={ak},"
        f"SignedHeaders={signed_headers_str},"
        f"Signature={signature}"
    )


def _sign_request(
    method: str,
    path: str,
    query_params: dict,
    body: Any,
    ak: str,
    sk: str,
    action: str,
) -> dict:
    """Return signed headers ready to attach to the HTTP request."""
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else b""
    nonce = uuid4().hex
    now = datetime.now(timezone.utc)
    date_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Query string – sorted
    query_str = "&".join(
        f"{k}={v}" for k, v in sorted(query_params.items())
    )

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "host": TINGWU_HOST,
        "x-acs-action": action,
        "x-acs-content-sha256": _sha256_hex(body_bytes),
        "x-acs-credentials-provider": "static_ak",
        "x-acs-date": date_utc,
        "x-acs-signature-nonce": nonce,
        "x-acs-version": "2023-09-30",
    }
    auth = _build_authorization(
        ak=ak,
        sk=sk,
        method=method,
        canonical_uri=path,
        query_str=query_str,
        headers=headers,
        body_bytes=body_bytes,
        date_utc=date_utc,
    )
    headers["Authorization"] = auth
    return headers, body_bytes, query_str


# ---------------------------------------------------------------------------
# API calls (sync, run in thread)
# ---------------------------------------------------------------------------

def _get_credentials():
    ak = (settings.tingwu_access_key_id or "").strip()
    sk = (settings.tingwu_access_key_secret or "").strip()
    app_key = (settings.tingwu_app_key or "").strip()
    if not ak or not sk:
        raise TingwuError("TINGWU_ACCESS_KEY_ID / TINGWU_ACCESS_KEY_SECRET not set.")
    if not app_key:
        raise TingwuError("TINGWU_APP_KEY not set.")
    ak_hint = f"{ak[:6]}...{ak[-4:]}" if len(ak) >= 10 else "<invalid>"
    sk_fp = hashlib.sha256(sk.encode()).hexdigest()[:12]
    logger.info("[TINGWU_AUTH] ak=%s sk_fp=%s endpoint=%s", ak_hint, sk_fp, TINGWU_HOST)
    return ak, sk, app_key


def _submit_task_sync(audio_url: str, file_name: str) -> str:
    ak, sk, app_key = _get_credentials()

    body = {
        "AppKey": app_key,
        "Input": {
            "SourceLanguage": "cn",
            "TaskKey": uuid4().hex,
            "FileName": file_name,
            "FileUrl": audio_url,
        },
        "Parameters": {
            "Transcription": {
                "DiarizationEnabled": True,
                "Diarization": {"SpeakerCount": 0},
            },
        },
    }

    headers, body_bytes, query_str = _sign_request(
        method="PUT",
        path="/openapi/tingwu/v2/tasks",
        query_params={"type": "offline"},
        body=body,
        ak=ak,
        sk=sk,
        action="CreateTask",
    )

    with httpx.Client(timeout=30) as client:
        resp = client.put(
            f"{TINGWU_ENDPOINT}/openapi/tingwu/v2/tasks?type=offline",
            content=body_bytes,
            headers=headers,
        )

    logger.info("[TINGWU_SUBMIT] status=%s body=%s", resp.status_code, resp.text[:500])
    try:
        data = resp.json()
    except Exception:
        raise TingwuError(f"Cannot parse Tingwu response: {resp.text[:400]}")

    if resp.status_code >= 400:
        code = data.get("Code", "")
        msg = data.get("Message", str(data))
        if "SignatureDoesNotMatch" in code or "SignatureDoesNotMatch" in msg:
            raise TingwuError(
                "SignatureDoesNotMatch – verify TINGWU_ACCESS_KEY_ID + TINGWU_ACCESS_KEY_SECRET "
                f"are correct and have no trailing spaces. AK hint: {ak[:6]}..."
            )
        raise TingwuError(f"SubmitTask HTTP {resp.status_code}: {msg}")

    task_id = data.get("Data", {}).get("TaskId")
    if not task_id:
        raise TingwuError(f"No TaskId in response: {data}")
    return task_id


def _query_task_sync(task_id: str) -> dict:
    ak, sk, app_key = _get_credentials()
    path = f"/openapi/tingwu/v2/tasks/{task_id}"
    headers, _, _ = _sign_request(
        method="GET",
        path=path,
        query_params={},
        body=None,
        ak=ak,
        sk=sk,
        action="GetTaskInfo",
    )

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{TINGWU_ENDPOINT}{path}",
            headers=headers,
        )

    try:
        data = resp.json()
    except Exception:
        raise TingwuError(f"Cannot parse Tingwu query response: {resp.text[:400]}")

    if resp.status_code >= 400:
        raise TingwuError(f"GetTaskInfo HTTP {resp.status_code}: {data.get('Message', data)}")

    return data.get("Data", {})


# ---------------------------------------------------------------------------
# Segment extraction helpers
# ---------------------------------------------------------------------------

def _as_ms(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, float):
        # Float implies seconds
        return int(value * 1000)
    if isinstance(value, int):
        # Integer implies milliseconds (Tingwu standard)
        return value
    if isinstance(value, str):
        try:
            if "." in value:
                # String with dot implies float (seconds)
                return int(float(value) * 1000)
            return int(value)
        except ValueError:
            return 0
    return 0


def _iter_dict_nodes(root: Any):
    stack = [root]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for item in cur:
                if isinstance(item, (dict, list)):
                    stack.append(item)


def _extract_segments_from_transcription_payload(payload: Any) -> list[TranscriptSegment]:
    """Parse the Tingwu official Transcription JSON structure."""
    transcription = payload.get("Transcription") if isinstance(payload, dict) else None
    if not isinstance(transcription, dict):
        return []
    paragraphs = transcription.get("Paragraphs")
    if not isinstance(paragraphs, list):
        return []

    segments: list[TranscriptSegment] = []
    for para in paragraphs:
        if not isinstance(para, dict):
            continue
        speaker_id = str(para.get("SpeakerId", "00")).strip() or "00"
        speaker = speaker_id if re.match(r"^SPEAKER_", speaker_id, re.I) else f"SPEAKER_{speaker_id.zfill(2)}"
        words = para.get("Words", [])
        if not words:
            continue
        start_ms = None
        end_ms = None
        text_parts: list[str] = []
        for w in words:
            if not isinstance(w, dict):
                continue
            if start_ms is None and "Start" in w:
                start_ms = _as_ms(w["Start"])
            if "End" in w:
                end_ms = _as_ms(w["End"])
            t = w.get("Text")
            if isinstance(t, str) and t.strip():
                text_parts.append(t.strip())
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            continue
        text = "".join(text_parts).strip()
        if not text:
            continue
        segments.append(TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text, speaker=speaker))

    segments.sort(key=lambda x: (x.start_ms, x.end_ms))
    return segments


def _extract_segments_fallback(payload: Any) -> list[TranscriptSegment]:
    """Fallback: walk all dict nodes looking for text + time fields."""
    text_keys = ["Text", "text", "Sentence", "Content", "content"]
    start_keys = ["StartTime", "BeginTime", "StartMs", "Start", "start"]
    end_keys = ["EndTime", "EndMs", "End", "end"]
    speaker_keys = ["SpeakerId", "Speaker", "speaker"]
    segments = []
    for node in _iter_dict_nodes(payload):
        text = next((node[k].strip() for k in text_keys if k in node and isinstance(node[k], str) and node[k].strip()), "")
        if not text:
            continue
        start_raw = next((node[k] for k in start_keys if k in node), None)
        end_raw = next((node[k] for k in end_keys if k in node), None)
        if start_raw is None or end_raw is None:
            continue
        start_ms = _as_ms(start_raw)
        end_ms = _as_ms(end_raw)
        if end_ms <= start_ms:
            continue
        speaker_raw = next((str(node[k]).strip() for k in speaker_keys if k in node and str(node[k]).strip()), "00")
        speaker = speaker_raw if re.match(r"^SPEAKER_", speaker_raw, re.I) else f"SPEAKER_{speaker_raw}"
        segments.append(TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text, speaker=speaker))
    segments.sort(key=lambda x: (x.start_ms, x.end_ms))
    return segments


async def _load_json_url(url: str) -> Any:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _extract_result_urls(payload: Any) -> list[str]:
    urls: list[str] = []
    for node in _iter_dict_nodes(payload):
        for v in node.values():
            if isinstance(v, str) and v.startswith(("http://", "https://")):
                urls.append(v)
    return urls


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_tingwu_transcription(
    audio_url: str,
    file_name: str,
    on_status: Optional[Callable[[str], Awaitable[None] | None]] = None,
) -> list[TranscriptSegment]:
    logger.info("[TINGWU] submit start file_name=%s audio_url=%.120s", file_name, audio_url)
    task_id = await asyncio.to_thread(_submit_task_sync, audio_url, file_name)
    logger.info("[TINGWU] submit ok task_id=%s", task_id)

    timeout_at = asyncio.get_running_loop().time() + settings.tingwu_poll_timeout_sec
    last_status = ""

    while True:
        data = await asyncio.to_thread(_query_task_sync, task_id)
        status = str(data.get("TaskStatus", "")).upper()
        snapshot = {k: data.get(k) for k in ("TaskStatus", "StatusText", "Code", "Message")}
        logger.info("[TINGWU_POLL] task_id=%s status=%s snap=%s", task_id, status, json.dumps(snapshot, ensure_ascii=False))

        if status != last_status:
            last_status = status
            if on_status:
                maybe = on_status(status)
                if asyncio.iscoroutine(maybe):
                    await maybe

        if status in {"COMPLETED", "SUCCESS"}:
            # Try structured parse first
            segs = _extract_segments_from_transcription_payload(data)
            if segs:
                return segs
            # Then walk result JSON URLs
            for url in _extract_result_urls(data):
                try:
                    payload = await _load_json_url(url)
                    segs = _extract_segments_from_transcription_payload(payload)
                    if segs:
                        return segs
                    segs = _extract_segments_fallback(payload)
                    if segs:
                        return segs
                except Exception:
                    continue
            raise TingwuError("Task succeeded but no transcript segments found.")

        if status in {"FAILED", "CANCELED", "TIME_EXPIRED", "INVALID"}:
            raise TingwuError(f"Tingwu task status={status}.")

        if asyncio.get_running_loop().time() >= timeout_at:
            raise TingwuError("Tingwu polling timed out.")

        await asyncio.sleep(settings.tingwu_poll_interval_sec)
