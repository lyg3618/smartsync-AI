from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker: str = "SPEAKER_00"
    confidence: Optional[float] = None
    segment_no: int = 0

