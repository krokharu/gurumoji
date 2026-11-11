"""配送候補の完全復元と、前回再現した検索・予算障害を検証する。"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import maf_dev_bridge as bridge, obussql, context_delivery, model_context

_path = Path(__file__).resolve().parents[1] / 'scripts/obussql_delivery_candidates.py'
_spec = importlib.util.spec_from_file_location('delivery_candidates', _path)
candidates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(candidates)


@pytest.mark.parametrize('profile', candidates.PROFILES)
def test_all_candidates_preserve_types_exceptions_and_truncated_embedded_json(profile):
    original = {'instruction': {'question': '条件と例外を比較する'}, 'resources': [
        {'rows': [{'id': str(i), 'value': n, 'condition': '条件の長い説明をそのまま保持する。' * 3,
                   'exception': '否定を落とさない。', 'excerpt': '{"broken":['} for i, n in enumerate([True, 1, 1.0, -0.0, None])]},
        {'native_table': {'columns': ['id', 'text'], 'rows': [['A', '日本語\n引用"と\\']]}},
    ]}
    before = candidates.canonical(original)
    encoded = candidates.encode(original, profile)
    assert candidates.canonical(candidates.decode(json.loads(encoded['user']))) == before
    assert candidates.canonical(original) == before


@pytest.mark.parametrize('profile', candidates.PROFILES)
def test_all_candidates_reject_tampering(profile):
    encoded = candidates.encode({'instruction': {'question': '合成'}, 'resources': [{'text': '本文'}]}, profile)
    value = json.loads(encoded['user'])
    value['instruction']['question'] = '改変'
    with pytest.raises(ValueError, match='hash_mismatch'):
        candidates.decode(value)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('MOJIOKOSI_OBUSSQL_ENABLED', '1')


def test_natural_question_finds_evidence_after_1024_and_keeps_source_order(enabled):
    rows = [{'evidence_id': f'ev-{i:04}', 'text': f'通常の観察{i}。'} for i in range(1200)]
    rows[17]['text'] = '投与を中止した。'
    rows[-1]['text'] = '副作用により投与を中止した。'
    index = bridge.FixedEvidenceIndex('after-1024', rows)
    selected = index.select(rows, '副作用で中止した事例は何か？', 2, 2000)
    assert selected == [rows[17], rows[-1]]
    assert index.select(rows, '副作用で中止した事例は何か？', 1, 2000) == [rows[-1]]


def test_best_score_wins_before_restoring_source_order(enabled):
    rows = [{'evidence_id': f'ev-{i}', 'text': 'adverse ' if i == 1 else ('adverse ' * 8 if i == 9 else 'ordinary')} for i in range(10)]
    index = bridge.FixedEvidenceIndex('rank', rows)
    assert index.select(rows, 'adverse', 1, 2000) == [rows[9]]
    assert index.select(rows, 'adverse', 2, 2000) == [rows[1], rows[9]]


def test_search_handles_width_without_modifying_quotes(enabled):
    rows = [{'evidence_id': 'ev-width', 'text': 'ＡＢＣの資料を確認した。'}]
    assert bridge.FixedEvidenceIndex('width', rows).select(rows, 'ABC', 1, 1000) == rows


def test_changed_or_duplicate_rows_are_rejected(enabled):
    rows = [{'evidence_id': 'ev', 'text': '原文'}]
    index = bridge.FixedEvidenceIndex('invalid', rows)
    for invalid in ([{**rows[0], 'text': '改変'}], rows * 2):
        with pytest.raises(AnalysisContractError):
            index.select(invalid, '原文', 1, 100)


def test_preview_aggregates_large_exclusion_list_and_preserves_selected_quote():
    value = {'schema_version': 'bounded-context-v1', 'selection': [{'node': {'id': 'chosen', 'original': {'quote': {'text': '条件と例外を含む原文'}}}}],
             'excluded': [{'node_id': str(i), 'reason': 'no_literal_match'} for i in range(2000)],
             'selected_blocks': 1, 'examined_blocks': 2001, 'total_blocks': 2001, 'exhaustive': False}
    before = copy.deepcopy(value)
    bounded = obussql.bounded_preview_context(value)
    assert value == before
    assert bounded['selection'] == value['selection']
    assert bounded['exclusion_summary']['total'] == 2000
    assert bounded['exclusion_summary']['details_complete'] is False
    assert len(obussql._context_json(bounded).encode()) <= obussql.MAX_PAYLOAD_BYTES


def test_preview_never_cuts_a_quote_to_fit():
    text = '原文の条件と例外' * 3000
    value = {'selection': [{'node': {'id': 'huge', 'original': {'quote': {'text': text}}}}], 'excluded': []}
    bounded = obussql.bounded_preview_context(value)
    assert bounded['selection'] == []
    assert bounded['exclusion_summary']['reasons'] == {'host_payload_budget': 1}
    assert value['selection'][0]['node']['original']['quote']['text'] == text


def test_production_adaptive_matches_evaluated_candidate_and_preserves_embedded_text(enabled):
    context = {'task': {'role': 'interpretation'}, 'results': [{'id': str(i), 'condition': '条件と例外を省略しない。',
        'value': n, 'excerpt': '{"rows":['} for i, n in enumerate([True, 1, 1.0, None, -0.0])], 'raw_evidence': []}
    user, data = model_context.reference_messages(context, compact_references=True)
    original = {'instruction': json.loads(user), 'resources': [json.loads(s) for s in data]}
    evaluated = json.loads(candidates.encode(json.loads(candidates.canonical(original)), 'adaptive')['user'])
    actual = context_delivery.prepare(user, data)
    value = json.loads(actual['user'])
    assert value['resources'] == evaluated['resources']
    assert model_context.restored_reference_context(actual['user'], []) == context
    assert 'strings' not in value
    assert '$prefix' not in actual['user']


def test_production_adaptive_rejects_shared_key_override(enabled):
    value = {'format': context_delivery.FORMAT, 'source_sha256': 'a' * 64, 'instruction': {},
        'resources': {'$records': {'common': {'value': 1}, 'rows': [{'value': 2}]}}}
    with pytest.raises(ValueError, match='records_invalid'):
        context_delivery.restore(value)


def test_oversized_quote_does_not_hide_following_small_match():
    small = {'node': {'id': 'small', 'original': {'quote': {'text': '短い関連根拠'}}}}
    value = {'selection': [{'node': {'id': 'huge', 'original': {'quote': {'text': '巨大な原文' * 9000}}}}, small], 'excluded': []}
    bounded = obussql.bounded_preview_context(value)
    assert bounded['selection'] == [small]


def test_legacy_saved_packet_can_still_be_restored(enabled):
    context = {'question': '過去形式の確認', 'results': [{'id': str(i), 'text': '同じ原文' * 20} for i in range(8)]}
    user, data = model_context.reference_messages(context, compact_references=True)
    legacy = context_delivery.prepare_legacy(user, data)
    assert legacy['format'] == context_delivery.LEGACY_FORMAT
    assert model_context.restored_reference_context(legacy['user'], []) == context


@pytest.mark.parametrize('baseline,candidate_tokens,baseline_fits,chosen_format', [
    (1000, 950, True, 'native_json'),
    (2000, 1750, True, context_delivery.FORMAT),
    (2000, 1950, False, context_delivery.FORMAT),
])
def test_adopted_policy_requires_material_saving_or_context_recovery(enabled, baseline, candidate_tokens, baseline_fits, chosen_format):
    user, data = model_context.reference_messages({'question': '条件を保持する', 'results': [{'id': str(i), 'text': '同じ原文'} for i in range(10)]}, compact_references=True)
    budget = {'template_input_tokens': baseline, 'count_method': 'loaded_model_tokenizer', 'fits': baseline_fits,
              'model': 'synthetic', 'model_info_sha256': 'm', 'load_config_sha256': 'c', 'loaded_context_length': 8192,
              'output_reserve': 1600, 'safety_margin': 512}
    _, sent, messages, chosen = context_delivery.select('system', user, data, budget,
        lambda *_: {**budget, 'template_input_tokens': candidate_tokens})
    assert chosen['context_delivery']['format'] == chosen_format
    assert model_context.restored_reference_context(sent, messages)['question'] == '条件を保持する'
