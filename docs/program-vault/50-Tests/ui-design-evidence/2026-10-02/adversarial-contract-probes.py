"""Independent isolated audit: pure modules, synthetic records and SQLite :memory:.
No Flask app import, runtime files, source writes, network, models, or external AI.
"""
import json
from pathlib import Path
import sqlite3
import sys
from html.parser import HTMLParser

APP = Path(__file__).resolve().parents[2] / 'app'
sys.path.insert(0, str(APP / 'src'))
from gurumoji.analysis_core import validate_definition
from gurumoji.analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store, measure_segments

class Ids(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = []
    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get('id')
        if value: self.ids.append(value)

ids = Ids()
for path in (APP / 'src/gurumoji/templates').rglob('*.html'):
    if path.name.endswith('.recovered'): continue
    ids.feed(path.read_text())
requested = ['source', 'rule', 'type', 'level', 'method']
missing = [f'analysis-definition-{name}' for name in requested if f'analysis-definition-{name}' not in ids.ids]
assert len(missing) == 5

base = {
    'definition_id': 'synthetic_duration', 'name': '発話秒数',
    'description': '各発話の持続時間を秒数で測る',
    'unit_of_analysis': 'segment', 'source_columns': ['text'],
    'output_column': 'synthetic_duration', 'data_type': 'number',
    'measurement_level': 'ratio', 'measurement_rule': 'text_length',
    'method': 'descriptive', 'status': 'draft',
}
# These defaults are independently confirmed against the JS form builder, not a
# claim that the Python contract infers source/rule from prose.
value = validate_definition(base)
rows = measure_segments({'segments': [
    {'id': 'synthetic-short', 'text': 'abc', 'duration': 60, 'start': 0, 'end': 60, 'valid_time': True},
    {'id': 'synthetic-long', 'text': 'abcdefghij', 'duration': 2, 'start': 60, 'end': 62, 'valid_time': True},
]}, [value])
assert [r['synthetic_duration'] for r in rows] == [3, 10]

# API-only counterexample: the backend genuinely supports a duration rule.
explicit = validate_definition({**base, 'source_columns': ['duration'], 'measurement_rule': 'duration'})
explicit_rows = measure_segments({'segments': [
    {'id': 'synthetic-short', 'text': 'abc', 'duration': 60, 'start': 0, 'end': 60, 'valid_time': True},
]}, [explicit])
assert explicit_rows[0]['synthetic_duration'] == 60

connection = sqlite3.connect(':memory:'); connection.row_factory = sqlite3.Row
initialize_pipeline_store(connection)
connection.commit()
service = AnalysisPipelineService(
    connect=lambda: connection, find_item=lambda _: {'id': 'synthetic-only'},
    source_fingerprint=lambda _: 'synthetic-only', snapshot_builder=lambda _: {},
    method_runner=lambda *_: {}, save_result=lambda **_: {}, publish_result=lambda _: {},
    publication_outcomes=lambda _: {}, public_run=lambda _: {}, runtime_key='synthetic-only',
)
adopted = service.save_definition('synthetic-only', base['definition_id'], {**base, 'status': 'adopted'})
saved = dict(connection.execute('SELECT status,last_trial_json FROM analysis_definitions').fetchone())
assert saved == {'status': 'adopted', 'last_trial_json': '{}'}
connection.close()

result = {
    'verification_level': 'isolated Python contract execution and HTML parsing; NOT live UI',
    'missing_template_ids': missing,
    'synthetic_prose_description': base['description'],
    'same_payload_measurement_rule': value['measurement_rule'],
    'actual_values_from_default_rule': [r['synthetic_duration'] for r in rows],
    'source_durations': [60, 2],
    'api_explicit_duration_rule_supported': explicit_rows[0]['synthetic_duration'],
    'adopt_without_trial_in_memory': saved,
    'external_ai_calls': 0,
    'real_app_or_runtime_data_access': False,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
