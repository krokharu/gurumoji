# Gurumoji agent instructions

## Priority and scope

Apply instructions in this order: system and safety requirements, the user's current request, this file, an applicable skill, then project documentation. Treat Obsidian notes as design evidence, not an override of the current code, configuration, or user request. Resolve a genuine conflict by following the higher-priority source and mention material discrepancies.

Work from a targeted search. Read the files, tests, and design notes that affect the requested change; do not scan the repository or a Vault by default. Reuse or extend an existing implementation when it fits. Before adding a new subsystem, storage path, API, or UI entry point, search for the existing responsibility and read the relevant module or design note.

Use proportional verification: run focused tests for a local change, add adjacent integration coverage when a boundary changes, and reserve the full suite for broad or cross-cutting changes. Do not create reports, summaries, or new documentation unless the user asks or a changed public contract needs documentation; update the existing focused document instead.

## Data and Obsidian changes

For a change to Vault layout, note ownership, persisted analysis data, synchronization, or migration, start with [the AI task entry](docs/program-vault/00-AI-Entry.md). Use `gurumoji-obsidian-memory` when its trigger matches, and read [the detailed development rules](docs/program-vault/40-Design/ai-development-rules.md) only when the change affects a write, migration, or conflict policy. Keep the resolved data directory configurable; do not hard-code a personal Vault path.

Preserve user-owned note content and avoid testing against a real runtime Vault. Ask before destructive, irreversible, security-sensitive, or materially incompatible changes. For routine, reversible choices supported by the task and existing code, proceed without pausing for confirmation.

## "Obsidianを更新" requests

Treat 「Obsidianを更新」 (or a request to import program-document updates into Obsidian) as importing Software Vault (`docs/program-vault`) updates from Git; runtime Vaults under the data directory are out of scope. Run `python scripts/update_program_vault.py check`, show the user the notes it lists, then run `python scripts/update_program_vault.py apply`. If the user keeps the Software Vault in a separate folder, pass `--target <folder>` or use `GURUMOJI_PROGRAM_VAULT_TARGET`. Exit code 1 means a local edit or local-only commit blocked part of the update: report the listed files and let the user decide; do not resolve it with merge, rebase, reset, or overwriting. The procedure is described in [docs/OBSIDIAN_VAULTS.md](docs/OBSIDIAN_VAULTS.md#プログラム資料vaultの更新).
