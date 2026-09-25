"""Check for and import Software Vault (docs/program-vault) updates locally.

Used when the user asks a local agent to "Obsidianを更新". Git is the
revision authority for the Software Vault, so updates arrive by fetching
the repository; this script reports what changed and applies it without
overwriting notes the user edited.

    python scripts/update_program_vault.py check
    python scripts/update_program_vault.py apply
    python scripts/update_program_vault.py apply --target "D:/Obsidian/GurumojiProgram"

Without --target the vault is the repository folder docs/program-vault
(the folder Obsidian opens, see docs/OBSIDIAN_VAULTS.md). apply then only
fast-forwards the current branch; it never merges, rebases or discards
local work.

With --target (or GURUMOJI_PROGRAM_VAULT_TARGET) the notes are copied into
a separate Obsidian vault. A note is overwritten only if it is unchanged
since this script last wrote it; otherwise the incoming version is saved
under <target>/.gurumoji-sync/incoming/ and reported. Notes removed
upstream are moved to <target>/.gurumoji-sync/removed/, never deleted.
Obsidian ignores dot-folders, so these copies do not appear in the vault.

The personal .obsidian folder is never read or written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

VAULT_PATH = "docs/program-vault"
TARGET_ENV = "GURUMOJI_PROGRAM_VAULT_TARGET"
SYNC_DIR = ".gurumoji-sync"
STATE_FILE = "state.json"
STATUS_LABELS = {"A": "追加", "M": "更新", "D": "削除", "R": "名前変更"}


class UpdateError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and result.returncode != 0:
        raise UpdateError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    if result.returncode != 0:
        raise UpdateError(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def upstream_ref(repo: Path, remote: str | None, branch: str | None) -> str:
    if remote and branch:
        return f"{remote}/{branch}"
    tracking = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False).strip()
    if tracking:
        return tracking
    return f"{remote or 'origin'}/{branch or 'main'}"


def fetch(repo: Path, ref: str) -> None:
    remote, _, branch = ref.partition("/")
    git(repo, "fetch", "--quiet", remote, branch)


def front_matter(text: str) -> dict[str, str]:
    """Read the simple 'key: value' pairs of a note's YAML front matter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep and key and not key.startswith((" ", "-")) and value.strip():
            values[key.strip()] = value.strip().strip("'\"")
    return values


def is_vault_file(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    return bool(parts) and parts[0] != ".obsidian" and SYNC_DIR not in parts


@dataclass
class Change:
    status: str
    path: str
    old_path: str = ""
    note_id: str = ""
    title: str = ""

    def describe(self) -> str:
        label = STATUS_LABELS.get(self.status, self.status)
        name = self.title or self.path
        ident = f" ({self.note_id})" if self.note_id else ""
        moved = f" ← {self.old_path}" if self.old_path else ""
        return f"[{label}] {name}{ident} — {self.path}{moved}"


def upstream_changes(repo: Path, ref: str) -> list[Change]:
    base = git(repo, "merge-base", "HEAD", ref).strip()
    raw = git(repo, "diff", "--name-status", "-M", base, ref, "--", VAULT_PATH)
    changes: list[Change] = []
    for line in raw.splitlines():
        fields = line.split("\t")
        status = fields[0][0]
        paths = [p[len(VAULT_PATH) + 1:] for p in fields[1:]]
        new_path = paths[-1]
        if not is_vault_file(new_path):
            continue
        change = Change(status, new_path, paths[0] if status == "R" else "")
        if status != "D" and new_path.endswith(".md"):
            text = git_bytes(repo, "show", f"{ref}:{VAULT_PATH}/{new_path}").decode("utf-8", "replace")
            meta = front_matter(text)
            change.note_id, change.title = meta.get("note_id", ""), meta.get("title", "")
        changes.append(change)
    return changes


def upstream_files(repo: Path, ref: str) -> dict[str, bytes]:
    listing = git(repo, "ls-tree", "-r", "--name-only", ref, "--", VAULT_PATH)
    files: dict[str, bytes] = {}
    for full in listing.splitlines():
        relative = full[len(VAULT_PATH) + 1:]
        if is_vault_file(relative) and relative != ".gitignore":
            files[relative] = git_bytes(repo, "show", f"{ref}:{full}")
    return files


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class SyncReport:
    written: list[str] = field(default_factory=list)
    unchanged: int = 0
    conflicts: list[str] = field(default_factory=list)
    skipped_deleted_locally: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    kept_modified: list[str] = field(default_factory=list)


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".gurumoji-tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def sync_to_target(files: dict[str, bytes], target: Path, source: str) -> SyncReport:
    """Copy upstream notes into a separate vault without losing local edits."""
    sync_root = target / SYNC_DIR
    state_path = sync_root / STATE_FILE
    state = {"files": {}}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    recorded: dict[str, str] = dict(state.get("files", {}))
    report = SyncReport()
    for relative, data in sorted(files.items()):
        destination = target / relative
        incoming = sha256(data)
        if destination.is_file():
            current = sha256(destination.read_bytes())
            if current == incoming:
                report.unchanged += 1
                recorded[relative] = incoming
                continue
            if recorded.get(relative) != current:
                # Edited locally (or never written by this script): keep it.
                write_file(sync_root / "incoming" / relative, data)
                report.conflicts.append(relative)
                continue
        elif relative in recorded:
            report.skipped_deleted_locally.append(relative)
            continue
        write_file(destination, data)
        recorded[relative] = incoming
        report.written.append(relative)
    for relative in sorted(set(recorded) - set(files)):
        destination = target / relative
        if destination.is_file() and sha256(destination.read_bytes()) == recorded[relative]:
            parked = sync_root / "removed" / relative
            parked.parent.mkdir(parents=True, exist_ok=True)
            os.replace(destination, parked)
            report.removed.append(relative)
        elif destination.is_file():
            report.kept_modified.append(relative)
        recorded.pop(relative, None)
    write_file(state_path, json.dumps(
        {"schema_version": 1, "source": source, "files": recorded},
        ensure_ascii=False, indent=1,
    ).encode("utf-8") + b"\n")
    return report


def local_vault_edits(repo: Path) -> list[str]:
    raw = git(repo, "status", "--porcelain", "--", VAULT_PATH)
    return [line[3:] for line in raw.splitlines() if line.strip()]


def behind_ahead(repo: Path, ref: str) -> tuple[int, int]:
    counts = git(repo, "rev-list", "--left-right", "--count", f"{ref}...HEAD").split()
    return int(counts[0]), int(counts[1])


def command_check(repo: Path, ref: str, as_json: bool) -> int:
    changes = upstream_changes(repo, ref)
    behind, ahead = behind_ahead(repo, ref)
    edits = local_vault_edits(repo)
    if as_json:
        print(json.dumps({
            "upstream": ref, "behind": behind, "ahead": ahead,
            "changes": [change.__dict__ for change in changes],
            "local_vault_edits": edits,
        }, ensure_ascii=False, indent=1))
        return 0
    print(f"取得元: {ref}（未取り込みのコミット {behind} 件、ローカルだけのコミット {ahead} 件）")
    if not changes:
        print("Software Vault（docs/program-vault）の更新はありません。")
    else:
        print(f"Software Vault の更新 {len(changes)} 件:")
        for change in changes:
            print("  " + change.describe())
    if edits:
        print("ローカルで未コミットの変更があるノート:")
        for path in edits:
            print("  " + path)
    return 0


def command_apply_in_repo(repo: Path, ref: str) -> int:
    behind, ahead = behind_ahead(repo, ref)
    if behind == 0:
        print("最新です。取り込む更新はありません。")
        return 0
    changed = {f"{VAULT_PATH}/{change.path}" for change in upstream_changes(repo, ref)}
    blocked = [path for path in local_vault_edits(repo) if path in changed]
    if blocked:
        print("次のノートはローカルでも編集中のため、更新を中止しました（何も変更していません）:")
        for path in blocked:
            print("  " + path)
        print("編集内容をコミットするか、別の場所に保存してから再実行してください。")
        return 1
    if ahead:
        print(f"ローカルだけのコミットが {ahead} 件あり、早送りで取り込めません（何も変更していません）。")
        print("統合方法（merge／rebase）は利用者が決めてください。")
        return 1
    changes = upstream_changes(repo, ref)
    git(repo, "merge", "--ff-only", "--quiet", ref)
    print(f"{ref} を取り込みました。Obsidian は docs/program-vault の変更を自動で読み込みます。")
    for change in changes:
        print("  " + change.describe())
    return 0


def command_apply_target(repo: Path, ref: str, target: Path) -> int:
    if not target.is_dir():
        raise UpdateError(f"取り込み先のフォルダーがありません: {target}")
    commit = git(repo, "rev-parse", ref).strip()
    report = sync_to_target(upstream_files(repo, ref), target, f"{ref}@{commit[:12]}")
    print(f"{ref} の Software Vault を {target} に取り込みました。")
    print(f"  書き込み {len(report.written)} 件、変更なし {report.unchanged} 件、"
          f"退避 {len(report.removed)} 件")
    for relative in report.written:
        print("  [書き込み] " + relative)
    for relative in report.removed:
        print(f"  [上流で削除 → {SYNC_DIR}/removed へ移動] " + relative)
    if report.conflicts:
        print(f"ローカルで編集されたため上書きしなかったノート（新しい版は {SYNC_DIR}/incoming/ に保存）:")
        for relative in report.conflicts:
            print("  " + relative)
    for relative in report.skipped_deleted_locally:
        print("  [ローカルで削除済みのため作成せず] " + relative)
    for relative in report.kept_modified:
        print("  [上流で削除されたがローカルで編集済みのため残す] " + relative)
    return 1 if report.conflicts else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check", "apply"])
    parser.add_argument("--remote", help="remote name (default: tracking branch, else origin)")
    parser.add_argument("--branch", help="branch name (default: tracking branch, else main)")
    parser.add_argument("--target", help=f"separate Obsidian vault folder (or set {TARGET_ENV})")
    parser.add_argument("--no-fetch", action="store_true", help="use already fetched refs")
    parser.add_argument("--json", action="store_true", help="machine-readable check output")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    try:
        ref = upstream_ref(repo, args.remote, args.branch)
        if not args.no_fetch:
            fetch(repo, ref)
        if args.command == "check":
            return command_check(repo, ref, args.json)
        target = args.target or os.environ.get(TARGET_ENV, "").strip()
        if target:
            return command_apply_target(repo, ref, Path(target).expanduser())
        return command_apply_in_repo(repo, ref)
    except UpdateError as exc:
        print(f"更新できませんでした: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
