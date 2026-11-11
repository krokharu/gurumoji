"""移植した全文分割分析を、現行アプリの設定・保存境界へ接続する。"""
from __future__ import annotations

import threading
import sqlite3

from ..analysis_store import AnalysisStore
from ..core_pipeline_service import AnalysisOrchestrationService
from ..method_experts import ExpertCatalog
from ..web.core_pipeline_routes import register_core_pipeline_routes
from .core_pipeline_adapters import ADAPTER_VERSION, make_orchestration_adapters
from .core_pipeline_history import AnalysisHistoryService
from .core_pipeline_methods import run_orchestration_method
from .core_pipeline_publication import AnalysisOrchestrationPublicationService
from .expert_agents import ExpertAgentRegistry
from .obsidian_management import ObsidianManagementAgent


def register_developed_features(application, runtime):
    """実行サービスは明示操作で作成し、閲覧では読み取り専用の接続を使う。"""
    services = {}
    publications = {}
    lock = threading.RLock()

    def call_ai(*args, request_budget=None, task_id="", attempt_id="",
                raw_usage_callback=None, diagnostic_callback=None, **kwargs):
        # 通常の送信オプションと、厳密な予算の転送先を一つにそろえる。
        return runtime.call_orchestration_ai_json(
            *args, request_budget=request_budget, task_id=task_id,
            attempt_id=attempt_id, raw_usage_callback=raw_usage_callback,
            diagnostic_callback=diagnostic_callback, **kwargs)

    prepare, runner = make_orchestration_adapters(
        call_ai_json=call_ai,
        load_token_config=lambda: runtime.load_token_config(),
        configured_ai_credentials=lambda *args: runtime.configured_ai_credentials(*args),
    )

    def publication():
        key = str(runtime.DATABASE_FILE.resolve())
        with lock:
            if key not in publications:
                publications[key] = AnalysisOrchestrationPublicationService(
                    connect=lambda: runtime.database_connection(),
                    store_factory=lambda: runtime.analysis_archive_store(),
                    source_guard=runtime.orchestration_source_guard,
                    export_locked=lambda db, item_id, run_id: service().result_locked(db, item_id, run_id),
                    write_lock=runtime.library_write_lock,
                )
            return publications[key]

    def service():
        key = str(runtime.DATABASE_FILE.resolve())
        with lock:
            if key not in services:
                registry = ExpertAgentRegistry(ExpertCatalog(
                    local_root=runtime.DATA_DIRECTORY / "local_knowledge"))
                services[key] = AnalysisOrchestrationService(
                    connect=lambda: runtime.database_connection(),
                    find_item=lambda item_id: runtime.library_row(item_id),
                    source_fingerprint=lambda row: runtime.archive_source_stamp(row),
                    snapshot_builder=lambda row: runtime.build_analysis_orchestration_snapshot(row),
                    initial_builder=runtime.make_staged_initial_builder(
                        derived_database=lambda: runtime.DATABASE_FILE.parent / "analysis-derived.sqlite3",
                        archive_snapshot=lambda *args, **kwargs: runtime.archive_snapshot(*args, **kwargs),
                        archive_source_stamp=lambda *args, **kwargs: runtime.archive_source_stamp(*args, **kwargs),
                        group_analysis_for_row=lambda *args, **kwargs: runtime.group_analysis_for_row(*args, **kwargs),
                    ),
                    agent_runner=runner,
                    method_runner=run_orchestration_method,
                    write_lock=runtime.library_write_lock,
                    adapter_version=ADAPTER_VERSION,
                    on_complete=lambda item_id, run_id: publication().finalize(item_id, run_id),
                    memory_manager=ObsidianManagementAgent(
                        registry_factory=runtime.vault_registry,
                        publication_status=lambda item_id, run_id: publication().status(item_id, run_id)),
                    expert_provider=registry.freeze,
                    table_store=runtime.analysis_archive_store(),
                )
            return services[key]

    def read_item(item_id):
        # 未初期化DBや旧版の台帳でも、読取だけで存在を確認する。
        try:
            with runtime.analysis_history_connection() as connection:
                row = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
                return dict(row) if row else None
        except sqlite3.OperationalError as exc:
            if str(exc).startswith("no such table: library_items"):
                return None
            raise

    def history():
        return AnalysisHistoryService(
            connect=runtime.analysis_history_connection,
            find_item=read_item)

    def table_reader():
        if not runtime.DATABASE_FILE.is_file():
            raise LookupError("保存済みの分析台帳がありません。")

        def source_stamp(row):
            with runtime.analysis_history_connection() as connection:
                return runtime.archive_source_stamp(row, connection=connection)

        reader = AnalysisOrchestrationService(
            connect=runtime.analysis_history_connection,
            find_item=read_item,
            source_fingerprint=source_stamp,
            snapshot_builder=None, agent_runner=None, method_runner=None,
            schedule=False, adapter_version=ADAPTER_VERSION,
            table_store=AnalysisStore(runtime.DATABASE_FILE, runtime.analysis_history_connection))
        with lock:
            driver = services.get(str(runtime.DATABASE_FILE.resolve()))
            if driver is not None:
                reader._run_budgets, reader._budget_clock = driver._run_budgets, driver._budget_clock
        return reader

    register_core_pipeline_routes(application, service, prepare,
        publication=publication, history_viewer=history, table_reader=table_reader)
    application.extensions["core_pipeline"] = {
        "service": service, "publication": publication, "history": history,
        "table_reader": table_reader, "prepare": prepare, "services": services,
    }
