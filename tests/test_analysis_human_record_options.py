"""Synthetic GET -> explicit POST -> fresh verified read, without app startup."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

from flask import Flask

from gurumoji.analysis_store import AnalysisStore, canonical, digest, safe_path
from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_human_records as human
import test_analysis_typed_assets as typed
import test_table_pilot_routes as pilot


class HumanRecordOptionsTests(unittest.TestCase):
    def setUp(self):
        self.h = human.HumanRecordTests(); self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.factory_helper = pilot.TablePilotFactoryTests()
        self.namespace, self.traces, self.connections = self.factory_helper.reader_namespace(
            self.h.fixture.path, source_hash=self.h.fixture.snapshot["input_hash"])
        self.writer = Mock(return_value=self.h.service)
        self.app = Flask(__name__)
        register_orchestration_routes(self.app, self.writer, lambda _: self.fail("No model preparation"),
                                      table_reader=self.namespace["analysis_table_pilot_reader"])
        self.client = self.app.test_client()
        self.url = self.h.url

    def options(self, **query):
        response = self.client.get(self.url, query_string=query)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return response.get_json()

    def candidate(self):
        return next(o for o in self.options()["options"] if o["target_kind"] == "candidate")

    def statement(self, option, step, *, decision="adopt"):
        # All researcher text/identity here is explicit TEST input. Only exact
        # references/revisions come from GET; never derive them from AI prose.
        old = step["latest_record"]
        record_id = old["record"]["record_id"] if old else "TEST-explicit-" + step["step_id"]
        revision = step["next_revision"]
        text = "TEST ONLY researcher typed statement 研究\r\n" + str(revision)
        record = {"record_id": record_id, "revision": revision,
            "supersedes_record_ref": step["next_supersedes_record_ref"],
            "actor": {"kind": "researcher", "actor_id": "TEST-explicit-researcher"}, "decision": decision,
            "target": copy.deepcopy(option["target"]), "allowed_step_ids": [step["step_id"]],
            "scope": copy.deepcopy(option["scope"]), "recorded_at": "2026-10-09T00:00:00Z",
            "reason": "TEST explicit researcher reason",
            "record_ref": {"target_type": "researcher_memo", "target_id": "human-source:" + record_id,
                "version": str(revision), "content_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "hash_domain": "raw-bytes-v1", "library_id": option["library_id"]}}
        return {"asset_key": option["asset_key"], "record": record, "source_text": text,
                "expected_state_revision": option["expected_state_revision"]}

    def post(self, statement):
        response = self.client.post(self.url, data=canonical(statement), content_type="application/json")
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_get_forms_exact_four_step_posts_and_reads_append_only_revisions(self):
        sealed = self.h.fresh().verified_package(self.h.saved_id)[3]
        initial = self.options()
        self.assertEqual(set(initial), {"schema_id", "schema_version", "item_id", "run_id", "generation",
            "enabled", "reason_code", "offset", "limit", "next_offset", "options"})
        self.assertEqual(initial["schema_id"], "gurumoji.human-record-options")
        self.assertEqual([o["target_kind"] for o in initial["options"]], ["candidate", "theme"])
        self.assertTrue(initial["enabled"]); self.assertIsNone(initial["reason_code"])
        option = initial["options"][0]
        self.assertEqual(option["expected_state_revision"], 0)
        self.assertEqual(set(option), {"asset_key", "library_id", "scope", "target_kind", "target", "label",
            "expected_state_revision", "enabled", "reason_code", "human_steps"})
        self.assertEqual([s["step_id"] for s in option["human_steps"]], ["ta-p1", "ta-p4", "ta-p5", "ta-p6"])
        profile = self.h.service.result("TEST-conversation", self.h.run_id)["expert_knowledge_snapshot"]["profiles"][typed.EXPERT]
        self.assertEqual([s["label"] for s in option["human_steps"]], [s["title"] for s in profile["human_steps"]])
        for index in range(4):
            option = self.candidate(); step = option["human_steps"][index]
            self.assertIsNone(step["latest_record"]); self.assertIsNone(step["next_supersedes_record_ref"])
            statement = self.statement(option, step); accepted = self.post(statement)
            read = self.candidate()
            self.assertEqual(read["expected_state_revision"], index + 1)
            latest = read["human_steps"][index]
            self.assertEqual(latest["latest_record"], {"record": statement["record"], "record_ref": accepted["record_ref"]})
            self.assertEqual(latest["next_revision"], 2)
            self.assertEqual(latest["next_supersedes_record_ref"]["content_hash"], accepted["record_ref"]["content_hash"])
        self.assertEqual(self.h.bind()["decision"], "eligible")
        records_before = {p["run_id"]: self.h.fresh().verified_package(p["run_id"])[3] for p in self.h.fresh()._human_packages()[0]}
        for decision, revision in (("defer", 2), ("reject", 3), ("adopt", 4)):
            option = self.candidate(); accepted = self.post(self.statement(option, option["human_steps"][0], decision=decision))
            self.assertEqual(accepted["record"]["revision"], revision)
            read = self.candidate(); self.assertTrue(read["enabled"])
            self.assertEqual(read["human_steps"][0]["next_revision"], revision + 1)
            self.assertEqual(read["human_steps"][0]["latest_record"]["record"]["decision"], decision)
            self.assertEqual(self.h.bind()["decision"], "eligible" if decision == "adopt" else "blocked")
        self.assertEqual(self.h.fresh().verified_package(self.h.saved_id)[3], sealed)
        for run_id, files in records_before.items(): self.assertEqual(self.h.fresh().verified_package(run_id)[3], files)
        self.assertNotIn("source_text", json.dumps(self.options(), ensure_ascii=False))

    def test_theme_exact_target_and_same_id_retarget_remain_rejected(self):
        option = self.candidate(); self.post(self.statement(option, option["human_steps"][0]))
        read = self.options(); candidate, theme = read["options"]
        self.assertEqual(theme["target"], self.h.candidate["content"]["theme_refs"][0])
        self.assertTrue(all(s["latest_record"] is None for s in theme["human_steps"]))
        statement = self.statement(candidate, candidate["human_steps"][0]); statement["record"]["target"] = theme["target"]
        response = self.client.post(self.url, json=statement)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason_code"], "human_record_supersedes")
        self.assertEqual(len(self.h.fresh()._human_packages()[0]), 1)

    def test_actual_reader_factory_get_is_readonly_in_sql_database_and_files(self):
        root = self.h.fixture.path.parent
        before = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
        with self.h.fixture.connect() as db: dump = list(db.iterdump())
        for _ in range(2): self.assertTrue(self.options()["enabled"])
        self.writer.assert_not_called()
        self.assertEqual(before, {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()})
        with self.h.fixture.connect() as db: self.assertEqual(list(db.iterdump()), dump)
        self.assertTrue(all(args[0].endswith("?mode=ro") for args, _ in self.connections))
        self.assertFalse(any(s.lstrip().upper().startswith(("CREATE", "INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "BEGIN IMMEDIATE")) for s in self.traces))

    def test_invalid_and_repeated_offset_rejected_before_any_reader_access(self):
        reader = Mock(side_effect=AssertionError("invalid query cannot open a reader"))
        app = Flask("bad-query"); register_orchestration_routes(app, self.writer, lambda _: {}, table_reader=reader)
        client = app.test_client()
        for value in ("", "00", "01", "-1", "+1", "1.0", "1e3", "²", "١", "１", "10001", "9" * 10000):
            with self.subTest(value=value[:10]):
                r = client.get(self.url, query_string={"offset": value}); self.assertEqual(r.status_code, 400)
                self.assertEqual(r.get_json()["reason_code"], "human_record_options_offset")
        for query in ([('offset', '0'), ('offset', '0')], {"limit": "20"}, {"actor_id": "forged"}):
            r = client.get(self.url, query_string=query); self.assertEqual(r.status_code, 400)
            self.assertEqual(r.get_json()["reason_code"], "human_record_options_query")
        reader.assert_not_called(); self.writer.assert_not_called()

    def test_missing_cold_and_legacy_never_initialize_database_or_folders(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cold.sqlite"
            namespace, traces, _connections = self.factory_helper.reader_namespace(path)
            app = Flask("cold"); register_orchestration_routes(app, self.writer, lambda _: {},
                table_reader=namespace["analysis_table_pilot_reader"])
            client = app.test_client()
            self.assertEqual(client.get(self.url).status_code, 404)
            self.assertEqual(list(Path(temp).iterdir()), [])
            with closing(sqlite3.connect(path)): pass
            before = path.read_bytes(); self.assertEqual(client.get(self.url).status_code, 404); self.assertEqual(path.read_bytes(), before)
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY)"); db.execute("INSERT INTO library_items VALUES ('TEST-conversation')")
            before = path.read_bytes(); response = client.get(self.url)
            self.assertEqual(response.status_code, 200); self.assertFalse(response.get_json()["enabled"])
            self.assertEqual(response.get_json()["reason_code"], "human_record_ledger_unavailable")
            self.assertEqual(response.get_json()["options"], []); self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(temp).iterdir()), [path]); self.writer.assert_not_called()
            self.assertFalse(any(s.lstrip().upper().startswith(("CREATE", "INSERT", "UPDATE", "BEGIN IMMEDIATE")) for s in traces))

    def test_cancel_stale_generation_source_and_ownership_disable_without_writes(self):
        with self.h.fixture.connect() as db:
            original = db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (self.h.run_id,)).fetchone()[0]
        for change, reason in (({"cancel_requested": True}, "human_run_cancelled"),
                               ({"status": "cancelled"}, "human_run_cancelled"),
                               ({"stale": True}, "human_target_stale"),
                               ({"generation": json.loads(original)["generation"] + 1}, "human_record_generation_changed")):
            with self.h.fixture.connect() as db:
                run = json.loads(original); run.update(change)
                db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (canonical(run).decode(), self.h.run_id))
            read = self.options(); self.assertFalse(read["enabled"], (change, read["reason_code"])); self.assertEqual(read["reason_code"], reason)
        with self.h.fixture.connect() as db: db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (original, self.h.run_id))
        self.namespace["archive_source_stamp"] = lambda *args, **kwargs: "TEST-changed-source"
        self.assertEqual(self.options()["reason_code"], "revision_conflict")
        self.namespace["archive_source_stamp"] = lambda *args, **kwargs: self.h.fixture.snapshot["input_hash"]
        with self.h.fixture.connect() as db: db.execute("UPDATE library_items SET revision_count=2 WHERE id='TEST-conversation'")
        self.assertEqual(self.options()["reason_code"], "revision_conflict")
        self.assertEqual(self.client.get(self.url.replace("TEST-conversation", "TEST-foreign")).status_code, 404)
        self.assertEqual(self.client.get(self.url.replace(self.h.run_id, "TEST-missing")).status_code, 404)
        self.assertEqual(self.h.fresh()._human_packages()[0], []); self.writer.assert_not_called()

    def test_current_policy_and_revocation_keep_history_but_disable_submission(self):
        outcomes = self.h.adopt(); state = copy.deepcopy(outcomes[-1]["state"])
        state.update(send_policy="prohibited", state_revision=state["state_revision"] + 1, policy_revision=2)
        self.h.fixture.register(states=[state])
        read = self.options(); self.assertFalse(read["enabled"])
        self.assertTrue(all(o["reason_code"] == "human_record_policy_unavailable" for o in read["options"]))
        self.assertTrue(all(s["latest_record"] for s in read["options"][0]["human_steps"]))
        state.update(revoked=True, state_revision=state["state_revision"] + 1, policy_revision=3)
        self.h.fixture.register(states=[state]); self.assertEqual(self.options()["reason_code"], "human_record_state_unavailable")

    def test_parent_revocation_disables_form_at_fresh_read(self):
        self.h.adopt(); states = self.h.fresh()._connection_index()[2][digest(self.h.original["asset_key"])]
        state = copy.deepcopy(states[max(states)]); state.update(revoked=True, state_revision=state["state_revision"] + 1, policy_revision=2)
        self.h.fixture.register(states=[state])
        read = self.options(); self.assertFalse(read["enabled"]); self.assertEqual(read["reason_code"], "parent_state_unavailable")
        self.assertEqual(self.h.bind()["reason"], "parent_state_unavailable")

    def test_tampered_human_and_candidate_bytes_never_return_unverified_options(self):
        self.h.adopt(); package = self.h.fresh()._human_packages()[0][0]
        record = next(a for a in self.h.fresh().artifacts(package["run_id"]) if a["name"] == "human/record.json")
        path = safe_path(self.h.fixture.store.root, record["path"]); old = path.read_bytes(); path.write_bytes(old + b" ")
        read = self.options(); self.assertFalse(read["enabled"]); self.assertEqual(read["options"], [])
        path.write_bytes(old)
        candidate = next(a for a in self.h.fresh().artifacts(self.h.saved_id) if a["name"].startswith("assets/thematic_candidates"))
        path = safe_path(self.h.fixture.store.root, candidate["path"]); path.write_bytes(path.read_bytes() + b" ")
        read = self.options(); self.assertFalse(read["enabled"]); self.assertEqual(read["options"], [])

    def test_real_many_theme_page_is_bounded_and_exact_cursor_reaches_every_target(self):
        service = self.h.helper.service(); real = service.agent_runner
        def agent(role, context, *args):
            raw = real(role, context, *args)
            if role == "interpretation":
                candidate = raw["expert_report"]["thematic_candidates_v1"]
                template, target = copy.deepcopy(candidate["themes"][0]), copy.deepcopy(candidate["content"]["theme_refs"][0])
                candidate["content"]["candidate_set_id"] = "TEST-many-candidates"
                template["content"]["candidate_set_id"] = target["candidate_set_id"] = "TEST-many-candidates"
                candidate["themes"] = []; candidate["content"]["theme_refs"] = []
                for index in range(25):
                    theme = copy.deepcopy(template); theme["content"].update(theme_id="TEST-theme-" + str(index), claim_id="TEST-claim-" + str(index))
                    candidate["themes"].append(theme); candidate["content"]["theme_refs"].append(copy.deepcopy(target))
                typed.rehash(candidate); candidate["history"][0]["to_themes"] = copy.deepcopy(candidate["content"]["theme_refs"])
            return raw
        service.agent_runner = agent; run = self.h.helper.start(service); service.run(run["run_id"])
        publisher = AnalysisOrchestrationPublicationService(connect=self.h.fixture.connect, store_factory=lambda: self.h.fixture.store,
            source_guard=lambda db, item, expected: {"id": item}, export_locked=service.result_locked)
        publication = publisher.finalize("TEST-conversation", run["run_id"])
        self.assertEqual(publication["save_status"], "saved", publication)
        self.url = self.url.replace(self.h.run_id, run["run_id"])
        offset, targets = 0, []
        while True:
            response = self.client.get(self.url, query_string={"offset": offset}); self.assertEqual(response.status_code, 200, response.get_json())
            page = response.get_json(); self.assertLessEqual(len(response.get_data()), 65536); self.assertLessEqual(len(page["options"]), 20)
            self.assertTrue(page["options"]); targets.extend(canonical(o["target"]) for o in page["options"])
            if page["next_offset"] is None: break
            self.assertGreater(page["next_offset"], offset); offset = page["next_offset"]
        self.assertEqual(len(targets), 26); self.assertEqual(len(set(targets)), 26)
        self.assertEqual(self.options(offset=10000)["options"], [])

    def test_large_verified_record_reports_byte_limit_without_truncating_identity(self):
        option = self.candidate(); statement = self.statement(option, option["human_steps"][0])
        statement["record"]["reason"] = "研" * 15000
        self.post(statement)
        response = self.client.get(self.url); self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["reason_code"], "human_record_options_byte_limit")
        self.assertEqual(len(self.h.fresh()._human_packages()[0]), 1)

    def test_no_writer_fallback_and_foreign_store_authority(self):
        app = Flask("no-reader"); register_orchestration_routes(app, self.writer, lambda _: {})
        response = app.test_client().get(self.url); self.assertEqual(response.status_code, 503); self.writer.assert_not_called()
        reader = self.namespace["analysis_table_pilot_reader"]()
        reader.table_store = AnalysisStore(self.h.fixture.path.with_name("TEST-foreign.sqlite"), reader.connect)
        app = Flask("foreign-store"); register_orchestration_routes(app, self.writer, lambda _: {}, table_reader=lambda: reader)
        response = app.test_client().get(self.url); self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["reason_code"], "human_record_options_storage_unavailable")
        self.writer.assert_not_called()


if __name__ == "__main__": unittest.main()
