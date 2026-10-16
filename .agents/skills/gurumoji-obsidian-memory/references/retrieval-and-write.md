# Retrieval and write protocol

## Retrieve in layers

Use local, deterministic retrieval before an LLM call. The normal sequence is:

1. Resolve the requested entity (`note_id`, `source_id`, `artifact_id`, or `run_id`) through the catalog if supplied.
2. Read the relevant `00-Home.md` or `00-Index.md`, then filter candidates by `vault_kind`, `note_type`, status, IDs, and keywords.
3. Read frontmatter plus `summary` for at most the candidates necessary to decide relevance.
4. Read only the heading, table rows, or quoted source ranges needed to answer or execute the task.
5. Render a context packet with provenance. It contains the request, source IDs/revisions/hashes, selected excerpts, and explicit omissions.

Default context ceilings are safeguards, not targets:

| Layer | What to load | Ceiling |
| --- | --- | ---: |
| L0 | home/index/catalog records | 1,200 characters |
| L1 | metadata and summaries from 2–4 candidates | 4,000 characters |
| L2 | exact excerpts from up to 3 confirmed sources | 8,000 characters |

If the request cannot be answered inside the ceiling, add the next most relevant source and state why. Do not compensate by loading an entire vault. Full transcripts, JSON payloads, and CSV tables require an explicit need such as a named range, record, or calculation.

### Context-packet template

```markdown
Request: …
Selected sources:
- note_id / revision / source_hash — reason selected

Constraints:
- …

Evidence:
### source-id — heading
<minimal excerpt>

Not loaded:
- raw transcript and artifact table; no named range required
```

The caller must validate that each excerpt still has the declared hash/revision. Cache a packet only by `(query, selected IDs, revisions, hashes, rendering version)` and invalidate on any source change.

## Writing compact memory

On a meaningful source update, write or refresh the matching note in this order:

1. Write the source artifact/record and calculate its hash/revision.
2. Write a factual `summary` that names scope, result or state, and evidence IDs. Do not add unsupported conclusions.
3. Update the same-vault index and catalog resolver as one recoverable operation.
4. Mark dependent summaries, visuals, or run interpretations stale if their source IDs or hashes differ.

Do not use a remote model merely to choose files, build an index, or refresh a routine manifest. If an LLM creates a summary, record the source IDs/hashes and review status; never let the generated summary become the only evidence.

## Sending material to an AI service

Build the prompt from the rendered context packet, not directly from Markdown files. Exclude by default:

- YAML frontmatter, Markdown links, checkboxes, UI instructions, duplicated histories
- API keys, bearer tokens, local paths, user identifiers, consent data, and sensitive raw input
- complete CSV/JSON exports, media, and unrelated analysis runs

Include only task-specific excerpts plus stable IDs. The application should report token usage from the provider response where available, but should not rely on token estimates to decide whether a source is safe to disclose.

## Managed versus user-owned content

Managed regions may contain an ID, generated summary, artifact references, and a clearly delimited status block. User text, tags, aliases, and research interpretation are user-owned. Update a managed region by ID/hash; never replace the whole note because its title happens to match.

Generated notes go through `vault_note_policy.write_generated_note`. When a researcher edited a generated note, that version is copied into the Vault history (tagged `graph/history`, with its own `note_id`) before the latest version is written, and the change is logged and listed in `90-運用/同期状況.md` (user decision, 2026-09-25). Researcher-owned notes are never rewritten. Never perform hidden retries that repeat an AI call.
