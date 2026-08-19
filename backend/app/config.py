from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "smartsync"
    mysql_password: str = ""
    mysql_db: str = "smartsync"

    @property
    def database_url(self) -> str:
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"

    # JWT
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # Transcription
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
    tingwu_poll_timeout_sec: int = 14400
    # Offline local recordings use S3-compatible object storage. SigV4 and
    # path-style addressing are enforced by the client implementation.
    tingwu_s3_endpoint: str = ""
    tingwu_s3_bucket: str = ""
    tingwu_s3_region: str = "auto"
    tingwu_s3_user_agent: str = "SmartSync"
    tingwu_s3_public_url_base: str = ""
    tingwu_s3_prefix: str = "smartsync/tingwu"
    tingwu_s3_url_expires_sec: int = 14400
    tingwu_s3_access_key_id: str = ""
    tingwu_s3_access_key_secret: str = ""

    # SMTP
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "SmartSync <noreply@example.com>"

    debug: bool = False

settings = Settings()
