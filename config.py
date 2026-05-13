"""Configuração centralizada via variáveis de ambiente."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"

    # Whisper
    whisper_model: str = "base"
    whisper_device: str = "cpu"  # "cuda" se houver GPU
    whisper_compute_type: str = "int8"  # "float16" em GPU

    # Storage
    s3_bucket: str = ""
    s3_region: str = "auto"
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    public_base_url: str = "http://localhost:8000/files"

    # Webhook de volta pro frontend
    frontend_webhook_url: str = ""
    webhook_secret: str = "changeme"

    # Limites
    max_clip_seconds: int = 60
    min_clip_seconds: int = 15
    max_clips_per_video: int = 10

    # Workdir
    data_dir: str = "/data"


settings = Settings()
