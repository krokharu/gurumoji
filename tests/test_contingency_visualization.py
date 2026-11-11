"""合成の整数度数だけで、計算・推測条件・保存結果の投影を確認する。"""
import copy
import io
import os
import tempfile
import unittest
from pathlib import Path

from gurumoji.analysis_contingency import analyze_contingency
from gurumoji.analysis_core import fingerprint
from gurumoji.analysis_templates import agent_guidance, TEMPLATE_VERSION, LEGACY_TEMPLATE_VERSION
from gurumoji.services.analysis_contingency_projection import contingency_pages
from gurumoji.services.analysis_slide_templates import load_slide_templates
from gurumoji.services.analysis_slide_visuals import can_render_visual
from gurumoji.services.analysis_slides import AnalysisSlidesService
from gurumoji.vault_registry import VaultRegistry
from test_analysis_slides_generation import broad_fixture

ROOT = Path(os.environ.get('GURUMOJI_CROSSTAB_PROJECT_ROOT', Path(__file__).resolve().parents[1]))


class ContingencyTests(unittest.TestCase):
    def example(self, independent=True):
        return analyze_contingency([[30, 10], [10, 30]], ['合成群A', '合成群B'], ['あり', 'なし'],
                                   independent=independent, analysis_unit='合成の独立観測')

    def test_calculation_matches_scipy_and_contributions_sum(self):
        from scipy.stats import chi2_contingency
        result = self.example()
        statistic, p, dof, expected = chi2_contingency([[30, 10], [10, 30]], correction=False)
        self.assertAlmostEqual(result['statistic'], statistic)
        self.assertAlmostEqual(result['reference_p_value'], p)
        self.assertEqual(result['degrees_of_freedom'], dof)
        self.assertEqual(result['expected'], expected.tolist())
        self.assertAlmostEqual(sum(sum(row) for row in result['chi_square_contributions']), statistic)
        self.assertAlmostEqual(result['cramers_v'], .5)
        self.assertTrue(result['inference_eligible'])

    def test_low_expected_or_unconfirmed_independence_cannot_claim_significance(self):
        for independent in (False, None):
            result = self.example(independent)
            self.assertIsNone(result['p_value'])
            self.assertIsNotNone(result['reference_p_value'])
            self.assertFalse(result['inference_eligible'])
            self.assertIn('保留', result['decision'])
        small = analyze_contingency([[3, 0], [0, 3]], ['A', 'B'], ['あり', 'なし'], independent=True)
        self.assertFalse(small['inference_eligible'])
        self.assertEqual(small['expected_below_5'], 4)

    def test_zero_margins_do_not_create_division_or_fake_residual(self):
        result = analyze_contingency([[30, 10, 0], [10, 30, 0], [0, 0, 0]],
                                     ['A', 'B', '空行'], ['あり', 'なし', '空列'], independent=True)
        self.assertEqual(result['degrees_of_freedom'], 1)
        self.assertEqual(result['excluded_zero_rows'], ['空行'])
        self.assertEqual(result['excluded_zero_columns'], ['空列'])
        self.assertIsNone(result['pearson_residuals'][2][0])
        self.assertAlmostEqual(result['statistic'], 20)
        empty = analyze_contingency([[0, 0], [0, 0]], ['A', 'B'], ['あり', 'なし'])
        self.assertIsNone(empty['statistic'])
        self.assertIsNone(empty['reference_p_value'])

    def test_non_integer_negative_nan_and_duplicate_labels_are_rejected(self):
        for matrix in ([[.5, 1], [1, 2]], [[-1, 1], [1, 2]], [[float('nan'), 1], [1, 2]], [[True, 1], [1, 2]]):
            with self.assertRaises(ValueError):
                analyze_contingency(matrix, ['A', 'B'], ['あり', 'なし'])
        with self.assertRaises(ValueError):
            analyze_contingency([[1, 2], [3, 4]], ['A', 'A'], ['あり', 'なし'])

    def test_projection_is_read_only_and_has_two_native_layouts(self):
        item = self.example(False)
        source = {'contingency_visualizations': [item]}
        before = copy.deepcopy(source)
        pages = contingency_pages(source, {'crosstab_chi_square': True})
        self.assertEqual(source, before)
        self.assertEqual([p['kind'] for p in pages], ['crosstab', 'chi_square'])
        self.assertTrue(all(can_render_visual(page) for page in pages), pages)
        self.assertIn('参考p', pages[1]['statistics_text'])
        self.assertIn('保留', pages[1]['title'])
        self.assertIn('75.0%', pages[0]['grid'][1][1])
        self.assertEqual(contingency_pages({}, {'crosstab_chi_square': True}), [])

    def test_old_agent_template_keeps_its_saved_guidance(self):
        old = agent_guidance(LEGACY_TEMPLATE_VERSION, {'id': 'quantitative'}, 'core')
        new = agent_guidance(TEMPLATE_VERSION, {'id': 'quantitative'}, 'core')
        self.assertIn('未実行の検定', old)
        self.assertNotIn('期待度数', old)
        self.assertIn('期待度数', new)
        self.assertIn(LEGACY_TEMPLATE_VERSION, old)

    def test_template_hashes_and_service_integration_use_temporary_vault(self):
        templates = load_slide_templates(ROOT)
        self.assertEqual(templates['gurumoji-evidence-review']['version'], '2.1.0')
        saved = broad_fixture()
        saved['initial']['snapshot']['analysis'] = {'research': {'statistics': {'contingency_visualizations': [self.example(False)]}}}
        saved['initial']['hash'] = fingerprint(saved['initial']['snapshot'])
        original = copy.deepcopy(saved)
        with tempfile.TemporaryDirectory() as temp:
            vault = VaultRegistry(Path(temp)/'data.sqlite3', Path(temp)/'software')
            service = AnalysisSlidesService(export_result=lambda *_: copy.deepcopy(saved), vault_factory=lambda: vault, templates=templates)
            service.save_design('item-1', 'run-1')
            preview = service.preview('item-1', 'run-1')
            pages = [s for s in preview['slides'] if (s.get('visual') or {}).get('kind') in {'crosstab', 'chi_square'}]
            self.assertEqual(len(pages), 2)
            from pptx import Presentation
            output = service.presentation('item-1', 'run-1', expected_snapshot=preview['snapshot_signature']).getvalue()
            presentation = Presentation(io.BytesIO(output))
            for page in pages:
                index = preview['slides'].index(page)
                self.assertTrue(any(s.has_table for s in presentation.slides[index].shapes))
        self.assertEqual(saved, original)


if __name__ == '__main__':
    unittest.main()
