"""開発版のMAF実行と、固定根拠だけを読むObusSQL接続。"""
import asyncio
import copy
from dataclasses import dataclass
from importlib import metadata
import json
import re
import sys
import threading
import unicodedata

from ..analysis_core import AnalysisContractError
from ..env_settings import env_enabled
from . import obussql
from .evidence_retrieval import SqlEvidenceIndex

ENV_ENABLED = "MOJIOKOSI_MAF_DEV_ENABLED"
DRIVER_VERSION = "gurumoji-maf-dev-v1"
_indexes = {}
_lock = threading.RLock()


def enabled():
    return env_enabled(ENV_ENABLED)


def require_available():
    if not enabled() or not env_enabled(obussql.ENV_ENABLED) or sys.version_info[:2] != (3, 12):
        raise AnalysisContractError("MAF開発版接続には有効化とPython 3.12が必要です。", code="provider_unavailable")
    try:
        if metadata.version("agent-framework-core") != obussql.MAF_CORE_VERSION:
            raise ValueError("version")
        from agent_framework import Executor as Executor, WorkflowBuilder as WorkflowBuilder, WorkflowContext as WorkflowContext, handler as handler
        obussql._load_api()
    except Exception:
        raise AnalysisContractError("MAFまたはObusSQLの固定版を導入し、接続を有効にしてください。", code="provider_unavailable") from None


def status():
    result = {"driver": DRIVER_VERSION, "enabled": enabled(), "execution_ready": False}
    if not enabled():
        return {**result, "status": "disabled", "message": "開発版MAF分析は無効です。"}
    try:
        require_available()
    except AnalysisContractError as exc:
        return {**result, "status": "unavailable", "message": str(exc)}
    return {**result, "execution_ready": True, "status": "ready",
            "message": "開発版MAF分析を利用できます。固定根拠をSQLから取得します。"}


class FixedEvidenceIndex:
    def __init__(self, run_id, rows):
        self.api = obussql._load_api()
        self.run_id = run_id
        self.rows = {row["evidence_id"]: copy.deepcopy(row) for row in rows}
        if len(self.rows) != len(rows):
            raise ValueError("duplicate evidence")
        scope = self.api.Scope("gurumoji", self.run_id)
        self.context = self.api.ReadContext("gurumoji-local-user", DRIVER_VERSION, scope)
        self.raw_sources = {}
        self.backend = self.api.MemoryBackend(lambda resource: self.raw_sources[resource])
        self.resources, self.revisions = {}, {}
        self._selection_lock = threading.RLock()
        for eid, row in self.rows.items():
            resource = self.api.Resource(eid, self.api.Source("fixed-analysis", scope))
            self.raw_sources[resource] = ("```json\n" + json.dumps(
                {"evidence_id": eid, "text": row["text"]}, ensure_ascii=False) + "\n```\n").encode("utf-8")
            self.resources[eid] = resource
            self.revisions[eid] = self.backend.put(resource, self.raw_sources[resource])
            self.backend.grant(self.context, resource)

    def select(self, rows, query, row_limit, text_limit):
        with self._selection_lock:
            return self._select(rows, query, row_limit, text_limit)

    def _select(self, rows, query, row_limit, text_limit):
        api = self.api
        backend, context = self.backend, self.context
        resources, revisions = self.resources, self.revisions
        for row in rows:
            eid = row["evidence_id"]
            if eid not in self.rows or row["text"] != self.rows[eid]["text"]:
                raise AnalysisContractError("固定根拠の版が一致しません。", code="evidence_missing")
        if len({row["evidence_id"] for row in rows}) != len(rows):
            raise AnalysisContractError("固定根拠のIDが重複しています。", code="evidence_missing")
        budget = api.PayloadBudget(max_bytes=1024 * 1024)
        scores = {}
        # 256件ずつ全候補を調べ、各バッチのスコアを全体で比較する。
        queries = search_queries(query)
        for start in range(0, len(rows), 256):
            selection = tuple((resources[row["evidence_id"]], revisions[row["evidence_id"]])
                              for row in rows[start:start + 256])
            for term in queries:
                pack = api.retrieve_context(backend, context, selection, query=term, budget=budget,
                                            candidate_limit=1024, search_profile="ja_surface_v1")
                for entry in json.loads(pack.serialized_payload)["selection"]:
                    eid = entry["node"]["original"]["quote"]["resource_id"]
                    weight = 1024 if term == query[:4096] else 1
                    scores[eid] = scores.get(eid, 0) + weight * entry.get("literal_count", 1)
        ordinals = {row["evidence_id"]: i for i, row in enumerate(rows)}
        ordered = sorted(rows, key=lambda row: (-scores.get(row["evidence_id"], 0), ordinals[row["evidence_id"]]))
        chosen, size = {}, 0
        for row in ordered:
            if len(chosen) >= row_limit:
                break
            if size + len(row["text"]) > text_limit:
                continue
            eid = row["evidence_id"]
            fetched = backend.fetch(context, resources[eid], expected_revision=revisions[eid],
                                    block_index=0, budget=budget)
            quote = fetched.evidence[0].quote.text
            restored = json.loads(quote[quote.index("\n") + 1:quote.rindex("\n```")])
            if restored != {"evidence_id": eid, "text": row["text"]}:
                raise AnalysisContractError("ObusSQLの固定根拠を復元できません。", code="evidence_missing")
            chosen[eid] = {**copy.deepcopy(row), "text": restored["text"]}
            size += len(row["text"])
        return [chosen[row["evidence_id"]] for row in rows if row["evidence_id"] in chosen]


def search_queries(query):
    """全文一致を優先し、自然文の助詞・質問表現を分けた検索語も使う。"""
    original = query[:4096]
    normalized = unicodedata.normalize("NFC", original)
    parts = re.split(r"[\s、。！？!?「」『』（）()\[\],:;]+|について|による|によって|した|する|された|される|なら|では|から|まで|[はがをにでとへの]", normalized)
    stop = {"何", "何か", "どれ", "どこ", "なぜ", "事例", "場合", "確認", "教えて", "ください", "ある", "いる", "か"}
    terms = [s for s in parts if len(s) >= 2 and s not in stop]
    return list(dict.fromkeys([original, *terms]))[:8] if original else []


def select_evidence(run_id, rows, query, row_limit, text_limit):
    with _lock:
        index = _indexes.get(run_id)
    if index is None:
        raise AnalysisContractError("MAF実行の固定根拠索引がありません。", code="provider_unavailable")
    try:
        return index.select(rows, query, row_limit, text_limit)
    except Exception:
        raise AnalysisContractError("SQLの固定根拠を取得できません。", code="evidence_index_unavailable") from None


@dataclass(frozen=True)
class RunRef:
    run_id: str


def drive(run_id, initialize, read_evidence, analyze):
    require_available()
    from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

    class InitialExecutor(Executor):
        @handler
        async def invoke(self, message: RunRef, ctx: WorkflowContext[RunRef, str]):
            if await asyncio.to_thread(initialize):
                await ctx.send_message(message)
            else:
                await ctx.yield_output(message.run_id)

    class IndexExecutor(Executor):
        @handler
        async def invoke(self, message: RunRef, ctx: WorkflowContext[RunRef, str]):
            rows = await asyncio.to_thread(read_evidence)
            index = await asyncio.to_thread(SqlEvidenceIndex, message.run_id, rows)
            with _lock:
                _indexes[message.run_id] = index
            await ctx.send_message(message)

    class AnalysisExecutor(Executor):
        @handler
        async def invoke(self, message: RunRef, ctx: WorkflowContext[None, str]):
            await asyncio.to_thread(analyze)
            await ctx.yield_output(message.run_id)

    # 本文と応答は既存台帳が保持し、MAFのメッセージにはrun参照だけを流す。
    initial = InitialExecutor(id="gurumoji-initial")
    index = IndexExecutor(id="gurumoji-evidence-index")
    analysis = AnalysisExecutor(id="gurumoji-analysis")
    workflow = (WorkflowBuilder(start_executor=initial, name=DRIVER_VERSION, max_iterations=4,
                                checkpoint_storage=None, output_from=[initial, analysis])
                .add_edge(initial, index).add_edge(index, analysis).build())

    async def execute():
        result = await workflow.run(RunRef(run_id), tools=[])
        if result.get_outputs() != [run_id]:
            raise RuntimeError("MAF output unavailable")

    try:
        asyncio.run(execute())
    finally:
        with _lock:
            index = _indexes.pop(run_id, None)
        if index is not None:
            index.close()
