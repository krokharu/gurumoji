import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from gurumoji import research_analysis as research
from gurumoji.services.derived_analysis_store import DerivedAnalysisStore, DerivedAnalysisError


class DerivedStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "analysis-derived.sqlite3"
        self.data = json.loads((Path(__file__).parent / "fixtures/analysis_three_conversations.json").read_text(encoding="utf-8"))
        for name in ("_load_ginza", "_load_sudachi"):
            p = patch.object(research, name, return_value=(None, "synthetic test"))
            p.start()
            self.addCleanup(p.stop)

    def count(self):
        with closing(sqlite3.connect(self.database)) as connection:
            return connection.execute("SELECT COUNT(*) FROM segment_parses").fetchone()[0]

    def test_three_conversation_parity_restart_and_only_edited_segment_reparsed(self):
        analyses = [c["analysis"] for c in self.data["conversations"]]
        expected = [research.build_research_linguistics(a) for a in analyses]
        with research.derived_storage(self.database):
            self.assertEqual([research.build_research_linguistics(a) for a in analyses], expected)
            initial_count = self.count()
            research._RESEARCH_CACHE.clear()
            with patch.object(research, "_analyze_with_fallback", wraps=research._analyze_with_fallback) as parser:
                self.assertEqual([research.build_research_linguistics(a) for a in analyses], expected)
                parser.assert_not_called()
                edited = copy.deepcopy(analyses[0])
                edited["segments"][1]["text"] += " 新しい文。"
                changed = research.build_research_linguistics(edited)
                self.assertEqual(parser.call_count, 1)
                self.assertEqual(parser.call_args.args[0][0]["text"], edited["segments"][1]["text"])
            self.assertEqual(self.count(), initial_count + 1)
            # The old version remains exactly readable after appending a new one.
            self.assertEqual(research.build_research_linguistics(analyses[0]), expected[0])
        self.assertNotEqual(changed["morphemes"], expected[0]["morphemes"])

    def test_shared_text_rebinds_identity_role_and_exclusion_without_reparse(self):
        analysis = self.data["conversations"][0]["analysis"]
        with research.derived_storage(self.database):
            research.build_research_linguistics(analysis)
            edited = copy.deepcopy(analysis)
            edited["segments"][0].update(id="different", speaker="X", speaker_name="別の話者", excluded=True, role="moderator")
            with patch.object(research, "_analyze_with_fallback", side_effect=AssertionError("reparsed")):
                result = research.build_research_linguistics(edited)
            row = result["morphemes"][0]
            self.assertEqual((row["segment_id"], row["speaker"], row["speaker_name"], row["excluded"], row["role"]),
                             ("different", "X", "別の話者", True, "moderator"))

    def test_version_and_settings_append_and_loss_rebuilds_same_hash(self):
        analysis = self.data["conversations"][0]["analysis"]
        with research.derived_storage(self.database):
            original = research.build_research_linguistics(analysis)
            count = self.count()
            with patch.object(research, "RESEARCH_ALGORITHM_VERSION", "synthetic-new-version"):
                research.build_research_linguistics(analysis)
            self.assertEqual(self.count(), count * 2)
            changed = copy.deepcopy(analysis)
            changed["config"]["stop_words"] = ["朝"]
            research.build_research_linguistics(changed)
            self.assertEqual(self.count(), count * 3)
            self.database.unlink()
            rebuilt = research.build_research_linguistics(analysis)
            self.assertEqual(rebuilt, original)
            self.assertEqual(self.count(), count)

    def test_append_only_conflict_and_tampering_are_rejected(self):
        store = DerivedAnalysisStore(self.database)
        result = ([{"surface": "synthetic"}], [], 1)
        store.save("synthetic", {"version": "1"}, {}, result)
        store.save("synthetic", {"version": "1"}, {}, result)
        with self.assertRaises(DerivedAnalysisError):
            store.save("synthetic", {"version": "1"}, {}, ([{"surface": "changed"}], [], 1))
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE morphemes SET row_json='{}'")
        with self.assertRaises(DerivedAnalysisError):
            store.read("synthetic", {"version": "1"}, {})
        with self.assertRaises(DerivedAnalysisError):
            store.save("synthetic", {"version": "1"}, {}, result)

    def test_cached_input_identity_cannot_be_reassigned_to_another_text(self):
        store = DerivedAnalysisStore(self.database)
        analyzer = {"version": "1"}
        store.save("original", analyzer, {}, ([{"surface": "original"}], [], 1))
        key = store.key("changed", analyzer, {})
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE segment_parses SET parse_key=?", (key,))
        with self.assertRaises(DerivedAnalysisError):
            store.read("changed", analyzer, {})

    def test_corrupt_cache_does_not_silently_change_parser(self):
        self.database.write_bytes(b"not SQLite")
        with research.derived_storage(self.database), self.assertRaises(DerivedAnalysisError):
            research.build_research_linguistics(self.data["conversations"][0]["analysis"])

    def test_ginza_dependencies_and_model_revision_are_cached_independently(self):
        analysis = self.data["conversations"][0]["analysis"]
        def parse(segments, _model, stop_words):
            rows, sentences = research._analyze_with_fallback(segments, stop_words)
            dependencies = [{**research._row_common(s), "sentence_id": 1, "token_id": 1,
                             "surface": s["text"][:1], "lemma": s["text"][:1], "upos": "NOUN",
                             "dependency": "ROOT", "head_token_id": 0, "head_surface": "", "named_entity": ""}
                            for s in segments]
            return rows, dependencies, sentences
        model = SimpleNamespace(meta={"name": "synthetic-ginza", "version": "1"})
        with patch.object(research, "_load_ginza", return_value=(model, "")), \
                patch.object(research, "_analyze_with_ginza", side_effect=parse) as parser:
            expected = research.build_research_linguistics(analysis)
            parser.reset_mock()
            with research.derived_storage(self.database):
                self.assertEqual(research.build_research_linguistics(analysis), expected)
                self.assertEqual(parser.call_count, 2)
                parser.reset_mock()
                self.assertEqual(research.build_research_linguistics(analysis), expected)
                parser.assert_not_called()
                model.meta["version"] = "2"
                research.build_research_linguistics(analysis)
                self.assertEqual(parser.call_count, 2)
                self.assertEqual(self.count(), 4)
