from app.services.local_asr import (
    _asr_model_has_integrated_vad_punc,
    _asr_model_supports_integrated_speaker_diarization,
    _asr_result_has_speaker_labels,
    _extract_embedding,
    _extract_asr_segments,
    _extract_segments_from_token_timestamps,
    _generate_asr_result,
    _is_funasr_nano_model,
    _looks_like_hallucinated_nano_result,
    _smooth_speaker_labels,
)
from app.services.transcription_types import TranscriptSegment
import torch


class _FakeAsrModel:
    def __init__(self):
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("sentence_timestamp"):
            raise KeyError("timestamp")
        return {"text": "test transcript"}


class _FakeNanoModel:
    def __init__(self):
        self.calls = []

    def inference(self, **kwargs):
        self.calls.append(kwargs)
        return ([{"text": "nano transcript"}], {"meta": 1})


def test_generate_asr_result_retries_without_sentence_timestamps():
    model = _FakeAsrModel()

    result = _generate_asr_result(model, "demo.wav")

    assert result == {"text": "test transcript"}
    assert len(model.calls) == 2
    assert model.calls[0]["sentence_timestamp"] is True
    assert model.calls[0]["pred_timestamp"] is True
    assert model.calls[1]["pred_timestamp"] is True
    assert "sentence_timestamp" not in model.calls[1]


def test_generate_asr_result_uses_nano_inference():
    model = _FakeNanoModel()

    result = _generate_asr_result((model, {"language": "Chinese", "itn": True}), "demo.wav")

    assert result == ([{"text": "nano transcript"}], {"meta": 1})
    assert model.calls == [{"data_in": ["demo.wav"], "language": "Chinese", "itn": True}]


def test_extract_asr_segments_uses_audio_duration_for_text_only_results():
    segments = _extract_asr_segments({"text": "full text"}, fallback_end_ms=60100)

    assert len(segments) == 1
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 60100
    assert segments[0].text == "full text"


def test_extract_asr_segments_accepts_space_separated_timestamp_pairs():
    segments = _extract_asr_segments(
        {
            "text": "李 涛 ， 好",
            "timestamp": [[0, 120], [120, 240], [240, 300], [300, 420]],
        }
    )

    assert len(segments) == 1
    assert segments[0].text == "李涛，好"
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 420


def test_extract_embedding_accepts_torch_tensor_results():
    embedding = _extract_embedding({"spk_embedding": torch.tensor([[1.0, 2.0, 3.0]])})

    assert embedding is not None
    assert embedding.shape == (3,)


def test_extract_segments_from_token_timestamps_splits_on_punctuation():
    segments = _extract_segments_from_token_timestamps(
        [
            {"token": "A", "start_time": 0.0, "end_time": 0.1, "score": 0.9},
            {"token": "B", "start_time": 0.1, "end_time": 0.2, "score": 0.8},
            {"token": ".", "start_time": 0.2, "end_time": 0.25, "score": 0.0},
            {"token": "C", "start_time": 0.3, "end_time": 0.4, "score": 0.7},
            {"token": "D", "start_time": 0.4, "end_time": 0.5, "score": 0.6},
            {"token": "!", "start_time": 0.5, "end_time": 0.55, "score": 0.0},
        ]
    )

    assert [segment.text for segment in segments] == ["AB.", "CD!"]
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 250
    assert segments[1].start_ms == 300
    assert segments[1].end_ms == 550


def test_extract_segments_from_token_timestamps_splits_on_comma_when_long_enough():
    segments = _extract_segments_from_token_timestamps(
        [
            {"token": "A", "start_time": 0.0, "end_time": 0.25, "score": 0.9},
            {"token": ",", "start_time": 0.75, "end_time": 0.8, "score": 0.0},
            {"token": "B", "start_time": 1.0, "end_time": 1.2, "score": 0.8},
        ]
    )

    assert [segment.text for segment in segments] == ["A,", "B"]
    assert segments[0].end_ms == 800
    assert segments[1].start_ms == 1000


def test_extract_segments_from_token_timestamps_splits_on_pause():
    segments = _extract_segments_from_token_timestamps(
        [
            {"token": "A", "start_time": 0.0, "end_time": 0.1, "score": 0.9},
            {"token": "B", "start_time": 0.1, "end_time": 0.2, "score": 0.8},
            {"token": "C", "start_time": 1.4, "end_time": 1.5, "score": 0.7},
        ]
    )

    assert [segment.text for segment in segments] == ["AB", "C"]
    assert segments[0].end_ms == 200
    assert segments[1].start_ms == 1400


def test_hallucinated_nano_result_detection_flags_repetitive_low_confidence_output():
    payload = {
        "text": "李涛，" * 64,
        "timestamps": [{"token": "李", "score": 0.0}, {"token": "涛", "score": 0.0}, {"token": "，", "score": 0.0}] * 64,
    }

    assert _looks_like_hallucinated_nano_result(payload, audio_duration_ms=120000)


def test_hallucinated_nano_result_detection_keeps_normal_transcript():
    payload = {
        "text": "今天讨论四月份工作推进以及渠道物料协同安排。",
        "timestamps": [{"token": "今", "score": 0.8}, {"token": "天", "score": 0.9}, {"token": "讨", "score": 0.7}],
    }

    assert not _looks_like_hallucinated_nano_result(payload, audio_duration_ms=120000)


def test_funasr_nano_model_detection():
    assert _is_funasr_nano_model("FunAudioLLM/Fun-ASR-Nano-2512")
    assert _is_funasr_nano_model("D:/models/Fun-ASR-Nano-2512")
    assert not _is_funasr_nano_model(
        "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )


def test_integrated_vad_punc_model_detection():
    assert _asr_model_has_integrated_vad_punc(
        "damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )
    assert not _asr_model_has_integrated_vad_punc(
        "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )


def test_integrated_speaker_diarization_model_detection():
    assert _asr_model_supports_integrated_speaker_diarization(
        "damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )
    assert _asr_model_supports_integrated_speaker_diarization(
        "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )
    assert not _asr_model_supports_integrated_speaker_diarization(
        "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )


def test_asr_result_has_speaker_labels():
    assert _asr_result_has_speaker_labels(
        {"sentence_info": [{"start": 0, "end": 1000, "sentence": "hello", "spk": 1}]}
    )
    assert not _asr_result_has_speaker_labels(
        {"sentence_info": [{"start": 0, "end": 1000, "sentence": "hello"}]}
    )


def test_smooth_speaker_labels_preserves_segments_when_all_default_speakers():
    segments = [
        TranscriptSegment(start_ms=0, end_ms=1000, text="A", speaker="SPEAKER_00", segment_no=0),
        TranscriptSegment(start_ms=1100, end_ms=2000, text="B", speaker="SPEAKER_00", segment_no=1),
    ]

    smoothed = _smooth_speaker_labels(segments)

    assert len(smoothed) == 2
    assert [segment.text for segment in smoothed] == ["A", "B"]
