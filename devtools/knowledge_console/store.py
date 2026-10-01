"""Standalone development control-plane projections for the knowledge builder.

The console shares the knowledge builder SQLite database but keeps its task,
trace, and event tables separate from the worker-owned job/commit tables.
Task model responses and their evidence checks are retained here; credentials
and unrelated runtime source data are not part of this store's contract.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import closing, contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# Two bounded 512 KiB worker responses (latest + best), with evidence metadata,
# JSON escaping and scored-attempt history. Keep full text, not a lossy preview.
MAX_TASK_RESULT_BYTES = 2 * 1024 * 1024


def _task_result_json(result: dict[str, Any]) -> str:
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_TASK_RESULT_BYTES:
        raise ValueError("A100 result exceeds the console storage limit (2 MiB)")
    return encoded


def _error_text(value: Any) -> str:
    """Keep diagnostic line breaks and length, excluding credential values."""
    return re.sub(
        r'''(?i)bearer\s+\S+|(?:api[_ -]?key|queue[_ -]?secret|(?:access|refresh)[_ -]?token|password)["']?\s*[:=]\s*["']?[^\s,"']+''',
        "[資格情報を除外]", str(value or "").strip(),
    )


EXPERTS: tuple[dict[str, str], ...] = (
    {"id": "conversation-timing", "name": "会話タイミング分析"},
    {"id": "correlation", "name": "相関分析"},
    {"id": "cross-session-comparison", "name": "セッション間比較"},
    {"id": "descriptive-statistics", "name": "記述統計"},
    {"id": "embedding-topic-exploration", "name": "埋め込み・トピック探索"},
    {"id": "focus-group-interaction", "name": "フォーカスグループ相互作用"},
    {"id": "framework-method", "name": "フレームワーク法"},
    {"id": "group-comparison-statistics", "name": "群間比較統計"},
    {"id": "japanese-text-preprocessing", "name": "日本語テキスト前処理"},
    {"id": "kj-method", "name": "KJ法"},
    {"id": "m-gta", "name": "M-GTA"},
    {"id": "participation-balance", "name": "参加バランス"},
    {"id": "qualitative-content-analysis", "name": "質的内容分析"},
    {"id": "quantitative-text-analysis", "name": "計量テキスト分析"},
    {"id": "scat", "name": "SCAT"},
    {"id": "speech-emotion-recognition", "name": "音声感情認識"},
    {"id": "thematic-analysis", "name": "テーマ分析"},
)

MODELS: tuple[dict[str, str], ...] = (
    {"id": "qwen3-80b", "name": "Qwen3 80B", "route": "a100"},
    {"id": "local-default", "name": "Local LLM", "route": "local"},
    {"id": "codex", "name": "Codex", "route": "codex"},
)

KNOWLEDGE_BLOCKS: tuple[dict[str, str], ...] = (
    {
        "id": "input-layer",
        "label": "入力層",
        "kind": "INPUT",
        "description": "テスト質問・対象データ",
    },
    {
        "id": "obsidian-layer-1",
        "label": "Obsidian 第1層",
        "kind": "INDEX",
        "description": "索引・対象Vaultの選択",
    },
    {
        "id": "obsidian-layer-2",
        "label": "Obsidian 第2層",
        "kind": "KNOWLEDGE",
        "description": "Source・Claim・Expertの関係",
    },
    {
        "id": "obsidian-layer-3",
        "label": "Obsidian 第3層",
        "kind": "CONTEXT",
        "description": "評価・Pack・適用条件",
    },
    {
        "id": "thought-buffer",
        "label": "思考一時保存",
        "kind": "TRANSIENT",
        "description": "中間状態のみ・内部推論は保存しない",
    },
    {
        "id": "label-generation",
        "label": "ラベル生成",
        "kind": "TRANSFORM",
        "description": "分類名・根拠IDの生成",
    },
    {
        "id": "output-data",
        "label": "出力データ",
        "kind": "OUTPUT",
        "description": "分析結果・監査イベント",
    },
)

DEFAULT_TASKS: tuple[dict[str, str], ...] = (
    {"title": "入力データ形式を検証", "expert_id": "japanese-text-preprocessing", "actor": "local", "model_id": "local-default"},
    {"title": "Obsidian 第1層の索引を確認", "expert_id": "embedding-topic-exploration", "actor": "codex", "model_id": "codex"},
    {"title": "Obsidian 第2層の知識関係を抽出", "expert_id": "qualitative-content-analysis", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "Obsidian 第3層の適用条件を評価", "expert_id": "framework-method", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "思考一時保存の保持範囲を検証", "expert_id": "thematic-analysis", "actor": "local", "model_id": "local-default"},
    {"title": "分析ラベル候補を生成", "expert_id": "kj-method", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "出力データのスキーマを検証", "expert_id": "descriptive-statistics", "actor": "codex", "model_id": "codex"},
    {"title": "会話タイミング知識を再評価", "expert_id": "conversation-timing", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "参加バランス指標を更新", "expert_id": "participation-balance", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "テーマ分析ルールを検証", "expert_id": "thematic-analysis", "actor": "local", "model_id": "local-default"},
    {"title": "KJ法の分類ルールを検証", "expert_id": "kj-method", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "SCAT分析ステップを確認", "expert_id": "scat", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "M-GTA概念生成条件を評価", "expert_id": "m-gta", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "質的内容分析の根拠を確認", "expert_id": "qualitative-content-analysis", "actor": "local", "model_id": "local-default"},
    {"title": "計量テキスト分析の指標を検証", "expert_id": "quantitative-text-analysis", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "相関分析の適用条件を確認", "expert_id": "correlation", "actor": "local", "model_id": "local-default"},
    {"title": "群間比較統計の前提を評価", "expert_id": "group-comparison-statistics", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "セッション間比較知識を更新", "expert_id": "cross-session-comparison", "actor": "codex", "model_id": "codex"},
    {"title": "音声感情認識ラベルを確認", "expert_id": "speech-emotion-recognition", "actor": "a100", "model_id": "qwen3-80b"},
    {"title": "Knowledge Pack候補を総合評価", "expert_id": "framework-method", "actor": "codex", "model_id": "codex"},
)

# Safety, routing, ordering, and numeric validation stay deterministic.  Only
# work that benefits from semantic interpretation is delegated to a local LLM.
LOCAL_LLM_DECISION_TASKS = frozenset({3, 4, 6, 8, 10, 11, 12, 13, 14, 19, 20})
VALID_DECISION_MODES = frozenset({"program", "local_llm"})
# A repeating task reruns on A100 until its score reaches target_score.
DEFAULT_MAX_ITERATIONS = 5
MAX_ITERATIONS_LIMIT = 10

TASK_PROGRESS_STEPS: tuple[tuple[int, str], ...] = (
    (15, "入力層を準備"),
    (30, "Obsidian 第1層を参照"),
    (45, "Obsidian 第2層を分析"),
    (60, "Obsidian 第3層を評価"),
    (75, "中間状態を一時保存"),
    (90, "ラベルを生成"),
    (100, "出力データを保存"),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class KnowledgeConsoleStore:
    """Small local ledger for console drafts and truthful trace events."""

    def __init__(self, data_dir: str | Path):
        if data_dir is None or not str(data_dir).strip():
            raise ValueError("data_dir must be explicitly configured")
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.root = self.data_dir / "knowledge_builder"
        self.db_path = self.root / "state.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_relative_to(self.data_dir):
            raise ValueError("knowledge console path escapes the configured data directory")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path.is_symlink() or getattr(self.db_path, "is_junction", lambda: False)():
            raise ValueError("knowledge console database may not be a link")
        connection = sqlite3.connect(self.db_path, timeout=20, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=20000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_console_tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    expert_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,
                    simulation INTEGER NOT NULL DEFAULT 1,
                    progress INTEGER NOT NULL DEFAULT 0,
                    phase TEXT NOT NULL DEFAULT '未実行',
                    position INTEGER NOT NULL DEFAULT 1000,
                    decision_mode TEXT NOT NULL DEFAULT 'program',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_console_traces (
                    trace_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    expert_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_console_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    occurred_at TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_console_events_entity
                    ON knowledge_console_events(entity_type, entity_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_knowledge_console_error_events
                    ON knowledge_console_events(sequence)
                    WHERE event_type IN ('task.failed','runtime.failed','api.failed');
                """
            )
            task_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(knowledge_console_tasks)")
            }
            if "progress" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN progress INTEGER NOT NULL DEFAULT 0"
                )
            if "phase" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN phase TEXT NOT NULL DEFAULT '未実行'"
                )
            if "position" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN position INTEGER NOT NULL DEFAULT 1000"
                )
            if "decision_mode" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN decision_mode TEXT NOT NULL DEFAULT 'program'"
                )
            if "result_json" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN result_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "error_message" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN error_message TEXT NOT NULL DEFAULT ''"
                )
            if "target_score" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN target_score INTEGER"
                )
            if "max_iterations" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN max_iterations INTEGER NOT NULL DEFAULT 1"
                )
            if "iteration" not in task_columns:
                connection.execute(
                    "ALTER TABLE knowledge_console_tasks ADD COLUMN iteration INTEGER NOT NULL DEFAULT 0"
                )
            if "score" not in task_columns:
                connection.execute("ALTER TABLE knowledge_console_tasks ADD COLUMN score INTEGER")
            connection.execute(
                "UPDATE knowledge_console_tasks SET progress=100, phase='完了' WHERE status='succeeded'"
            )

    @staticmethod
    def _clean_text(value: Any, *, field: str, maximum: int) -> str:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            raise ValueError(f"{field} is required")
        if len(text) > maximum:
            raise ValueError(f"{field} is too long")
        return text

    @staticmethod
    def _known(value: Any, choices: tuple[dict[str, str], ...], *, field: str) -> str:
        normalized = str(value or "").strip()
        if normalized not in {item["id"] for item in choices}:
            raise ValueError(f"unknown {field}")
        return normalized

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": uuid.uuid4().hex,
            "occurred_at": utc_now_iso(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_type": event_type,
            "payload": payload or {},
        }
        cursor = connection.execute(
            """INSERT INTO knowledge_console_events
               (event_id,occurred_at,entity_type,entity_id,event_type,payload_json)
               VALUES(?,?,?,?,?,?)""",
            (
                event["event_id"],
                event["occurred_at"],
                entity_type,
                entity_id,
                event_type,
                json.dumps(event["payload"], ensure_ascii=False, separators=(",", ":")),
            ),
        )
        event["sequence"] = cursor.lastrowid
        return event

    @staticmethod
    def _task(row: sqlite3.Row) -> dict[str, Any]:
        try:
            result = json.loads(row["result_json"] or "{}")
        except (TypeError, ValueError):
            result = {}
        quality = result.get("quality", {}) if isinstance(result, dict) else {}
        if not isinstance(quality, dict):
            quality = {}
        quality_state = quality.get("state", "unverified")
        phase = row["phase"]
        if not row["simulation"]:
            if row["status"] == "succeeded":
                phase = "応答受信・引用照合済み" if quality_state == "evidence_checked" else "応答受信・未評価"
            elif row["status"] == "failed" and quality_state in {"needs_input", "invalid"}:
                phase = "入力不足・採点停止" if quality_state == "needs_input" else "根拠要確認・採点停止"
        return {
            "task_id": row["task_id"],
            "title": row["title"],
            "expert_id": row["expert_id"],
            "actor": row["actor"],
            "model_id": row["model_id"],
            "status": row["status"],
            "run_count": row["run_count"],
            "revision": row["revision"],
            "simulation": bool(row["simulation"]),
            "progress": max(0, min(100, int(row["progress"]))),
            "phase": phase,
            "quality_state": quality_state,
            "position": int(row["position"]),
            "decision_mode": row["decision_mode"],
            "result": result if isinstance(result, dict) else {},
            "error_message": row["error_message"],
            "target_score": row["target_score"],
            "max_iterations": int(row["max_iterations"]),
            "iteration": int(row["iteration"]),
            "score": row["score"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_console_tasks ORDER BY position, created_at, task_id"
            ).fetchall()
            tasks = [self._task(row) for row in rows]
            self._attach_score_history(connection, tasks)
        return tasks

    @classmethod
    def _attach_score_history(
        cls, connection: sqlite3.Connection, tasks: list[dict[str, Any]]
    ) -> None:
        """Add the scored attempts of each task's latest run as ``score_history``."""
        histories: dict[str, list[dict[str, Any]]] = {task["task_id"]: [] for task in tasks}
        if not histories:
            return
        query = """SELECT * FROM knowledge_console_events
                   WHERE entity_type='task' AND event_type IN ('task.running','task.scored')"""
        parameters: tuple[str, ...] = ()
        if len(histories) <= 500:
            query += f" AND entity_id IN ({','.join('?' * len(histories))})"
            parameters = tuple(histories)
        rows = connection.execute(query + " ORDER BY sequence", parameters).fetchall()
        for row in rows:
            history = histories.get(row["entity_id"])
            if history is None:
                continue
            if row["event_type"] == "task.running":
                # A new run restarts the attempts; only the latest run is shown.
                history.clear()
                continue
            payload = cls._event(row)["payload"]
            history.append(
                {
                    "iteration": payload.get("iteration"),
                    "score": payload.get("score"),
                    "scorer": payload.get("scorer"),
                    "feedback": payload.get("feedback", ""),
                }
            )
        for task in tasks:
            task["score_history"] = histories[task["task_id"]]

    def seed_default_tasks(self) -> int:
        """Create the development backlog once, without replacing user tasks."""
        now = utc_now_iso()
        created = 0
        with self._transaction() as connection:
            for index, seed in enumerate(DEFAULT_TASKS, start=1):
                task_id = f"seed-task-{index:02d}"
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO knowledge_console_tasks
                       (task_id,title,expert_id,actor,model_id,status,run_count,revision,
                       simulation,progress,phase,position,decision_mode,created_at,updated_at)
                       VALUES(?,?,?,?,?,'draft',0,1,1,0,'未実行',?,?,?,?)""",
                    (
                        task_id,
                        seed["title"],
                        seed["expert_id"],
                        seed["actor"],
                        seed["model_id"],
                        index,
                        "local_llm" if index in LOCAL_LLM_DECISION_TASKS else "program",
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "UPDATE knowledge_console_tasks SET position=?, decision_mode=? WHERE task_id=?",
                    (
                        index,
                        "local_llm" if index in LOCAL_LLM_DECISION_TASKS else "program",
                        task_id,
                    ),
                )
                if cursor.rowcount:
                    created += 1
                    self._append_event(
                        connection,
                        entity_type="task",
                        entity_id=task_id,
                        event_type="task.seeded",
                        payload={"position": index, "simulation": True},
                    )
        return created

    def create_task(self, payload: dict[str, Any], *, _connection=None) -> dict[str, Any]:
        title = self._clean_text(payload.get("title"), field="title", maximum=160)
        expert_id = self._known(payload.get("expert_id"), EXPERTS, field="expert_id")
        model_id = self._known(payload.get("model_id"), MODELS, field="model_id")
        actor = str(payload.get("actor") or "a100").strip().casefold()
        if actor not in {"a100", "local", "codex"}:
            raise ValueError("unknown actor")
        decision_mode = str(
            payload.get("decision_mode") or ("local_llm" if actor == "a100" else "program")
        ).strip().casefold()
        if decision_mode not in VALID_DECISION_MODES:
            raise ValueError("unknown decision_mode")
        target_score, max_iterations = self._iteration_settings(payload, actor=actor)
        task_id = uuid.uuid4().hex
        now = utc_now_iso()
        with (nullcontext(_connection) if _connection is not None else self._transaction()) as connection:
            position = max(
                20,
                int(
                    connection.execute(
                        "SELECT COALESCE(MAX(position), 20) FROM knowledge_console_tasks"
                    ).fetchone()[0]
                ),
            ) + 1
            connection.execute(
                """INSERT INTO knowledge_console_tasks
                   (task_id,title,expert_id,actor,model_id,status,run_count,revision,
                    simulation,progress,phase,position,decision_mode,target_score,
                    max_iterations,created_at,updated_at)
                   VALUES(?,?,?,?,?,'draft',0,1,1,0,'未実行',?,?,?,?,?,?)""",
                (
                    task_id, title, expert_id, actor, model_id, position, decision_mode,
                    target_score, max_iterations, now, now,
                ),
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="task.created",
                payload={
                    "expert_id": expert_id,
                    "actor": actor,
                    "model_id": model_id,
                    "decision_mode": decision_mode,
                    "target_score": target_score,
                    "max_iterations": max_iterations,
                },
            )
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(row)

    @staticmethod
    def _iteration_settings(payload: dict[str, Any], *, actor: str) -> tuple[int | None, int]:
        """Validate the optional repeat-until-score settings of a new task."""
        raw_target = payload.get("target_score")
        if raw_target in (None, ""):
            return None, 1
        if actor != "a100":
            raise ValueError("目標スコアまで繰り返せるのはA100担当タスクだけです。")
        try:
            target_score = int(raw_target)
            max_iterations = int(payload.get("max_iterations") or DEFAULT_MAX_ITERATIONS)
        except (TypeError, ValueError):
            raise ValueError("目標スコアと最大回数は整数で指定してください。") from None
        if not 1 <= target_score <= 100:
            raise ValueError("目標スコアは1〜100で指定してください。")
        if not 1 <= max_iterations <= MAX_ITERATIONS_LIMIT:
            raise ValueError(f"最大回数は1〜{MAX_ITERATIONS_LIMIT}で指定してください。")
        return target_score, max_iterations

    def execute_task(self, task_id: str, *, expected_revision: int, simulation: bool) -> dict[str, Any]:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("task not found")
            if int(row["revision"]) != expected_revision:
                raise RuntimeError("task revision conflict")
            now = utc_now_iso()
            revision = int(row["revision"]) + 1
            run_count = int(row["run_count"]) + 1
            if row["status"] == "running":
                raise RuntimeError("task is already running")
            if not simulation and row["actor"] != "a100":
                raise ValueError("実モデルへ送信できるのはA100担当タスクだけです。")
            phase = "実行キューを準備" if simulation else "Colab A100への送信待ち"
            connection.execute(
                """UPDATE knowledge_console_tasks
                   SET status='running', run_count=?, revision=?, simulation=?,
                       progress=5, phase=?, result_json='{}', error_message='',
                       iteration=0, score=NULL, updated_at=?
                   WHERE task_id=?""",
                (run_count, revision, int(simulation), phase, now, task_id),
            )
            for event_type, payload in (
                ("task.queued", {"simulation": simulation}),
                (
                    "task.running",
                    {
                        "actor": row["actor"],
                        "model_id": row["model_id"],
                        "simulation": simulation,
                    },
                ),
            ):
                self._append_event(
                    connection,
                    entity_type="task",
                    entity_id=task_id,
                    event_type=event_type,
                    payload=payload,
                )
            updated = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(updated)

    def advance_task(self, task_id: str, *, expected_revision: int) -> dict[str, Any]:
        """Advance one persisted simulation step for Web UI progress playback."""
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("task not found")
            if not bool(row["simulation"]):
                # Real tasks are advanced by the worker; the poll only reads them.
                task = self._task(row)
                self._attach_score_history(connection, [task])
                return task
            if int(row["revision"]) != expected_revision:
                raise RuntimeError("task revision conflict")
            if row["status"] != "running":
                raise ValueError("task is not running")

            current_progress = int(row["progress"])
            progress, phase = next(
                (step for step in TASK_PROGRESS_STEPS if step[0] > current_progress),
                TASK_PROGRESS_STEPS[-1],
            )
            now = utc_now_iso()
            revision = int(row["revision"]) + 1
            status = "succeeded" if progress >= 100 else "running"
            connection.execute(
                """UPDATE knowledge_console_tasks
                   SET status=?, progress=?, phase=?, revision=?, updated_at=?
                   WHERE task_id=?""",
                (status, progress, phase, revision, now, task_id),
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="task.progressed",
                payload={"progress": progress, "phase": phase, "simulation": True},
            )
            if status == "succeeded":
                self._append_event(
                    connection,
                    entity_type="task",
                    entity_id=task_id,
                    event_type="knowledge.accessed",
                    payload={
                        "block_ids": [
                            "obsidian-layer-1",
                            "obsidian-layer-2",
                            "obsidian-layer-3",
                        ]
                    },
                )
                self._append_event(
                    connection,
                    entity_type="task",
                    entity_id=task_id,
                    event_type="task.succeeded",
                    payload={"simulation": True, "run_count": int(row["run_count"])},
                )
            updated = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(updated)

    def update_real_task(self, task_id: str, *, progress: int, phase: str) -> dict[str, Any]:
        """Persist an observable stage reported by the real A100 adapter."""
        bounded_progress = max(5, min(95, int(progress)))
        clean_phase = self._clean_text(phase, field="phase", maximum=120)
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("task not found")
            if row["status"] != "running" or bool(row["simulation"]):
                raise RuntimeError("task is not a running real-model task")
            now = utc_now_iso()
            connection.execute(
                """UPDATE knowledge_console_tasks
                   SET progress=?, phase=?, revision=revision+1, updated_at=? WHERE task_id=?""",
                (bounded_progress, clean_phase, now, task_id),
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="task.progressed",
                payload={"progress": bounded_progress, "phase": clean_phase, "simulation": False},
            )
            updated = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(updated)

    def record_task_score(
        self, task_id: str, *, iteration: int, score: int, feedback: str, scorer: str
    ) -> dict[str, Any]:
        """Persist the score of one A100 attempt of a repeating task."""
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("task not found")
            if row["status"] != "running" or bool(row["simulation"]):
                raise RuntimeError("task is not a running real-model task")
            now = utc_now_iso()
            connection.execute(
                """UPDATE knowledge_console_tasks
                   SET iteration=?, score=?, revision=revision+1, updated_at=? WHERE task_id=?""",
                (iteration, score, now, task_id),
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="task.scored",
                payload={
                    "iteration": iteration,
                    "score": score,
                    "target_score": row["target_score"],
                    "scorer": scorer,
                    "feedback": feedback[:240],
                },
            )
            updated = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(updated)

    def complete_real_task(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Commit a bounded real-model response after the remote call succeeds."""
        result_json = _task_result_json(result)
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("task not found")
            if row["status"] != "running" or bool(row["simulation"]):
                raise RuntimeError("task is not a running real-model task")
            now = utc_now_iso()
            connection.execute(
                """UPDATE knowledge_console_tasks
                   SET status='succeeded', progress=100, phase='A100実推論完了',
                       result_json=?, error_message='', revision=revision+1, updated_at=?
                   WHERE task_id=?""",
                (result_json, now, task_id),
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="task.succeeded",
                payload={"simulation": False, "run_count": int(row["run_count"])},
            )
            updated = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(updated)

    def fail_real_task(
        self, task_id: str, error_message: str, *, result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Record a truthful terminal failure without storing credentials or prompts.

        A stopped repeat keeps its best attempt and latest response separately.
        No supplied result means retain whatever was already saved.
        """
        full_message = _error_text(error_message or "A100実行に失敗しました")
        message = " ".join(full_message.split())[:500]
        result_json = _task_result_json(result) if result is not None else None
        quality = (result or {}).get("quality")
        quality_state = quality.get("state", "unverified") if isinstance(quality, dict) else "unverified"
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("task not found")
            now = utc_now_iso()
            connection.execute(
                """UPDATE knowledge_console_tasks
                   SET status='failed', phase='A100実推論失敗', error_message=?,
                       result_json=COALESCE(?, result_json), revision=revision+1, updated_at=? WHERE task_id=?""",
                (message, result_json, now, task_id),
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="task.failed",
                payload={"simulation": False, "message": full_message,
                         "title": row["title"], "run_count": int(row["run_count"]),
                         "iteration": (result or {}).get("stopped_iteration", int(row["iteration"])),
                         "phase": row["phase"],
                         "quality_state": quality_state},
            )
            updated = connection.execute(
                "SELECT * FROM knowledge_console_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(updated)

    def create_trace(self, payload: dict[str, Any]) -> dict[str, Any]:
        question = self._clean_text(payload.get("question"), field="question", maximum=1000)
        expert_id = self._known(payload.get("expert_id"), EXPERTS, field="expert_id")
        model_id = self._known(payload.get("model_id"), MODELS, field="model_id")
        trace_id = uuid.uuid4().hex
        now = utc_now_iso()
        selected_ids = [block["id"] for block in KNOWLEDGE_BLOCKS]
        contribution = [22, 21, 18, 24, 15]
        result = {
            "summary": "入力から3層のObsidian知識を参照し、一時的な中間状態からラベルと出力データを生成しました。",
            "block_ids": selected_ids,
            "contribution": [
                {"label": label, "value": value}
                for label, value in zip(
                    ("Obsidian 第1層", "Obsidian 第2層", "Obsidian 第3層", "ラベル生成", "出力データ"),
                    contribution,
                    strict=True,
                )
            ],
            "simulation": True,
        }
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_console_traces
                   (trace_id,question,expert_id,model_id,status,result_json,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    trace_id, question, expert_id, model_id, "completed",
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")), now,
                ),
            )
            for index, block_id in enumerate(selected_ids, start=1):
                self._append_event(
                    connection,
                    entity_type="trace",
                    entity_id=trace_id,
                    event_type="knowledge.block_accessed",
                    payload={"block_id": block_id, "step": index, "simulation": True},
                )
        return self.get_trace(trace_id)

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_console_traces WHERE trace_id=?", (trace_id,)
            ).fetchone()
            if row is None:
                raise LookupError("trace not found")
            event_rows = connection.execute(
                """SELECT * FROM knowledge_console_events
                   WHERE entity_type='trace' AND entity_id=? ORDER BY sequence""",
                (trace_id,),
            ).fetchall()
        return {
            "trace_id": row["trace_id"],
            "question": row["question"],
            "expert_id": row["expert_id"],
            "model_id": row["model_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "result": json.loads(row["result_json"]),
            "events": [self._event(event) for event in event_rows],
        }

    @staticmethod
    def _event(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": row["sequence"],
            "event_id": row["event_id"],
            "occurred_at": row["occurred_at"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]),
        }

    def record_runtime_status(self, status: dict[str, Any]) -> None:
        """Persist transitions, not every identical heartbeat poll. Never prune."""
        payload = {"state": status.get("state"), "message": _error_text(status.get("message"))}
        with self._transaction() as connection:
            previous = connection.execute("""SELECT payload_json FROM knowledge_console_events
                WHERE entity_type='runtime' AND entity_id='a100' ORDER BY sequence DESC LIMIT 1""").fetchone()
            if previous and json.loads(previous["payload_json"]) == payload:
                return
            event_type = "runtime.failed" if payload["state"] in {"worker_failed", "unreachable", "stale"} else "runtime.status"
            self._append_event(connection, entity_type="runtime", entity_id="a100", event_type=event_type, payload=payload)

    def record_api_error(self, *, path: str, method: str, status: int, message: str) -> None:
        with self._transaction() as connection:
            self._append_event(connection, entity_type="api", entity_id=path, event_type="api.failed",
                               payload={"method": method, "status": status, "message": _error_text(message)})

    def list_events(self, *, limit: int = 100, before: int | None = None,
                    errors_only: bool = False) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        clauses, params = [], []
        if before is not None:
            if int(before) < 1:
                raise ValueError("before must be positive")
            clauses.append("sequence < ?")
            params.append(int(before))
        if errors_only:
            clauses.append("event_type IN ('task.failed','runtime.failed','api.failed')")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_console_events" + where + " ORDER BY sequence DESC LIMIT ?", (*params, limit)
            ).fetchall()
        return [self._event(row) for row in reversed(rows)]

    def summary(self) -> dict[str, Any]:
        tasks = self.list_tasks()
        with closing(self._connect()) as connection:
            existing_job_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_jobs'"
            ).fetchone()
            job_counts: dict[str, int] = {}
            if existing_job_table:
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM knowledge_jobs GROUP BY status"
                ):
                    job_counts[str(row["status"])] = int(row["count"])
            pack_count = 0
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_packs'"
            ).fetchone():
                pack_count = int(connection.execute("SELECT COUNT(*) FROM knowledge_packs").fetchone()[0])
        return {
            "runtime": {
                "kind": "colab-a100",
                "state": "not_connected",
                "gpu": "A100 (接続待ち)",
                "heartbeat": None,
                "session_seconds": 0,
                "automation": "drive-transport-only",
            },
            "budget": {
                "policy": "conservative",
                "usage": None,
                "remaining": None,
                "state": "unknown",
                "message": "Colabの使用量は取得できないため、安全側で実行を停止します。",
            },
            "counts": {
                "experts": len(EXPERTS),
                "tasks": len(tasks),
                "completed_tasks": sum(task["status"] == "succeeded" for task in tasks),
                "running_tasks": sum(task["status"] == "running" for task in tasks),
                "average_progress": round(
                    sum(task["progress"] for task in tasks) / len(tasks)
                ) if tasks else 0,
                "packs": pack_count,
                "jobs_by_status": job_counts,
            },
            "models": list(MODELS),
            "sample_data": True,
        }


def expert_projection() -> list[dict[str, Any]]:
    """Return deterministic sample metrics without claiming measured model quality."""
    rows = []
    for index, expert in enumerate(EXPERTS):
        rows.append(
            {
                **expert,
                "approved_claims": 18 + (index * 7) % 41,
                "candidate_claims": 3 + (index * 5) % 12,
                "coverage": 62 + (index * 3) % 33,
                "score": 68 + (index * 4) % 29,
                "has_inference": index % 4 != 0,
                "latest_run_state": ("succeeded", "accepted", "draft", "not_started")[index % 4],
                "run_count": index % 6,
                "sample": True,
            }
        )
    return rows


def graph_projection() -> dict[str, Any]:
    nodes = [
        {"id": "source:test-data", "label": "テストデータ", "kind": "source"},
        {"id": "expert:thematic-analysis", "label": "テーマ分析", "kind": "expert"},
        {"id": "model:qwen3-80b", "label": "Qwen3 80B", "kind": "model"},
        {"id": "evaluation:coverage", "label": "Coverage評価", "kind": "evaluation"},
        {"id": "pack:sample", "label": "Sample Pack", "kind": "pack"},
    ]
    edges = [
        {"source": "source:test-data", "target": "expert:thematic-analysis", "type": "feeds"},
        {"source": "expert:thematic-analysis", "target": "model:qwen3-80b", "type": "guides"},
        {"source": "model:qwen3-80b", "target": "evaluation:coverage", "type": "evaluated_by"},
        {"source": "evaluation:coverage", "target": "pack:sample", "type": "qualifies"},
    ]
    return {"nodes": nodes, "edges": edges, "sample_data": True}
