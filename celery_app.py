"""Celery app + task pipeline."""
import os
import uuid
from pathlib import Path

from celery import Celery

from app.config import settings
from app.schemas import Project, Clip, PipelineStep
from app.store import save_project, get_project, update_step
from app.services import ingest, transcribe, scoring, render, storage, webhook


celery_app = Celery("vclip", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.workers.pipeline.process_project": {"queue": "pipeline"}}
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1  # 1 job pesado por worker


def _initial_pipeline() -> list[PipelineStep]:
    return [
        PipelineStep(key="ingest",    label="Ingestão da fonte",         status="pending"),
        PipelineStep(key="whisper",   label="Transcrição (Whisper)",     status="pending"),
        PipelineStep(key="score",     label="Scoring viral (GPT-4o)",    status="pending"),
        PipelineStep(key="cut",       label="Corte e formatação 9:16",   status="pending"),
        PipelineStep(key="captions",  label="Legendagem dinâmica",       status="pending"),
    ]


@celery_app.task(bind=True, name="app.workers.pipeline.process_project")
def process_project(self, project_id: str, source_url: str | None, upload_path: str | None,
                    source_type: str, language: str | None):
    project = get_project(project_id)
    if not project:
        return

    workdir = Path(settings.data_dir) / "projects" / project_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        project.status = "processing"
        save_project(project)

        # ---- 1. INGEST ----
        update_step(project_id, "ingest", status="active", progress=10)
        if source_type == "youtube":
            video_path, title, duration = ingest.download_youtube(source_url, str(workdir))
        else:
            video_path = upload_path
            duration = ingest.probe_duration(video_path)
            title = project.title or os.path.basename(video_path)

        project = get_project(project_id)
        project.title = project.title or title
        project.duration_sec = duration
        save_project(project)

        audio_path = str(workdir / "audio.wav")
        ingest.extract_audio(video_path, audio_path)
        update_step(project_id, "ingest", status="done", progress=100)

        # ---- 2. WHISPER ----
        update_step(project_id, "whisper", status="active", progress=15)
        captions = transcribe.transcribe(audio_path, language=language)
        update_step(project_id, "whisper", status="done", progress=100)

        # ---- 3. SCORING ----
        update_step(project_id, "score", status="active", progress=30)
        moments = scoring.score_moments(
            captions,
            max_clips=settings.max_clips_per_video,
            min_seconds=settings.min_clip_seconds,
            max_seconds=settings.max_clip_seconds,
        )
        update_step(project_id, "score", status="done", progress=100)

        # cria entradas de clipe pendentes
        project = get_project(project_id)
        project.clips = [
            Clip(
                id=f"clip_{i:02d}",
                title=m.title,
                hook=m.hook,
                score=m.score,
                start=m.start,
                end=m.end,
                duration=m.end - m.start,
                caption_preview=m.keyword.upper(),
                status="pending",
            )
            for i, m in enumerate(moments)
        ]
        save_project(project)

        # ---- 4. CUT + 5. CAPTIONS (loop por clipe) ----
        total = len(moments)
        update_step(project_id, "cut", status="active", progress=0)
        update_step(project_id, "captions", status="active", progress=0)

        for i, m in enumerate(moments):
            clip_id = f"clip_{i:02d}"
            out_path = str(workdir / f"{clip_id}.mp4")

            # Atualiza status do clipe individual
            project = get_project(project_id)
            for c in project.clips:
                if c.id == clip_id:
                    c.status = "processing"
            save_project(project)

            render.render_clip(
                source_video=video_path,
                moment=m,
                captions=captions,
                out_path=out_path,
            )

            # Upload
            url = storage.upload_clip(out_path, f"{project_id}/{clip_id}.mp4")

            project = get_project(project_id)
            for c in project.clips:
                if c.id == clip_id:
                    c.download_url = url
                    c.status = "ready"
            save_project(project)

            pct = int(((i + 1) / total) * 100)
            update_step(project_id, "cut", progress=pct)
            update_step(project_id, "captions", progress=pct)

            webhook.notify("clip.ready", {
                "project_id": project_id,
                "clip_id": clip_id,
                "url": url,
            })

        update_step(project_id, "cut", status="done", progress=100)
        update_step(project_id, "captions", status="done", progress=100)

        project = get_project(project_id)
        project.status = "ready"
        save_project(project)
        webhook.notify("project.ready", {"project_id": project_id})

    except Exception as e:  # noqa
        project = get_project(project_id)
        if project:
            project.status = "failed"
            project.error = str(e)
            save_project(project)
        webhook.notify("project.failed", {"project_id": project_id, "error": str(e)})
        raise
