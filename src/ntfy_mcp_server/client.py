"""ntfy.sh HTTP client — Publish + Read."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

NTFY_URL = os.getenv("NTFY_URL", "").rstrip("/")
NTFY_TOKEN = os.getenv("NTFY_TOKEN", "")


def _check_config() -> None:
    if not NTFY_URL or not NTFY_TOKEN:
        raise RuntimeError("NTFY_URL und NTFY_TOKEN müssen gesetzt sein.")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NTFY_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def publish(
    topic: str,
    message: str,
    title: str | None = None,
    priority: int | None = None,
    tags: list[str] | None = None,
    click: str | None = None,
    delay: str | None = None,
    markdown: bool = False,
    actions: list[dict[str, Any]] | None = None,
    attach: str | None = None,
    filename: str | None = None,
    icon: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """JSON-publish an die ntfy-Root-URL.

    ntfy docs: https://docs.ntfy.sh/publish/#publish-as-json
    """
    _check_config()
    payload: dict[str, Any] = {"topic": topic, "message": message}
    if title:
        payload["title"] = title
    if priority is not None:
        payload["priority"] = priority
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click
    if delay:
        payload["delay"] = delay
    if markdown:
        payload["markdown"] = True
    if actions:
        payload["actions"] = actions
    if attach:
        payload["attach"] = attach
    if filename:
        payload["filename"] = filename
    if icon:
        payload["icon"] = icon
    if email:
        payload["email"] = email

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(NTFY_URL, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_messages(
    topic: str,
    since: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Holt gecachte Messages eines Topics (poll-mode, kein SSE).

    `since` kann sein: Unix-Timestamp, ISO-Datum, '10m', '1h', 'all'
    """
    _check_config()
    params = {"poll": "1"}
    if since:
        params["since"] = since

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NTFY_URL}/{topic}/json",
            params=params,
            headers={"Authorization": f"Bearer {NTFY_TOKEN}", "Accept": "application/x-ndjson"},
        )
        resp.raise_for_status()
        # NDJSON: ein Message-Objekt pro Zeile, plus optionale "open"/"keepalive"-Events
        import json as _json
        out: list[dict[str, Any]] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = _json.loads(line)
            except Exception:
                continue
            if obj.get("event") != "message":
                continue
            out.append(obj)
            if limit and len(out) >= limit:
                break
        return out


async def list_user_topics() -> dict[str, Any]:
    """Listet die Topics, auf die der konfigurierte Token Zugriff hat.

    ntfy hat keine offizielle 'list topics'-API für User. Wir nutzen den
    `/v1/account` Endpoint, der die Zugriffsmatrix zurückgibt.
    """
    _check_config()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{NTFY_URL}/v1/account", headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        # Wir geben das ganze Account-Objekt zurück; access[] enthält die Topics
        return data
