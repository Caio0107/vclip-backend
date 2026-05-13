"""Transcrição com faster-whisper (timestamps por palavra)."""
from functools import lru_cache
from faster_whisper import WhisperModel

from app.config import settings
from app.schemas import Caption, WordTimestamp


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def transcribe(audio_path: str, language: str | None = None) -> list[Caption]:
    """Retorna segmentos com palavras cronometradas."""
    model = get_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    captions: list[Caption] = []
    for seg in segments:
        words = [
            WordTimestamp(text=w.word.strip(), start=w.start, end=w.end)
            for w in (seg.words or [])
        ]
        captions.append(
            Caption(start=seg.start, end=seg.end, text=seg.text.strip(), words=words)
        )
    return captions
