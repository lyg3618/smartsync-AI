from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BASE_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "smartsync"
    mysql_password: str = "smartsync123"
    mysql_db: str = "smartsync"

    @property
    def database_url(self) -> str:
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"

    # JWT
    secret_key: str = "change-me-in-production-32-chars!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM
    llm_api_key: str = "sk-F3IjGiMYla9MwPyvhF3IjGiMYla9MwPyvh"
    llm_base_url: str = "http://34.124.175.101:8371/v1"
    llm_model: str = "gpt-4o-mini"

    # Whisper
    whisper_model: str = "base"

    # Transcription provider
    asr_provider: str = "local"
    transcription_enabled: bool = True

    # Tingwu (Alibaba Cloud)
    tingwu_enabled: bool = False
    tingwu_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices("TINGWU_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_ID"),
    )
    tingwu_access_key_secret: str = Field(
        default="",
        validation_alias=AliasChoices("TINGWU_ACCESS_KEY_SECRET", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    )
    tingwu_app_key: str = ""
    tingwu_endpoint: str = "tingwu.cn-beijing.aliyuncs.com"
    tingwu_poll_interval_sec: int = 8
    tingwu_poll_timeout_sec: int = 3600
    # If you upload local files, this must be a public URL prefix that Tingwu can access.
    # Example: https://your-domain.com/uploads
    tingwu_file_url_base: str = ""
    tingwu_gradio_base_url: str = "https://qwen-qwen3-asr.ms.show"
    tingwu_gradio_file_prefix: str = "https://qwen-qwen3-asr.ms.show/gradio_api/file="
    tingwu_gradio_x_studio_token: str = ""

    # FunASR local transcription + CAM++ + Faiss
    funasr_asr_model: str = "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    funasr_vad_model: str = "damo/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    funasr_punc_model: str = "damo/punc_ct-transformer_cn-en-common-vocab471067-large"
    funasr_campp_model: str = "iic/speech_campplus_sv_zh-cn_16k-common"
    funasr_model_dir: str = str(PROJECT_DIR / "models" / "funasr")
    funasr_device: str = "cpu"
    funasr_ngpu: int = 0
    funasr_disable_update: bool = True
    funasr_hub: str = "ms"
    funasr_sample_rate: int = 16000
    funasr_batch_size_s: int = 300
    funasr_min_segment_ms: int = 800
    funasr_merge_gap_ms: int = 1200
    funasr_max_speakers: int = 8
    funasr_speaker_similarity_threshold: float = 0.72

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "AI会议助手 <noreply@smartsync.ai>"

    debug: bool = False

settings = Settings()
