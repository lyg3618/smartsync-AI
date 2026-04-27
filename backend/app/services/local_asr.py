import asyncio
import inspect
import logging
import os
import re
import sys
import tempfile
import wave
from collections import Counter
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Any, Awaitable, Callable, Optional

import httpx

from app.config import settings
from app.services.transcription_types import TranscriptSegment

logger = logging.getLogger("uvicorn.error")


class LocalTranscriptionError(RuntimeError):
    pass


StatusCallback = Optional[Callable[[str], Awaitable[None]]]

_ASR_MODEL = None
_SV_MODEL = None
_FALLBACK_ASR_MODEL = None

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_NANO_VENDOR_DIR = Path(__file__).resolve().parents[2] / "vendor" / "Fun-ASR"
_FALLBACK_ASR_MODEL_NAME = "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
_NANO_LONG_AUDIO_THRESHOLD_MS = 60_000


def _configure_model_cache() -> Path:
    cache_dir = Path(settings.funasr_model_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MODELSCOPE_CACHE"] = str(cache_dir)
    return cache_dir


async def _emit_status(on_status: StatusCallback, status: str) -> None:
    if on_status:
        await on_status(status)


def _require_dependency(module_name: str, install_hint: str):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise LocalTranscriptionError(f"Missing dependency `{module_name}`. Install with `{install_hint}`.") from exc


def _get_numpy():
    return _require_dependency("numpy", "pip install numpy")


def _get_faiss():
    try:
        return __import__("faiss")
    except ImportError as exc:
        raise LocalTranscriptionError("Missing dependency `faiss`. Install with `pip install faiss-cpu`.") from exc


def _get_funasr_auto_model():
    cache_dir = _configure_model_cache()
    try:
        from funasr import AutoModel

        logger.info("[LOCAL_ASR] using model cache dir=%s", cache_dir)
        return AutoModel
    except ImportError as exc:
        raise LocalTranscriptionError(
            "Missing dependency `funasr`. Install with `pip install funasr modelscope` and ensure PyTorch is available."
        ) from exc


def _make_temp_audio_path(suffix: str) -> str:
    fd, path = tempfile.mkstemp(prefix="smartsync-audio-", suffix=suffix)
    os.close(fd)
    return path


async def _download_audio(url: str) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix or ".bin"
    target_path = _make_temp_audio_path(suffix)
    timeout = httpx.Timeout(60.0, read=600.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        with open(target_path, "wb") as file_obj:
            file_obj.write(response.content)
    return target_path


def _convert_to_wav_16k_mono(input_path: str) -> str:
    output_path = _make_temp_audio_path(".wav")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        output_path,
    ]
    try:
        result = run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        if result.stderr:
            logger.info("[LOCAL_ASR] ffmpeg=%s", result.stderr.strip())
        return output_path
    except FileNotFoundError as exc:
        raise LocalTranscriptionError("`ffmpeg` was not found in PATH. Please install FFmpeg for local transcription.") from exc
    except CalledProcessError as exc:
        raise LocalTranscriptionError(f"FFmpeg audio conversion failed: {exc.stderr.strip() or exc.stdout.strip()}") from exc


def _read_wav_pcm_float32(wav_path: str):
    numpy = _get_numpy()
    with wave.open(wav_path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frame_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width != 2:
        raise LocalTranscriptionError("Only 16-bit PCM WAV is supported after FFmpeg conversion.")

    audio = numpy.frombuffer(frames, dtype=numpy.int16).astype(numpy.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if frame_rate != 16000:
        raise LocalTranscriptionError(f"Expected 16k WAV after conversion, got {frame_rate} Hz.")
    return audio


def _get_wav_duration_ms(wav_path: str) -> int:
    with wave.open(wav_path, "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
    if frame_rate <= 0:
        return 0
    return int(frame_count * 1000 / frame_rate)


def _maybe_await(value):
    if inspect.isawaitable(value):
        return value
    return None


def _build_auto_model_kwargs(base_kwargs: dict[str, Any]) -> dict[str, Any]:
    kwargs = {key: value for key, value in base_kwargs.items() if value not in (None, "")}
    if settings.funasr_disable_update:
        kwargs["disable_update"] = True
    if settings.funasr_hub:
        kwargs["hub"] = settings.funasr_hub
    return kwargs


def _validate_supported_asr_model(model_name: str) -> None:
    return None


def _is_funasr_nano_model(model_name: str) -> bool:
    normalized = str(model_name).replace("\\", "/").lower()
    return "fun-asr-nano" in normalized or "funaudiollm/fun-asr-nano" in normalized


def _asr_model_has_integrated_vad_punc(model_name: str) -> bool:
    normalized = str(model_name).replace("\\", "/").lower()
    return "vad-punc_asr" in normalized


def _asr_model_supports_integrated_speaker_diarization(model_name: str) -> bool:
    normalized = str(model_name).replace("\\", "/").lower()
    return "vad-punc_asr" in normalized or "seaco_paraformer" in normalized


def _resolve_runtime_model_path(model_name: str) -> str:
    model_path = Path(model_name)
    if not model_path.is_absolute():
        model_path = (_BACKEND_DIR / model_path).resolve()
    if not model_path.exists():
        return model_name
    try:
        return os.path.relpath(model_path, Path.cwd())
    except ValueError:
        return str(model_path)


def _get_funasr_nano_class():
    if not _NANO_VENDOR_DIR.exists():
        raise LocalTranscriptionError(f"Missing Fun-ASR vendor code at `{_NANO_VENDOR_DIR}`.")
    vendor_dir = str(_NANO_VENDOR_DIR)
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)
    try:
        from model import FunASRNano
    except ImportError as exc:
        raise LocalTranscriptionError(
            "Failed to import Fun-ASR Nano runtime. Ensure vendor/Fun-ASR and its dependencies are installed."
        ) from exc
    return FunASRNano


def _resolve_fallback_asr_model_path() -> Optional[str]:
    model_root = Path(settings.funasr_model_dir).resolve()
    candidates = [
        model_root / "models" / "damo" / _FALLBACK_ASR_MODEL_NAME,
        model_root / "damo" / _FALLBACK_ASR_MODEL_NAME,
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _get_asr_model():
    global _ASR_MODEL
    if _ASR_MODEL is None:
        _validate_supported_asr_model(settings.funasr_asr_model)
        if _is_funasr_nano_model(settings.funasr_asr_model):
            FunASRNano = _get_funasr_nano_class()
            runtime_model = _resolve_runtime_model_path(settings.funasr_asr_model)
            logger.info("[LOCAL_ASR] loading Fun-ASR Nano model=%s", runtime_model)
            model, kwargs = FunASRNano.from_pretrained(model=runtime_model, device=settings.funasr_device)
            kwargs["batch_size"] = 1
            kwargs["language"] = "中文"
            kwargs["itn"] = True
            _ASR_MODEL = (model, kwargs)
        else:
            AutoModel = _get_funasr_auto_model()
            has_integrated_vad_punc = _asr_model_has_integrated_vad_punc(settings.funasr_asr_model)
            supports_integrated_spk = _asr_model_supports_integrated_speaker_diarization(settings.funasr_asr_model)
            kwargs = _build_auto_model_kwargs(
                {
                    "model": settings.funasr_asr_model,
                    "vad_model": None if has_integrated_vad_punc else settings.funasr_vad_model,
                    "punc_model": settings.funasr_punc_model,
                    "spk_model": settings.funasr_campp_model if supports_integrated_spk else None,
                    "device": settings.funasr_device,
                    "ngpu": settings.funasr_ngpu,
                }
            )
            logger.info("[LOCAL_ASR] loading ASR model=%s", settings.funasr_asr_model)
            if has_integrated_vad_punc:
                logger.info("[LOCAL_ASR] ASR model has integrated VAD; skipping external vad_model and keeping punc_model")
            if supports_integrated_spk:
                logger.info("[LOCAL_ASR] ASR model supports integrated speaker diarization; attaching spk_model=%s", settings.funasr_campp_model)
            _ASR_MODEL = AutoModel(**kwargs)
    return _ASR_MODEL


def _get_fallback_asr_model():
    global _FALLBACK_ASR_MODEL
    if _FALLBACK_ASR_MODEL is None:
        model_path = _resolve_fallback_asr_model_path()
        if not model_path:
            raise LocalTranscriptionError(
                f"Bundled fallback ASR model `{_FALLBACK_ASR_MODEL_NAME}` was not found under `{settings.funasr_model_dir}`."
            )

        AutoModel = _get_funasr_auto_model()
        kwargs = _build_auto_model_kwargs(
            {
                "model": model_path,
                "device": settings.funasr_device,
                "ngpu": settings.funasr_ngpu,
            }
        )
        logger.info("[LOCAL_ASR] loading fallback ASR model=%s", model_path)
        _FALLBACK_ASR_MODEL = AutoModel(**kwargs)
    return _FALLBACK_ASR_MODEL


def _get_sv_model():
    global _SV_MODEL
    if _SV_MODEL is None:
        AutoModel = _get_funasr_auto_model()
        kwargs = _build_auto_model_kwargs(
            {
                "model": settings.funasr_campp_model,
                "device": settings.funasr_device,
                "ngpu": settings.funasr_ngpu,
            }
        )
        logger.info("[LOCAL_ASR] loading speaker model=%s", settings.funasr_campp_model)
        _SV_MODEL = AutoModel(**kwargs)
    return _SV_MODEL


def _first_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, tuple):
        for item in result:
            payload = _first_dict(item)
            if payload:
                return payload
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                return item
            payload = _first_dict(item)
            if payload:
                return payload
    return {}


def _log_asr_sentence_info(result: Any) -> None:
    payload = _first_dict(result)
    sentence_info = payload.get("sentence_info") or payload.get("sentences") or payload.get("SentenceInfo") or []
    sentence_count = 0
    speaker_count = 0

    if isinstance(sentence_info, list):
        sentence_count = len(sentence_info)
        speaker_count = sum(
            1
            for item in sentence_info
            if isinstance(item, dict) and item.get("spk") not in (None, "")
        )

    logger.info(
        "[LOCAL_ASR] raw sentence_info count=%s with_spk=%s text_len=%s",
        sentence_count,
        speaker_count,
        len(str(payload.get("text") or "")),
    )


def _coerce_timestamp_tokens(timestamp_tokens: Any, text: str = "") -> list[dict[str, Any]]:
    if not isinstance(timestamp_tokens, list) or not timestamp_tokens:
        return []

    if all(isinstance(item, dict) for item in timestamp_tokens):
        return timestamp_tokens

    tokens = [token for token in str(text or "").split() if token]
    if len(tokens) != len(timestamp_tokens):
        return []

    normalized_tokens: list[dict[str, Any]] = []
    for token, timing in zip(tokens, timestamp_tokens):
        if not isinstance(timing, (list, tuple)) or len(timing) < 2:
            return []
        try:
            start_ms = int(timing[0])
            end_ms = int(timing[1])
        except (TypeError, ValueError):
            return []
        normalized_tokens.append(
            {
                "token": token,
                "start_time": start_ms / 1000,
                "end_time": end_ms / 1000,
            }
        )
    return normalized_tokens


def _looks_like_hallucinated_nano_result(payload: dict[str, Any], audio_duration_ms: int) -> bool:
    if audio_duration_ms < _NANO_LONG_AUDIO_THRESHOLD_MS:
        return False

    text = str(payload.get("text") or "").strip()
    if not text:
        return False

    normalized = re.sub(r"\s+", "", text)
    core_text = re.sub(r"[，。、！？；：,.!?;:'\"“”‘’（）()\[\]…·-]", "", normalized)
    if len(core_text) < 80:
        return False

    unique_ratio = len(set(core_text)) / len(core_text)
    phrase_candidates = [item for item in re.split(r"[，。、！？；：,.!?;:]+", normalized) if item]
    short_phrases = [item for item in phrase_candidates if 1 <= len(item) <= 6]
    repeated_phrase = ""
    repeated_count = 0
    repeated_ratio = 0.0
    if short_phrases:
        repeated_phrase, repeated_count = Counter(short_phrases).most_common(1)[0]
        repeated_ratio = repeated_count / len(short_phrases)

    timestamp_scores: list[float] = []
    for item in payload.get("timestamps") or []:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        try:
            timestamp_scores.append(float(score))
        except (TypeError, ValueError):
            continue
    low_conf_ratio = (
        sum(score <= 0.01 for score in timestamp_scores) / len(timestamp_scores)
        if timestamp_scores
        else 0.0
    )

    looks_hallucinated = (
        repeated_count >= 10
        and repeated_ratio >= 0.35
        and unique_ratio <= 0.22
        and (low_conf_ratio >= 0.6 or len(set(short_phrases)) <= 3)
    )
    if looks_hallucinated:
        logger.warning(
            "[LOCAL_ASR] suspicious Nano transcript detected phrase=%r repeated_count=%s repeated_ratio=%.2f unique_ratio=%.2f low_conf_ratio=%.2f",
            repeated_phrase,
            repeated_count,
            repeated_ratio,
            unique_ratio,
            low_conf_ratio,
        )
    return looks_hallucinated


def _extract_asr_segments(result: Any, fallback_end_ms: int = 0) -> list[TranscriptSegment]:
    payload = _first_dict(result)
    candidates = payload.get("sentence_info") or payload.get("sentences") or payload.get("SentenceInfo") or []
    segments: list[TranscriptSegment] = []

    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("sentence") or item.get("Text") or "").strip()
        if not text:
            continue

        start_ms = int(item.get("start") or item.get("start_ms") or item.get("begin_time") or item.get("Start") or 0)
        end_ms = int(item.get("end") or item.get("end_ms") or item.get("end_time") or item.get("End") or start_ms)

        confidence = item.get("confidence")
        try:
            confidence = None if confidence is None else float(confidence)
        except (TypeError, ValueError):
            confidence = None

        speaker = item.get("speaker")
        if speaker in (None, ""):
            speaker_id = item.get("spk")
            try:
                speaker = f"SPEAKER_{int(speaker_id):02d}" if speaker_id is not None else "SPEAKER_00"
            except (TypeError, ValueError):
                speaker = str(speaker_id).strip() or "SPEAKER_00"
        else:
            speaker = str(speaker).strip() or "SPEAKER_00"

        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                speaker=speaker,
                confidence=confidence,
                segment_no=index,
            )
        )

    if segments:
        return segments

    text = str(payload.get("text") or "").strip()
    raw_timestamp_tokens = payload.get("timestamps") or payload.get("timestamp") or payload.get("ctc_timestamps") or []
    timestamp_tokens = _coerce_timestamp_tokens(raw_timestamp_tokens, text=text)
    timestamp_kwargs: dict[str, Any] = {}
    if payload.get("timestamp") and not payload.get("timestamps"):
        timestamp_kwargs = {
            "pause_break_ms": 300,
            "soft_break_min_ms": 450,
            "max_segment_ms": 12000,
            "max_segment_gap_ms": 180,
        }
    segments = _extract_segments_from_token_timestamps_configurable(timestamp_tokens, **timestamp_kwargs)
    if segments:
        return segments

    if text:
        return [TranscriptSegment(start_ms=0, end_ms=max(0, fallback_end_ms), text=text, segment_no=0)]
    raise LocalTranscriptionError("FunASR returned no usable transcript segments.")


def _extract_segments_from_token_timestamps(timestamp_tokens: Any) -> list[TranscriptSegment]:
    if not isinstance(timestamp_tokens, list):
        return []

    sentence_breaks = {"。", "！", "？", ".", "!", "?"}
    pause_break_ms = 900
    segments: list[TranscriptSegment] = []
    current_tokens: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current_tokens
        if not current_tokens:
            return
        text = "".join(str(item.get("token") or "") for item in current_tokens).strip()
        if not text:
            current_tokens = []
            return
        start_ms = int(float(current_tokens[0].get("start_time", 0)) * 1000)
        end_ms = int(float(current_tokens[-1].get("end_time", current_tokens[0].get("start_time", 0))) * 1000)
        scores = [float(item.get("score")) for item in current_tokens if item.get("score") not in (None, "")]
        confidence = sum(scores) / len(scores) if scores else None
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                confidence=confidence,
                segment_no=len(segments),
            )
        )
        current_tokens = []

    previous_end_ms: Optional[int] = None
    for raw_item in timestamp_tokens:
        if not isinstance(raw_item, dict):
            continue
        token = str(raw_item.get("token") or "")
        if not token:
            continue
        start_ms = int(float(raw_item.get("start_time", 0)) * 1000)
        if previous_end_ms is not None and start_ms - previous_end_ms >= pause_break_ms:
            flush()
        current_tokens.append(raw_item)
        previous_end_ms = int(float(raw_item.get("end_time", raw_item.get("start_time", 0))) * 1000)
        if token in sentence_breaks:
            flush()

    flush()
    return segments


def _extract_segments_from_token_timestamps(timestamp_tokens: Any) -> list[TranscriptSegment]:
    if not isinstance(timestamp_tokens, list):
        return []

    strong_breaks = {"。", "！", "？", ".", "!", "?"}
    soft_breaks = {"，", ",", "；", ";", "、"}
    pause_break_ms = 900
    soft_break_min_ms = 700
    segments: list[TranscriptSegment] = []
    current_tokens: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current_tokens
        if not current_tokens:
            return
        text = "".join(str(item.get("token") or "") for item in current_tokens).strip()
        if not text:
            current_tokens = []
            return
        start_ms = int(float(current_tokens[0].get("start_time", 0)) * 1000)
        end_ms = int(float(current_tokens[-1].get("end_time", current_tokens[0].get("start_time", 0))) * 1000)
        scores = [float(item.get("score")) for item in current_tokens if item.get("score") not in (None, "")]
        confidence = sum(scores) / len(scores) if scores else None
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                confidence=confidence,
                segment_no=len(segments),
            )
        )
        current_tokens = []

    previous_end_ms: Optional[int] = None
    for raw_item in timestamp_tokens:
        if not isinstance(raw_item, dict):
            continue
        token = str(raw_item.get("token") or "")
        if not token:
            continue
        start_ms = int(float(raw_item.get("start_time", 0)) * 1000)
        if previous_end_ms is not None and start_ms - previous_end_ms >= pause_break_ms:
            flush()
        current_tokens.append(raw_item)
        previous_end_ms = int(float(raw_item.get("end_time", raw_item.get("start_time", 0))) * 1000)
        current_duration_ms = previous_end_ms - int(float(current_tokens[0].get("start_time", 0)) * 1000)
        if token in strong_breaks:
            flush()
        elif token in soft_breaks and current_duration_ms >= soft_break_min_ms:
            flush()

    flush()
    return segments


def _extract_segments_from_token_timestamps_configurable(
    timestamp_tokens: Any,
    *,
    pause_break_ms: int = 900,
    soft_break_min_ms: int = 700,
    max_segment_ms: Optional[int] = None,
    max_segment_gap_ms: int = 0,
) -> list[TranscriptSegment]:
    if not isinstance(timestamp_tokens, list):
        return []
    return _extract_segments_from_token_timestamps_configurable_fixed(
        timestamp_tokens,
        pause_break_ms=pause_break_ms,
        soft_break_min_ms=soft_break_min_ms,
        max_segment_ms=max_segment_ms,
        max_segment_gap_ms=max_segment_gap_ms,
    )
    """

    strong_breaks = {"銆?, "锛?, "锛?, ".", "!", "?"}
    soft_breaks = {"锛?, ",", "锛?, ";", "銆?"}
    segments: list[TranscriptSegment] = []
    current_tokens: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current_tokens
        if not current_tokens:
            return
        text = "".join(str(item.get("token") or "") for item in current_tokens).strip()
        if not text:
            current_tokens = []
            return
        start_ms = int(float(current_tokens[0].get("start_time", 0)) * 1000)
        end_ms = int(float(current_tokens[-1].get("end_time", current_tokens[0].get("start_time", 0))) * 1000)
        scores = [float(item.get("score")) for item in current_tokens if item.get("score") not in (None, "")]
        confidence = sum(scores) / len(scores) if scores else None
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                confidence=confidence,
                segment_no=len(segments),
            )
        )
        current_tokens = []

    previous_end_ms: Optional[int] = None
    for raw_item in timestamp_tokens:
        if not isinstance(raw_item, dict):
            continue
        token = str(raw_item.get("token") or "")
        if not token:
            continue
        start_ms = int(float(raw_item.get("start_time", 0)) * 1000)
        gap_ms = start_ms - previous_end_ms if previous_end_ms is not None else 0
        if previous_end_ms is not None and gap_ms >= pause_break_ms:
            flush()
        current_tokens.append(raw_item)
        previous_end_ms = int(float(raw_item.get("end_time", raw_item.get("start_time", 0))) * 1000)
        current_duration_ms = previous_end_ms - int(float(current_tokens[0].get("start_time", 0)) * 1000)
        if token in strong_breaks:
            flush()
        elif token in soft_breaks and current_duration_ms >= soft_break_min_ms:
            flush()
        elif (
            max_segment_ms is not None
            and current_duration_ms >= max_segment_ms
            and gap_ms >= max_segment_gap_ms
        ):
            flush()

    flush()
    return segments


    """


def _extract_segments_from_token_timestamps_configurable_fixed(
    timestamp_tokens: Any,
    *,
    pause_break_ms: int = 900,
    soft_break_min_ms: int = 700,
    max_segment_ms: Optional[int] = None,
    max_segment_gap_ms: int = 0,
) -> list[TranscriptSegment]:
    if not isinstance(timestamp_tokens, list):
        return []

    strong_breaks = {"。", "！", "？", ".", "!", "?"}
    soft_breaks = {"，", ",", "；", ";", "、"}
    segments: list[TranscriptSegment] = []
    current_tokens: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current_tokens
        if not current_tokens:
            return
        text = "".join(str(item.get("token") or "") for item in current_tokens).strip()
        if not text:
            current_tokens = []
            return
        start_ms = int(float(current_tokens[0].get("start_time", 0)) * 1000)
        end_ms = int(float(current_tokens[-1].get("end_time", current_tokens[0].get("start_time", 0))) * 1000)
        scores = [float(item.get("score")) for item in current_tokens if item.get("score") not in (None, "")]
        confidence = sum(scores) / len(scores) if scores else None
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                confidence=confidence,
                segment_no=len(segments),
            )
        )
        current_tokens = []

    previous_end_ms: Optional[int] = None
    for raw_item in timestamp_tokens:
        if not isinstance(raw_item, dict):
            continue
        token = str(raw_item.get("token") or "")
        if not token:
            continue
        start_ms = int(float(raw_item.get("start_time", 0)) * 1000)
        gap_ms = start_ms - previous_end_ms if previous_end_ms is not None else 0
        if previous_end_ms is not None and gap_ms >= pause_break_ms:
            flush()
        current_tokens.append(raw_item)
        previous_end_ms = int(float(raw_item.get("end_time", raw_item.get("start_time", 0))) * 1000)
        current_duration_ms = previous_end_ms - int(float(current_tokens[0].get("start_time", 0)) * 1000)
        if token in strong_breaks:
            flush()
        elif token in soft_breaks and current_duration_ms >= soft_break_min_ms:
            flush()
        elif (
            max_segment_ms is not None
            and current_duration_ms >= max_segment_ms
            and gap_ms >= max_segment_gap_ms
        ):
            flush()

    flush()
    return segments


def _asr_result_has_speaker_labels(result: Any) -> bool:
    payload = _first_dict(result)
    candidates = payload.get("sentence_info") or payload.get("sentences") or payload.get("SentenceInfo") or []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if item.get("speaker") not in (None, ""):
            return True
        if item.get("spk") not in (None, ""):
            return True
    return False


def _generate_asr_result(asr_model: Any, wav_path: str) -> Any:
    if isinstance(asr_model, tuple):
        nano_model, nano_kwargs = asr_model
        kwargs = dict(nano_kwargs)
        return nano_model.inference(data_in=[wav_path], **kwargs)
    base_kwargs = {
        "input": wav_path,
        "batch_size_s": settings.funasr_batch_size_s,
        "pred_timestamp": True,
    }
    try:
        return asr_model.generate(**base_kwargs, sentence_timestamp=True)
    except KeyError as exc:
        if exc.args != ("timestamp",):
            raise
        logger.warning(
            "[LOCAL_ASR] model=%s returned no timestamps; retrying without sentence timestamps",
            settings.funasr_asr_model,
        )
        return asr_model.generate(**base_kwargs)


def _extract_embedding(candidate: Any):
    numpy = _get_numpy()

    if candidate is None:
        return None
    if hasattr(candidate, "detach") and hasattr(candidate, "cpu") and hasattr(candidate, "numpy"):
        try:
            return candidate.detach().cpu().numpy().astype(numpy.float32).reshape(-1)
        except Exception:
            pass
    if isinstance(candidate, numpy.ndarray):
        return candidate.astype(numpy.float32).reshape(-1)
    if isinstance(candidate, (list, tuple)) and candidate and isinstance(candidate[0], (int, float)):
        return numpy.asarray(candidate, dtype=numpy.float32).reshape(-1)
    if isinstance(candidate, dict):
        for key in ("spk_embedding", "speaker_embedding", "embedding", "embeddings", "xvector", "sv_embedding"):
            value = candidate.get(key)
            embedding = _extract_embedding(value)
            if embedding is not None:
                return embedding
        for value in candidate.values():
            embedding = _extract_embedding(value)
            if embedding is not None:
                return embedding
    if isinstance(candidate, list):
        for item in candidate:
            embedding = _extract_embedding(item)
            if embedding is not None:
                return embedding
    return None


def _segment_audio(audio_array, start_ms: int, end_ms: int):
    numpy = _get_numpy()
    sample_rate = settings.funasr_sample_rate
    start_idx = max(0, int(start_ms * sample_rate / 1000))
    end_idx = max(start_idx + 1, int(end_ms * sample_rate / 1000))
    chunk = audio_array[start_idx:end_idx]
    if chunk.size == 0:
        return None

    min_samples = int(settings.funasr_min_segment_ms * sample_rate / 1000)
    if chunk.size < min_samples:
        pad_width = min_samples - chunk.size
        chunk = numpy.pad(chunk, (0, pad_width), mode="constant")
    return chunk.astype(numpy.float32)


def _extract_embedding_with_campp(audio_chunk):
    sv_model = _get_sv_model()
    result = sv_model.generate(input=audio_chunk)
    embedding = _extract_embedding(result)
    if embedding is None:
        logger.warning(
            "[LOCAL_ASR] CAM++ returned no speaker embedding; falling back for this segment. "
            "Check FUNASR_CAMPP_MODEL=%s",
            settings.funasr_campp_model,
        )
        return None
    return embedding


def _assign_speakers_with_faiss(segments: list[TranscriptSegment], embeddings: list[Any]) -> None:
    numpy = _get_numpy()
    faiss = _get_faiss()

    valid_pairs = [(segment, embedding) for segment, embedding in zip(segments, embeddings) if embedding is not None]
    if not valid_pairs:
        for segment in segments:
            segment.speaker = "SPEAKER_00"
        return

    dimension = int(valid_pairs[0][1].shape[0])
    centroids: list[Any] = []
    centroid_counts: list[int] = []
    labels: list[int] = []

    def rebuild_index():
        index = faiss.IndexFlatIP(dimension)
        if centroids:
            centroid_matrix = numpy.vstack(centroids).astype(numpy.float32)
            index.add(centroid_matrix)
        return index

    index = rebuild_index()
    threshold = settings.funasr_speaker_similarity_threshold
    max_speakers = max(1, settings.funasr_max_speakers)

    for _, embedding in valid_pairs:
        norm = float(numpy.linalg.norm(embedding))
        vector = embedding if norm == 0 else embedding / norm
        vector = vector.astype(numpy.float32).reshape(1, -1)

        if not centroids:
            centroids.append(vector.reshape(-1))
            centroid_counts.append(1)
            labels.append(0)
            index = rebuild_index()
            continue

        scores, nearest = index.search(vector, 1)
        best_score = float(scores[0][0])
        best_label = int(nearest[0][0])
        if best_score < threshold and len(centroids) < max_speakers:
            best_label = len(centroids)
            centroids.append(vector.reshape(-1))
            centroid_counts.append(1)
        else:
            count = centroid_counts[best_label]
            updated = (centroids[best_label] * count + vector.reshape(-1)) / (count + 1)
            updated_norm = float(numpy.linalg.norm(updated))
            centroids[best_label] = updated if updated_norm == 0 else updated / updated_norm
            centroid_counts[best_label] = count + 1

        labels.append(best_label)
        index = rebuild_index()

    label_iter = iter(labels)
    for segment, embedding in zip(segments, embeddings):
        if embedding is None:
            segment.speaker = "SPEAKER_00"
            continue
        segment.speaker = f"SPEAKER_{next(label_iter):02d}"


def _smooth_speaker_labels(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    if not segments:
        return segments

    # Preserve ASR timing segmentation when diarization failed and every segment
    # fell back to the default speaker label.
    if all(segment.speaker == "SPEAKER_00" for segment in segments):
        for index, segment in enumerate(segments):
            segment.segment_no = index
        return segments

    smoothed: list[TranscriptSegment] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        if smoothed and smoothed[-1].speaker == segment.speaker and segment.start_ms - smoothed[-1].end_ms <= settings.funasr_merge_gap_ms:
            smoothed[-1].end_ms = max(smoothed[-1].end_ms, segment.end_ms)
            smoothed[-1].text = f"{smoothed[-1].text} {text}".strip()
            confidences = [value for value in (smoothed[-1].confidence, segment.confidence) if value is not None]
            smoothed[-1].confidence = sum(confidences) / len(confidences) if confidences else None
            continue
        smoothed.append(segment)

    for index, segment in enumerate(smoothed):
        segment.segment_no = index
    return smoothed


async def run_local_transcription(audio_source: str, source_kind: str = "file", on_status: StatusCallback = None) -> list[TranscriptSegment]:
    temp_paths: list[str] = []
    try:
        await _emit_status(on_status, "PREPARING")
        if source_kind == "url":
            input_path = await _download_audio(audio_source)
            temp_paths.append(input_path)
        else:
            input_path = audio_source

        wav_path = await asyncio.to_thread(_convert_to_wav_16k_mono, input_path)
        temp_paths.append(wav_path)
        audio_duration_ms = await asyncio.to_thread(_get_wav_duration_ms, wav_path)

        await _emit_status(on_status, "TRANSCRIBING")
        use_nano_long_audio_fallback = (
            _is_funasr_nano_model(settings.funasr_asr_model)
            and audio_duration_ms >= _NANO_LONG_AUDIO_THRESHOLD_MS
            and _resolve_fallback_asr_model_path() is not None
        )
        if use_nano_long_audio_fallback:
            logger.info(
                "[LOCAL_ASR] Nano configured for %sms audio; using bundled Paraformer fallback model for transcription",
                audio_duration_ms,
            )
            asr_model = _get_fallback_asr_model()
        else:
            asr_model = _get_asr_model()

        asr_result = await asyncio.to_thread(_generate_asr_result, asr_model, wav_path)
        _log_asr_sentence_info(asr_result)
        if (
            not use_nano_long_audio_fallback
            and _is_funasr_nano_model(settings.funasr_asr_model)
            and _resolve_fallback_asr_model_path() is not None
            and _looks_like_hallucinated_nano_result(_first_dict(asr_result), audio_duration_ms)
        ):
            logger.warning("[LOCAL_ASR] retrying suspicious Nano transcript with bundled Paraformer fallback model")
            asr_result = await asyncio.to_thread(_generate_asr_result, _get_fallback_asr_model(), wav_path)
            _log_asr_sentence_info(asr_result)

        segments = _extract_asr_segments(asr_result, fallback_end_ms=audio_duration_ms)
        if _asr_result_has_speaker_labels(asr_result):
            logger.info("[LOCAL_ASR] using integrated speaker diarization from ASR result")
            await _emit_status(on_status, "MERGING")
            return await asyncio.to_thread(_smooth_speaker_labels, segments)

        await _emit_status(on_status, "EMBEDDING")
        audio_array = await asyncio.to_thread(_read_wav_pcm_float32, wav_path)
        embeddings = []
        for segment in segments:
            audio_chunk = _segment_audio(audio_array, segment.start_ms, segment.end_ms)
            if audio_chunk is None:
                embeddings.append(None)
                continue
            embedding = await asyncio.to_thread(_extract_embedding_with_campp, audio_chunk)
            embeddings.append(embedding)

        if not any(embedding is not None for embedding in embeddings):
            logger.warning(
                "[LOCAL_ASR] no speaker embeddings were extracted for any segment; "
                "continuing with single-speaker fallback. Check FUNASR_CAMPP_MODEL=%s",
                settings.funasr_campp_model,
            )

        await _emit_status(on_status, "CLUSTERING")
        await asyncio.to_thread(_assign_speakers_with_faiss, segments, embeddings)

        await _emit_status(on_status, "MERGING")
        return await asyncio.to_thread(_smooth_speaker_labels, segments)
    except httpx.HTTPError as exc:
        raise LocalTranscriptionError(f"Failed to fetch remote audio: {exc}") from exc
    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass
