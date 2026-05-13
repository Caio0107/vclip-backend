"""Webhook assinado de volta pro frontend."""
import hmac
import hashlib
import json
import httpx

from app.config import settings


def _sign(body: bytes) -> str:
    return hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()


def notify(event: str, payload: dict) -> None:
    if not settings.frontend_webhook_url:
        return
    body = json.dumps({"event": event, "data": payload}).encode()
    sig = _sign(body)
    try:
        httpx.post(
            settings.frontend_webhook_url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": sig,
            },
            timeout=10.0,
        )
    except Exception as e:  # noqa
        print(f"[webhook] erro: {e}")
