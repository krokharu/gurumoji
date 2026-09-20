"""Analysis save and Vault retry use cases, independent from Flask."""

from __future__ import annotations

from typing import Any, Callable

from ..analysis_store import StoreConflict


class AnalysisCommandNotFound(LookupError):
    """The requested conversation or saved run does not exist."""


class AnalysisCommands:
    """Coordinate fixed-result saves without changing store ownership rules."""

    def __init__(
        self,
        *,
        store: Any,
        find_item: Callable[[str], Any],
        build_analysis: Callable[[Any], dict[str, Any]],
        search_kwic: Callable[..., dict[str, Any]],
        archive_analysis: Callable[..., dict[str, Any]],
        source_fingerprint: Callable[[Any], str],
        mark_stale: Callable[[str], None],
        write_lock: Any,
        expose_local_paths: bool,
    ) -> None:
        self._store = store
        self._find_item = find_item
        self._build_analysis = build_analysis
        self._search_kwic = search_kwic
        self._archive_analysis = archive_analysis
        self._source_fingerprint = source_fingerprint
        self._mark_stale = mark_stale
        self._write_lock = write_lock
        self._expose_local_paths = expose_local_paths

    def save(
        self,
        item_id: str,
        *,
        request_id: str,
        source_revision: int,
        analysis_revision: int,
        kwic_request: dict[str, Any] | None,
        app_url: str,
    ) -> dict[str, Any]:
        with self._write_lock:
            item = self._find_item(item_id)
            if item is None:
                raise AnalysisCommandNotFound("対象の会話が見つかりません。")
            if (
                source_revision != item["revision_count"]
                or analysis_revision != item["analysis_revision"]
            ):
                raise StoreConflict(
                    "元データまたは分析条件が更新されています。再集計してください。"
                )

            analysis = self._build_analysis(item)
            kwic = None
            if kwic_request is not None:
                kwic = self._search_kwic(
                    analysis,
                    analysis["research"]["linguistics"]["morphemes"],
                    kwic_request.get("q", ""),
                    mode=kwic_request.get("mode", "literal"),
                    speaker=kwic_request.get("speaker", ""),
                    limit=None,
                )
            run = self._archive_analysis(
                item,
                analysis,
                request_id,
                kwic=kwic,
                kind="kwic" if kwic is not None else "text_analysis",
                app_url=app_url,
                store=self._store,
            )
        return self._store.public(run, local=self._expose_local_paths)

    def retry_vault(self, run_id: str) -> dict[str, Any]:
        run = self._store.get(run_id)
        if not run or self._find_item(run["item_id"]) is None:
            raise AnalysisCommandNotFound("保存結果が見つかりません。")
        with self._write_lock:
            item = self._find_item(run["item_id"])
            if item is None:
                raise AnalysisCommandNotFound("対象の会話が見つかりません。")
            if run["input_fingerprint"] != self._source_fingerprint(item):
                self._mark_stale(run_id)
            result = self._store.retry(run_id)
        return self._store.public(result, local=self._expose_local_paths)
