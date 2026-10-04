"""Archive completed batch inputs, receipts, and local acceptance state."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "Gurumoji_Colab_Batch_Checkpoint_20260927.zip"
RECEIPTS = {
    "b20260927t201116-02": "1Stpi0B17doTUrX6Lw2g519dyViXRY_25",
    "b20260927t201116-04": "1jMd3I0OYrkcrxreWq76U8MHgdQ5cSTlT",
    "b20260927t201116-06": "1KWRFj45z5LouSSf8O4RcYddraBNh4_gZ",
    "b20260927t201116-07": "1dP_mc2lx1-vvi9X3Y5kPnyqEZYZBpBZx",
    "b20260927t201116-08": "1vryp9_bbgfe09VuJy-m5Ppej9WUk7P79",
    "b20260927t202729-01": "14vWgc48E9UFGOsYm6yzSAhbKg6JdK_LR",
    "b20260927t202729-02": "1YuB5TsCSxtyoGf9oq6kNbI2Uv1ML6Xih",
    "b20260927t202729-03": "12YCOc6TefRmy3nKmSZBxBBOpjhKWeTo9",
}


def main() -> None:
    files = []
    for pattern in (
        "b20260927t20*.json", "jobs/*/Gurumoji_Job_*.zip",
        "jobs/*/*.local-approved-sources.json", "jobs/*/Gurumoji_Result_*.zip",
        "jobs/*/status.json", "jobs/*/generator_error.json",
        "inputs/*/*.json", "state/knowledge_builder/state.sqlite3",
    ):
        files.extend(path for path in HERE.glob(pattern) if path.is_file())
    files = sorted(set(files))
    receipt = {"schema_version": 1, "drive_folder_id": "1wd69nc_9Xaw80Id54Nt7WW_9x3ztm9j5",
               "results": {job_id: {"file_id": file_id,
                                    "url": f"https://drive.google.com/file/d/{file_id}/view"}
                           for job_id, file_id in sorted(RECEIPTS.items())}}
    contents = {str(path.relative_to(HERE)).replace("\\", "/"): path.read_bytes() for path in files}
    contents["drive-receipts.json"] = json.dumps(receipt, sort_keys=True).encode("utf-8")
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    contents["checkpoint-manifest.json"] = json.dumps(
        {"schema_version": 1, "files_sha256": hashes}, sort_keys=True).encode("utf-8")
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 9, 27, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data)
    print(json.dumps({"path": str(OUTPUT), "files": len(contents),
                      "size_bytes": OUTPUT.stat().st_size,
                      "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
