"""Pure synthetic v1 ZIP tests, with no application/runtime dependencies."""
import copy
import hashlib
import io
import json
import stat
import struct
import unittest
import warnings
import zipfile
from unittest.mock import patch

from gurumoji.services import ai_data_export_bundle as bundle


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def sample_payload():
    source_hash = "a" * 64
    segments = [{"id": "u0", "speaker": "S1", "text": "原文 🌸\n  text", "start": 0, "end": 1},
                {"id": "u1", "speaker": "UNKNOWN", "text": "時刻不明", "time_unknown": True},
                {"id": "u2", "text": "ラベルなし"}]
    rows = []
    for index, segment in enumerate(segments):
        label = segment.get("speaker")
        rows.append({"interview_id": "synthetic", "group_id": None, "input_version": 1, "source_hash": source_hash,
            "segment_id": segment["id"], "order": index + 1, "order_verified": False,
            "speaker_id": label if label != "UNKNOWN" else None, "speaker_verified": False, "role": "unknown",
            "start": segment.get("start"), "end": segment.get("end"), "source_locator": "", "source_segment_ids": [segment["id"]],
            "original_text": segment["text"], "original_status": "initial_import", "text": segment["text"],
            "text_status": "unreviewed", "boundary_verified": False, "previous_segment_id": f"u{index - 1}" if index else None,
            "next_segment_id": f"u{index + 1}" if index < 2 else None, "content_ready": False, "interaction_ready": False,
            "analysis_needs_review": False, "raw_speaker_label": label,
            "speaker_no": {"S1": 1, "UNKNOWN": 2}.get(label)})
    p = {"schema_version": 1, "revision": 0, "source_hash": source_hash, "input_version": 1, "status": "draft",
         "analysis_source_hash": None, "rows": rows,
         "versions": [{"version": 1, "source_hash": source_hash, "origin": "synthetic", "created_at": "2026-01-01T00:00:00Z",
                       "source": {"segments": copy.deepcopy(segments), "speaker_profiles": {"S1": {"speaker_label": "S1"}},
                                  "session_profile": {"note": "名前は自由本文に残る"}}}],
         "review_history": [], "original_segments": copy.deepcopy(segments), "original_status": "initial_import",
         "manifest": {"schema_version": 1, "columns": list(bundle.ROW_FIELDS), "row_count": len(rows),
                      "rows_sha256": digest([{k: r[k] for k in bundle.ROW_FIELDS} for r in rows])}}
    return {"schema_version": 1, "item": {"id": "synthetic", "language": "ja"}, "preparation": p,
            "speakers": [{"speaker_no": 1, "raw_label": "S1", "display_name": None, "attributes": {}},
                         {"speaker_no": 2, "raw_label": "UNKNOWN", "display_name": None, "attributes": {}}],
            "outline": None, "outline_provenance": {"kind": "absent", "source_hash": source_hash, "input_version": 1, "analysis_source_hash": None},
            "selection": {"include_names": False, "speaker_attributes": []},
            "frames": {"status": "disabled", "reason": "not_requested", "media": None, "items": []}}


def with_frames(value, times=(0, 1)):
    value["frames"] = {"status": "complete", "reason": None,
        "media": {"kind": "video", "identity_hash_domain": "stat_identity",
                  "identity": {"device": 1, "inode": 2, "size": 10, "mtime_ns": 3, "ctime_ns": 4}},
        "items": [{"frame_id": f"f{i:04d}", "requested_time": t, "actual_time": t, "method": "synthetic_decoder_pts",
                   "utterance_ids": ["u0"] if 0 <= t <= 1 else [], "data": b"\xff\xd8synthetic-envelope\xff\xd9"}
                  for i, t in enumerate(times, 1)]}
    return value


def zip_files(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {name: z.read(name) for name in z.namelist()}


def pack(files, compression=zipfile.ZIP_STORED, attributes=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as z:
        for name, data in files.items():
            if attributes and name in attributes:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = attributes[name]
                z.writestr(info, data)
            else:
                z.writestr(name, data)
    return output.getvalue()


def rehash(files):
    manifest = json.loads(files["manifest.json"])
    manifest["files"] = [{"path": p, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                         for p, data in sorted(files.items()) if p != "manifest.json"]
    files["manifest.json"] = json.dumps(manifest).encode()
    return files


class AIDataExportBundleTests(unittest.TestCase):
    def setUp(self):
        self.payload = sample_payload()

    def refresh_rows_hash(self):
        p = self.payload["preparation"]
        p["manifest"]["rows_sha256"] = digest([{k: r[k] for k in bundle.ROW_FIELDS} for r in p["rows"]])

    def assert_invalid(self, value):
        for fn in (bundle.validate_ai_bundle, bundle.build_ai_bundle):
            with self.subTest(function=fn.__name__), self.assertRaises(ValueError):
                fn(value)

    def test_unicode_null_zero_deterministic_and_no_mutation(self):
        before = copy.deepcopy(self.payload)
        bundle.validate_ai_bundle(self.payload)
        one = bundle.build_ai_bundle(self.payload)
        self.assertEqual(one, bundle.build_ai_bundle(self.payload))
        self.assertEqual(before, self.payload)
        manifest = bundle.validate_ai_bundle_zip(one)
        self.assertEqual(manifest["frames"]["count"], 0)
        self.assertEqual(manifest["hash_domains"], bundle.HASH_DOMAINS)
        with zipfile.ZipFile(io.BytesIO(one)) as z:
            self.assertEqual(z.namelist(), sorted(bundle.BASE_FILES))
            self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in z.infolist()))
            rows = [json.loads(line) for line in z.read("utterances.jsonl").splitlines()]
            self.assertEqual(rows[0]["start"], 0)
            self.assertIsNone(rows[1]["start"])
            self.assertIsNone(rows[2]["raw_speaker_label"])
            self.assertIsNone(rows[2]["speaker_no"])
            self.assertIn("原文 🌸", z.read("conversation.json").decode())
            self.assertNotIn(b"\\u539f", z.read("conversation.json"))

    def test_migrated_saved_outline_lineage_and_hash_domains(self):
        p = self.payload["preparation"]
        p["original_status"] = "migrated_current_snapshot"
        p["rows"][0].update(original_status="migrated_current_snapshot", text="編集", source_segment_ids=["u0", "u1"])
        self.refresh_rows_hash()
        self.payload["outline"] = {"raw": ["保存された概要", None, 0], "note": "unverified"}
        self.payload["outline_provenance"]["kind"] = "saved"
        files = zip_files(bundle.build_ai_bundle(self.payload))
        self.assertEqual(json.loads(files["outline.json"])["outline"], self.payload["outline"])
        self.assertEqual(json.loads(files["conversation.json"])["preparation"], p)
        self.assertIn(b"original_preparation_rows", files["README.md"])
        self.assertIn(b"NOT anonymization", files["README.md"])
        self.assertIn(b"unverified", files["schema.json"])

    def test_selected_names_and_one_raw_attribute(self):
        self.payload["selection"] = {"include_names": True, "speaker_attributes": ["organization"]}
        self.payload["speakers"][0].update(display_name="名前", attributes={"organization": ""})
        source = self.payload["preparation"]["versions"][0]["source"]
        source["speaker_names"] = {"S1": "名前"}
        source["speaker_profiles"]["S1"].update(display_name="名前", organization="")
        bundle.validate_ai_bundle_zip(bundle.build_ai_bundle(self.payload))

    def test_reject_typed_name_and_profile_metadata_leaks(self):
        for kind in ("speaker_names", "display_name", "global_speaker_id", "consent", "notes", "department", "arbitrary_source"):
            value = copy.deepcopy(self.payload)
            source = value["preparation"]["versions"][0]["source"]
            if kind == "speaker_names":
                source[kind] = {"S1": "secret"}
            elif kind == "arbitrary_source":
                source[kind] = "secret"
            else:
                source["speaker_profiles"]["S1"][kind] = "secret"
            with self.subTest(kind=kind):
                self.assert_invalid(value)
        self.payload["speakers"][0]["display_name"] = "secret"
        self.assert_invalid(self.payload)

    def test_reject_extra_segment_metadata(self):
        for source in (self.payload["preparation"]["original_segments"], self.payload["preparation"]["versions"][0]["source"]["segments"]):
            source[0]["path"] = "/private/media"
            self.assert_invalid(self.payload)
            del source[0]["path"]

    def test_reject_invalid_keys_types_and_nonfinite(self):
        cases = [None, [], {**self.payload, "extra": 1}, {**self.payload, "schema_version": True}]
        for v in (float("nan"), float("inf"), float("-inf"), object(), b"bytes", (1, 2)):
            cases.append({**self.payload, "outline": v})
        for value in cases:
            with self.subTest(value=type(value)):
                self.assert_invalid(value)

    def test_reject_unknown_speaker_lineage_and_mismatched_rows_hash(self):
        for key, value in (("speaker_no", 999), ("speaker_no", True), ("source_segment_ids", ["missing"]),
                           ("previous_segment_id", "u2"), ("text", "tampered"), ("start", False)):
            candidate = copy.deepcopy(self.payload)
            candidate["preparation"]["rows"][0][key] = value
            with self.subTest(key=key):
                self.assert_invalid(candidate)

    def test_reject_unsorted_or_duplicate_speaker_numbers(self):
        self.payload["speakers"].reverse()
        self.assert_invalid(self.payload)
        self.payload["speakers"].reverse()
        self.payload["speakers"][1]["speaker_no"] = 1
        self.assert_invalid(self.payload)

    def test_empty_unavailable_legacy_export(self):
        self.payload["speakers"] = []
        p = self.payload["preparation"]
        p.update(rows=[], versions=[], original_segments=[], input_version=None, original_status="unavailable")
        p["manifest"].update(row_count=0, rows_sha256=digest([]))
        self.payload["outline_provenance"]["input_version"] = None
        manifest = bundle.validate_ai_bundle_zip(bundle.build_ai_bundle(self.payload))
        self.assertIsNone(manifest["input_version"])

    def test_frames_hash_index_null_actual_and_no_invented_time(self):
        with_frames(self.payload)
        self.payload["frames"]["items"][1].update(actual_time=None, utterance_ids=[])
        files = zip_files(bundle.build_ai_bundle(self.payload))
        frames = [json.loads(line) for line in files["frames/index.jsonl"].splitlines()]
        self.assertIsNone(frames[1]["actual_time"])
        self.assertNotIn("data", frames[0])
        self.assertEqual(frames[0]["sha256"], hashlib.sha256(files[frames[0]["path"]]).hexdigest())
        self.assertEqual(bundle.validate_ai_bundle_zip(pack(files))["frames"]["count"], 2)

    def test_decimal_timestamps_and_maximum_frame_count(self):
        with_frames(self.payload, [0.1 + k for k in range(24)])
        self.assertEqual(bundle.validate_ai_bundle_zip(bundle.build_ai_bundle(self.payload))["frames"]["count"], 24)
        self.payload["frames"]["items"].append(copy.deepcopy(self.payload["frames"]["items"][-1]))
        self.assert_invalid(self.payload)

    def test_reject_frame_bytes_ids_temporal_refs_and_partial_states(self):
        with_frames(self.payload)
        for key, value in (("data", b"bad"), ("frame_id", "../../bad"), ("requested_time", True),
                           ("actual_time", float("inf")), ("utterance_ids", ["u1"]), ("path", "elsewhere")):
            candidate = copy.deepcopy(self.payload)
            candidate["frames"]["items"][0][key] = value
            with self.subTest(key=key):
                self.assert_invalid(candidate)
        self.payload["frames"]["items"][0]["actual_time"] = None
        self.assert_invalid(self.payload)
        self.payload["frames"]["status"] = "partial"
        self.assert_invalid(self.payload)

    def test_reject_media_path_metadata(self):
        with_frames(self.payload)
        self.payload["frames"]["media"]["identity"]["path"] = "/private"
        self.assert_invalid(self.payload)

    def test_row_frame_and_serialized_size_bounds(self):
        with patch.object(bundle, "MAX_ROWS", 2):
            self.assert_invalid(self.payload)
        with_frames(self.payload)
        with patch.object(bundle, "MAX_FRAME_BYTES", 4):
            self.assert_invalid(self.payload)
        with patch.object(bundle, "MAX_FRAME_TOTAL", 4):
            self.assert_invalid(self.payload)
        with patch.object(bundle, "MAX_TEXT_BYTES", 1024):
            self.assert_invalid(self.payload)
        with patch.object(bundle, "MAX_TOTAL_BYTES", 1024):
            self.assert_invalid(self.payload)

    def test_reject_bad_zip_missing_extra_traversal_absolute_backslash_and_nul(self):
        data = bundle.build_ai_bundle(self.payload)
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(b"not a zip")
        for name in ("../escape", "/absolute", "frames\\f0001.jpg", "other.json", "frames/f0025.jpg", "frames/"):
            files = zip_files(data)
            files[name] = b"extra"
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(pack(files))
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(data.replace(b"README.md", b"README\x00md"))
        files = zip_files(data)
        del files["outline.json"]
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(pack(files))

    def test_reject_duplicate_and_symlink_members(self):
        data = bundle.build_ai_bundle(self.payload)
        output = io.BytesIO(data)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(output, "a") as z:
                z.writestr("README.md", b"duplicate")
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(output.getvalue())
        files = zip_files(data)
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(pack(files, attributes={"README.md": (stat.S_IFLNK | 0o777) << 16}))

    def test_reject_crc_hash_and_size_mismatches(self):
        files = zip_files(bundle.build_ai_bundle(self.payload))
        files["README.md"] += b"tampered"
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(pack(files))
        files = zip_files(bundle.build_ai_bundle(self.payload))
        manifest = json.loads(files["manifest.json"])
        manifest["files"][0]["size"] += 1
        files["manifest.json"] = json.dumps(manifest).encode()
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(pack(files))
        data = bytearray(bundle.build_ai_bundle(self.payload))
        data[data.index(b"# Gurumoji")] ^= 1
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(bytes(data))

    def test_reject_rehashed_schema_rows_refs_and_snapshot_mismatches(self):
        original = zip_files(bundle.build_ai_bundle(with_frames(self.payload)))
        for target in ("schema.json", "utterances.jsonl", "frames/index.jsonl", "manifest.json"):
            files = original.copy()
            if target == "schema.json":
                value = json.loads(files[target]); value["schema_version"] = 2
                files[target] = json.dumps(value).encode()
            elif target == "utterances.jsonl":
                lines = files[target].splitlines(); row = json.loads(lines[0]); row["text"] = "forged"
                files[target] = json.dumps(row).encode() + b"\n" + b"\n".join(lines[1:])
            elif target == "frames/index.jsonl":
                lines = files[target].splitlines(); frame = json.loads(lines[0]); frame["utterance_ids"] = ["u1"]
                files[target] = json.dumps(frame).encode() + b"\n" + b"\n".join(lines[1:])
            else:
                value = json.loads(files[target]); value["source_hash"] = "b" * 64
                files[target] = json.dumps(value).encode()
            with self.subTest(target=target), self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(pack(rehash(files)))

    def test_reject_duplicate_json_keys_and_nonfinite_rehashed_json(self):
        files = zip_files(bundle.build_ai_bundle(self.payload))
        for bad in (b'{"outline":null,"outline":0,"provenance":{}}', b'{"outline":NaN,"provenance":{}}'):
            files["outline.json"] = bad
            with self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(pack(rehash(files)))

    def test_zip_bomb_and_declared_oversize_rejected_before_member_read(self):
        files = zip_files(bundle.build_ai_bundle(self.payload))
        files["README.md"] = b"x" * (3 * 1024 * 1024)
        bomb = pack(files, compression=zipfile.ZIP_DEFLATED)
        with patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("must not decompress")):
            with self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(bomb)
        data = bytearray(bundle.build_ai_bundle(self.payload))
        index = data.index(b"PK\x01\x02")
        struct.pack_into("<I", data, index + 24, bundle.MAX_TEXT_BYTES + 1)
        with patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("must not decompress")):
            with self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(bytes(data))

    def test_zip_directory_count_bounded_before_zipfile_allocation(self):
        data = bytearray(bundle.build_ai_bundle(self.payload))
        end = data.rindex(b"PK\x05\x06")
        struct.pack_into("<HH", data, end + 8, 65535, 65535)
        with patch.object(zipfile, "ZipFile", side_effect=AssertionError("must not parse huge directory")):
            with self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(bytes(data))

    def test_corrupted_compression_and_excess_json_lines_are_value_errors(self):
        files = zip_files(bundle.build_ai_bundle(self.payload))
        data = bytearray(pack(files, compression=zipfile.ZIP_DEFLATED))
        # Damage the first deflate stream without changing its directory bounds.
        name_length, extra_length = struct.unpack_from("<HH", data, 26)
        start = 30 + name_length + extra_length
        data[start:start + 3] = b"\xff\xff\xff"
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(bytes(data))
        files["utterances.jsonl"] = b"\n" * 100002
        with self.assertRaises(ValueError):
            bundle.validate_ai_bundle_zip(pack(rehash(files)))

    def test_valid_deflated_zip_and_no_filesystem_or_network_dependencies(self):
        data = pack(zip_files(bundle.build_ai_bundle(self.payload)), compression=zipfile.ZIP_DEFLATED)
        self.assertEqual(bundle.validate_ai_bundle_zip(data)["item_id"], "synthetic")
        self.assertNotIn("PIL", bundle.__dict__)
        self.assertNotIn("Path", bundle.__dict__)


if __name__ == "__main__":
    unittest.main()
