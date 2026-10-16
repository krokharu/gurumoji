"""One isolation policy for pytest and the module subprocess runner."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from urllib.parse import urlsplit,unquote

REPOSITORY = Path(__file__).resolve().parents[1]
NATIVE_PATH = type(REPOSITORY)


def configure_environment(root):
    root = Path(root)
    for key, name in (("MOJIOKOSI_DATA_DIR", "data"), ("MOJIOKOSI_OUTPUT_DIR", "output"),
                      ("MOJIOKOSI_BACKUP_DIR", "backups")):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    os.environ['KNOWLEDGE_CONSOLE_DATA_DIR'] = str(root / 'knowledge-console')


def application_paths(root):
    root = Path(root)
    data = root / "data"
    return dict(DATA_DIRECTORY=data, DATABASE_FILE=data / "library.sqlite3",
        DEFAULT_OUTPUT_DIRECTORY=root / "output", BACKUP_DIRECTORY=root / "backups",
        UPLOAD_DIRECTORY=root / "uploads", MEDIA_DIRECTORY=data / "media",
        THUMBNAIL_DIRECTORY=data / "thumbnails", TRAINING_DIRECTORY=data / "kushinada_training",
        TRAINING_AUDIO_DIRECTORY=data / "kushinada_training" / "audio",
        TRAINING_JSONL_FILE=data / "kushinada_training" / "corrections.jsonl",
        TRAINING_MANIFEST_FILE=data / "kushinada_training" / "manifest.csv",
        CUSTOM_VOCABULARY_FILE=data / "custom_vocabulary.json",
        INSTANCE_LOCK_FILE=root / "uploads" / ".gurumoji.instance.lock",
        DATA_INSTANCE_LOCK_FILE=data / ".gurumoji.instance.lock", TOKEN_FILE=root / "tokens.json")


def protect_runtime(protected=None, allowed=None):
    roots = tuple(Path(p).resolve() for p in (protected or (REPOSITORY / "runtime", REPOSITORY / "output")))
    exceptions = tuple(Path(p).resolve() for p in (allowed or (REPOSITORY / "output" / "validation",)))

    def check(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        resolved = NATIVE_PATH(os.fsdecode(path)).resolve()
        if any(resolved.is_relative_to(root) for root in roots) and not any(
                resolved.is_relative_to(root) for root in exceptions):
            raise RuntimeError(f"Test attempted a write outside isolated storage: {resolved}")

    def audit(event, args):
        if event == 'sqlite3.connect':
            database=args[0]
            if isinstance(database,str) and database.startswith('file:'):
                database=unquote(urlsplit(database).path)
                if REPOSITORY.drive and len(database)>2 and database[0]=='/' and database[2]==':': database=database[1:]
            if database != ':memory:': check(database)
        elif event == "open":
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                    isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                check(args[0])
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime"}:
            check(args[0])
        elif event in {"os.rename", "os.link", "os.symlink"}:
            check(args[0]); check(args[1])
    sys.addaudithook(audit)


def metadata_snapshot():
    result = {}
    for root in (REPOSITORY / "runtime", REPOSITORY / "output"):
        if not root.exists():
            continue
        for directory, folders, files in os.walk(root):
            if Path(directory) == REPOSITORY / "output":
                folders[:] = [name for name in folders if name != "validation"]
            for name in files:
                path = Path(directory) / name
                stat = path.stat()
                result[str(path.relative_to(REPOSITORY))] = (stat.st_size, stat.st_mtime_ns)
    return result
