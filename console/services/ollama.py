from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings


@dataclass(frozen=True)
class OllamaError(Exception):
    message: str
    status_code: int | None = None
    details: dict[str, Any] | None = None

    def __str__(self) -> str:  # pragma: no cover
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        return " ".join(bits)


def _base_url() -> str:
    base = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    return base.rstrip("/")


def _timeout() -> float:
    return float(getattr(settings, "OLLAMA_REQUEST_TIMEOUT_SECONDS", 60))


def _raise_for_status(resp: requests.Response) -> None:
    if 200 <= resp.status_code < 300:
        return

    details: dict[str, Any] | None = None
    try:
        details = resp.json()
    except Exception:
        details = {"text": resp.text}

    raise OllamaError(
        message="Ollama request failed",
        status_code=resp.status_code,
        details=details,
    )


def _iter_json_lines(resp: requests.Response) -> Iterator[dict[str, Any]]:
    """
    Ollama streaming endpoints return a stream of JSON objects, one per line.
    This generator yields decoded objects as they arrive.
    """
    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise OllamaError(
                message="Failed to decode Ollama streaming JSON",
                status_code=resp.status_code,
                details={"line": line, "error": str(e)},
            ) from e
        yield obj


def get_version() -> str:
    """
    GET /api/version -> {"version": "x.y.z"}
    """
    url = f"{_base_url()}/api/version"
    try:
        resp = requests.get(url, timeout=_timeout())
    except requests.RequestException as e:
        raise OllamaError("Unable to connect to Ollama", details={"error": str(e)}) from e
    _raise_for_status(resp)
    data = resp.json()
    return str(data.get("version", ""))


def list_models() -> dict[str, Any]:
    """
    GET /api/tags -> {"models": [...]}
    """
    url = f"{_base_url()}/api/tags"
    try:
        resp = requests.get(url, timeout=_timeout())
    except requests.RequestException as e:
        raise OllamaError("Unable to connect to Ollama", details={"error": str(e)}) from e
    _raise_for_status(resp)
    return resp.json()


def list_running_models() -> dict[str, Any]:
    """
    GET /api/ps -> {"models": [...]}
    """
    url = f"{_base_url()}/api/ps"
    try:
        resp = requests.get(url, timeout=_timeout())
    except requests.RequestException as e:
        raise OllamaError("Unable to connect to Ollama", details={"error": str(e)}) from e
    _raise_for_status(resp)
    return resp.json()


def delete_model(model: str) -> None:
    """
    DELETE /api/delete { "model": "name" }
    """
    url = f"{_base_url()}/api/delete"
    payload = {"model": model}
    try:
        resp = requests.delete(url, json=payload, timeout=_timeout())
    except requests.RequestException as e:
        raise OllamaError("Unable to connect to Ollama", details={"error": str(e)}) from e
    _raise_for_status(resp)


def pull_model_stream(model: str, *, insecure: bool | None = None) -> Iterator[dict[str, Any]]:
    """
    POST /api/pull (streaming)

    Yields progress objects such as:
      {"status": "pulling manifest"}
      {"status": "pulling <digest>", "digest": "...", "total": ..., "completed": ...}
      {"status": "success"}
    """
    url = f"{_base_url()}/api/pull"
    payload: dict[str, Any] = {"model": model, "stream": True}
    if insecure is not None:
        payload["insecure"] = insecure

    try:
        resp = requests.post(url, json=payload, timeout=_timeout(), stream=True)
    except requests.RequestException as e:
        raise OllamaError("Unable to connect to Ollama", details={"error": str(e)}) from e

    _raise_for_status(resp)
    yield from _iter_json_lines(resp)


def chat_stream(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    keep_alive: str | None = None,
    format: str | dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """
    POST /api/chat (streaming)

    Each streamed object looks like:
      {"model": "...", "message": {"role": "assistant", "content": "The"}, "done": false}
    Final object includes timings + done=true.
    """
    url = f"{_base_url()}/api/chat"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools is not None:
        payload["tools"] = tools
    if options is not None:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    if format is not None:
        payload["format"] = format

    try:
        resp = requests.post(url, json=payload, timeout=_timeout(), stream=True)
    except requests.RequestException as e:
        raise OllamaError("Unable to connect to Ollama", details={"error": str(e)}) from e

    _raise_for_status(resp)
    yield from _iter_json_lines(resp)


def ensure_list_of_messages(messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convenience helper: validate/normalize messages iterable into a list of dicts.
    """
    normalized: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            raise OllamaError("Invalid message object", details={"message": repr(m)})
        if "role" not in m or "content" not in m:
            raise OllamaError("Message missing required fields", details={"message": m})
        normalized.append(m)
    return normalized


