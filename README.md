# V-CLIP Backend (FastAPI + Whisper + GPT-4o + FFmpeg)

API que transforma vídeos longos em cortes verticais 9:16 com legendas burn-in.

## Pipeline

```
URL/Upload  →  yt-dlp (download)
            →  ffmpeg (extrai áudio 16kHz mono)
            →  Whisper (transcrição com timestamps por palavra)
            →  GPT-4o (scoring viral + seleção de momentos)
            →  ffmpeg (corte + crop dinâmico 9:16)
            →  ffmpeg + ASS (legendas burn-in estilizadas)
            →  S3/R2/Local (upload dos MP4s)
            →  Webhook → frontend
```

## Stack

- FastAPI (API HTTP)
- Celery + Redis (fila de jobs assíncronos — múltiplos usuários em paralelo)
- faster-whisper (transcrição local, ~4x mais rápido que openai-whisper)
- OpenAI GPT-4o (scoring de viralidade)
- yt-dlp (download de YouTube)
- ffmpeg + ffmpeg-python (corte, crop, legenda)
- boto3 (upload pra S3/R2)

## Rodando local

```bash
docker compose up --build
```

Depois:
- API: http://localhost:8000/docs
- Flower (monitor de fila): http://localhost:5555

## Variáveis (`.env`)

```env
OPENAI_API_KEY=sk-...
REDIS_URL=redis://redis:6379/0
WHISPER_MODEL=base            # tiny | base | small | medium | large-v3
WHISPER_DEVICE=cpu            # cpu | cuda
S3_BUCKET=vclip-clips
S3_REGION=auto
S3_ENDPOINT=https://...r2.cloudflarestorage.com
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
PUBLIC_BASE_URL=https://cdn.seudominio.com
WEBHOOK_SECRET=changeme
FRONTEND_WEBHOOK_URL=https://seuapp.lovable.app/api/public/clip-webhook
```

## Endpoints

- `POST /api/projects` — cria projeto a partir de URL ou upload
- `GET  /api/projects/{id}` — status + clipes
- `GET  /api/projects/{id}/events` — Server-Sent Events de progresso
- `GET  /healthz`

## Deploy

- **Render / Railway / Fly.io**: use o `Dockerfile`. Para Whisper rápido use plano com GPU (RunPod, Lambda Labs).
- **CPU-only** funciona com `WHISPER_MODEL=base` para vídeos < 20 min.
