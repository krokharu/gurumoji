"""Synthetic-only contract/security tests; no Store, Vault, network or models."""
import copy
import io
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image
from gurumoji.services.analysis_visuals import (
    MAX_BYTES, RENDERER_VERSION, SCHEMA_VERSION, SLOTS, VisualSpecError,
    render_visual_png, validate_visual_spec, visual_data_hash,
)


DATA = {
    "thematic": {"rows": [{"theme": "Access", "support_ids": ["ev-1"],
                            "counterevidence_ids": ["ev-2"]}]},
    "participation": {"labels": ["A", "B", "Unknown"], "values": [3, 0, None],
                      "timeline": [{"time_seconds": 0, "value": 1},
                                   {"time_seconds": 10, "value": None},
                                   {"time_seconds": 20, "value": 2}]},
    "distribution": {"bin_unit": "seconds", "bins": [{"lower": -1, "upper": 0, "count": 0},
                               {"lower": 0, "upper": 1, "count": None},
                               {"lower": 1, "upper": 2, "count": 3}]},
    "correlation": {"labels": ["A", "B", "C"],
                    "values": [[1, -.5, None], [-.5, 1, .2], [None, .2, None]]},
    "crosstab": {"row_labels": ["A", "B"], "column_labels": ["X", "Y"],
                 "values": [[0, 2], [None, 1]]},
    "parallel": {"labels": ["Before", "After"], "series": [
        {"name": "A", "values": [-2, 3]}, {"name": "B", "values": [0, None]}]},
    "dependency": {"nodes": [{"id": "a", "label": "Input"},
                              {"id": "b", "label": "Result"}],
                   "edges": [{"source": "a", "target": "b", "weight": None}]},
    "coverage": {"rows": [{"label": "A", "covered": 2, "total": 3},
                           {"label": "B", "covered": None, "total": None},
                           {"label": "C", "covered": 0, "total": 0}]},
}


def fixture(slot="participation"):
    data = copy.deepcopy(DATA[slot])
    return {"schema_version": SCHEMA_VERSION, "renderer_version": RENDERER_VERSION,
            "slot": slot, "run_id": "run-synthetic", "run_hash": "a" * 64,
            "input_hash": "b" * 64, "data_hash": visual_data_hash(data),
            "title": "Synthetic " + slot, "unit": "observations",
            "denominator": {"label": "eligible observations", "value": 4},
            "missingness": {"count": None, "reason": "Not recorded"},
            "evidence_ids": ["ev-1", "ev-2"],
            "alt_text": "Synthetic fixed data. Unknown entries are explicitly marked.",
            "data": data}


def expected(spec):
    return {"expected_" + key: spec[key] for key in
            ("run_id", "run_hash", "input_hash", "data_hash")}


class AnalysisVisualsTests(unittest.TestCase):
    def test_all_eight_real_png_decode_metadata_and_determinism(self):
        self.assertEqual(set(DATA), set(SLOTS))
        for slot in SLOTS:
            with self.subTest(slot=slot):
                spec = fixture(slot)
                original = copy.deepcopy(spec)
                png = render_visual_png(spec, **expected(spec))
                self.assertEqual(png, render_visual_png(spec, **expected(spec)))
                self.assertLess(len(png), 2_000_000)
                with Image.open(io.BytesIO(png)) as image:
                    image.load()
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.size, (1200, 800))
                    self.assertGreater(len(image.getcolors(2_000_000)), 20)
                    self.assertEqual(json.loads(image.info["Description"])["spec"], spec)
                    self.assertEqual(image.info["Software"], RENDERER_VERSION)
                self.assertEqual(spec, original)

    def test_validated_snapshot_is_independent(self):
        spec = fixture()
        result = validate_visual_spec(spec, **expected(spec))
        result["data"]["values"][0] = 999
        self.assertEqual(spec["data"]["values"][0], 3)

    def test_unknown_is_visible_and_not_zero_bar(self):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.text import Text
        original = FigureCanvasAgg.print_png
        seen = {}

        def inspect(canvas, *args, **kwargs):
            seen["texts"] = [t.get_text() for t in canvas.figure.findobj(Text)]
            seen["bars"] = [p.get_height() for p in canvas.figure.axes[0].patches]
            return original(canvas, *args, **kwargs)
        spec = fixture()
        with patch.object(FigureCanvasAgg, "print_png", inspect):
            render_visual_png(spec, **expected(spec))
        self.assertIn("unknown", seen["texts"])
        self.assertEqual(seen["bars"], [3, 0])
        footer = "\n".join(seen["texts"])
        for text in ("Unit: observations", "Denominator eligible observations: 4",
                     "Missing: unknown", "Evidence: ev-1, ev-2"):
            self.assertIn(text, footer)

    def test_each_trusted_binding_and_self_consistent_tamper(self):
        spec = fixture()
        for key in expected(spec):
            trust = expected(spec)
            trust[key] = "wrong"
            with self.subTest(key=key), self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **trust)
        trust = expected(spec)
        spec["data"]["values"][0] = 9
        spec["data_hash"] = visual_data_hash(spec["data"])
        with self.assertRaises(VisualSpecError):
            render_visual_png(spec, **trust)

    def test_closed_schema_versions_required_metadata(self):
        for key in fixture():
            spec = fixture()
            del spec[key]
            with self.subTest(key=key), self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **expected(fixture()))
        for key, value in (("url", "https://example.org"), ("width", 1000000),
                           ("schema_version", "new"), ("renderer_version", "new"),
                           ("slot", "python"), ("evidence_ids", []),
                           ("data_hash", "ABC"), ("alt_text", "")):
            spec = fixture()
            spec[key] = value
            with self.subTest(key=key), self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **expected(fixture()))

    def test_rejects_active_text_urls_paths_and_control_characters(self):
        bad = ["https://example.org", "//example.org", "/tmp/out.png", "../image",
               r"C:\output.png", "<script>alert(1)</script>", "javascript:alert(1)",
               "data:image/png", "file:secret", "www.example.org", "x\x00y",
               "a\nb", "x\ud800", "`code`", "function() { return 1; }"]
        for text in bad:
            for key in ("title", "alt_text", "unit"):
                spec = fixture()
                spec[key] = text
                with self.subTest(text=text, key=key), self.assertRaises(VisualSpecError):
                    render_visual_png(spec, **expected(spec))

    def test_finite_numeric_type_and_resource_limits(self):
        for value in (True, "4", float("nan"), float("inf"), -1, 10**1000):
            spec = fixture()
            spec["data"]["values"][0] = value
            with self.subTest(value=str(value)[:30]), self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **expected(spec))
        for value in ("x" * 241, list(range(129)), {str(i): 0 for i in range(33)}):
            with self.assertRaises(VisualSpecError):
                visual_data_hash(value)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(VisualSpecError):
            visual_data_hash(cycle)
        with self.assertRaises(VisualSpecError):
            visual_data_hash([["長" * 240] * 128] * 2)
        self.assertEqual(MAX_BYTES, 65536)

    def test_slot_specific_semantic_failures(self):
        cases = [("thematic", lambda d: d["rows"][0]["support_ids"].append("unbound")),
                 ("thematic", lambda d: d["rows"][0]["support_ids"].append("ev-2")),
                 ("participation", lambda d: d["values"].pop()),
                 ("participation", lambda d: d["timeline"].reverse()),
                 ("distribution", lambda d: d["bins"][0].update(upper=1)),
                 ("distribution", lambda d: d["bins"][0].update(count=1.5)),
                 ("correlation", lambda d: d["values"][0].__setitem__(1, .8)),
                 ("correlation", lambda d: d["values"][0].__setitem__(0, .8)),
                 ("correlation", lambda d: d["values"][0].__setitem__(1, 1.1)),
                 ("crosstab", lambda d: d["values"][0].pop()),
                 ("parallel", lambda d: d["series"][0]["values"].pop()),
                 ("dependency", lambda d: d["edges"][0].update(target="missing")),
                 ("dependency", lambda d: d["edges"].append(copy.deepcopy(d["edges"][0]))),
                 ("coverage", lambda d: d["rows"][0].update(covered=4))]
        for slot, mutate in cases:
            spec = fixture(slot)
            mutate(spec["data"])
            spec["data_hash"] = visual_data_hash(spec["data"])
            with self.subTest(slot=slot), self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **expected(spec))

    def test_nested_extra_keys_and_duplicate_ids(self):
        for field in ("data", "missingness", "denominator"):
            spec = fixture()
            spec[field]["extra"] = "unexpected"
            spec["data_hash"] = visual_data_hash(spec["data"])
            with self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **expected(spec))
        spec = fixture()
        spec["evidence_ids"].append("ev-1")
        with self.assertRaises(VisualSpecError):
            validate_visual_spec(spec, **expected(spec))

    def test_invalid_spec_never_enters_renderer(self):
        spec = fixture()
        spec["title"] = "https://example.org"
        with patch("matplotlib.backends.backend_agg.FigureCanvasAgg.print_png") as paint:
            with self.assertRaises(VisualSpecError):
                render_visual_png(spec, **expected(spec))
            paint.assert_not_called()

    def test_unknown_denominator_and_empty_dependency_edges(self):
        spec = fixture("dependency")
        spec["denominator"]["value"] = None
        spec["data"]["edges"] = []
        spec["data_hash"] = visual_data_hash(spec["data"])
        self.assertIsNone(validate_visual_spec(spec, **expected(spec))["denominator"]["value"])
        self.assertTrue(render_visual_png(spec, **expected(spec)).startswith(b"\x89PNG"))

    def test_render_is_independent_of_ambient_style(self):
        import matplotlib
        spec = fixture()
        baseline = render_visual_png(spec, **expected(spec))
        with matplotlib.rc_context({"text.usetex": True, "figure.facecolor": "red",
                                    "font.size": 40, "savefig.dpi": 20}):
            self.assertEqual(baseline, render_visual_png(spec, **expected(spec)))
            self.assertTrue(matplotlib.rcParams["text.usetex"])

    def test_metadata_numeric_failures(self):
        for denominator, missing in ((-1, 0), (1, 2), (0, 1), (4, -1), (4, 1.5)):
            spec = fixture()
            spec["denominator"]["value"] = denominator
            spec["missingness"]["count"] = missing
            with self.subTest(denominator=denominator, missing=missing), self.assertRaises(VisualSpecError):
                validate_visual_spec(spec, **expected(spec))

    def test_all_unknown_and_zero_values_remain_distinct(self):
        for slot in ("correlation", "parallel", "participation"):
            spec = fixture(slot)
            if slot == "correlation":
                spec["data"]["values"] = [[None] * 3 for _ in range(3)]
            elif slot == "parallel":
                for row in spec["data"]["series"]:
                    row["values"] = [None, None]
            else:
                spec["data"]["values"] = [None, None, None]
                for row in spec["data"]["timeline"]:
                    row["value"] = None
            spec["data_hash"] = visual_data_hash(spec["data"])
            png = render_visual_png(spec, **expected(spec))
            with Image.open(io.BytesIO(png)) as image:
                self.assertEqual(json.loads(image.info["Description"])["spec"]["data"], spec["data"])

    def test_no_clipping_on_overfull_table(self):
        spec = fixture("crosstab")
        spec["data"] = {"row_labels": ["A"], "column_labels": [str(i) + "W" * 31 for i in range(6)],
                        "values": [[1] * 6]}
        spec["data_hash"] = visual_data_hash(spec["data"])
        with self.assertRaisesRegex(VisualSpecError, "fit"):
            render_visual_png(spec, **expected(spec))

    def test_oversized_tick_labels_are_rejected_without_clipping(self):
        spec = fixture("coverage")
        spec["data"]["rows"] = [{"label": chr(65 + i) + "W" * 31,
                                  "covered": 1, "total": 1} for i in range(12)]
        spec["data_hash"] = visual_data_hash(spec["data"])
        with self.assertRaisesRegex(VisualSpecError, "overlap|fit"):
            render_visual_png(spec, **expected(spec))

    def test_japanese_glyph_support_or_explicit_rejection(self):
        from gurumoji.services.analysis_visuals import _select_font
        spec = fixture("thematic")
        spec["title"] = "支持根拠と反証"
        try:
            family, _ = _select_font(spec["title"])
        except VisualSpecError:
            with self.assertRaisesRegex(VisualSpecError, "font"):
                render_visual_png(spec, **expected(spec))
        else:
            png = render_visual_png(spec, **expected(spec))
            with Image.open(io.BytesIO(png)) as image:
                image.load()
                self.assertEqual(json.loads(image.info["Description"])["runtime"]["font_family"], family)

    def test_japanese_title_and_table_cell_use_same_verified_face(self):
        from gurumoji.services.analysis_visuals import _select_font
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.table import Table
        spec = fixture("thematic")
        spec["title"] = "支援根拠と反証"
        spec["data"]["rows"][0]["theme"] = "学習支援"
        spec["data_hash"] = visual_data_hash(spec["data"])
        try:
            family, font_path = _select_font(spec["title"] + "学習支援")
        except VisualSpecError:
            self.skipTest("No installed allowlisted font covers the Japanese fixture")
        original = FigureCanvasAgg.print_png
        seen = []
        def inspect(canvas, *args, **kwargs):
            for table in canvas.figure.findobj(Table):
                for cell in table.get_celld().values():
                    text = cell.get_text()
                    self.assertEqual(text.get_fontproperties().get_file(), font_path)
                    seen.append(text.get_text())
            return original(canvas, *args, **kwargs)
        with patch("gurumoji.services.analysis_visuals._select_font", wraps=_select_font) as select, \
                patch.object(FigureCanvasAgg, "print_png", inspect):
            png = render_visual_png(spec, **expected(spec))
            self.assertIn("学習支援", select.call_args.args[0])
            self.assertIn("支援根拠と反証", select.call_args.args[0])
        self.assertIn("学習支援", seen)
        with Image.open(io.BytesIO(png)) as image:
            image.load()
            self.assertEqual(image.size, (1200, 800))
            metadata = json.loads(image.info["Description"])
            self.assertEqual(metadata["runtime"]["font_family"], family)
            self.assertEqual(metadata["spec"], spec)

    def test_windows_font_candidates_use_actual_coverage(self):
        from gurumoji.services.analysis_visuals import _select_font
        ascii_glyphs = set(range(32, 127)) | {0x2212}
        japanese_glyphs = ascii_glyphs | {ord(c) for c in "日本語"}
        for family in ("Meiryo", "Yu Gothic", "Yu Gothic UI", "MS Gothic"):
            fonts = [SimpleNamespace(name="Noto Sans CJK JP"), SimpleNamespace(name=family)]
            def resolve(properties, **kwargs):
                self.assertFalse(kwargs["fallback_to_default"])
                return properties.get_family()[0]
            def face(path):
                return SimpleNamespace(get_charmap=lambda: (
                    ascii_glyphs if path == "Noto Sans CJK JP" else japanese_glyphs))
            with self.subTest(family=family), \
                    patch("matplotlib.font_manager.fontManager.ttflist", fonts), \
                    patch("matplotlib.font_manager.findfont", side_effect=resolve), \
                    patch("matplotlib.ft2font.FT2Font", side_effect=face):
                self.assertEqual(_select_font("日本語"), (family, family))

    def test_font_selection_is_fixed_priority_and_rejects_missing_coverage(self):
        from gurumoji.services.analysis_visuals import _select_font
        fonts = [SimpleNamespace(name="MS Gothic"), SimpleNamespace(name="Meiryo")]
        glyphs = set(range(32, 127)) | {0x2212} | {ord(c) for c in "日本語"}
        with patch("matplotlib.font_manager.fontManager.ttflist", fonts), \
                patch("matplotlib.font_manager.findfont", side_effect=lambda p, **k: p.get_family()[0]), \
                patch("matplotlib.ft2font.FT2Font", return_value=SimpleNamespace(get_charmap=lambda: glyphs)):
            self.assertEqual(_select_font("日本語")[0], "Meiryo")
            with self.assertRaisesRegex(VisualSpecError, "covers"):
                _select_font("日本語漢字")
        with patch("matplotlib.font_manager.fontManager.ttflist", []):
            with self.assertRaisesRegex(VisualSpecError, "font"):
                _select_font("plain text")

    def test_reciprocal_dependency_edges_and_weights_do_not_overlap(self):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        original = FigureCanvasAgg.print_png
        spec = fixture("dependency")
        spec["data"]["edges"] = [{"source": "a", "target": "b", "weight": 1},
                                 {"source": "b", "target": "a", "weight": 2}]
        spec["data_hash"] = visual_data_hash(spec["data"])
        seen = {}
        def inspect(canvas, *args, **kwargs):
            renderer = canvas.get_renderer()
            texts = canvas.figure.axes[0].texts
            labels = [t for t in texts if t.get_text() in ("1", "2")]
            boxes = [t.get_bbox_patch().get_window_extent(renderer) for t in labels]
            self.assertEqual(len(boxes), 2)
            self.assertFalse(boxes[0].overlaps(boxes[1]))
            arrows = [t.arrow_patch for t in texts if getattr(t, "arrow_patch", None) is not None]
            self.assertEqual(len(arrows), 2)
            self.assertFalse((arrows[0].get_path().vertices == arrows[1].get_path().vertices).all())
            seen["weights"] = [t.get_text() for t in labels]
            return original(canvas, *args, **kwargs)
        with patch.object(FigureCanvasAgg, "print_png", inspect):
            png = render_visual_png(spec, **expected(spec))
        self.assertEqual(seen["weights"], ["1", "2"])
        with Image.open(io.BytesIO(png)) as image:
            image.load()
            self.assertEqual(image.size, (1200, 800))
            self.assertEqual(json.loads(image.info["Description"])["spec"], spec)
        self.assertEqual(png, render_visual_png(spec, **expected(spec)))

    def test_impossible_dependency_label_layout_is_rejected(self):
        spec = fixture("dependency")
        spec["data"]["nodes"] = [{"id": c, "label": c.upper()} for c in "abcd"]
        # Two diameter edges have identical label midpoints, with no reciprocal
        # partner to route around. This bounded layout must reject, not obscure.
        spec["data"]["edges"] = [{"source": "a", "target": "c", "weight": 1},
                                 {"source": "b", "target": "d", "weight": 2}]
        spec["data_hash"] = visual_data_hash(spec["data"])
        with self.assertRaisesRegex(VisualSpecError, "dependency labels overlap"):
            render_visual_png(spec, **expected(spec))

    def test_previous_renderer_version_is_not_silently_upgraded(self):
        spec = fixture()
        spec["renderer_version"] = "analysis-png-1"
        with self.assertRaisesRegex(VisualSpecError, "renderer version"):
            render_visual_png(spec, **expected(spec))

    def test_hash_is_order_independent_and_sensitive(self):
        self.assertEqual(visual_data_hash({"a": 1, "b": None}),
                         visual_data_hash({"b": None, "a": 1}))
        self.assertNotEqual(visual_data_hash({"a": None}), visual_data_hash({"a": 0}))


if __name__ == "__main__":
    unittest.main()
