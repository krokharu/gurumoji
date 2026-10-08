"""Read-only Git/manifest receipt for Dot and Orca; never merges or checks out."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--expected-commit", help="Exact 40-character shared commit")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "docs/git-handoff-manifest.json").read_text(encoding="utf-8"))
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
        path = (ROOT / row["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            mismatches.append(row["path"])
        elif hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
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
