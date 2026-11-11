"""mainの現行bytesと固定した開発資料から、隔離した検証cloneを作成する。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


class PreparationError(ValueError):
    pass


def git(repository, *arguments):
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(repository), *arguments], stderr=subprocess.PIPE)


def reject_links(path):
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise PreparationError(f"symlink/junctionは使用できません: {candidate}")


def checked_relative(value):
    if not value or "\\" in value or any(part in {"", ".", ".."} or ":" in part for part in value.split("/")):
        raise PreparationError(f"安全な相対パスではありません: {value}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise PreparationError(f"絶対パスは使用できません: {value}")
    return path


def protected(value):
    parts = checked_relative(value).parts
    lowered = [part.casefold() for part in parts]
    return (any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in lowered)
            or lowered[0] in {"runtime", "output", ".validation"}
            or any(part == ".env" or part.startswith(".env.") for part in lowered)
            or "/".join(lowered) == "config/tokens.json")


def development_asset(value):
    return (value.startswith(("tests/", "scripts/", "devtools/", "scratch/", "docs/"))
            or value in {"pytest.ini", "config/requirements-dev.txt",
                         ".agents/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py"})


def separate(left, right):
    if left == right or left in right.parents or right in left.parents:
        raise PreparationError(f"sourceとtargetは重複できません: {left} / {right}")


def main_identity(source):
    branch = git(source, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip()
    head = git(source, "rev-parse", "HEAD").decode().strip()
    if branch != "main" or head != git(source, "rev-parse", "refs/heads/main").decode().strip():
        raise PreparationError("sourceはlocal mainをcheckoutしたsnapshotにしてください。")
    return head


def prepare(source, target, archive_ref, archive_repository=None, include=()):
    source, target = Path(source).absolute(), Path(target).absolute()
    archive_repository = Path(archive_repository or source).absolute()
    for path in (source, target, archive_repository):
        reject_links(path)
    source, target, archive_repository = source.resolve(), target.resolve(), archive_repository.resolve()
    separate(source, target)
    separate(archive_repository, target)
    if target.exists():
        raise PreparationError(f"targetは新規の未作成パスを指定してください: {target}")
    if not target.parent.is_dir():
        raise PreparationError("targetの親フォルダーを先に作成してください。")
    if Path(git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve() != source:
        raise PreparationError("sourceにはrepository rootを指定してください。")
    head = main_identity(source)
    before_status = git(source, "status", "--porcelain=v1", "-z", "--untracked-files=no")
    archive_commit = git(archive_repository, "rev-parse", "--verify", archive_ref + "^{commit}").decode().strip()
    tracked, omitted, missing = {}, [], []
    for entry in git(source, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, _, stage = header.decode().split()
        name = raw_path.decode("utf-8")
        checked_relative(name)
        if stage != "0":
            raise PreparationError(f"未解決のindex競合があります: {name}")
        if protected(name):
            omitted.append({"path": name, "reason": "protected"})
            continue
        if mode not in {"100644", "100755"}:
            raise PreparationError(f"symlink/submoduleは使用できません: {name}")
        tracked[name] = "main"
    for name in include:
        name = str(checked_relative(name))
        if protected(name):
            raise PreparationError(f"保護対象は明示指定でもコピーできません: {name}")
        if name not in tracked:
            tracked[name] = "main-explicit"
    main_files = {}
    occupied = set()
    for name, origin in sorted(tracked.items()):
        path = source / name
        reject_links(path)
        if name.casefold() in occupied:
            raise PreparationError(f"大文字小文字だけが異なるパスがあります: {name}")
        occupied.add(name.casefold())
        if not path.exists() and origin == "main":
            missing.append(name)
            continue
        if not path.is_file():
            raise PreparationError(f"通常ファイルではありません: {name}")
        main_files[name] = {"origin": origin, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    supplementary = {}
    supplementary_names = set()
    for entry in git(archive_repository, "ls-tree", "-r", "-z", archive_commit).split(b"\0"):
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        name = raw_path.decode("utf-8")
        checked_relative(name)
        if not development_asset(name) or protected(name):
            continue
        # mainの削除・大文字小文字違いも含め、mainが所有するパスは補完しない。
        if name.casefold() in occupied or (source / name).exists():
            continue
        if mode not in {"100644", "100755"} or kind != "blob":
            raise PreparationError(f"開発資料にsymlink/submoduleがあります: {name}")
        reject_links(source / name)
        if name.casefold() in supplementary_names:
            raise PreparationError(f"開発資料のパスが重複しています: {name}")
        supplementary[name] = oid
        supplementary_names.add(name.casefold())
    # 検査が終わるまでtargetを作成しない。失敗時の半完成cloneは削除せず調査用に残す。
    target.mkdir()
    subprocess.run(["git", "clone", "--no-checkout", "--no-hardlinks", "--no-tags", "--single-branch",
                    "--branch", "main", str(source), str(target)], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(target, "read-tree", "HEAD")
    if git(target, "rev-parse", "HEAD").decode().strip() != head:
        raise PreparationError("準備中にsourceのmainが変更されました。別targetで再実行してください。")
    records = []
    for name, record in main_files.items():
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise PreparationError(f"準備中にsourceが変更されました: {name}")
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        reject_links(destination)
        with destination.open("xb") as output:
            output.write(raw)
        records.append({"path": name, **record})
    for name, oid in sorted(supplementary.items()):
        raw = git(archive_repository, "cat-file", "blob", oid)
        destination = target / name
        if destination.exists():
            raise PreparationError(f"既存ファイルは上書きできません: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        reject_links(destination)
        with destination.open("xb") as output:
            output.write(raw)
        records.append({"path": name, "origin": "archive", "blob": oid,
                        "sha256": hashlib.sha256(raw).hexdigest()})
    if main_identity(source) != head or git(source, "status", "--porcelain=v1", "-z", "--untracked-files=no") != before_status:
        raise PreparationError("準備中にsourceのHEAD/index/statusが変更されました。")
    for name, record in main_files.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != record["sha256"]:
            raise PreparationError(f"準備中にsourceが変更されました: {name}")
    if any((source / name).exists() for name in missing):
        raise PreparationError("準備中にsourceの削除状態が変更されました。")
    manifest = {"schema_version": 1, "source": str(source), "source_head": head,
                "source_branch": "main", "archive_repository": str(archive_repository),
                "archive_ref": archive_ref, "archive_commit": archive_commit,
                "source_status_porcelain": before_status.decode("utf-8"),
                "files": records, "main_deleted_paths": missing, "excluded_tracked_paths": omitted}
    destination = target / "output/validation/prepare-manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--archive-ref", required=True, help="確認した保存資料branch/refまたはcommit SHA")
    parser.add_argument("--archive-repository", type=Path, help="省略時はsource内のGit objectを参照")
    parser.add_argument("--include", action="append", default=[], help="未追跡の対象変更を通常ファイル単位で明示指定")
    args = parser.parse_args()
    try:
        manifest = prepare(args.source, args.target, args.archive_ref, args.archive_repository, args.include)
    except (PreparationError, subprocess.CalledProcessError, OSError) as exc:
        parser.exit(1, f"準備失敗: {exc}\n")
    print(f"検証clone: {args.target.resolve()}\nmain: {manifest['source_head']}\narchive: {manifest['archive_commit']}")
    print(f"記録: output/validation/prepare-manifest.json ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
