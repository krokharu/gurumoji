# Four-vault contract

## Current state

The four vault roles exist. `src/gurumoji/vault_registry.py` (`VaultRegistry`) records roots, schema version, and every managed note's `note_id`, path, written hash, `revision`, and `source_hash` in `<MOJIOKOSI_DATA_DIR>/obsidian_layout/vaults.json`. Generated roots must be single folders directly under `<data>/obsidian`, so they are siblings and never nested; the registry refuses `ResearchVault` as a generated root.

`<MOJIOKOSI_DATA_DIR>/obsidian/ResearchVault` remains the researcher-facing reading and AI-finishing Vault. It is not one of the four roles and must stay compatible until a versioned migration and configuration switch have succeeded.

Publication paths today:

| Trigger | Code | Notes written |
| --- | --- | --- |
| Whisper job saved; transcript edited; AI speaker identification; Obsidian finishing applied; output JSON imported | `app.py`: `publish_input_vault` (Whisper settings via `whisper_vault_settings`) | Input `10-Inputs/input-<key>.md` (ledger, Whisper and diarization settings, vocabulary count and hash, quality counts; no text) |
| Conversation deleted | `app.py`: `retire_input_vault` | Input ledger set to `status: deleted`; runs and notes kept |
| Any analysis run completed (text analysis, KWIC, AI insights, Transformer, AI finishing) | `AnalysisStore.publish_vaults` | Input `20-Snapshots/`, Orchestrator `10-Methods/` and `20-Runs/`, Visualization `10-Visuals/run-<id>/` |
| Meeting minutes (own run, kind `meeting_minutes`) | `app.py`: `archive_meeting_minutes` | Same as an analysis run, for one conversation |
| Group-interview comparison (own run, kind `interview_comparison`) | `app.py`: `archive_interview_comparison`; members in `analysis_run_members` | Comparison snapshot listing members, run note with `conversation_ids`, ResearchVault `40-研究/インタビュー比較/` |
| Input, condition, or speaker change marks runs stale | `AnalysisStore.refresh_vaults` (includes comparisons containing the conversation) | Run and visual notes republished with `status: stale` |

Never mix meeting minutes or comparisons into a conversation's text-analysis run; each is a separate run and method.

| Vault | Root | Markdown is authoritative for | Machine authority / large artifacts |
| --- | --- | --- | --- |
| Software | `docs/program-vault` | architecture, module contracts, ADRs, public data contracts, development plans | source code and tests; Git is revision authority |
| Input | `<data>/obsidian/InputVault` | input catalog, schema notes, collection purpose, consent/retention notes, compact snapshot descriptions | `library.sqlite3`, original media, normalized input snapshots, import JSON |
| Visualization | `<data>/obsidian/VisualizationVault` | visual question, chart specification, interpretation, provenance, accessibility description | CSV data tables, PNG/SVG/HTML figures, analysis manifests |
| Orchestrator | `<data>/obsidian/OrchestratorVault` | method cards, routing rules, prerequisites, limitations, run plans, evaluation decisions | analysis-run manifests, parameters, result JSON/CSV, job state in SQLite |

`<data>` means the resolved runtime data directory, normally `runtime/data`; never silently hard-code a second path when `MOJIOKOSI_DATA_DIR` is configured. Each root has its own `.obsidian` folder and is opened separately by Obsidian. Do not nest one vault inside another.

## Note contract

Every managed note has small YAML frontmatter. Preserve user-owned properties (`tags`, `aliases`, free text) and reserve the listed keys for the app.

```yaml
note_id: input-snapshot-01J...
vault_kind: input
note_type: snapshot
title: 2026-09-14 interview import
summary: Short, factual retrieval summary. It must stand alone.
source_ids: [library-item-01J...]
artifact_ids: [artifact-01J...]
revision: 3
source_hash: sha256:...
status: current
updated: 2026-09-14T10:30:00Z
sensitivity: restricted
tags: [gurumoji/input]
```

Use only fields that are meaningful. `summary` is a compact retrieval layer, not a replacement for evidence. For a result or visual, include `run_id`, parameter-set ID, and the exact source revision. For an orchestrator rule, include applicability and a current/review status.

Each vault contains:

```text
00-Home.md                 # human entry point and scope
00-Index.md                # concise machine- and human-readable catalog
10-...                     # domain notes
90-Templates/              # only if reusable authoring templates are needed
99-Archive/                # superseded notes; not default retrieval candidates
```

Create index entries from declared metadata; never infer identity from title or path alone. Index entries should contain an ID, one-line summary, status, and same-vault link. Cross-vault links are resolver records such as `source_id`, `artifact_id`, and `run_id`, not `[[relative links]]`.

## Data routing

| Data shape / operation | Primary location | Obsidian representation |
| --- | --- | --- |
| Human-readable decision or explanation | vault Markdown | canonical note |
| Ingestion state, deduplication, relationships, transactions | SQLite | small note with stable IDs and state summary |
| Reproducible run request or nested result | JSON + manifest | result/run note with IDs, conditions, concise findings |
| Rows for a chart, external export, wide tables | CSV | visual/result note with artifact ID, schema, row count, hash |
| Audio, media, image, model output | managed files | provenance note and relative artifact reference |

The existing `analysis_store` convention remains useful: JSON/CSV/figures are immutable artifacts addressed from a run manifest, while a readable note gives the interpretation and links to artifacts. Never duplicate a large CSV or raw transcript into several vaults solely for discoverability.

## Migration rules

1. Add a config-controlled vault registry before creating new roots. Record schema version and roots in a durable catalog.
2. Inventory notes, artifacts, IDs, links, and hashes. Back up affected SQLite data, workbench state, vault folders, and manifests before writing.
3. Create target notes and resolver records transactionally. Keep legacy paths readable until validation passes.
4. Validate each ID resolves once, hashes match, same-vault links are valid, and no raw/private material crossed into a new Vault.
5. Switch the configured reader/writer only after validation; retain a rollback marker and migration report. A migration must not invoke AI or recompute analyses.

## Privacy boundary

Input notes must avoid credentials and need only enough personal/sensitive metadata to enforce consent, access, retention, and lookup. Raw text, media, and identifiers should remain in the governed data store. A summary used for retrieval must be redacted when its note is shared or used with a remote model.
