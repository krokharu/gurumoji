import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.expert_knowledge_context import (
    MAX_PACKET_CLAIMS, ExpertKnowledgeContext, ExpertPackError, load_expert_pack,
    _redact_local_paths, render_agent_request, validate_output_evidence, validate_packet,
)


def _record_pair():
    source = {"schema_version": 1, "source_id": "source-1", "version": "v1", "sha256": "a" * 64,
              "title": "Using the framework method for the analysis of qualitative data in multi-disciplinary health research",
              "authors": ["Nicola K. Gale", "Gemma Heath", "Elaine Cameron", "Sabina Rashid", "Sabi Redwood"],
              "publication_year": 2013,
              "adaptation_notice": "Claim paraphrased from the cited source; no article text is reproduced.",
              "source_type": "paper",
              "locator": {"kind": "doi", "value": "10.1234/synthetic"}, "access_scope": "full_text",
              "license": {"license_id": "synthetic", "terms": "Fixture only"},
              "license_url": {"kind": "https", "value": "https://example.org/license"},
              "anchors": [{"anchor_id": "p1", "kind": "page", "start": "1", "end": "1",
                           "extracted_text_sha256": "b" * 64}],
              "rights": {"classification": "licensed", "allowed_routes": ["local", "colab"]}}
    claim = {"schema_version": 1, "claim_id": "claim-1", "expert_id": "exp-00",
             "claim": "Synthetic checked claim.", "applicability": ["fixture"], "exceptions": [],
             "claim_type": "literature",
             "evidence": [{"source_id": "source-1", "source_version": "v1", "source_sha256": "a" * 64,
                           "anchor_id": "p1", "span": {"kind": "page", "start": "1", "end": "1"},
                           "extracted_text_sha256": "b" * 64,
                           "transform_history": [{"operation": "synthetic", "tool": "fixture", "version": "1",
                                                  "output_sha256": "c" * 64}]}],
             "contradictions": [], "status": "approved", "provenance": {"method": "fixture", "created_at": "2026-01-01T00:00:00Z"},
             "rights": {"classification": "licensed", "allowed_routes": ["local"]}}
    claim["reviewer"] = {"identity": "fixture-reviewer", "reviewed_at": "2026-01-01T00:00:00Z",
                         "target_sha256": contracts.claim_review_target(claim)}
    return source, claim


def _write_bundle(root: Path):
    source, claim = _record_pair()
    experts = [{"expert_id": f"exp-{index:02d}", "source_note_sha256": hashlib.sha256(f"note-{index}".encode()).hexdigest(),
                "definition_sha256": "0" * 64} for index in range(17)]
    files = []
    file_data = {}
    for name, record, role in (("sources.jsonl", source, "knowledge_source"),
                               ("claims.jsonl", claim, "knowledge_claim")):
        data = contracts.canonical_json(record) + b"\n"
        file_data[name] = data
        files.append({"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "role": role})
    for expert in experts:
        expert_id = expert["expert_id"]
        data = contracts.canonical_json({"expert_id": expert_id, "definition": "fixture"})
        expert["definition_sha256"] = hashlib.sha256(data).hexdigest()
        name = f"definitions/{expert_id}.json"
        file_data[name] = data
        files.append({"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "role": "expert_definition", "expert_id": expert_id})
    manifest = {"schema_version": 1, "pack_id": "pack-synthetic", "flavor": "base",
                "stage": "internal_candidate", "distribution_route": "local", "compiler_version": "fixture-v1",
                "experts": experts, "commits": [{"job_id": "job-synthetic", "generation": 1,
                                                    "manifest_sha256": "d" * 64}],
                "claim_ids": [claim["claim_id"]], "source_ids": [source["source_id"]], "files": files,
                "base_root_sha256": contracts.sha256_json([
                    {"expert_id": row["expert_id"], "source_note_sha256": row["source_note_sha256"],
                     "definition_sha256": row["definition_sha256"]} for row in sorted(experts, key=lambda r: r["expert_id"])]),
                "overlay_root_sha256": None}
    manifest["root_sha256"] = contracts.sha256_json(manifest)
    (root / "pack-manifest.json").write_bytes(contracts.canonical_json(manifest))
    for name, data in file_data.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return manifest


class ExpertKnowledgeContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "pack"
        self.root.mkdir()
        self.manifest = _write_bundle(self.root)

    def test_prompt_redaction_covers_local_path_forms_recursively(self):
        marker = "[text withheld: local path present]"
        payload = {
            "quoted_posix": 'Paper at "/home/user/private.pdf"',
            "colon_posix": "Path:/Users/kurok/private.pdf",
            "drive_absolute": r"C:\Users\kurok\private.pdf",
            "drive_relative": r"C:Users\kurok\private.pdf",
            "root_relative": r"\secret.pdf",
            "unc_backslash": r"\\server\share\private.pdf",
            "unc_slashes": "//server/share/private.pdf",
            "tilde_home": "~/Documents/private.pdf",
            "named_home": "~alice/private.pdf",
            "file_uri": "file:C:relative",
            "nested": [{"kind": "local_uri", "value": "opaque private locator"}],
            "https_url": "https://example.org/papers/private.pdf",
        }
        redacted = _redact_local_paths(payload)
        for key in ("quoted_posix", "colon_posix", "drive_absolute", "drive_relative",
                    "root_relative", "unc_backslash", "unc_slashes", "tilde_home",
                    "named_home", "file_uri"):
            self.assertEqual(redacted[key], marker, key)
        self.assertEqual(redacted["nested"][0]["value"], "[local paper path withheld]")
        self.assertEqual(redacted["https_url"], payload["https_url"])

    def test_candidate_requires_explicit_local_opt_in_and_binds_packet_evidence(self):
        with self.assertRaises(ExpertPackError):
            load_expert_pack(self.root, self.manifest["root_sha256"], "local")
        with self.assertRaises(ExpertPackError):
            load_expert_pack(self.root, self.manifest["root_sha256"], "export", True)
        context = load_expert_pack(self.root, self.manifest["root_sha256"], "local", True)
        packet = context.build_expert_packet("exp-00", "fixture question", "local")
        self.assertEqual(context.sources["source-1"]["authors"][0], "Nicola K. Gale")
        self.assertEqual(context.sources["source-1"]["publication_year"], 2013)
        prompt = render_agent_request(packet)
        self.assertIn("approved_claims", prompt)
        rendered_payload = json.loads(prompt.partition("[PACKET_JSON]\n")[2])
        cited_source = rendered_payload["sources"]["source-1"]
        self.assertEqual(cited_source["authors"], ["Nicola K. Gale", "Gemma Heath", "Elaine Cameron",
                                                   "Sabina Rashid", "Sabi Redwood"])
        self.assertEqual(cited_source["publication_year"], 2013)
        self.assertEqual(cited_source["title"], packet["sources"]["source-1"]["title"])
        self.assertEqual(cited_source["locator"], {"kind": "doi", "value": "10.1234/synthetic"})
        self.assertEqual(cited_source["license"]["license_id"], "synthetic")
        self.assertEqual(cited_source["license_url"], {"kind": "https", "value": "https://example.org/license"})
        self.assertIn("Claim paraphrased", cited_source["adaptation_notice"])
        self.assertIn("Nicola K. Gale", prompt)
        self.assertIn("2013", prompt)
        self.assertIn("10.1234/synthetic", prompt)
        self.assertIn("https://example.org/license", prompt)
        row = packet["evidence"][0]
        output = {"answer": "Based on the synthetic claim.", "evidence": [row]}
        self.assertEqual(validate_output_evidence(packet, output), output)
        with self.assertRaises(ExpertPackError):
            validate_output_evidence(packet, {"answer": "unsupported", "evidence": [{**row, "claim_id": "invented"}]})

    def test_manifest_sidecar_and_expected_root_are_required(self):
        with self.assertRaises(ExpertPackError):
            load_expert_pack(self.root, "f" * 64, "local", True)
        (self.root / "pack-manifest.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ExpertPackError):
            load_expert_pack(self.root, self.manifest["root_sha256"], "local", True)

    def test_zip_reader_rejects_traversal_before_reading_bundle(self):
        archive_path = Path(self.temp.name) / "bad.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("../escape", b"x")
            archive.writestr("pack-manifest.json", b"{}")
        with self.assertRaises(ExpertPackError):
            load_expert_pack(archive_path, self.manifest["root_sha256"], "local", True)

    def test_valid_zip_is_read_without_extraction(self):
        archive_path = Path(self.temp.name) / "synthetic.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in self.root.rglob("*"):
                if item.is_file():
                    archive.write(item, item.relative_to(self.root).as_posix())
        context = load_expert_pack(archive_path, self.manifest["root_sha256"], "local", True)
        self.assertEqual(context.pack_root_sha256, self.manifest["root_sha256"])

    def test_jsonl_hash_or_schema_mismatch_fails_closed(self):
        (self.root / "claims.jsonl").write_bytes(b"not-json\n")
        with self.assertRaises(ExpertPackError):
            load_expert_pack(self.root, self.manifest["root_sha256"], "local", True)

    def test_directory_member_count_is_bounded(self):
        for index in range(520):
            (self.root / f"extra-{index}.txt").write_bytes(b"x")
        with self.assertRaises(ExpertPackError):
            load_expert_pack(self.root, self.manifest["root_sha256"], "local", True)

    def test_packet_source_keys_must_match_source_ids(self):
        context = load_expert_pack(self.root, self.manifest["root_sha256"], "local", True)
        packet = context.build_expert_packet("exp-00", "fixture question", "local")
        alias = deepcopy(packet)
        alias["sources"] = {"alias-source": alias["sources"]["source-1"]}
        alias["packet_sha256"] = contracts.sha256_json(
            {key: value for key, value in alias.items() if key != "packet_sha256"})
        with self.assertRaises(ExpertPackError):
            validate_packet(alias)

    def test_packet_rejects_unbounded_claim_set(self):
        context = load_expert_pack(self.root, self.manifest["root_sha256"], "local", True)
        template = next(iter(context.claims.values()))
        for index in range(MAX_PACKET_CLAIMS):
            claim = deepcopy(template)
            claim["claim_id"] = f"claim-extra-{index}"
            claim["reviewer"]["target_sha256"] = contracts.claim_review_target(claim)
            context.claims[claim["claim_id"]] = claim
        with self.assertRaises(ExpertPackError):
            context.build_expert_packet("exp-00", "fixture question", "local")


if __name__ == "__main__":
    unittest.main()
