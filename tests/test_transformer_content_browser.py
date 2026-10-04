"""Browser rendering contracts use synthetic output and mock network only."""
import json
import re
import tempfile
import unittest
from pathlib import Path

import browser_support


@browser_support.ui_browser_test
class TransformerContentBrowserTests(unittest.TestCase):
    def test_unverified_stale_truncation_invalid_candidate_and_kwic_mode_are_visible(self):
        browser_support.require_browser_executable()
        script = (Path(__file__).parents[1] / "src/gurumoji/static/analysis-content.js").read_text()
        fixture = {
            "itemId": "synthetic", "dirty": False, "config": {},
            "data": {"config": {}, "segments": [], "research": {}, "transformer": {
                "stale": True, "result": {
                    "parameters": {"mode": "candidate", "topic_count": 2}, "engine": {"name": "synthetic"},
                    "coverage": {"segment_count": 6, "topic_count": 2, "speaker_result_count": 1,
                        "candidate_speaker_result_count": 1, "token_measurement_status": "measured",
                        "token_truncated_segment_count": 1, "truncated_segment_ids": ["s1"],
                        "target_truncated_segment_ids": ["s1"]},
                    "quality": {"cluster_candidates": [
                        {"topic_count": 2, "actual_topic_count": 2, "status": "valid", "silhouette_cosine": .8},
                        {"topic_count": 3, "actual_topic_count": 2, "status": "invalid_topic_count", "silhouette_cosine": None}]},
                    "speaker_results": [{"speaker": "A", "speaker_name": "A", "confidence": "unverified_candidate",
                        "result_label": "変化（表現候補）", "topic_label": "候補", "evidence_segment_ids": ["s1"]}],
                    "evidence": {"s1": {"speaker": "A", "text": "合成の本文", "start": 0, "end": 1}},
                }},
                "insights": {"fingerprint": "ui-fixture", "ai": {"model": "mock", "findings": [
                    {"title": "主張候補", "text": "検証用", "segment_ids": ["s1"]}],
                    "evidence": {"s1": {"speaker": "A", "text": "合成の本文"}}}},
            },
        }
        bootstrap = """
const analysisState = FIXTURE;
const analysisSaveInProgress = false;
const analysisDesktopContent = document.body, analysisMobileContent = document.body;
function analysisElement(tag, className = '', text = '') {
  const node = document.createElement(tag); node.className = className; node.textContent = text; return node;
}
function analysisCardPanel() { const panel = document.createElement('section'); return {panel, body: panel}; }
function analysisExportLink(label, dataset) { const a = document.createElement('a'); a.textContent = label; a.href = '?dataset=' + dataset; return a; }
function formatTime(value) { return String(value); }
function formatDate(value) { return String(value || ''); }
function analysisStorageState() { return {busy: false}; }
function selectAnalysisPage() {}
function saveAnalysisPackage() { throw new Error('Unexpected save'); }
let lastKwicUrl = '';
async function apiFetch(url) {
  lastKwicUrl = url;
  const params = new URL(url, 'https://example.invalid').searchParams;
  return {ok: true, json: async () => ({query: params.get('q'), mode: params.get('mode'), speaker: '', total: 0, hits: [], offset: 0, fingerprint: 'ui-fixture'})};
}
async function readJsonResponse(response) { return response.json(); }
""".replace("FIXTURE", json.dumps(fixture, ensure_ascii=False))
        assertions = """
(async () => {
  function assert(value, text) { if (!value) throw new Error(text); }
  try {
    contentAnalysisState().transformerMode = 'candidate'; contentAnalysisState().topicCount = 2;
    document.body.append(buildTransformerAnalysisPanel());
    document.body.append(buildContentExplorer());
    const ai = document.createElement('div'); ai.dataset.insightOutput = 'true'; document.body.append(ai);
    refreshInsightControls(); refreshTransformerControls();
    assert(document.body.textContent.includes('未確認の候補'), 'candidate warning');
    assert(document.body.textContent.includes('更新が必要'), 'stale warning');
    assert(document.body.textContent.includes('token上限で切詰め 1件'), 'token cutoff');
    assert(document.body.textContent.includes('本文が一部または全部落ちた発話ID: s1'), 'lost target');
    assert(document.querySelector('[data-transformer-candidate-pick="3"]').disabled, 'invalid candidate enabled');
    assert(document.body.textContent.includes('不成立（実際2件）'), 'actual count missing');
    assert(!document.querySelector('[data-transformer-candidate-pick="2"]').disabled, 'valid candidate disabled');
    assert(ai.textContent.includes('真偽') && ai.textContent.includes('研究者'), 'semantic truth warning');
    assert(document.body.textContent.includes('入力・切詰め範囲CSV'), 'coverage export absent');
    const mode = document.querySelector('[data-kwic-mode]');
    assert(mode.value === 'normalized' && mode.options.length === 3, 'KWIC modes');
    await runKwicSearch({query: 'cat', matchMode: 'literal'});
    assert(lastKwicUrl.includes('mode=literal'), 'mode not passed to API');
    assert(mode.value === 'literal', 'mode selector does not follow cross-tab');
    assert(document.body.textContent.includes('部分文字列'), 'literal label absent');
    document.body.dataset.contractTest = 'passed';
  } catch (error) { document.body.dataset.contractTest = 'failed: ' + error.message; }
})();
"""
        with tempfile.TemporaryDirectory(prefix="gurumoji-transformer-ui-") as temp:
            path = Path(temp) / "fixture.html"
            path.write_text("<!doctype html><meta charset='utf-8'><body><script>" + bootstrap + script + assertions + "</script>")
            result = browser_support.run_browser_dom(
                path.as_uri(), profile=Path(temp) / "profile",
                virtual_time_budget_ms=10000, timeout_seconds=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        status = re.search(r'data-contract-test="([^"]+)"', result.stdout)
        self.assertIsNotNone(status, result.stderr[-1000:])
        self.assertEqual(status.group(1), "passed")


if __name__ == "__main__":
    unittest.main()
