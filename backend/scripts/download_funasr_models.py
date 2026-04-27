from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = PROJECT_ROOT / "models" / "funasr"

MODELS = [
    ("ASR", "damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"),
    ("PUNC", "damo/punc_ct-transformer_cn-en-common-vocab471067-large"),
    ("SV", "iic/speech_campplus_sv_zh-cn_16k-common"),
]


def main() -> int:
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ["MODELSCOPE_CACHE"] = str(MODEL_ROOT)

    try:
        from funasr import AutoModel
    except ImportError:
        print("Missing dependency: funasr")
        print("Please run: pip install funasr modelscope")
        return 1

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Model target : {MODEL_ROOT}")
    print("Starting model download...\n")

    for category, model_name in MODELS:
        print(f"[{category}] downloading {model_name}")
        try:
            AutoModel(model=model_name, disable_update=True, hub="ms")
        except Exception as exc:
            print(f"[{category}] failed: {exc}")
            return 2
        print(f"[{category}] done\n")

    print("All models downloaded successfully.")
    print(f"Saved under: {MODEL_ROOT}")
    print("\nRecommended offline .env values:")
    print(f"FUNASR_MODEL_DIR={MODEL_ROOT.as_posix()}")
    print("FUNASR_ASR_MODEL=<downloaded ASR model directory>")
    print("FUNASR_VAD_MODEL=")
    print("FUNASR_PUNC_MODEL=<downloaded PUNC model directory>")
    print("FUNASR_CAMPP_MODEL=<downloaded CAM++ model directory>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
