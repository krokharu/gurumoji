"""AI-assisted transcript finishing without application-global state."""

from __future__ import annotations

from typing import Any, Callable


def clean(
    segments: list[dict[str, Any]], provider: str, api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None], *,
    call_json: Callable[..., dict[str, Any]], finish: Callable[..., list[dict[str, Any]]],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    outline: dict[str, Any] | None = None, ai_efforts: dict | None = None,
) -> list[dict[str, Any]]:
    def call(system: str, prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
        return call_json(provider, api_key, model, system, prompt, name, schema,
                         check_cancelled, usage_callback, base_url,
                         **({"ai_efforts": ai_efforts} if ai_efforts else {}))
    return finish(segments, call, status, check_cancelled, outline=outline)


def review_with_jev(
    segments: list[dict[str, Any]], api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None], *,
    clean_single_line: Callable[[Any, int], str], default_model: str,
    post: Callable[..., dict[str, Any]], review: Callable[..., tuple[dict[str, dict[str, Any]], dict[str, Any]]],
    outline: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not api_key:
        raise ValueError("tokens.json に typesafe_api_key を設定してください。")
    resolved_model = clean_single_line(model, 200) or default_model

    def call(state: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
        return post("https://api.typesafe.ai/v1/systemone",
                    {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    {"state": state, "model": resolved_model, "questions": questions},
                    check_cancelled=check_cancelled)
    return review(segments, outline, call, status, check_cancelled, model=resolved_model)


def repair_recommended(
    segments: list[dict[str, Any]], reviews: dict[str, dict[str, Any]],
    provider: str, api_key: str, model: str, status: Callable[[str], None],
    check_cancelled: Callable[[], None], *, call_json: Callable[..., dict[str, Any]],
    repair: Callable[..., list[dict[str, Any]],], usage_callback: Callable[[dict[str, Any]], None] | None = None,
    base_url: str = "", ai_efforts: dict | None = None, effort: str = "medium",
    outline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    def call(system: str, prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
        return call_json(provider, api_key, model, system, prompt, name, schema,
                         check_cancelled, usage_callback, base_url,
                         **({"ai_efforts": ai_efforts} if ai_efforts else {}))
    return repair(segments, reviews, call, status, check_cancelled, effort=effort, outline=outline)


def classify_with_jev(
    segments: list[dict[str, Any]], topics: list[dict[str, str]], api_key: str,
    model: str, *, clean_single_line: Callable[[Any, int], str], default_model: str,
    post: Callable[..., dict[str, Any]], classify: Callable[..., tuple[dict[str, dict[str, Any]], dict[str, Any]]],
    status: Callable[[str], None] = lambda _message: None,
    check_cancelled: Callable[[], None] = lambda: None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not api_key:
        raise ValueError("tokens.json に typesafe_api_key を設定してください。")
    resolved_model = clean_single_line(model, 200) or default_model

    def call(state: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
        return post("https://api.typesafe.ai/v1/systemone",
                    {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    {"state": state, "model": resolved_model, "questions": questions},
                    check_cancelled=check_cancelled)
    return classify(segments, topics, call, status, check_cancelled, model=resolved_model)


def create_outline(
    segments: list[dict[str, Any]], speaker_names: dict[str, str], provider: str,
    api_key: str, model: str, status: Callable[[str], None], check_cancelled: Callable[[], None], *,
    call_json: Callable[..., dict[str, Any]], create: Callable[..., dict[str, Any]], now_iso: Callable[[], str],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    def call(system: str, prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
        return call_json(provider, api_key, model, system, prompt, name, schema,
                         check_cancelled, usage_callback, base_url,
                         **({"ai_efforts": ai_efforts} if ai_efforts else {}))
    result = create(segments, speaker_names, call, status, check_cancelled)
    result["provenance"].update({"provider": provider, "model": model, "generated_at": now_iso()})
    return result
