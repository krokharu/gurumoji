"""Public synthetic package fixtures; no Store, Vault, network or model use."""
import copy
import hashlib
import io
import json
import struct
import unittest
import zlib
from unittest.mock import patch

from PIL import Image, ImageFile
from gurumoji.services.analysis_visuals import (
    RENDERER_VERSION, SCHEMA_VERSION, SLOTS, visual_data_hash,
)
from gurumoji.services.analysis_visual_package import (
    MAX_DESCRIPTION_BYTES, MAX_PNG_BYTES, MAX_SPEC_BYTES, VisualPackageError,
    render_visual_package, verify_visual_package,
)


DATA = {
    "thematic": {"rows": [{"theme": "Access", "support_ids": ["ev-1"],
                            "counterevidence_ids": ["ev-2"]}]},
    "participation": {"labels": ["A", "B", "Unknown"], "values": [3, 0, None],
                      "timeline": [{"time_seconds": 0, "value": 1},
                                   {"time_seconds": 10, "value": None},
                                   {"time_seconds": 20, "value": 2}]},
    "distribution": {"bin_unit": "seconds", "bins": [
        {"lower": -1, "upper": 0, "count": 0},
        {"lower": 0, "upper": 1, "count": None},
        {"lower": 1, "upper": 2, "count": 3}]},
    "correlation": {"labels": ["A", "B", "C"],
                    "values": [[1, 0, None], [0, 1, .2], [None, .2, None]]},
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


def fixture(slot="participation", *, japanese=False):
    """Reusable representative input for Linux/Windows probes; fully synthetic."""
    data = copy.deepcopy(DATA[slot])
    if japanese and slot == "thematic":
        data["rows"][0]["theme"] = "参加の機会"
    if japanese and slot == "crosstab":
        data["row_labels"] = ["参加者甲", "参加者乙"]
        data["column_labels"] = ["質問", "応答"]
    return {"schema_version": SCHEMA_VERSION, "renderer_version": RENDERER_VERSION,
            "slot": slot, "run_id": "run-synthetic", "run_hash": "a" * 64,
            "input_hash": "b" * 64, "data_hash": visual_data_hash(data),
            "title": "合成テーマ表" if japanese and slot == "thematic" else
                     "合成クロス表" if japanese else "Synthetic " + slot,
            "unit": "件" if japanese else "observations",
            "denominator": {"label": "対象発話" if japanese else "eligible observations", "value": 4},
            "missingness": {"count": None, "reason": "未記録" if japanese else "Not recorded"},
            "evidence_ids": ["ev-1", "ev-2"],
            "alt_text": "合成データ。欠測とゼロを区別する。" if japanese else
                        "Synthetic fixed data. Unknown entries are explicitly marked.",
            "data": data}


def expected(spec):
    return {"expected_" + key: spec[key] for key in
            ("run_id", "run_hash", "input_hash", "data_hash")}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", zlib.crc32(data, zlib.crc32(kind)) & 0xffffffff)


def chunks(png):
    offset = 8
    while offset < len(png):
        length, kind = struct.unpack_from(">I4s", png, offset)
        yield kind, png[offset + 8:offset + 8 + length]
        offset += 12 + length


def change_chunks(png, transform):
    return png[:8] + b"".join(chunk(kind, data) for kind, data in transform(list(chunks(png))))


def metadata_chunk(key, text, kind=b"iTXt", *, compressed=False):
    value = text.encode("utf-8" if kind == b"iTXt" else "latin-1")
    if kind == b"iTXt":
        value = bytes([int(compressed), 0]) + b"\0\0" + (zlib.compress(value) if compressed else value)
    elif kind == b"zTXt":
        value = b"\0" + zlib.compress(value)
    return kind, key.encode("ascii") + b"\0" + value


def replace_metadata(png, key, text, **kwargs):
    return change_chunks(png, lambda pairs: [metadata_chunk(key, text, **kwargs)
        if kind in (b"tEXt", b"zTXt", b"iTXt") and data.partition(b"\0")[0] == key.encode()
        else (kind, data) for kind, data in pairs])


class AnalysisVisualPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packages = {slot: render_visual_package(fixture(slot), **expected(fixture(slot)))
                        for slot in SLOTS}

    def verify(self, spec_bytes=None, png_bytes=None, *, approved=None, png_hash=None, **bindings):
        original_spec, original_png, receipt = self.packages["participation"]
        spec_bytes = original_spec if spec_bytes is None else spec_bytes
        png_bytes = original_png if png_bytes is None else png_bytes
        approved = fixture() if approved is None else approved
        return verify_visual_package(spec_bytes, png_bytes, approved_spec=approved,
            **(bindings or expected(fixture())),
            expected_png_hash=receipt["png_hash"] if png_hash is None else png_hash)

    def reject_png(self, png):
        # Recalculate the external hash so malformed bytes actually exercise
        # structural/metadata checks instead of only the hash mismatch path.
        with self.assertRaises(VisualPackageError):
            self.verify(png_bytes=png, png_hash=hashlib.sha256(png).hexdigest())

    def test_01_japanese_thematic_and_crosstab(self):
        for slot in ("thematic", "crosstab"):
            with self.subTest(slot=slot):
                spec = fixture(slot, japanese=True)
                raw, png, receipt = render_visual_package(spec, **expected(spec))
                self.assertEqual(verify_visual_package(raw, png, approved_spec=spec,
                    **expected(spec), expected_png_hash=receipt["png_hash"]), receipt)
                self.assertEqual(json.loads(raw), spec)
                with Image.open(io.BytesIO(png)) as image:
                    self.assertEqual(json.loads(image.info["Description"])["spec"], spec)

    def test_02_all_eight_roundtrip_closed_receipt_and_null_zero(self):
        self.assertEqual(set(self.packages), set(DATA))
        for slot, (raw, png, receipt) in self.packages.items():
            with self.subTest(slot=slot):
                spec = fixture(slot)
                self.assertEqual(raw, canonical(spec))
                self.assertEqual(verify_visual_package(raw, png, approved_spec=spec,
                    **expected(spec), expected_png_hash=receipt["png_hash"]), receipt)
                self.assertEqual(set(receipt), {"spec_hash", "spec_bytes", "png_hash", "png_bytes",
                    "width", "height", "schema_version", "renderer_version", "runtime"})
                self.assertEqual(receipt["spec_hash"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(receipt["png_hash"], hashlib.sha256(png).hexdigest())
                self.assertEqual((receipt["spec_bytes"], receipt["png_bytes"]), (len(raw), len(png)))
                self.assertEqual((receipt["width"], receipt["height"]), (1200, 800))
                self.assertEqual(set(receipt["runtime"]), {"matplotlib", "pillow", "font_family"})
                self.assertEqual(json.loads(json.dumps(receipt)), receipt)
                self.assertEqual(json.loads(raw)["missingness"]["count"], None)
        matrix = json.loads(self.packages["crosstab"][0])["data"]["values"]
        self.assertEqual(matrix[0][0], 0)
        self.assertIsNone(matrix[1][0])


    def test_saved_bytes_retry_never_renders_and_snapshots_are_independent(self):
        original = fixture()
        with patch("gurumoji.services.analysis_visual_package.render_visual_png", side_effect=AssertionError("rerender")):
            receipt = self.verify()
            again = self.verify()
        receipt["runtime"]["pillow"] = "changed"
        self.assertNotEqual(receipt, again)
        self.assertEqual(fixture(), original)

    def test_render_calls_renderer_once_and_does_not_mutate_approval(self):
        spec = fixture()
        before = copy.deepcopy(spec)
        png = self.packages["participation"][1]
        with patch("gurumoji.services.analysis_visual_package.render_visual_png", return_value=png) as render:
            raw, actual, receipt = render_visual_package(spec, **expected(spec))
            render.assert_called_once()
        self.assertEqual(spec, before)
        self.assertEqual((raw, actual, receipt), self.packages["participation"])

    def test_every_existing_schema_field_is_bound_to_approval(self):
        self.assertEqual(len(fixture()), 14)  # The existing v1 schema, not a new fifteenth field.
        for key in fixture():
            candidate = fixture()
            del candidate[key]
            with self.subTest(missing=key), self.assertRaises(VisualPackageError):
                self.verify(spec_bytes=canonical(candidate))
        mutations = {
            "title": "Changed title", "unit": "seconds",
            "denominator": {"label": "another population", "value": 3},
            "missingness": {"count": 0, "reason": "Changed reason"},
            "evidence_ids": ["ev-2", "ev-1"], "alt_text": "Changed description",
            "run_id": "other-run", "run_hash": "c" * 64, "input_hash": "d" * 64,
            "schema_version": "analysis-visual-2", "renderer_version": "analysis-png-unknown",
            "slot": "coverage", "data_hash": "e" * 64,
            "data": {"labels": ["A"], "values": [8], "timeline": [{"time_seconds": 0, "value": 8}]},
        }
        for key, value in mutations.items():
            changed = fixture()
            changed[key] = value
            with self.subTest(changed=key), self.assertRaises(VisualPackageError):
                self.verify(spec_bytes=canonical(changed))
        # The candidate can be internally self-consistent; trusted full
        # approval and original external data binding still win.
        changed = fixture()
        changed["data"]["values"][0] = 9
        changed["data_hash"] = visual_data_hash(changed["data"])
        with self.assertRaises(VisualPackageError):
            self.verify(spec_bytes=canonical(changed))
        with self.assertRaises(VisualPackageError):
            self.verify(spec_bytes=canonical(changed), **expected(changed))

    def test_metadata_only_changes_fail_with_same_four_bindings(self):
        for key, value in (("title", "Different"), ("unit", "seconds"),
            ("denominator", {"label": "new population", "value": 4}),
            ("denominator", {"label": "eligible observations", "value": None}),
            ("missingness", {"count": 0, "reason": "Not recorded"}),
            ("evidence_ids", ["ev-1"]), ("alt_text", "Different text")):
            candidate = fixture()
            candidate[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(VisualPackageError, "approved spec mismatch"):
                self.verify(spec_bytes=canonical(candidate))
            with self.subTest(approval_key=key), self.assertRaisesRegex(VisualPackageError, "approved spec mismatch"):
                self.verify(approved=candidate)
        candidate = fixture()
        candidate["denominator"]["value"] = 4.0
        with self.assertRaisesRegex(VisualPackageError, "approved spec mismatch"):
            self.verify(spec_bytes=canonical(candidate))

    def test_each_external_binding_is_required_by_both_apis(self):
        for key in expected(fixture()):
            bindings = expected(fixture())
            bindings[key] = "wrong"
            with self.subTest(key=key), self.assertRaises(VisualPackageError):
                self.verify(**bindings)
            with self.subTest(render_key=key), self.assertRaises(VisualPackageError):
                render_visual_package(fixture(), **bindings)
        raw, png, _ = self.packages["participation"]
        for key in expected(fixture()):
            bindings = expected(fixture())
            del bindings[key]
            with self.subTest(missing=key), self.assertRaises(TypeError):
                verify_visual_package(raw, png, approved_spec=fixture(),
                                      expected_png_hash="a" * 64, **bindings)

    def test_expected_bindings_reject_custom_equality_and_non_json_values(self):
        class EqualAnything:
            def __eq__(self, other):
                raise AssertionError("custom equality must never run")
        class StringSubclass(str):
            def __eq__(self, other):
                raise AssertionError("custom string equality must never run")
        for key in expected(fixture()):
            for value in (EqualAnything(), StringSubclass("a" * 64), None, True, 4):
                bindings = expected(fixture())
                bindings[key] = value
                with self.subTest(key=key, value=type(value).__name__), self.assertRaises(VisualPackageError):
                    self.verify(**bindings)

    def test_saved_png_hash_is_mandatory_and_exact(self):
        raw, png, _ = self.packages["participation"]
        with self.assertRaises(TypeError):
            verify_visual_package(raw, png, approved_spec=fixture(), **expected(fixture()))
        for value in (None, "", "A" * 64, "g" * 64, "a" * 63, "a" * 64, 12, True):
            with self.subTest(value=value), self.assertRaises(VisualPackageError):
                verify_visual_package(raw, png, approved_spec=fixture(),
                                      expected_png_hash=value, **expected(fixture()))
        different_png = self.packages["thematic"][1]
        with self.assertRaises(VisualPackageError):
            self.verify(png_bytes=different_png)

    def test_spec_bytes_must_be_canonical_utf8_and_exact_bytes(self):
        raw = self.packages["participation"][0]
        for value in (raw + b" ", b"\xef\xbb\xbf" + raw, raw.decode(), bytearray(raw),
                      b"", b"\xff", b"[", b"null", b"[]", b"{}",
                      json.dumps(fixture(), indent=2).encode()):
            with self.subTest(value=type(value).__name__), self.assertRaises(VisualPackageError):
                self.verify(spec_bytes=value)
        for value in (b"x" * (MAX_SPEC_BYTES + 1), b"[" * 11 + b"0" + b"]" * 11):
            with self.assertRaises(VisualPackageError):
                self.verify(spec_bytes=value)

    def test_duplicate_keys_nonfinite_surrogates_and_extra_fields(self):
        raw = self.packages["participation"][0]
        cases = [raw[:-1] + b',"title":"same"}',
                 raw.replace(b'"value":4', b'"value":4,"value":4'),
                 raw.replace(b'"value":4', b'"value":NaN'),
                 raw.replace(b'"value":4', b'"value":Infinity'),
                 raw.replace(b'"value":4', b'"value":-Infinity'),
                 raw.replace(b'"value":4', b'"value":1e999'),
                 raw.replace(b'"value":4', b'"value":true'),
                 raw.replace(b'"title":"Synthetic participation"', b'"title":"\\ud800"')]
        for value in cases:
            with self.subTest(raw=value[:80]), self.assertRaises(VisualPackageError):
                self.verify(spec_bytes=value)
        for key in ("url", "path", "style", "font", "html"):
            spec = fixture()
            spec[key] = "extra"
            with self.subTest(key=key), self.assertRaises(VisualPackageError):
                self.verify(spec_bytes=canonical(spec))
            with self.assertRaises(VisualPackageError):
                render_visual_package(spec, **expected(fixture()))

    def test_unsafe_or_non_json_approval_fails_before_rendering(self):
        for value in ("https://example.org", "../out.png", "<b>text</b>", "file:out", "line\nnext"):
            spec = fixture()
            spec["title"] = value
            with self.subTest(value=value), patch("gurumoji.services.analysis_visual_package.render_visual_png") as render:
                with self.assertRaises(VisualPackageError):
                    render_visual_package(spec, **expected(fixture()))
                render.assert_not_called()
        for value in (float("nan"), float("inf"), True, object()):
            spec = fixture()
            spec["denominator"]["value"] = value
            with self.assertRaises(VisualPackageError):
                render_visual_package(spec, **expected(fixture()))
        spec = fixture()
        spec["data"] = spec
        with self.assertRaises(VisualPackageError):
            render_visual_package(spec, **expected(fixture()))

    def test_png_type_signature_limits_and_truncation(self):
        png = self.packages["participation"][1]
        for value in ("PNG", bytearray(png), b"", b"not-png", png[:8], png[:20],
                      png[:-1], png[:-12], png + b"trailing", png + png,
                      b"x" * (MAX_PNG_BYTES + 1)):
            with self.subTest(value=type(value).__name__), self.assertRaises(VisualPackageError):
                self.verify(png_bytes=value)
        corrupt = bytearray(png)
        corrupt[29] ^= 1  # IHDR CRC, independent of expected hash.
        self.reject_png(bytes(corrupt))
        corrupt = bytearray(png)
        struct.pack_into(">I", corrupt, 8, 0xffffffff)
        self.reject_png(bytes(corrupt))

    def test_png_header_exact_dimensions_depth_color_and_methods(self):
        png = self.packages["participation"][1]
        header = list(struct.unpack(">IIBBBBB", next(chunks(png))[1]))
        for index, value in ((0, 1199), (0, 1201), (0, 0xffffffff), (1, 801), (2, 16),
                             (3, 0), (3, 3), (3, 4), (4, 1), (5, 1), (6, 1)):
            altered = header[:]
            altered[index] = value
            changed = change_chunks(png, lambda pairs: [(b"IHDR", struct.pack(">IIBBBBB", *altered))] + pairs[1:])
            with self.subTest(index=index, value=value):
                self.reject_png(changed)
        self.reject_png(change_chunks(png, lambda pairs: [(b"IHDR", b"short")] + pairs[1:]))

    def test_png_chunk_order_unknown_duplicate_crc_and_end(self):
        png = self.packages["participation"][1]
        transforms = [
            lambda p: [p[1], p[0]] + p[2:],
            lambda p: p[:1] + p,
            lambda p: [(k, d) for k, d in p if k != b"IDAT"],
            lambda p: p[:-1] + [(b"IEND", b"nonempty")],
            lambda p: p[:-1] + [(b"acTL", b"animation"), p[-1]],
            lambda p: p[:-1] + [(b"zzZZ", b"unknown"), p[-1]],
            lambda p: p[:-1] + [(b"IDAT", b""), p[-1]],
            lambda p: p[:-1] + [(b"tEXt", b"Software\0analysis-png-2"), p[-1]],
            lambda p: p[:1] + [(b"pHYs", b"short")] + p[1:],
            lambda p: p[:1] + [(b"pHYs", b"\0" * 8 + b"\2")] + p[1:],
            lambda p: p[:1] + [(b"IDAT", b"x")] * 1024 + p[1:],
        ]
        for index, transform in enumerate(transforms):
            with self.subTest(index=index):
                self.reject_png(change_chunks(png, transform))
        for target in (b"tEXt", b"IDAT", b"IEND"):
            offset = 8
            corrupt = bytearray(png)
            for kind, data in chunks(png):
                if kind == target:
                    corrupt[offset + 8 + len(data)] ^= 1
                    break
                offset += 12 + len(data)
            self.reject_png(bytes(corrupt))

    def test_png_idat_stream_is_complete_even_when_pillow_is_permissive(self):
        png = self.packages["participation"][1]
        compressed = b"".join(d for k, d in chunks(png) if k == b"IDAT")
        decoded = zlib.decompress(compressed)
        variants = [compressed[:-4], compressed + b"extra", compressed + zlib.compress(b"extra"),
                    compressed[:len(compressed)//2], zlib.compress(decoded[:-1]),
                    zlib.compress(decoded + b"x"), zlib.compress(b"\5" + decoded[1:])]
        for index, value in enumerate(variants):
            changed = change_chunks(png, lambda p: [(k, d) for k, d in p if k != b"IDAT"][:-1]
                                    + [(b"IDAT", value), (b"IEND", b"")])
            with self.subTest(index=index), patch.object(ImageFile, "LOAD_TRUNCATED_IMAGES", True):
                self.reject_png(changed)

    def test_description_complete_spec_and_closed_envelope(self):
        png = self.packages["participation"][1]
        with Image.open(io.BytesIO(png)) as image:
            original = json.loads(image.info["Description"])
        for key in fixture():
            altered = copy.deepcopy(original)
            del altered["spec"][key]
            with self.subTest(key=key):
                self.reject_png(replace_metadata(png, "Description", canonical(altered).decode()))
        for value in (None, [], {}, {**original, "extra": 1}, {"spec": original["spec"]},
                      {"spec": {**original["spec"], "unit": "seconds"}, "runtime": original["runtime"]}):
            self.reject_png(replace_metadata(png, "Description", canonical(value).decode()))
        for text in ("not json", "{", "NaN", '["x"]', "[" * 11 + "0" + "]" * 11,
                     canonical(original).decode()[:-1] + ',"runtime":{}}',
                     canonical(original).decode().replace('"value":4', '"value":4,"value":4'),
                     canonical(original).decode().replace('"value":4', '"value":1e999')):
            self.reject_png(replace_metadata(png, "Description", text))

    def test_description_software_duplicates_and_missing_cross_chunk_types(self):
        png = self.packages["participation"][1]
        with Image.open(io.BytesIO(png)) as image:
            description = image.info["Description"]
        for key, text in (("Software", RENDERER_VERSION), ("Description", description)):
            for kind in (b"tEXt", b"zTXt", b"iTXt"):
                extra = metadata_chunk(key, text, kind)
                with self.subTest(key=key, kind=kind):
                    self.reject_png(change_chunks(png, lambda p: p[:1] + [extra] + p[1:]))
            self.reject_png(change_chunks(png, lambda p: [(k, d) for k, d in p
                if not (k in (b"tEXt", b"zTXt", b"iTXt") and d.partition(b"\0")[0] == key.encode())]))
        for value in ("analysis-png-1", "analysis-png-3", "Matplotlib", "", "analysis-png-2\0"):
            self.reject_png(replace_metadata(png, "Software", value))
        self.reject_png(change_chunks(png, lambda p: p[:1] + [(b"tEXt", b"Comment\0extra")] + p[1:]))

    def test_runtime_closed_and_safe_but_historical_versions_are_accepted(self):
        png = self.packages["participation"][1]
        with Image.open(io.BytesIO(png)) as image:
            description = json.loads(image.info["Description"])
        for value in (None, [], {}, {**description["runtime"], "extra": "bad"},
                      {"matplotlib": "1.0", "pillow": "2.0"},
                      {"matplotlib": "", "pillow": "2.0", "font_family": "DejaVu Sans"},
                      {"matplotlib": "1.0", "pillow": "NaN", "font_family": "../font"},
                      {"matplotlib": 1, "pillow": "2.0", "font_family": "DejaVu Sans"}):
            changed = {**description, "runtime": value}
            self.reject_png(replace_metadata(png, "Description", canonical(changed).decode()))
        historical = {"matplotlib": "3.8.0", "pillow": "10.0.0", "font_family": "Meiryo"}
        changed = replace_metadata(png, "Description", canonical({**description, "runtime": historical}).decode())
        with patch("gurumoji.services.analysis_visual_package.render_visual_png", side_effect=AssertionError("rerender")):
            receipt = self.verify(png_bytes=changed, png_hash=hashlib.sha256(changed).hexdigest())
        self.assertEqual(receipt["runtime"], historical)

    def test_compressed_metadata_bounded_and_malformed_streams_rejected(self):
        png = self.packages["participation"][1]
        with Image.open(io.BytesIO(png)) as image:
            description = image.info["Description"]
        for kind, compressed in ((b"zTXt", False), (b"iTXt", True)):
            changed = replace_metadata(png, "Description", description, kind=kind, compressed=compressed)
            self.verify(png_bytes=changed, png_hash=hashlib.sha256(changed).hexdigest())
            bomb = replace_metadata(png, "Description", "x" * (MAX_DESCRIPTION_BYTES + 1),
                                    kind=kind, compressed=compressed)
            with patch.object(Image, "open", side_effect=AssertionError("Pillow before bounded preflight")):
                self.reject_png(bomb)
            huge_software = replace_metadata(png, "Software", "x" * 65, kind=kind, compressed=compressed)
            self.reject_png(huge_software)
        invalid = [b"Description\0\1" + zlib.compress(b"{}"),
                   b"Description\0\0" + zlib.compress(b"{}")[:-1],
                   b"Description\0\0" + zlib.compress(b"{}") + b"extra"]
        def reject_replacement(kind, data):
            self.reject_png(change_chunks(png, lambda pairs: [(kind, data)
                if k in (b"tEXt", b"zTXt", b"iTXt") and d.partition(b"\0")[0] == b"Description"
                else (k, d) for k, d in pairs]))

        for data in invalid:
            reject_replacement(b"zTXt", data)
        for data in (b"Description\0\2\0\0\0{}", b"Description\0\0\1\0\0{}",
                     b"Description\0\0\0en\0\0{}", b"Description\0\0\0\0translated\0{}",
                     b"Description\0\0\0\0\0\xff", b"Description\0x"):
            reject_replacement(b"iTXt", data)
        self.reject_png(replace_metadata(png, "Description", "x" * (MAX_DESCRIPTION_BYTES + 1)))

    def test_contiguous_multiple_idat_chunks_are_valid(self):
        png = self.packages["participation"][1]
        compressed = b"".join(data for kind, data in chunks(png) if kind == b"IDAT")
        for split in (1, 2, 37):
            pieces = [(b"IDAT", compressed[:split]), (b"IDAT", compressed[split:])]
            changed = change_chunks(png, lambda pairs: [(k, d) for k, d in pairs
                if k not in (b"IDAT", b"IEND")] + pieces + [(b"IEND", b"")])
            with self.subTest(split=split):
                self.verify(png_bytes=changed, png_hash=hashlib.sha256(changed).hexdigest())

    def test_rgb_and_latin1_metadata_normal_cases(self):
        from PIL.PngImagePlugin import PngInfo
        raw, png, _ = self.packages["participation"]
        with Image.open(io.BytesIO(png)) as image:
            info = PngInfo()
            for key in ("Software", "Description"):
                info.add_text(key, image.info[key])
            output = io.BytesIO()
            image.convert("RGB").save(output, format="PNG", pnginfo=info)
        rgb = output.getvalue()
        self.verify(png_bytes=rgb, png_hash=hashlib.sha256(rgb).hexdigest())
        # Latin-1 Description is tEXt; decoding every text chunk as UTF-8 is wrong.
        spec = fixture()
        spec["alt_text"] = "Synthetic café with unknown and zero values"
        raw, latin_png, receipt = render_visual_package(spec, **expected(spec))
        self.assertTrue(any(k == b"tEXt" and d.startswith(b"Description\0") for k, d in chunks(latin_png)))
        self.assertEqual(verify_visual_package(raw, latin_png, approved_spec=spec,
            **expected(spec), expected_png_hash=receipt["png_hash"]), receipt)

    def test_pillow_verify_and_load_are_both_required(self):
        from PIL.PngImagePlugin import PngImageFile
        for method in ("verify", "load"):
            with self.subTest(method=method), patch.object(PngImageFile, method, side_effect=OSError("bad pixels")):
                with self.assertRaises(VisualPackageError):
                    self.verify()

if __name__ == "__main__":
    unittest.main()
