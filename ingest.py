"""Download de vídeo via yt-dlp (ou cópia do upload local)."""
import os
import subprocess
from pathlib import Path

import yt_dlp


def download_youtube(url: str, dest_dir: str) -> tuple[str, str, float]:
    """Baixa o melhor MP4 (até 1080p). Retorna (path, title, duration_sec)."""
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    out_tpl = os.path.join(dest_dir, "source.%(ext)s")
    opts = {
        "outtmpl": out_tpl,
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")
        duration = float(info.get("duration", 0))
    final = os.path.join(dest_dir, "source.mp4")
    if not os.path.exists(final):
        # yt-dlp pode ter salvo com outra extensão; pega o primeiro
        for f in os.listdir(dest_dir):
            if f.startswith("source."):
                final = os.path.join(dest_dir, f)
                break
    return final, title, duration


def extract_audio(video_path: str, out_path: str) -> str:
    """Extrai áudio mono 16kHz WAV pra Whisper."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
            out_path,
        ],
        check=True, capture_output=True,
    )
    return out_path


def probe_duration(video_path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())
