"""FastAPI HTTP API."""
import os
import uuid
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.schemas import CreateProjectRequest, Project
from app.store import save_project, get_project, subscribe_events
from app.workers.celery_app import process_project, _initial_pipeline


app = FastAPI(title="V-CLIP API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/projects", response_model=Project)
def create_project(req: CreateProjectRequest):
    if req.source_type == "youtube" and not req.source_url:
        raise HTTPException(400, "source_url é obrigatório para youtube")
    if req.source_type == "upload" and not req.upload_path:
        raise HTTPException(400, "upload_path é obrigatório para upload")

    pid = uuid.uuid4().hex[:10]
    project = Project(
        id=pid,
        title=req.title or "Novo projeto",
        source=str(req.source_url or req.upload_path),
        source_type=req.source_type,
        status="queued",
        pipeline=_initial_pipeline(),
    )
    save_project(project)

    process_project.delay(
        pid,
        str(req.source_url) if req.source_url else None,
        req.upload_path,
        req.source_type,
        req.language,
    )
    return project


@app.post("/api/uploads", response_model=dict)
async def upload_video(file: UploadFile = File(...)):
    """Upload de arquivo. Retorna upload_path para usar no POST /api/projects."""
    uid = uuid.uuid4().hex[:10]
    dest_dir = Path(settings.data_dir) / "uploads" / uid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (file.filename or "upload.mp4")
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return {"upload_path": str(dest)}


@app.get("/api/projects/{pid}", response_model=Project)
def project_status(pid: str):
    p = get_project(pid)
    if not p:
        raise HTTPException(404, "Projeto não encontrado")
    return p


@app.get("/api/projects/{pid}/events")
async def project_events(pid: str):
    """SSE: stream de atualizações em tempo real."""
    if not get_project(pid):
        raise HTTPException(404, "Projeto não encontrado")

    async def event_gen():
        # snapshot inicial
        yield {"event": "snapshot", "data": get_project(pid).model_dump_json()}
        # loop bloqueante em thread
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def listen():
            for data in subscribe_events(pid):
                asyncio.run_coroutine_threadsafe(queue.put(data), loop)

        loop.run_in_executor(None, listen)
        while True:
            data = await queue.get()
            yield {"event": "update", "data": data}

    return EventSourceResponse(event_gen())


# Serve arquivos locais quando S3 não está configurado
@app.get("/files/{path:path}")
def serve_file(path: str):
    full = Path(settings.data_dir) / "public" / path
    if not full.exists():
        raise HTTPException(404)
    return FileResponse(full, media_type="video/mp4")
