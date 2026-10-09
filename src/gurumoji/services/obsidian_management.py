"""Deterministic Obsidian management agent for committed Core/Handler records.

It receives a bounded projection, never an executor, credentials, or raw input.
SQLite/AnalysisStore remain authoritative; VaultRegistry owns every note write.
"""
from __future__ import annotations

from urllib.parse import quote, urlsplit

from ..analysis_core import fingerprint
from ..analysis_store import StoreConflict, safe_path
from ..vault_registry import VAULT_LOCK, entity_key, sha256


MANAGEMENT_VERSION = "obsidian-management-1"
REFERENCE_LIMIT = 40


def management_packet(run: dict, decisions: list[dict]) -> dict:
    """Allowlist committed identifiers and short summaries, not arbitrary payloads."""
    item_id, run_id = run["item_id"], run["run_id"]
    base = f"/api/library/{quote(item_id, safe='')}/analysis/orchestration/{quote(run_id, safe='')}"
    parsed = urlsplit(run.get("app_url") or "http://127.0.0.1:7860")
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or any(ord(char) < 33 or char in "<>\\\"`" for char in parsed.netloc)):
        raise StoreConflict("管理ノートのアプリ参照先を確認できません。")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    events = run.get("events", [])
    packet = {"schema_version": 1, "management_version": MANAGEMENT_VERSION,
        **{key: run.get(key) for key in ("item_id", "run_id", "initial_id", "input_hash", "source_revision",
            "analysis_revision", "generation", "status", "phase", "view_version", "annotation_version", "codebook_version", "stale")},
        "event_seq": max((event["seq"] for event in events), default=0),
        "core_summary": str(run.get("current_view", {}).get("summary", ""))[:1200],
        "core_summary_truncated": len(str(run.get("current_view", {}).get("summary", ""))) > 1200,
        "links": {"state": origin + base, "ledger": origin + base + "/export.json",
                  "history": origin + base + "/viewer"},
        "references": {
            "initial": {"table": "orchestration_initials", "initial_id": run["initial_id"]},
            "events": {"table": "orchestration_events", "run_id": run_id, "through_seq": max((e["seq"] for e in events), default=0)},
            "labels": {"table": "orchestration_label_versions", "run_id": run_id, "annotation_version": run["annotation_version"]}},
        "tasks": [{key: task.get(key) for key in ("task_id", "role", "method_id", "status", "result_id", "dataset_version", "annotation_version")}
                  for task in run.get("tasks", [])[-REFERENCE_LIMIT:]],
        "results": [{key: result.get(key) for key in ("result_id", "task_id", "role", "raw_hash", "validation_status", "dataset_version", "annotation_version", "stale")}
                    for result in run.get("results", [])[-REFERENCE_LIMIT:]],
        "decisions": [{key: decision.get(key) for key in ("decision_id", "result_id", "task_id", "iteration", "annotation_version")}
                      for decision in decisions[-REFERENCE_LIMIT:]],
        "counts": {"tasks": len(run.get("tasks", [])), "results": len(run.get("results", [])), "decisions": len(decisions), "events": len(events)},
        "package": None}
    catalog = run.get("expert_agents", {})
    packet["expert_agents"] = [{key: entry.get(key) for key in (
        "expert_id", "definition_version", "contract_version", "profile_hash", "knowledge_hash")}
        for entry in catalog.get("experts", [])[:9]]
    packet["expert_calls"] = [{"task_id": task["task_id"], "status": task["status"],
        "calculation_result_ids": [ref["result_id"] for ref in task.get("expert_calculation_refs", [])][:8],
        **{key: task["expert_agent"].get(key) for key in ("expert_id", "profile_hash", "knowledge_hash", "contract_version")}}
        for task in run.get("tasks", [])[-REFERENCE_LIMIT:] if task.get("expert_agent")]
    return packet


class ObsidianManagementAgent:
    """Core decisions -> Handler -> managed note and stable-ID resolver."""

    def __init__(self, *, registry_factory, publication_status=None):
        self.registry_factory = registry_factory
        self.publication_status = publication_status

    @staticmethod
    def note_id(run_id):
        return "orchestration-memory-" + entity_key(run_id)

    def receive(self, packet: dict) -> dict:
        if packet.get("management_version") != MANAGEMENT_VERSION:
            raise StoreConflict("Obsidian管理の情報形式が異なります。")
        packet = dict(packet)
        packet.pop("source_hash", None)
        # Resolve saved artifacts through the existing store, never copy them.
        if self.publication_status is not None and packet["status"] == "completed":
            publication = self.publication_status(packet["item_id"], packet["run_id"])
            saved = publication.get("result_run")
            if saved is not None:
                packet["package"] = {"run_id": saved["id"], "package_hash": publication["package_hash"],
                    "sealed_hash": publication["sealed_hash"],
                    "artifacts": [{key: artifact.get(key) for key in ("id", "name", "sha256", "url")}
                                  for artifact in saved.get("artifacts", [])]}
        packet["source_hash"] = fingerprint(packet)
        registry = self.registry_factory()
        value = registry.publish_orchestration_memory(packet)
        return {**value, "source_hash": packet["source_hash"], "event_seq": packet["event_seq"],
                "generation": packet["generation"], "view_version": packet["view_version"],
                "management_version": MANAGEMENT_VERSION}

    def inspect(self, run: dict, receipt: dict) -> dict:
        """GET checks current bytes; it never creates files or repairs a note."""
        if not receipt.get("note_id"):
            return receipt
        registry = self.registry_factory()
        with VAULT_LOCK:
            data = registry.load()
            entry = data["notes"].get(self.note_id(run["run_id"]))
            entity = data["entities"].get(self.note_id(run["run_id"]))
            if (not entry or not entity or entity.get("item_id") != run["item_id"]
                    or entity.get("run_id") != run["run_id"] or entry.get("vault") != "orchestrator"):
                return {**receipt, "status": "conflict"}
            path = safe_path(registry.root("orchestrator", data), entry["path"])
            if not path.is_file():
                return {**receipt, "status": "missing"}
            if entry.get("pending") or sha256(path.read_bytes()) != entry.get("sha256"):
                return {**receipt, "status": "edited"}
            if (entry.get("source_hash") != receipt.get("source_hash")
                    or entity.get("source_hash") != receipt.get("source_hash")):
                return {**receipt, "status": "conflict"}
            if (receipt.get("event_seq", 0) < max((e["seq"] for e in run.get("events", [])), default=0)
                    or receipt.get("generation") != run.get("generation")
                    or receipt.get("view_version") != run.get("view_version")
                    or entity.get("status") != run.get("status")):
                return {**receipt, "status": "pending"}
            return {**receipt, "status": "linked", "stale": bool(run.get("stale") or receipt.get("stale"))}

    def read_note(self, run: dict, receipt: dict) -> bytes:
        with VAULT_LOCK:
            state = self.inspect(run, receipt)
            if state.get("status") not in {"linked", "pending"}:
                raise StoreConflict("管理ノートが未保存・編集済み・削除済みです。元の台帳を参照してください。")
            registry = self.registry_factory()
            data = registry.load()
            entry = data["notes"][self.note_id(run["run_id"])]
            content = safe_path(registry.root("orchestrator", data), entry["path"]).read_bytes()
            if sha256(content) != entry.get("sha256"):
                raise StoreConflict("取得中に管理ノートが変更されました。")
            return content
