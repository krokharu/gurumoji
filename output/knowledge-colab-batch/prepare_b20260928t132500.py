from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t132500"
SESSION = "gurumoji-a100-correlation-20260928-132500"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "RES-scipy-pearsonr"
SOURCE_SHA = "9999856b875cf15abcad22654b16bd3d2801f89eef28b42a048114e93eac68c3"
SOURCE_URL = "https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.pearsonr.html"
SOURCE_REGISTRY = (
    HERE / "jobs" / "b20260928t025516-09" /
    "Gurumoji_Job_b20260928t025516-09_g1.local-approved-sources.json"
)
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "expert_id": "exp-correlation",
        "anchor_id": "pearsonr-resampling-pvalue-methods",
        "start": "pearsonr method parameter",
        "end": "ResamplingMethod version and selected p-value test",
        "text": (
            "SciPy v1.18.0 stats.pearsonrの公式API資料では、methodにPermutationMethodまたは"
            "MonteCarloMethodのインスタンスを渡すと、それぞれ設定に応じてscipy.stats.permutation_testまたは"
            "scipy.stats.monte_carlo_testでp値を計算する。このAPI上の選択肢だけを記述する。"
            "会話の発話データ一般で置換可能性や独立性が成立すると推論せず、デザイン上の妥当性を保証しない。"
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "expert_id": "exp-correlation",
        "anchor_id": "pearsonr-confidence-interval-methods",
        "start": "PearsonRResult confidence_interval method",
        "end": "Fisher transformation, bootstrap, and degenerate resamples",
        "text": (
            "SciPy v1.18.0 stats.pearsonrの公式API資料によると、結果のconfidence_intervalでmethodを"
            "省略した場合はFisher変換を用い、BootstrapMethodを渡した場合はscipy.stats.bootstrapを用いる。"
            "退化した再標本化では信頼限界がNaNになりうること、これは非常に小さい標本（約6観測）で典型的とされることも含める。"
            "約6を一般的な最小標本数や実装閾値に言い換えない。"
        ),
    },
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    matches = [source for source in registry["sources"] if source.get("source_id") == SOURCE_ID]
    if len(matches) != 1:
        raise RuntimeError("approved SciPy Source registry mismatch")
    source = copy.deepcopy(matches[0])
    if source["sha256"] != SOURCE_SHA or source["locator"]["value"] != SOURCE_URL:
        raise RuntimeError("approved SciPy Source hash or locator mismatch")
    if "colab" not in source["rights"]["allowed_routes"] or source["rights"]["classification"] != "licensed":
        raise RuntimeError("Colab processing is not allowed by the Source registry")
    source["adaptation_notice"] = (
        "Selected findings paraphrased from the official SciPy v1.18.0 API documentation. "
        "No user data or verbatim documentation passages are included."
    )

    evidence_text = (
        "SciPy community. SciPy v1.18.0 stats.pearsonr API reference.\n"
        f"Official API page: {SOURCE_URL}\n"
        f"Document SHA-256: {SOURCE_SHA}. License: BSD-3-Clause.\n"
        "Evidence paraphrase A (method parameter): when a PermutationMethod or MonteCarloMethod instance is supplied, "
        "pearsonr computes its p-value through the corresponding configured permutation_test or monte_carlo_test. "
        "This documents API capability; it does not validate exchangeability, independence, or a research design.\n"
        "Evidence paraphrase B (confidence interval): PearsonRResult.confidence_interval uses the Fisher transformation "
        "when no method is supplied; BootstrapMethod selects scipy.stats.bootstrap. Degenerate resamples can produce NaN "
        "confidence limits, which the manual describes as typical for very small samples of about six observations.\n"
        "This local evidence text is a curated paraphrase, not a verbatim transcription; its hash is separate from the official page hash.\n"
    )
    EVIDENCE_SNAPSHOT.write_bytes(evidence_text.encode("utf-8"))
    evidence_snapshot_sha = digest(evidence_text.encode("utf-8"))
    for task in TASKS:
        task["excerpt_sha256"] = digest(task["text"].encode("utf-8"))
        source["anchors"].append({
            "anchor_id": task["anchor_id"],
            "kind": "section",
            "start": task["start"],
            "end": task["end"],
            "extracted_text_sha256": task["excerpt_sha256"],
        })
    write_json(SOURCE_RECORD, source)

    jobs = []
    for task in TASKS:
        job_id = task["job_id"]
        input_dir = HERE / "inputs" / BATCH_ID / "jobs" / job_id
        job_dir = HERE / "jobs" / job_id
        if input_dir.exists() or job_dir.exists():
            raise FileExistsError(job_id)
        input_dir.mkdir(parents=True)
        job_dir.mkdir(parents=True)
        excerpt = {
            "source_id": source["source_id"],
            "source_version": source["version"],
            "source_sha256": source["sha256"],
            "anchor_id": task["anchor_id"],
            "extracted_text_sha256": task["excerpt_sha256"],
            "text": task["text"],
        }
        write_json(input_dir / "source.json", source)
        write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
        write_json(input_dir / "excerpt.json", excerpt)
        bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
            "--data-dir", str(HERE / "state"),
            "--expert-id", task["expert_id"],
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle),
            "--job-id", job_id,
            "--ttl-minutes", "55",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{job_id} preparation failed: {result.stdout}\n{result.stderr}")
        prepared = json.loads(result.stdout)
        prepared.update({
            "batch_id": BATCH_ID,
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": source["source_id"],
            "source_record_path": SOURCE_RECORD.relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "evidence_snapshot_path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "evidence_snapshot_sha256": evidence_snapshot_sha,
            "source_sha256": SOURCE_SHA,
            "excerpt_sha256": task["excerpt_sha256"],
            "expert_id": task["expert_id"],
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        template = (HERE / "jobs" / "b20260928t120000-01" / "colab_run_job.py").read_text(encoding="utf-8")
        template = template.replace("b20260928t120000-01", job_id)
        template = re.sub(
            r'EXPECTED_BUNDLE_SHA256 = "[0-9a-f]{64}"',
            f'EXPECTED_BUNDLE_SHA256 = "{prepared["bundle_sha256"]}"',
            template,
        )
        (job_dir / "colab_run_job.py").write_text(template, encoding="utf-8")
        jobs.append(prepared)

    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": len(jobs),
        "expert_id": "exp-correlation",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "BSD-3-Clause",
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "curated paraphrase; not a verbatim transcription",
        },
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    run_template = (HERE / "run_b20260928t125600.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t125600.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-deepknowledge-20260928-125600", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot_sha256": evidence_snapshot_sha,
        "jobs": [{
            "job_id": job["job_id"], "expert_id": job["expert_id"], "anchor_id": job["anchor_id"],
            "bundle_path": job["bundle_path"], "bundle_sha256": job["bundle_sha256"],
            "excerpt_sha256": job["excerpt_sha256"], "deadline": job["deadline"],
        } for job in jobs],
    }, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
