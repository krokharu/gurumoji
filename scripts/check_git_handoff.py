"""Read-only Git/manifest receipt for Dot and Orca; never merges or checks out."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_manifest(manifest):
    """Reject incomplete receipts before reading files or fetching any refs."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported manifest schema_version")
    for key in ("source_commit", "base_commit"):
        if not isinstance(manifest.get(key), str) or not re.fullmatch(r"[0-9a-f]{40}", manifest[key]):
            raise ValueError(f"invalid {key}")
    if not isinstance(manifest.get("status"), str) or not manifest["status"].strip():
        raise ValueError("status must be a nonempty string")
    branch = manifest.get("branch")
    if not isinstance(branch, str) or not branch or "\x00" in branch:
        raise ValueError("invalid branch")
    if subprocess.run(["git", "check-ref-format", f"refs/heads/{branch}"],
            cwd=ROOT, capture_output=True).returncode:
        raise ValueError("invalid branch")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("files must be a nonempty list")
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"files[{index}] must be an object")
        name = row.get("path")
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or any(ord(char) < 32 for char in name)
                or any(part in ("", ".", "..") for part in name.split("/"))):
            raise ValueError(f"files[{index}] has an unsafe or noncanonical path")
        if name in seen:
            raise ValueError(f"duplicate file path: {name}")
        seen.add(name)
        if not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError(f"invalid sha256 for {name}")
        if type(row.get("bytes")) is not int or row["bytes"] < 0:
            raise ValueError(f"invalid bytes for {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--expected-commit", help="Exact 40-character shared commit")
    args = parser.parse_args()
    try:
        manifest = json.loads((ROOT / "docs/git-handoff-manifest.json").read_text(encoding="utf-8"),
            object_pairs_hook=unique_object)
        validate_manifest(manifest)
    except (OSError, ValueError) as exc:
        print(json.dumps({"schema_version": 1, "received": False,
            "manifest_error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    branch = manifest["branch"]
    if args.fetch:
        # Fetch updates refs only; existing work and the current branch stay intact.
        url = git("remote", "get-url", "origin")
        if url not in ("https://github.com/krokharu/gurumoji.git", "git@github.com:krokharu/gurumoji.git"):
            raise ValueError("origin is not the agreed Gurumoji repository")
        subprocess.run(["git", "fetch", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}"], cwd=ROOT, check=True)
    current = git("rev-parse", "HEAD")
    remote_ref = subprocess.run(["git", "rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
        cwd=ROOT, text=True, capture_output=True)
    remote = remote_ref.stdout.strip() if remote_ref.returncode == 0 else None
    mismatches = []
    for row in manifest["files"]:
        try:
            path = (ROOT / row["path"]).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                mismatches.append(row["path"])
                continue
            data = path.read_bytes()
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                mismatches.append(row["path"])
        except (OSError, ValueError, RuntimeError):
            mismatches.append(row["path"])
    dirty = bool(git("status", "--porcelain", "--untracked-files=normal"))
    expected_ok = args.expected_commit is None or current == args.expected_commit
    received = not mismatches and not dirty and expected_ok and current == remote
    print(json.dumps({"schema_version": 1, "branch": git("branch", "--show-current"),
        "commit": current, "remote_commit": remote, "expected_commit_matches": expected_ok,
        "dirty": dirty, "checked_files": len(manifest["files"]), "mismatches": mismatches,
        "received": received, "engineering_status": manifest["status"]}, ensure_ascii=False, indent=2))
    return 0 if received else 1


if __name__ == "__main__":
    raise SystemExit(main())
