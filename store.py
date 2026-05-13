"""Store em Redis para estado de projetos (em produção, troque por Postgres)."""
import json
from typing import Optional
import redis
from app.config import settings
from app.schemas import Project

_r = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _key(pid: str) -> str:
    return f"vclip:project:{pid}"


def save_project(p: Project) -> None:
    _r.set(_key(p.id), p.model_dump_json())
    _r.publish(f"vclip:events:{p.id}", p.model_dump_json())


def get_project(pid: str) -> Optional[Project]:
    raw = _r.get(_key(pid))
    return Project.model_validate_json(raw) if raw else None


def update_step(pid: str, step_key: str, *, progress: int = None, status: str = None) -> None:
    p = get_project(pid)
    if not p:
        return
    for s in p.pipeline:
        if s.key == step_key:
            if progress is not None:
                s.progress = progress
            if status is not None:
                s.status = status
    save_project(p)


def subscribe_events(pid: str):
    """Generator de eventos para SSE."""
    pubsub = _r.pubsub()
    pubsub.subscribe(f"vclip:events:{pid}")
    for msg in pubsub.listen():
        if msg["type"] == "message":
            yield msg["data"]
