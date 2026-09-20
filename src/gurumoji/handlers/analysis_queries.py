"""Read-only analysis use cases, independent from Flask."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..analysis_method_registry import METHODS, REGISTRY_VERSION


class AnalysisQueryNotFound(LookupError):
    """The requested conversation, run, or artifact does not exist."""


@dataclass(frozen=True)
class AnalysisArtifact:
    data: bytes
    media_type: str
    download_name: str


class AnalysisQueries:
    """Coordinate analysis reads using the existing store and item lookup."""

    def __init__(
        self,
        *,
        store: Any,
        find_item: Callable[[str], Any],
        source_fingerprint: Callable[[Any], str],
        database_connection: Callable[[], Any],
        build_analysis: Callable[[Any], dict[str, Any]],
        public_insight_request: Callable[[Any], dict[str, Any] | None],
        public_transformer_request: Callable[[Any], dict[str, Any] | None],
        expose_local_paths: bool,
    ) -> None:
        self._store = store
        self._find_item = find_item
        self._source_fingerprint = source_fingerprint
        self._database_connection = database_connection
        self._build_analysis = build_analysis
        self._public_insight_request = public_insight_request
        self._public_transformer_request = public_transformer_request
        self._expose_local_paths = expose_local_paths

    def methods(self) -> dict[str, Any]:
        return {
            "version": REGISTRY_VERSION,
            "methods": [
                {"id": key, "title": title, "datasets": tables}
                for key, title, tables in METHODS
            ],
        }

    def runs(self, item_id: str) -> dict[str, Any]:
        item = self._find_item(item_id)
        if item is None:
            raise AnalysisQueryNotFound("対象の会話が見つかりません。")
        fingerprint = self._source_fingerprint(item)
        runs = []
        for stored in self._store.list(item_id):
            run = dict(stored)
            run["stale"] = bool(
                run["stale"] or run["input_fingerprint"] != fingerprint
            )
            runs.append(
                self._store.public(run, local=self._expose_local_paths)
            )
        return {
            "runs": runs,
            "storage": {
                "database": "SQLite",
                "artifacts": "CSV / JSON",
                "notes": "ResearchVault",
            },
        }

    def artifact(self, artifact_id: str) -> AnalysisArtifact:
        try:
            metadata, data = self._store.read_artifact(artifact_id)
        except LookupError as exc:
            raise AnalysisQueryNotFound("保存ファイルが見つかりません。") from exc
        run = self._store.get(metadata["run_id"])
        if not run or self._find_item(run["item_id"]) is None:
            raise AnalysisQueryNotFound("保存ファイルが見つかりません。")
        return AnalysisArtifact(
            data=data,
            media_type=metadata["media_type"],
            download_name=Path(metadata["name"]).name,
        )

    def insights(self, item_id: str) -> dict[str, Any]:
        """Read the latest request and saved insight from one SQLite snapshot."""
        with self._database_connection() as connection:
            connection.execute("BEGIN")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisQueryNotFound("処理済みデータが見つかりません。")
            run = connection.execute(
                "SELECT * FROM analysis_insight_requests WHERE item_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        analysis = self._build_analysis(item)
        return {
            "insights": analysis["insights"],
            "run": self._public_insight_request(run),
        }

    def transformer(self, item_id: str) -> dict[str, Any]:
        with self._database_connection() as connection:
            connection.execute("BEGIN")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisQueryNotFound("処理済みデータが見つかりません。")
            run = connection.execute(
                "SELECT * FROM transformer_analysis_requests WHERE item_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        analysis = self._build_analysis(item)
        return {
            "transformer": analysis["transformer"],
            "run": self._public_transformer_request(run),
        }

    def classifications(self, item_id: str) -> dict[str, Any]:
        with self._database_connection() as connection:
            connection.execute("BEGIN")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisQueryNotFound("データが見つかりません。")
        analysis = self._build_analysis(item)
        return {"segment_classification": analysis["segment_classification"]}
