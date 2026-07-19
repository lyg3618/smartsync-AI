from typing import Awaitable, Callable, Optional

from app.services.tingwu import TingwuError, run_tingwu_transcription
from app.services.transcription_types import TranscriptSegment


TranscriptionError = TingwuError
StatusCallback = Optional[Callable[[str], Awaitable[None]]]


async def run_transcription(
    *,
    audio_source: str,
    source_kind: str,
    file_name: str,
    on_status: StatusCallback = None,
) -> list[TranscriptSegment]:
    return await run_tingwu_transcription(
        audio_source=audio_source,
        source_kind=source_kind,
        file_name=file_name,
        on_status=on_status,
    )
