import json
import wave

from app.services import tingwu_realtime
from app.services.tingwu_realtime import RealtimeWavRecorder, normalize_realtime_event


def test_realtime_task_enables_open_ended_speaker_diarization(monkeypatch):
    monkeypatch.setattr(tingwu_realtime, "_get_credentials", lambda: ("ak", "sk", "app-key"))

    body = tingwu_realtime.build_realtime_task_body(speaker_count=0)

    transcription = body["Parameters"]["Transcription"]
    assert transcription["DiarizationEnabled"] is True
    assert transcription["Diarization"] == {"SpeakerCount": 0}


def test_normalize_partial_result():
    event = normalize_realtime_event(
        "partial",
        json.dumps(
            {
                "header": {"name": "TranscriptionResultChanged", "status": 20000000},
                "payload": {
                    "index": 2,
                    "time": 1835,
                    "result": "北京的天",
                    "words": [
                        {"text": "北京", "startTime": 630, "endTime": 930},
                        {"text": "天", "startTime": 1110, "endTime": 1140},
                    ],
                },
            }
        ),
    )

    assert event == {
        "type": "partial",
        "name": "TranscriptionResultChanged",
        "status": 20000000,
        "status_text": "",
        "index": 2,
        "start_ms": 630,
        "end_ms": 1835,
        "speaker": "SPEAKER_00",
        "text": "北京的天",
        "words": [
            {"text": "北京", "startTime": 630, "endTime": 930},
            {"text": "天", "startTime": 1110, "endTime": 1140},
        ],
    }


def test_normalize_final_result_appends_stash_and_speaker():
    event = normalize_realtime_event(
        "final",
        {
            "header": {"name": "SentenceEnd", "status": 20000000},
            "payload": {
                "index": "3",
                "begin_time": 2000,
                "time": 4200,
                "result": "项目按期",
                "stash_result": {"text": "上线。"},
                "speaker_id": 1,
            },
        },
    )

    assert event["index"] == 3
    assert event["start_ms"] == 2000
    assert event["end_ms"] == 4200
    assert event["speaker"] == "SPEAKER_01"
    assert event["text"] == "项目按期上线。"


def test_normalize_malformed_event_is_safe():
    event = normalize_realtime_event("error", "not-json")
    assert event["type"] == "error"
    assert event["status_text"] == ""


def test_realtime_wav_recorder_preserves_pcm_timeline(tmp_path):
    output_path = tmp_path / "meeting.wav"
    recorder = RealtimeWavRecorder(output_path)
    one_second_of_silence = b"\x00\x00" * 16000

    recorder.write(one_second_of_silence[:12000])
    recorder.write(one_second_of_silence[12000:])
    assert recorder.duration_ms == 1000
    recorder.close()
    recorder.close()

    with wave.open(str(output_path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 16000
        assert audio.getnframes() == 16000
        assert audio.readframes(16000) == one_second_of_silence
