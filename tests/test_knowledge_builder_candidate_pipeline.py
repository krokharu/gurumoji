import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import candidate_pipeline as pipeline, contracts


def _definition():
    return {
        "expert_id": pipeline.P3_EXPERT_ID,
        "definition_version": 1,
        "title": "Synthetic expert fixture",
        "scope": "Synthetic test scope",
        "out_of_scope": [],
        "required_inputs": [],
        "applicability_checks": [],
        "prohibited_conclusions": [],
    }


def _extraction(root: Path, *, routes=None, excerpt=None):
    excerpt = excerpt or (
        "This synthetic fixture verifies private extraction binding, local routing, "
        "and candidate provenance without containing any real method guidance."
    )
    excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    source = {
        "schema_version": 1,
        "source_id": pipeline.P3_SOURCE_ID,
        "version": "fixture-v1",
        "sha256": "a" * 64,
        "title": "Synthetic source fixture",
        "source_type": "paper",
        "locator": {"kind": "doi", "value": "10.1234/synthetic-fixture"},
        "access_scope": "full_text",
        "license": {"license_id": "synthetic-test", "terms": "Synthetic fixture; no external rights."},
        "anchors": [{
            "anchor_id": pipeline.GALE_ANCHOR_ID,
            "kind": "page",
            "start": str(pipeline.GALE_PDF_PAGE),
            "end": str(pipeline.GALE_PDF_PAGE),
            "extracted_text_sha256": excerpt_hash,
        }],
        "rights": {"classification": "licensed", "allowed_routes": routes or ["local"]},
    }
    rights_review = {"review_status": "synthetic_test_only"}
    note_hash = "b" * 64
    unsigned_manifest = {
        "kind": "private_source_extraction",
        "storage_class": "private_local_only",
        "source": source,
        "rights_review": rights_review,
        "authority_note_sha256": note_hash,
        "original_sha256": source["sha256"],
    }
    manifest = {
        **unsigned_manifest,
        "manifest_sha256": contracts.sha256_json(unsigned_manifest),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_bytes(contracts.canonical_json(manifest))
    row = {
        "text": excerpt,
        "extracted_text_sha256": excerpt_hash,
        "locations": [pipeline.GALE_ANCHOR_ID],
    }
    (root / "excerpts.jsonl").write_bytes(contracts.canonical_json(row) + b"\n")
    return source, rights_review, note_hash, manifest


def _model_response(candidate=None):
    candidate = candidate or {
        "claim": "This synthetic candidate remains a draft pending source review.",
        "applicability": ["synthetic test"],
        "exceptions": [],
        "claim_type": "limitation",
        "evidence_basis": "[source-explicit] The fixture exists only to test verified source binding.",
    }
    return {
        "choices": [{
            "message": {"content": json.dumps({"candidates": [candidate]})},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 40, "completion_tokens": 18, "total_tokens": 58},
    }


def _run_with_fixture(extraction_dir, output, model_response=None, *, routes=None, excerpt=None,
                      base_url="http://127.0.0.1:1234/v1"):
    source, rights_review, note_hash, manifest = _extraction(
        extraction_dir, routes=routes, excerpt=excerpt)
    definition = _definition()
    definition_hash = hashlib.sha256(pipeline._definition_bytes(definition)).hexdigest()
    with patch.object(pipeline.source_ingestion, "_trusted_source_authority",
                      return_value=(source, rights_review, note_hash)), \
            patch.object(pipeline, "_load_base_expert", return_value=(definition, definition_hash)), \
            patch.object(pipeline, "_request_json", side_effect=[
                {"data": [{"id": pipeline.LOCAL_MODEL_ID}]}, model_response or _model_response()
            ]) as request:
        summary = pipeline.generate_gale_candidates_local(
            extraction_dir, output, base_url=base_url, timeout=30)
    return summary, request, manifest


def test_generation_writes_only_hash_bound_pending_candidate_and_never_source_excerpt(tmp_path):
    extraction_dir = tmp_path / "private-extraction"
    output = tmp_path / "candidate-batch.json"
    source_text = "Synthetic excerpt text is used only for this local pipeline test fixture."

    summary, request, manifest = _run_with_fixture(
        extraction_dir, output, excerpt=source_text)

    batch = json.loads(output.read_text(encoding="utf-8"))
    assert summary["candidate_count"] == 1
    assert summary["review_status"] == "pending_human_review"
    assert batch["review_status"] == "pending_human_review"
    assert batch["promotion_gate"]["formal_claim_created"] is False
    assert batch["promotion_gate"]["approved_for_expert_pack"] is False
    assert batch["source_manifest_sha256"] == manifest["manifest_sha256"]
    assert batch["source_anchor"]["pdf_page"] == 4
    assert batch["source_anchor"]["printed_page"] == 3
    assert source_text not in output.read_text(encoding="utf-8")
    assert request.call_count == 2
    generation_request = request.call_args_list[1].args[1]
    assert generation_request["model"] == pipeline.LOCAL_MODEL_ID
    assert source_text in generation_request["messages"][1]["content"]


def test_generation_rejects_remote_endpoint_before_reading_extraction(tmp_path):
    with pytest.raises(pipeline.CandidatePipelineError, match="loopback LM Studio"):
        pipeline.generate_gale_candidates_local(
            tmp_path / "missing", tmp_path / "candidate.json", base_url="https://example.com/v1")


def test_generation_rejects_source_authorized_for_colab(tmp_path):
    with pytest.raises(pipeline.CandidatePipelineError, match="not authorized for local-only"):
        _run_with_fixture(tmp_path / "extract", tmp_path / "candidate.json",
                          routes=["local", "colab"])


def test_generation_rejects_candidate_repeating_long_source_span(tmp_path):
    repeated = "A" * 72
    candidate = {
        "claim": repeated,
        "applicability": [],
        "exceptions": [],
        "claim_type": "limitation",
        "evidence_basis": "[source-explicit] This is a synthetic source-binding test fixture.",
    }
    with pytest.raises(pipeline.CandidatePipelineError, match="source overlap"):
        _run_with_fixture(tmp_path / "extract", tmp_path / "candidate.json",
                          model_response=_model_response(candidate), excerpt=repeated)
    assert not (tmp_path / "candidate.json").exists()


def test_generation_rejects_inconsistent_model_usage_totals(tmp_path):
    response = _model_response()
    response["usage"]["total_tokens"] += 1
    with pytest.raises(pipeline.CandidatePipelineError, match="usage totals are inconsistent"):
        _run_with_fixture(tmp_path / "extract", tmp_path / "candidate.json", model_response=response)


def test_local_path_forms_and_closed_candidate_alias_are_checked():
    for value in (
        r"C:\\private\\paper.pdf",
        r"C:relative\\paper.pdf",
        r"relative\paper.pdf",
        r"\\server\share\paper.pdf",
        r"\rooted\paper.pdf",
        "/home/user/paper.pdf",
        "~/private/paper.pdf",
        "~alice/private/paper.pdf",
        "file:/private/paper.pdf",
        "file:///private/paper.pdf",
    ):
        assert pipeline._contains_local_path(value), value
    assert not pipeline._contains_local_path("https://example.org/article")

    alias = {
        "candidate_statement": "Pending fixture candidate.",
        "applicability": [],
        "exceptions": [],
        "candidate_type": "limitation",
        "rationale": "[source-explicit] This fixture checks one observed closed alias.",
    }
    normalized = pipeline._normalize_generated_candidate(alias)
    assert normalized["claim"] == alias["candidate_statement"]
    assert normalized["claim_type"] == "limitation"
    alias["unsupported_extra"] = True
    with pytest.raises(pipeline.CandidatePipelineError, match="closed schema"):
        pipeline._normalize_generated_candidate(alias)


def test_loopback_endpoint_normalizes_localhost_and_http_client_disables_proxies():
    assert pipeline._loopback_endpoint("http://localhost:1234/v1") == "http://127.0.0.1:1234/v1"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return b'{"ok":true}'

    class Opener:
        def open(self, request, timeout):
            self.request = request
            self.timeout = timeout
            return Response()

    opener = Opener()
    with patch.object(pipeline.urllib.request, "build_opener", return_value=opener) as build_opener:
        assert pipeline._request_json("http://127.0.0.1:1234/v1/models", timeout=5) == {"ok": True}

    handlers = build_opener.call_args.args
    proxy_handlers = [handler for handler in handlers if isinstance(handler, urllib.request.ProxyHandler)]
    assert len(proxy_handlers) == 1
    assert proxy_handlers[0].proxies == {}
    assert opener.request.full_url.startswith("http://127.0.0.1:")
