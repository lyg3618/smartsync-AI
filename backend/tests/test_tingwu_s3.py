import pytest
from botocore.exceptions import ClientError

from app.config import settings
from app.services import tingwu
from app.services.tingwu import TingwuError


class FakeS3Client:
    def __init__(self):
        self.upload_request = None
        self.head_request = None
        self.presign_request = None
        self.delete_request = None
        self.content_length = 0

    def upload_file(self, **kwargs):
        self.upload_request = kwargs
        self.content_length = len(open(kwargs["Filename"], "rb").read())

    def head_object(self, **kwargs):
        self.head_request = kwargs
        return {"ContentLength": self.content_length}

    def generate_presigned_url(self, **kwargs):
        self.presign_request = kwargs
        params = kwargs["Params"]
        return (
            "https://account-id.r2.cloudflarestorage.com/"
            f"{params['Bucket']}/{params['Key']}"
            f"?X-Amz-Expires={kwargs['ExpiresIn']}&X-Amz-Signature=secret"
        )

    def delete_object(self, **kwargs):
        self.delete_request = kwargs


def _configure_s3(monkeypatch):
    monkeypatch.setattr(
        settings,
        "tingwu_s3_endpoint",
        "https://account-id.r2.cloudflarestorage.com",
    )
    monkeypatch.setattr(settings, "tingwu_s3_bucket", "recordings")
    monkeypatch.setattr(settings, "tingwu_s3_region", "auto")
    monkeypatch.setattr(settings, "tingwu_s3_user_agent", "SmartSync")
    monkeypatch.setattr(settings, "tingwu_s3_public_url_base", "")
    monkeypatch.setattr(settings, "tingwu_s3_prefix", "meeting uploads/听悟")
    monkeypatch.setattr(settings, "tingwu_s3_url_expires_sec", 60)
    monkeypatch.setattr(settings, "tingwu_s3_access_key_id", "s3-ak")
    monkeypatch.setattr(settings, "tingwu_s3_access_key_secret", "s3-sk")


def test_local_recording_is_uploaded_with_sigv4_path_style(tmp_path, monkeypatch):
    _configure_s3(monkeypatch)
    monkeypatch.setattr(tingwu, "_verify_download_url_sync", lambda _url: None)
    fake_client = FakeS3Client()
    client_options = {}

    def fake_boto3_client(service_name, **kwargs):
        client_options.update(service_name=service_name, **kwargs)
        return fake_client

    import boto3

    monkeypatch.setattr(boto3, "client", fake_boto3_client)
    audio_path = tmp_path / "带 空格的会议录音.wav"
    audio_path.write_bytes(b"RIFF-test-audio")

    signed_url = tingwu._prepare_tingwu_audio_url_sync(str(audio_path), "file")

    assert client_options["service_name"] == "s3"
    assert client_options["endpoint_url"] == "https://account-id.r2.cloudflarestorage.com"
    assert client_options["region_name"] == "auto"
    assert client_options["aws_access_key_id"] == "s3-ak"
    assert client_options["config"].signature_version == "s3v4"
    assert client_options["config"].s3["addressing_style"] == "path"
    assert client_options["config"].user_agent_extra == "SmartSync"
    assert client_options["config"].request_checksum_calculation == "when_required"
    assert client_options["config"].response_checksum_validation == "when_required"
    request = fake_client.upload_request
    assert request["Bucket"] == "recordings"
    assert request["Key"].startswith("meeting-uploads/")
    assert request["Key"].endswith(".wav")
    assert " " not in request["Key"]
    assert request["ExtraArgs"]["ContentType"].startswith("audio/")
    assert request["Config"].max_concurrency == 4
    assert fake_client.head_request == {"Bucket": request["Bucket"], "Key": request["Key"]}
    assert fake_client.presign_request["ClientMethod"] == "get_object"
    assert fake_client.presign_request["ExpiresIn"] == 10800
    assert signed_url.startswith(
        "https://account-id.r2.cloudflarestorage.com/recordings/"
    )
    assert "X-Amz-Signature=secret" in signed_url


def test_external_url_is_validated_without_s3_upload():
    url = "https://media.example.com/meeting.wav?token=signed"
    assert tingwu._prepare_tingwu_audio_url_sync(url, "url") == url
    assert tingwu._safe_url_for_log(url) == "https://media.example.com/meeting.wav"


def test_tingwu_file_name_inherits_audio_extension():
    assert tingwu._ensure_tingwu_file_extension(
        "演示音频 2026-07-19 17:00",
        "https://pub-example.r2.dev/smartsync/tingwu/audio.mp3",
    ) == "演示音频 2026-07-19 17:00.mp3"
    assert tingwu._ensure_tingwu_file_extension(
        "already.wav",
        "https://pub-example.r2.dev/audio.mp3",
    ) == "already.wav"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/meeting.wav",
        "https://media.example.com/meeting audio.wav",
        "file:///tmp/meeting.wav",
    ],
)
def test_invalid_tingwu_file_url_is_rejected(url):
    with pytest.raises(TingwuError):
        tingwu._validate_tingwu_file_url(url)


def test_invalid_s3_endpoint_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "tingwu_s3_endpoint", "http://127.0.0.1:9000")
    with pytest.raises(TingwuError, match="HTTPS 域名"):
        tingwu._normalize_s3_endpoint()


def test_s3_credentials_do_not_fall_back_to_aliyun_keys(monkeypatch):
    monkeypatch.setattr(settings, "tingwu_s3_access_key_id", "")
    monkeypatch.setattr(settings, "tingwu_s3_access_key_secret", "")
    with pytest.raises(TingwuError, match="S3 凭证未配置"):
        tingwu._get_s3_credentials()


def test_r2_public_url_is_used_instead_of_presigned_url(tmp_path, monkeypatch):
    _configure_s3(monkeypatch)
    monkeypatch.setattr(
        settings,
        "tingwu_s3_public_url_base",
        "https://pub-example.r2.dev",
    )
    monkeypatch.setattr(tingwu, "_verify_download_url_sync", lambda _url: None)
    fake_client = FakeS3Client()

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: fake_client)
    audio_path = tmp_path / "meeting.mp3"
    audio_path.write_bytes(b"public-r2-audio")

    download_url = tingwu._upload_local_file_to_s3_sync(str(audio_path))

    assert download_url.startswith("https://pub-example.r2.dev/meeting-uploads/")
    assert download_url.endswith(".mp3")
    assert fake_client.presign_request is None


def test_s3_401_error_explains_which_access_key_to_use():
    error = ClientError(
        {
            "Error": {"Code": "401", "Message": "Unauthorized"},
            "ResponseMetadata": {"HTTPStatusCode": 401},
        },
        "PutObject",
    )

    message = tingwu._describe_s3_error(error, "capsule-bucket")

    assert "重新生成并启用" in message
    assert "Bucket capsule-bucket" in message
    assert "不是阿里云听悟 AccessKey" in message
    assert "重启后端" in message


def test_presigned_download_401_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 401

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeHttpClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(tingwu.httpx, "Client", FakeHttpClient)

    with pytest.raises(TingwuError, match="下载 URL"):
        tingwu._verify_download_url_sync("https://media.example.com/audio.mp3")


def test_failed_download_check_retains_uploaded_recording(tmp_path, monkeypatch):
    _configure_s3(monkeypatch)
    fake_client = FakeS3Client()

    def reject_download(_url):
        raise TingwuError("预签名下载 URL 无法被公网客户端访问（HTTP 401）")

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: fake_client)
    monkeypatch.setattr(tingwu, "_verify_download_url_sync", reject_download)
    audio_path = tmp_path / "meeting.mp3"
    audio_path.write_bytes(b"saved-original-audio")

    with pytest.raises(TingwuError, match="原录音已保存在对象存储") as caught:
        tingwu._upload_local_file_to_s3_sync(str(audio_path))

    assert fake_client.delete_request is None
    assert fake_client.upload_request["Key"] in str(caught.value)
