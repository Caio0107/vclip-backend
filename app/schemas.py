"""Schemas Pydantic compartilhados entre API e workers."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl


class CreateProjectRequest(BaseModel):
    source_url: Optional[HttpUrl] = None
    source_type: Literal["youtube", "upload"] = "youtube"
    upload_path: Optional[str] = None  # caminho do arquivo após upload
    title: Optional[str] = None
    language: Optional[str] = Field(default=None, description="ISO 639-1, auto-detecta se None")


class PipelineStep(BaseModel):
    key: str
    label: str
    progress: int = 0  # 0-100
    status: Literal["pending", "active", "done", "failed"] = "pending"


class WordTimestamp(BaseModel):
    text: str
    start: float
    end: float


class Caption(BaseModel):
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = []


class ViralMoment(BaseModel):
    start: float
    end: float
    score: float  # 0-10
    title: str
    hook: str
    keyword: str  # palavra-chave para destacar nas legendas


class Clip(BaseModel):
    id: str
    title: str
    hook: str
    score: float
    start: float
    end: float
    duration: float
    download_url: Optional[str] = None
    caption_preview: str = ""
    status: Literal["pending", "processing", "ready", "failed"] = "pending"


class Project(BaseModel):
    id: str
    title: str
    source: str
    source_type: Literal["youtube", "upload"]
    duration_sec: float = 0
    status: Literal["queued", "processing", "ready", "failed"] = "queued"
    pipeline: list[PipelineStep] = []
    clips: list[Clip] = []
    error: Optional[str] = None
