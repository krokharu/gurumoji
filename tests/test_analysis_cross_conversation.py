"""C2–C4 contracts on synthetic conversations, without model or DB calls."""
import copy
import json
from pathlib import Path
import unittest

from gurumoji import analysis_core as core
from gurumoji import transformer_analysis as transformer
from unittest.mock import patch


def fixture():
    return json.loads((Path(__file__).parent/'fixtures/analysis_three_conversations.json').read_text(encoding='utf-8'))


class CrossConversationContractsTests(unittest.TestCase):
    def test_standard_rejects_mixed_model_revision_dimensions_and_encoding(self):
        standard = core.EMBEDDING_STANDARD_V1
        self.assertEqual(core.validate_embedding_compatibility([dict(standard)]), standard)
        for key, value in [('model_name', 'other'), ('model_revision', 'other'),
                           ('model_revision', ''), ('dimensions', 383), ('encoding', 'float32')]:
            with self.subTest(key=key, value=value), self.assertRaises(core.AnalysisContractError) as caught:
                core.validate_embedding_compatibility([dict(standard), {**standard, key: value}])
            self.assertEqual(caught.exception.code, 'embedding_standard_mismatch')

    def test_default_loader_pins_revision_before_cache_or_download(self):
        standard = core.EMBEDDING_STANDARD_V1
        cached = (object(), object(), 'cpu')
        with patch.dict(transformer._MODEL_CACHE, {(standard['model_name'], standard['model_revision']): cached}, clear=True):
            self.assertIs(transformer._load_model(standard['model_name']), cached)
            self.assertIs(transformer._load_model(standard['model_name'], standard['model_revision']), cached)
            with self.assertRaisesRegex(ValueError, '再計算'):
                transformer._load_model(standard['model_name'], 'different-revision')

    def test_default_encode_records_fixed_revision_dimensions_and_prefix(self):
        import torch
        from types import SimpleNamespace
        from test_transformer_provenance import CharacterTokenizer
        standard = core.EMBEDDING_STANDARD_V1
        class Tokenizer(CharacterTokenizer):
            inputs = []
            def __call__(self, texts, **kwargs):
                self.inputs.extend(texts)
                return super().__call__(texts, **kwargs)
        class Model:
            config = SimpleNamespace(_commit_hash=standard['model_revision'])
            def __call__(self, **inputs):
                batch, width = inputs['input_ids'].shape
                return SimpleNamespace(last_hidden_state=torch.ones((batch, width, 384)))
        tokenizer = Tokenizer()
        with patch.object(transformer, '_load_model', return_value=(tokenizer, Model(), 'cpu')):
            vectors, engine = transformer.encode_texts(['架空の窓口'], kind='query')
        self.assertEqual(vectors.shape, (1, 384))
        self.assertEqual(engine['revision'], standard['model_revision'])
        self.assertTrue(all(value.startswith('query: ') for value in tokenizer.inputs))
        bad_model = Model()
        bad_model.config = SimpleNamespace(_commit_hash='different-revision')
        with patch.object(transformer, '_load_model', return_value=(tokenizer, bad_model, 'cpu')):
            with self.assertRaisesRegex(ValueError, '再計算'):
                transformer.encode_texts(['架空の窓口'])

    def test_definition_groups_use_verified_frozen_hash_not_local_id(self):
        data = fixture()
        snapshots = []
        for conversation in data['conversations']:
            for reference in conversation['definition_refs']:
                definition = data['definitions'][reference]
                snapshots.append({'item_id': conversation['analysis']['item']['id'], 'payload': definition,
                                  'definition_hash': core.definition_identity(definition)})
        original = copy.deepcopy(snapshots)
        groups = core.group_definitions_by_hash(snapshots)
        self.assertEqual(sorted(len(group['members']) for group in groups), [1, 2])
        self.assertEqual({group['definition']['definition_id'] for group in groups}, {'utterance_size'})
        self.assertEqual(snapshots, original)
        changed_metadata = {**snapshots[0]['payload'], 'revision': 88, 'updated_at': 'later', 'status': 'trial'}
        self.assertEqual(core.definition_identity(changed_metadata), snapshots[0]['definition_hash'])
        for changed in ([{**snapshots[0], 'definition_hash': '0'*64}], [snapshots[0], snapshots[0]]):
            with self.assertRaises(core.AnalysisContractError):
                core.group_definitions_by_hash(changed)

    def test_nonstandard_saved_revision_blocks_search_before_encoding(self):
        saved = {'engine': {'name': transformer.DEFAULT_MODEL, 'revision': 'other-revision'},
                 'vectors': {'dimensions': 2, 'encoding': 'base64-int8', 'scale': 127,
                             'segment_ids': ['u1'], 'data': 'fwA='}}
        with patch.object(transformer, 'encode_texts') as encode:
            with self.assertRaisesRegex(ValueError, '再計算'):
                transformer.semantic_search(saved, '窓口')
            encode.assert_not_called()

    def test_group_members_select_correct_measurement_and_missing_denominator(self):
        from gurumoji.analysis_pipeline import measure_segments
        data = fixture()
        snapshots, measures = [], {}
        for conversation in data['conversations']:
            analysis = conversation['analysis']
            definition = data['definitions'][conversation['definition_refs'][0]]
            snapshots.append({'item_id': analysis['item']['id'], 'payload': definition,
                              'definition_hash': core.definition_identity(definition)})
            measures[analysis['item']['id']] = measure_segments(analysis, [core.validate_definition(definition)])
        groups = core.group_definitions_by_hash(snapshots)
        summaries = []
        for group in groups:
            values = [row['utterance_size'] for member in group['members'] for row in measures[member['item_id']]]
            summaries.append((len(values), sum(value is None for value in values)))
        self.assertEqual(sorted(summaries), [(2, 1), (4, 0)])

    def test_node_ids_distinguish_local_ids_and_preserve_registered_people(self):
        data = fixture()
        first, second = data['conversations'][:2]
        self.assertNotEqual(core.graph_node_id('utt', item_id=first['analysis']['item']['id'], segment_id='u1'),
                            core.graph_node_id('utt', item_id=second['analysis']['item']['id'], segment_id='u1'))
        self.assertEqual(core.graph_node_id('spk', participant_code=first['speaker_person_ids']['A']),
                         core.graph_node_id('spk', participant_code=second['speaker_person_ids']['B']))
        self.assertNotEqual(core.graph_node_id('spk', item_id='one', speaker='A'),
                            core.graph_node_id('spk', item_id='two', speaker='A'))
        ids = [core.graph_node_id('utt', item_id='a:b', segment_id='u%3A'),
               core.graph_node_id('term', lemma='窓口:朝%', pos='名詞'),
               core.graph_node_id('def', definition_hash='a'*64), core.graph_node_id('clm', claim_id='claim:1')]
        for identifier in ids:
            self.assertEqual(core.validate_graph_node_id(identifier), identifier)
        self.assertNotEqual(core.graph_node_id('utt', item_id='a:b', segment_id='c'),
                            core.graph_node_id('utt', item_id='a', segment_id='b:c'))
        for identifier in ('utt:a:b:c', 'spk:', 'term:朝:%3a', 'clm:line\nbreak', 'def:abc', 'unknown:x'):
            with self.subTest(identifier=identifier), self.assertRaises(core.AnalysisContractError):
                core.validate_graph_node_id(identifier)

    def edge(self):
        return {'source': 'utt:one:u1', 'target': 'spk:person1', 'relation': 'spoken_by',
                'weight': 1, 'provenance': 'rule', 'method': 'fixture', 'method_version': '1',
                'input_hash': 'a'*64, 'evidence_segment_ids': ['utt:one:u1']}

    def test_edge_identity_preserves_provenance_input_and_evidence(self):
        value = self.edge()
        original = copy.deepcopy(value)
        edge = core.validate_graph_edge(value, evidence_ids={'utt:one:u1'})
        self.assertEqual(value, original)
        self.assertEqual(core.validate_graph_edge(edge), edge)
        for key, replacement in [('provenance', 'ai_draft'), ('provenance', 'researcher'),
                                 ('input_hash', 'b'*64), ('method_version', '2')]:
            changed = core.validate_graph_edge({**value, key: replacement})
            self.assertNotEqual(edge['edge_id'], changed['edge_id'])
        normalized = {**value, 'evidence_segment_ids': ['utt:one:u2', 'utt:one:u1', 'utt:one:u1']}
        reverse = {**normalized, 'evidence_segment_ids': list(reversed(normalized['evidence_segment_ids']))}
        self.assertEqual(core.validate_graph_edge(normalized), core.validate_graph_edge(reverse))

    def test_edge_rejects_missing_invalid_or_unknown_evidence(self):
        for key in self.edge():
            value = self.edge()
            value.pop(key)
            with self.subTest(missing=key), self.assertRaises(core.AnalysisContractError):
                core.validate_graph_edge(value)
        for key, value in [('weight', float('nan')), ('weight', float('inf')), ('weight', True),
                           ('provenance', 'confirmed'), ('input_hash', 'unknown'),
                           ('evidence_segment_ids', ['u1']), ('evidence_segment_ids', ['spk:p'])]:
            with self.subTest(key=key, value=value), self.assertRaises(core.AnalysisContractError):
                core.validate_graph_edge({**self.edge(), key: value})
        with self.assertRaises(core.AnalysisContractError):
            core.validate_graph_edge(self.edge(), evidence_ids={'utt:another:u1'})
        with self.assertRaises(core.AnalysisContractError):
            core.validate_graph_edge({**self.edge(), 'edge_id': 'edge:'+'0'*64})


if __name__ == '__main__':
    unittest.main()
