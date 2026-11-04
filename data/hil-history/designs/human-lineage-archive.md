# Design: Human Lineage Archive — Capture & Index All Stiwi Input

**Author**: arnold (Tooling & DX keeper)
**Date**: 2026-02-18
**Status**: Partially shipped — HLA MCP tools deployed, IRC→HLA pipeline working. Full lineage search via Pensieve (ian PO). See also: human-intent-archive.md.
**Bead**: aegis-isc9s

## The Goal

Any crew member can query "has Stiwi said anything about X?" and get verbatim
results. Stiwi's words are the canonical source of truth — they should be
searchable, not locked in session transcripts that expire with context windows.

## Where Stiwi's Input Lives Today

### 1. Claude Code Session Transcripts (JSONL)

Location: `~/.claude-accounts/*/projects/*/` on luvu
Format: JSONL with `type: "user"` entries

Problem: These contain mostly tool_results (automated), not human typing.
Actual human input is a small fraction of `type: "user"` entries. Additionally,
Gas Town crew sessions are mostly autonomous — Stiwi's direct input is in his
OWN sessions (not crew sessions), and in nudges that arrive as system-reminders.

### 2. Telegram Messages (via Stiwi bot)

Stiwi types into Telegram → bot routes to Gas Town → captured as beads with
`from:overseer` label. These are already in Dolt (beads database).

Example: `"From Telegram user Stiwi (id=<redacted>) at 2026-02-18T00:47:05Z"`

**This is the cleanest source** — timestamped, attributed, already stored.

### 3. Beads with `from:overseer` Label

All human-originated work items carry the `from:overseer` label. These capture
Stiwi's directives in their bead descriptions.

### 4. stiwi-wants.md

Living document in `docs/plans/stiwi-wants.md` — curated human intent, but
not raw verbatim input.

### 5. Direct Session Input

When Stiwi types directly into a crew session (rare in autonomous mode), it
appears as a `type: "user"` JSONL entry with actual text content (not
tool_result).

## Capture Architecture

```text
Input Sources                    Extraction             Storage            Index
─────────────                    ──────────             ───────            ─────
Telegram messages ──────────┐
                            ├──▶ Extractor ──▶ Archive ──▶ Bobbin
Session transcripts ────────┤    (cron job)    (files)     (search)
                            │
Beads (from:overseer) ──────┘
```

### Source Priority

| Source | Quality | Volume | Extraction Difficulty |
|--------|---------|--------|----------------------|
| Telegram messages | High — timestamped, clean text | Medium | Easy — already beads in Dolt |
| `from:overseer` beads | High — structured directives | Low | Easy — bd query |
| Session transcripts | Mixed — lots of noise | High | Hard — need human/system filtering |
| stiwi-wants.md | High — curated | Very low | Trivial — just read the file |

**Recommendation**: Start with Telegram + overseer beads (easy, high quality).
Add session transcript extraction later (hard, noisy).

## Storage Options

### Option A: Plain Files on ZFS (Recommended)

```text
/tank/archive/human-lineage/
├── by-date/
│   ├── 2026-02-17/
│   │   ├── telegram-001.md    # Raw Telegram message
│   │   ├── telegram-002.md
│   │   └── session-input-001.md
│   └── 2026-02-18/
│       └── ...
├── by-source/
│   ├── telegram/              # Symlinks to by-date
│   ├── session/
│   └── bead/
└── index.jsonl                # Metadata for Bobbin ingestion
```

**Why plain files**:

- ZFS snapshots provide versioning + backup for free
- Bobbin can index a directory of markdown files natively
- No new infrastructure (MinIO is overkill for text files)
- grep/ripgrep work immediately — no special tooling needed
- Human-readable, inspectable, portable

**Why NOT MinIO**: Object storage adds operational complexity (another service
to maintain, API to learn). The archive is text — not binary blobs. Plain files
on ZFS are simpler, faster, and already backed up.

### Option B: Dolt Table

Store directly in beads database as a `human_input` table.

| timestamp | source | channel | raw_text | bead_ref | session_id |
|-----------|--------|---------|----------|----------|------------|

**Pros**: Already have Dolt, structured queries work, backed up.
**Cons**: Dolt connection pool issues (known P1 — hq-do92s), adds load to
shared database, not ideal for full-text search (that's Bobbin's job).

### Recommendation: Option A (plain files) + Dolt metadata

- Raw text in ZFS files (archival, Bobbin-indexable)
- Lightweight metadata in Dolt (timestamp, source, file path, bead ref)
- Best of both: files for bulk storage/indexing, Dolt for structured queries

## Extraction Pipeline

### Phase 1: Telegram + Overseer Beads (Easy)

Cron job (hourly) on luvu:

```bash
#!/usr/bin/env bash
# human-lineage-extract.sh

# 1. Query beads for from:overseer messages since last run
bd list --json --label from:overseer --since "$LAST_RUN" |
  jq -r '.[] | @base64' |
  while read -r encoded; do
    bead=$(echo "$encoded" | base64 -d)
    id=$(echo "$bead" | jq -r '.id')
    date=$(echo "$bead" | jq -r '.created_at[:10]')
    desc=$(echo "$bead" | jq -r '.description')

    # Write to archive
    mkdir -p "/tank/archive/human-lineage/by-date/$date"
    echo "---"                                          > "/tank/archive/human-lineage/by-date/$date/$id.md"
    echo "source: bead"                                >> "/tank/archive/human-lineage/by-date/$date/$id.md"
    echo "bead: $id"                                   >> "/tank/archive/human-lineage/by-date/$date/$id.md"
    echo "date: $(echo "$bead" | jq -r '.created_at')" >> "/tank/archive/human-lineage/by-date/$date/$id.md"
    echo "---"                                          >> "/tank/archive/human-lineage/by-date/$date/$id.md"
    echo ""                                             >> "/tank/archive/human-lineage/by-date/$date/$id.md"
    echo "$desc"                                        >> "/tank/archive/human-lineage/by-date/$date/$id.md"
  done

# 2. Update last-run timestamp
date -u +%Y-%m-%dT%H:%M:%SZ > /tank/archive/human-lineage/.last-run
```

### Phase 2: Session Transcript Extraction (Hard)

Need to solve the filtering problem: most `type: "user"` entries in JSONL are
tool_results, not human typing.

**Human input heuristics**:

1. `type: "user"` AND content is a plain string (not tool_result array)
2. Content doesn't start with `[GAS TOWN]` (system prefix)
3. Content doesn't start with `<system` (system reminder)
4. Content length > 10 characters (filter out "y", "ok", empty approvals)
5. Content doesn't match known nudge patterns

**Risk**: False positives (capturing automated messages as human input).
**Mitigation**: Tag extracted entries with confidence score. Manual review
for first batch to calibrate filters.

### Phase 3: Live Capture Hook

Instead of post-hoc extraction, intercept human input at the source:

- Claude Code `UserPromptSubmit` hook could write to archive in real-time
- Telegram bot already creates beads — add archive write as side-effect
- This is the long-term solution; Phases 1-2 are catch-up

## Bobbin Integration (coordinate with ian)

Bobbin indexes document collections for semantic search. The archive is a
collection of markdown files — Bobbin's native format.

**arnold's piece** (storage/tooling):

- Provide archive as a directory of markdown files with YAML frontmatter
- Each file has: source, date, bead reference, raw text
- Provide an index.jsonl for bulk ingestion

**ian's piece** (Bobbin indexing):

- Configure Bobbin to index `/tank/archive/human-lineage/`
- Expose search as MCP tool or API endpoint
- Support queries like: "What has Stiwi said about IRC?"

**Interface contract**: arnold produces files, ian configures Bobbin to read them.
No tight coupling needed.

## Consumer: maldoon Intent Sync (aegis-warden-intent-sync)

maldoon is the **primary consumer** of the Intent Archive. The `aegis-warden-intent-sync`
deacon plugin runs on a 10-minute cooldown and:

1. Queries Bobbin `/archive/recent` for new records since last sync
2. Classifies records as new directives, reinforcements, or noise
3. Searches archive for citation candidates for existing stiwi-wants.md entries
4. Produces `data/warden/intent-sync.json` with structured findings

maldoon's patrol loop (Phase 5: Intent Sync Review) reads this output and uses
judgment to update `docs/plans/stiwi-wants.md` with:

- New want entries for genuine new directives
- `**Intent Records**: hi-XXXXX` citation lines linking wants to verbatim records
- Priority adjustments when wants are repeatedly reinforced

See: `plugins/aegis-warden-intent-sync.md` for full plugin specification.

## What's NOT Needed (Yet)

- **Deduplication** — same message may appear in Telegram + bead. Accept dupes
  for now; Bobbin's semantic search handles near-duplicates gracefully.
- **Access control** — all crew can read the archive. Stiwi's input is
  operational guidance, not private.
- **Retention policy** — keep everything forever. ZFS compression makes text
  storage cheap.
- **Web UI** — Bobbin search + CLI is sufficient. Tapestry can add UI later.

## Risks

1. **Session transcript noise** — Phase 2 filtering is hard. Start with Phase 1
   (Telegram + beads) which is clean and valuable on its own.
2. **ZFS dataset availability** — need `/tank/` mount on luvu. Check with malcolm.
3. **Bobbin not ready** — if Bobbin indexing isn't available, the archive is still
   useful via grep/ripgrep. Don't block on Bobbin.

## Recommended Next Steps

1. **Create ZFS dataset** — `/tank/archive/human-lineage/` (malcolm, P2)
2. **Write Phase 1 extractor** — cron script for Telegram + overseer beads (P2)
3. **Seed archive** — backfill from existing beads history (one-time)
4. **Coordinate with ian** — Bobbin indexing config for the archive directory
5. **Phase 2 extractor** — session transcript filtering (P3, after Phase 1 proves value)
6. **Live capture hook** — Claude Code hook integration (P3)
