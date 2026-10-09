"""Isolated JSON client used by the cancellable transcription worker.

Request secrets arrive only through stdin.  This process deliberately accepts
requests for the configured cloud AI hosts, TypeSafe Jev, and LM Studio on the local loopback
interface, and never echoes request headers or payloads to stdout/stderr.
"""

from __future__ import annotations

import json
import ipaddress
import sys
import time
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


ALLOWED_HOSTS = frozenset({
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "api.typesafe.ai",
})
LMSTUDIO_LOOPBACK_PATH = "/v1/chat/completions"
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
    hostname = parsed.hostname
    is_cloud_request = (
        parsed.scheme == "https"
        and hostname in ALLOWED_HOSTS
        and parsed.port in {None, 443}
    )
    try:
        is_loopback = bool(hostname and ipaddress.ip_address(hostname).is_loopback)
    except ValueError:
        is_loopback = False
    is_lmstudio_request = (
        parsed.scheme in {"http", "https"}
        and is_loopback
        and parsed.port is not None
        and parsed.path == LMSTUDIO_LOOPBACK_PATH
    )
    if (
        not (is_cloud_request or is_lmstudio_request)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_url")
    return raw_url


def main() -> int:
    try:
        request_data = read_request()
        if "request_budget" in request_data:
            return guarded_main(request_data)
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
        # request text or credentials into it.  Only a numeric Retry-After is
        # passed on so the parent can pace a retry.
        result: dict[str, Any] = {"ok": False, "kind": "http", "status": int(exc.code)}
        retry_after = str((exc.headers or {}).get("Retry-After") or "").strip()
        if retry_after.isascii() and retry_after.isdigit() and len(retry_after) <= 4:
            result["retry_after"] = int(retry_after)
        emit(result)
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


def guarded_main(request_data: dict) -> int:
    """Opt-in absolute deadlines, including all pre-send child preparation.

    -I omits the script directory; import only the adjacent application package,
    not cwd or user PYTHONPATH. This module is standard-library-only.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from gurumoji.services.ai.request_budget import BudgetHold, HASH_PATTERN, wire_timeout, prepare_wire

    ticket, payload = request_data.get("request_budget"), request_data.get("payload")
    safe_ticket = ticket if isinstance(ticket, dict) else {}
    receipt = {key: safe_ticket.get(key) if isinstance(safe_ticket.get(key), str)
        and HASH_PATTERN.fullmatch(safe_ticket[key]) else None
        for key in ("ticket_hash", "reservation_id", "payload_hash")}
    receipt.update(checked_at=time.monotonic(), send_started_at=None, response_at=None,
        cleanup_at=None, wire_timeout=None, sent=False)
    result: dict[str, Any] = {"ok": False, "kind": "worker_error"}
    try:
        wire_timeout(ticket, payload, time.monotonic)
        url = validate_url(request_data.get("url"))
        # Guarded requests are local-only, even though ordinary worker requests
        # also support approved cloud hosts.
        parsed = urllib.parse.urlsplit(url)
        if not ipaddress.ip_address(parsed.hostname or "").is_loopback or parsed.port is None or not 1 <= parsed.port <= 65535:
            raise BudgetHold("local_endpoint_required")
        headers = request_data.get("headers")
        if not isinstance(headers, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()):
            raise ValueError
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirects())
        # JSON serialization, opener construction and startup have consumed the
        # same absolute clock. Recheck immediately before the HTTP operation.
        timeout, sending_at = prepare_wire(ticket, payload, time.monotonic)
        receipt.update(send_started_at=sending_at, wire_timeout=timeout, sent="unknown")
        with opener.open(request, timeout=timeout) as response:
            receipt.update(sent=True, response_at=time.monotonic())
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_RESPONSE_BYTES:
                result = {"ok": False, "kind": "response_too_large"}
            else:
                content = response.read(MAX_RESPONSE_BYTES + 1)
                result = ({"ok": False, "kind": "response_too_large"} if len(content) > MAX_RESPONSE_BYTES
                    else {"ok": True, "status": int(getattr(response, "status", 200)),
                        "body": content.decode("utf-8", errors="replace")})
    except urllib.error.HTTPError as exc:
        receipt.update(sent=True, response_at=time.monotonic())
        result = {"ok": False, "kind": "http", "status": int(exc.code)}
        exc.close()  # Never read or relay an error body or headers.
    except BudgetHold:
        result = {"ok": False, "kind": "guard"}
    except (urllib.error.URLError, TimeoutError, OSError):
        result = {"ok": False, "kind": "network"}
    except Exception:
        result = {"ok": False, "kind": "worker_error"}
    finally:
        receipt["cleanup_at"] = time.monotonic()
    result["budget_receipt"] = receipt
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
