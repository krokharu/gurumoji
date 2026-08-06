"""Isolated HTTPS JSON client used by the cancellable transcription worker.

Request secrets arrive only through stdin.  This process deliberately accepts
requests for the two configured AI API hosts and never echoes request headers
or payloads to stdout/stderr.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


ALLOWED_HOSTS = frozenset({"api.openai.com", "generativelanguage.googleapis.com"})
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def configure_utf8_stdio() -> None:
    """Keep the worker protocol UTF-8 even on Windows code-page consoles."""
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            # Embedded or already-closed streams are not expected in production,
            # but skipping them keeps the helper safe to import in test harnesses.
            pass


configure_utf8_stdio()


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.flush()


def read_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("request_too_large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("invalid_request")
    return value


def validate_url(raw_url: Any) -> str:
    if not isinstance(raw_url, str):
        raise ValueError("invalid_url")
    parsed = urllib.parse.urlsplit(raw_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or parsed.fragment
    ):
        raise ValueError("invalid_url")
    return raw_url


def main() -> int:
    try:
        request_data = read_request()
        url = validate_url(request_data.get("url"))
        raw_headers = request_data.get("headers")
        payload = request_data.get("payload")
        if not isinstance(raw_headers, dict) or not isinstance(payload, dict):
            raise ValueError("invalid_request")
        headers = {
            str(key): str(value)
            for key, value in raw_headers.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if len(headers) != len(raw_headers):
            raise ValueError("invalid_headers")
        timeout = max(1.0, min(600.0, float(request_data.get("timeout", 240))))
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        opener = urllib.request.build_opener(RejectRedirects())
        with opener.open(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                emit({"ok": False, "kind": "response_too_large"})
                return 0
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_body) > MAX_RESPONSE_BYTES:
                emit({"ok": False, "kind": "response_too_large"})
                return 0
            emit({
                "ok": True,
                "status": int(getattr(response, "status", 200)),
                "body": response_body.decode("utf-8", errors="replace"),
            })
            return 0
    except urllib.error.HTTPError as exc:
        # Do not relay an error body: a provider or intermediary could reflect
        # request text or credentials into it.
        emit({"ok": False, "kind": "http", "status": int(exc.code)})
        return 0
    except (urllib.error.URLError, TimeoutError, OSError):
        emit({"ok": False, "kind": "network"})
        return 0
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        emit({"ok": False, "kind": str(exc)[:80] or "invalid_request"})
        return 0
    except Exception:
        emit({"ok": False, "kind": "worker_error"})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
