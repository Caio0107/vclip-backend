"""Corte 9:16, crop centralizado e legendas burn-in via FFmpeg + ASS."""
import os
import subprocess
from pathlib import Path

from app.schemas import Caption, ViralMoment, WordTimestamp


def _ass_time(t: float) -> str:
    """Converte segundos para H:MM:SS.cs (formato ASS)."""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


# Estilo ASS: fonte negrito, branco com contorno preto pesado.
# PrimaryColour = &H00BBGGRR (BGR + alpha)
ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,DejaVu Sans,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,260,1
Style: Hot,DejaVu Sans,72,&H0000F2FF,&H0000F2FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _build_ass(
    captions: list[Caption],
    clip_start: float,
    clip_end: float,
    keyword: str,
) -> str:
    """Gera arquivo ASS com legendas palavra-por-palavra dentro do clipe.
    Palavras que contêm `keyword` ganham cor ciano (estilo Hot)."""
    keyword_norm = (keyword or "").lower().strip()
    lines = [ASS_HEADER]

    # Agrupa palavras em "frases" curtas (max ~3 palavras por linha pra estilo Reels)
    words: list[WordTimestamp] = []
    for c in captions:
        if c.end < clip_start or c.start > clip_end:
            continue
        for w in c.words:
            if w.start >= clip_start and w.end <= clip_end:
                words.append(w)

    GROUP = 3
    for i in range(0, len(words), GROUP):
        chunk = words[i : i + GROUP]
        if not chunk:
            continue
        start = chunk[0].start - clip_start
        end = chunk[-1].end - clip_start

        # Detecta se algum token do chunk contém a keyword → muda estilo
        text_parts = []
        is_hot = False
        for w in chunk:
            t = _ass_escape(w.text)
            if keyword_norm and keyword_norm in w.text.lower():
                text_parts.append(f"{{\\c&H0000F2FF&}}{t}{{\\c&HFFFFFF&}}")
                is_hot = True
            else:
                text_parts.append(t)
        text = " ".join(text_parts).upper()
        style = "Hot" if is_hot else "Base"
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{text}"
        )

    return "\n".join(lines)


def render_clip(
    *,
    source_video: str,
    moment: ViralMoment,
    captions: list[Caption],
    out_path: str,
) -> str:
    """Recorta o trecho, faz crop centralizado para 9:16 (1080x1920) e queima legendas."""
    Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)
    duration = moment.end - moment.start

    # 1) ASS file
    ass_path = out_path + ".ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(_build_ass(captions, moment.start, moment.end, moment.keyword))

    # 2) Filtro: scale para preencher altura, crop centralizado em 1080x1920, depois subtitles
    # Assume vídeo horizontal — crop pega o centro. Em produção: rodar detecção facial.
    vf = (
        "scale=-2:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920:(in_w-1080)/2:0,"
        f"subtitles='{ass_path}':fontsdir=/usr/share/fonts"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{moment.start:.2f}",
        "-i", source_video,
        "-t", f"{duration:.2f}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(ass_path)
    return out_path
