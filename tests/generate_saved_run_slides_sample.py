"""Produce an anonymous acceptance artifact after the reviewed design is saved.

Run from the checkout with PYTHONPATH=src:tests. The output path must be supplied
explicitly. This never opens the application's database or any existing Vault.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from gurumoji.services.analysis_slides import AnalysisSlidesService
from gurumoji.services.analysis_slide_templates import load_slide_templates
from gurumoji.vault_registry import VaultRegistry
from test_analysis_slides_generation import broad_fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    templates = load_slide_templates(root)
    if not templates:
        raise SystemExit("Reviewed Software Vault design/catalog is required before generation")
    saved = broad_fixture()
    saved["run"]["config"]["question"] = "匿名の合成会話から、観察・解釈・未解決点をどう区別できるか"
    saved["run"]["config"]["synthetic"] = True
    # Explicitly invented anonymous demonstration data, never a research result.
    saved["run"]["config"]["question"] = "発言を促す働きかけは、参加の機会とどう関係するか"
    view = saved["run"]["current_view"]
    view["summary"] = "発言を促す場面はあるが、参加への効果は未確定"
    view["claims"][0]["text"] = "進行役が発言を促す場面を記録した"
    quote = "議論の途中で、進行役が発言を促した。"
    ev = saved["initial"]["snapshot"]["evidence"][0]
    ev["text"] = quote
    from gurumoji.analysis_core import fingerprint
    ev["source_hash"] = fingerprint(quote)
    saved["initial"]["hash"] = fingerprint(saved["initial"]["snapshot"])
    role_copy = {
        "interpretation": ("働きかけと参加の機会を検討", "発言の促しが参加の機会を作った可能性がある"),
        "verification": ("同じ保存根拠の範囲で検討", "この発話だけでは参加の増加を確認できない"),
        "critic": ("反対事例の不足を指摘", "現時点の根拠では効果の一般化を保留する"),
    }
    for result in saved["raw_results"]:
        if result["role"] == "core": result["raw"] = copy.deepcopy(view)
        elif result["role"] in role_copy:
            result["raw"]["summary"], result["raw"]["claims"][0]["text"] = role_copy[result["role"]]
        result["raw_hash"] = fingerprint(result["raw"])
    # The program-design document is real, while all source data and the runtime
    # design-publication target below are temporary synthetic test fixtures.
    with tempfile.TemporaryDirectory(prefix="gurumoji-slide-sample-") as temp:
        vault = VaultRegistry(Path(temp) / "data" / "library.sqlite3", Path(temp) / "software")
        service = AnalysisSlidesService(export_result=lambda *_: copy.deepcopy(saved),
            vault_factory=lambda: vault, templates=templates)
        receipt = service.save_design("item-1", "run-1")
        preview = service.preview("item-1", "run-1")
        deck = service.presentation("item-1", "run-1", expected_snapshot=preview["snapshot_signature"])
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / "anonymous-saved-run.pptx"
        path.write_bytes(deck.getvalue())
        (args.output / "anonymous-preview.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
        note_path = vault.root("visualization") / receipt["receipt"]["path"]
        (args.output / "anonymous-design-receipt.json").write_text(json.dumps({
            "scope": "anonymous synthetic sample; temporary test Vault only",
            "design_hash": receipt["design"]["design_hash"],
            "snapshot_signature": preview["snapshot_signature"],
            "design_note_sha256": hashlib.sha256(note_path.read_bytes()).hexdigest(),
            "pptx_sha256": hashlib.sha256(deck.getvalue()).hexdigest(),
            "slide_count": len(preview["slides"]),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(path), "slide_count": len(preview["slides"]),
                          "bytes": len(deck.getvalue())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
