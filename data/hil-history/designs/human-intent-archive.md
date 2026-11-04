# Design: Human Intent Archive — Capturing the Human's Will

**Authors**: arnold (storage/abstraction), ellie (capture), ian (search/index), maldoon (consumer)
**Date**: 2026-02-18
**Status**: Core concept shipped as HLA MCP tools (hla_store/hla_query/hla_recent). Remaining: Pensieve integration for full search. PO: ian.
**Bead**: aegis-isc9s

## The Abstraction

Human Intent Archival for multi-agent systems. Not a homelab feature. Not a
Gas Town feature. A foundational layer.

In any multi-agent system, a human's words are the highest authority. Those
words arrive through many channels, flow through agents, and become commits,
configs, and artifacts. Today, the chain from "human said X" to "code does Y"
is invisible.

**The archive IS the human's will in data form.**

### Core Properties

1. **Channel-agnostic** — captures from any input channel (today: IRC, Telegram,
   sessions; tomorrow: anything)
2. **Verbatim** — raw human input, never paraphrased or summarized by agents
3. **Append-only** — agents NEVER modify human input; only humans can
4. **Provenance-rich** — every record has timestamp, channel, and context
5. **Universally queryable** — any agent in any system can search it
6. **System-agnostic** — not coupled to Gas Town, beads, or any specific tool

---

## 1. Data Format (arnold)

### The Intent Record

Every piece of human input becomes an Intent Record. This is the atomic unit
of the archive:

```yaml
---
schema: human-intent/v2
id: hi-<ulid>                    # Unique, sortable ID
timestamp: 2026-02-18T02:41:30Z  # When the human said it (UTC, RFC3339)
author: stiwi                    # Human identity
author_type: human               # Always "human" in this archive
source:
  channel: telegram              # Input channel
  channel_id: 8360797693         # Channel-specific identifier
  context: dm                    # Channel-specific context (dm, #channel, session:arnold)
  adapter: aegis-tg              # Which adapter captured this
provenance:
  bead_ref: hq-7rt61d            # Linked bead (if captured via beads)
  session_ref: null              # Linked session (if captured from transcript)
  raw_hash: sha256:abc123...     # Content-addressable hash of raw text
extrapolation:                   # Capturing agent's interpretation (may be null)
  agent: aegis/crew/ellie        # Who wrote this extrapolation
  interpretation: >              # What the human meant (not a paraphrase — add signal)
    Stiwi wants bidirectional IRC — agents must SEND messages to IRC
    channels, not just receive. Current design is read-only.
  implies:                       # What this means for ongoing work
    - IRC agent needs write capability
    - Comms guide needs update for agent→IRC flow
  relates_to:                    # Cross-references to beads/docs
    - aegis-bcwn
  confidence: high               # high/medium/low
---

The actual verbatim human input goes here, unmodified.
Multiple lines preserved exactly as typed.
```

### Extrapolation Layer

Every Intent Record optionally includes an `extrapolation` block — the capturing
agent's interpretation of what the human meant and what it implies. This is
SEPARATE from the verbatim text but stored in the same file.

**Why**: "fix the IRC thing" is 5 words. The agent who received it knows WHICH
IRC thing, what context surrounded it, and what urgency was implied. Without
extrapolation, consumers get raw text and must re-derive context.

**Who writes it**: The agent who captures the input. They have session context.
If no agent can extrapolate (e.g., raw log capture), the field is null.

**Confidence levels**:

| Level | Meaning | Example |
|-------|---------|---------|
| high | Clear directive, unambiguous | "IRC is now a primary input channel" |
| medium | Implied from context | "fix the IRC thing" (agent infers which) |
| low | Ambiguous, multiple interpretations | "maybe we should think about IRC" |

**Rules**: Extrapolations disambiguate, identify implications, and cross-reference
related work. They do NOT paraphrase, speculate beyond evidence, judge correctness,
or include implementation details.

**Indexing**: Both verbatim text AND extrapolation text are indexed by Bobbin.
Search for "bidirectional IRC" should match the extrapolation even if the verbatim
only says "agents can talk back on IRC."

### Why This Format

- **YAML frontmatter + body**: Structured metadata on top, raw text below.
  Bobbin and any markdown indexer can parse this natively.
- **schema version**: Allows format evolution without breaking consumers.
- **ULID id**: Sortable by time, globally unique, no coordination needed.
- **Content hash**: Deduplication and integrity verification. Same input from
  two channels produces same hash — consumers can detect duplicates.
- **Channel-agnostic source block**: Every channel adapter fills the same fields;
  `channel_id` and `context` are channel-specific but the structure is universal.

### File Layout

```text
{archive_root}/
├── records/
│   ├── 2026/02/17/
│   │   ├── hi-01ARYZ6S41.md
│   │   └── hi-01ARYZ6S42.md
│   └── 2026/02/18/
│       ├── hi-01ARYZ7K01.md
│       └── hi-01ARYZ7K02.md
├── index/
│   └── catalog.jsonl            # Machine-readable index of all records
└── .state/
    ├── adapters/
    │   ├── telegram.cursor       # Last-processed position per adapter
    │   └── irc.cursor
    └── consumers/
        └── maldoon.cursor        # Last-read position per consumer
```

**Date-partitioned**: Easy to browse, backup, and age-off (though we keep forever).
**catalog.jsonl**: One JSON line per record with metadata (no body) — enables
fast filtering without reading individual files.

---

## 2. Storage Abstraction (arnold)

### Interface

The archive backend is abstracted behind a simple interface:

```text
Write(record IntentRecord) → error
Read(id string) → IntentRecord, error
Query(filter QueryFilter) → []IntentRecord, error
List(since time.Time, limit int) → []IntentRecord, error
Cursor(consumer string) → time.Time
SetCursor(consumer string, at time.Time) → error
```

### Implementation: Plain Files on ZFS

The first (and likely only) implementation uses the filesystem:

- **Write**: Create `{root}/records/YYYY/MM/DD/{id}.md`
- **Read**: Read file by ID (date prefix from ULID)
- **Query**: Read `catalog.jsonl`, filter, then read matching files
- **List**: Scan `catalog.jsonl` for records after cursor
- **Cursor**: Read/write `{root}/.state/consumers/{name}.cursor`

**Why filesystem, not a database**:

- ZFS snapshots = free versioning and backup
- Files = Bobbin indexes directly, grep works immediately
- No new services to operate (no MinIO, no additional Dolt load)
- Human-readable: Stiwi can browse the archive with a file manager
- Portable: rsync, tar, any tool works

**ZFS configuration**:

- Dataset: `tank/archive/human-intent`
- Compression: lz4 (text compresses well)
- Snapshots: daily automated
- Quota: 10G (generous for text)

### Future Backends

If the filesystem doesn't scale (unlikely for text), the interface supports:

- Object storage (S3/MinIO) — same interface, different Write/Read
- Database (Dolt/PostgreSQL) — records as rows
- But we don't build these until we need them.

---

## 3. Capture Pipeline (ellie)

### Architecture

A centralized bot per channel captures messages at the transport layer. Each
adapter normalizes to the Intent Record format before writing to storage.

```text
IRC (#aegis, #ops, ...) ──▶ aegis-irc adapter ──┐
                                                  │
Telegram (DMs, groups) ──▶ aegis-tg adapter ──────┤
                                                  ├──▶ Archive Writer ──▶ Storage
Session transcripts ──▶ session-harvester ────────┤
                                                  │
Future channels ──▶ new adapter ──────────────────┘
```

### Adapter Contract

Each channel adapter MUST:

1. **Normalize** to the Intent Record format (schema: human-intent/v2)
2. **Tag provenance** — human vs agent, with channel-specific metadata
3. **Handle reconnection/buffering** — no lost messages
4. **Batch writes** — every 5 minutes or N messages, whichever first
5. **Deduplicate** — via content hash (timestamp+author+content → SHA-256)
6. **Track cursor** — maintain per-adapter last-processed position

### Existing Adapters

| Adapter | Channel | Status | Notes |
|---------|---------|--------|-------|
| aegis-tg | Telegram | Exists — needs adapter extraction | Currently creates beads; add archive write |
| aegis-irc | IRC | Designed — ellie has full spec | See `crew/ellie/docs/designs/irc-conversation-and-lineage.md` |
| session-harvester | Claude Code sessions | New — post-session extraction | Needs human/system message filtering (hardest adapter) |

### Session Capture: Why Post-Hoc Extraction Fails

Analysis of 111 session transcripts (JSONL) reveals that **post-hoc extraction
cannot reliably distinguish human typing from system-injected instructions**.

Claude Code JSONL `type: "user"` entries break down as:

| Content Type | Count | Source |
|---|---|---|
| `list` of `tool_result` objects | ~95% | Tool responses (automated) |
| String: `[GAS TOWN] ...` | ~25% of strings | Gas Town startup hooks |
| String: `📬 ...` | ~11% of strings | Mail notification hooks |
| String: `<task-notification>...` | ~5% of strings | Task system |
| String: `[from ...]` | ~4% of strings | Sling injection (mayor/witness) |
| String: plain English | ~51% of strings | **AMBIGUOUS** |

The "plain English" category is the problem: both human typing AND `gt sling --args`
content appear as plain strings with no structural difference. "Search the codebase
for Prometheus config" could be Stiwi typing OR a mayor sling instruction.

**Conclusion: Heuristic filtering is NOT acceptable.** (Stiwi directive.)

### Session Capture: Provenance Marking at Entry Time

Instead of post-hoc extraction, we capture provenance AT THE POINT OF INPUT
using a Claude Code `UserPromptSubmit` hook. **(Stiwi decision: Option A chosen.
Option B — JSONL prefix marking — rejected as ZFC violation.)**

Gas Town already injects content via hooks. A new hook writes human input to
the archive in real-time:

```bash
# In .claude/hooks/UserPromptSubmit
# Gas Town already distinguishes human from system input at injection time.
# If the prompt was submitted by the human (not by a hook/sling), archive it.
if [ "$GT_INPUT_SOURCE" = "human" ]; then
  echo "$PROMPT_CONTENT" | gt-archive-writer --channel session --author stiwi
fi
```

This requires Gas Town to set `GT_INPUT_SOURCE` (or equivalent) to distinguish
human-submitted prompts from hook/sling-injected ones. Gas Town already knows
the difference — it's the injector.

**This is a Gas Town core change** — it goes into the gastown repo, not hometown.
It benefits any deployment, not just aegis.

### Pipeline Flow

```text
adapter captures → normalize to record → content hash → dedup check →
  write to storage → append to catalog.jsonl → git commit (batched hourly)
```

---

## 4. Search & Index (ian)

*Ian's full design is integrated below. See commit 12fa986 for the standalone
version history.*

### Role of Bobbin

Bobbin is the search/index layer. It does NOT capture or store raw input — it
indexes what's already in storage and makes it queryable.

```ini
[capture] → [storage] → [bobbin indexing] → [query API] → [consumers]
  ellie       arnold         ian               ian          maldoon + any agent
```

### Chunking Strategy: Speaker-Turn with Size Bounds

Human input varies from one-liners to multi-paragraph directives. Naive fixed-line
chunking would split directives mid-thought.

**Speaker-turn chunking** — chunk boundaries at:

1. **Frontmatter boundary** — each file starts a new chunk sequence
2. **Speaker turn** — when speaker changes (in multi-party transcripts)
3. **Temporal gap** — >5 minute silence within a session = new chunk
4. **Size cap** — single turn > 100 lines = split at paragraph breaks

This requires a new Bobbin language type: `transcript`. Language detector sees
`---` frontmatter with `source:` field → routes to transcript chunker.

Chunk metadata (using existing Chunk struct):

- `file_path`: archive path
- `chunk_type`: `ChunkType::Section` (reuse existing)
- `language`: `"transcript"` (new)
- `name`: source channel + timestamp (e.g., `telegram/2026-02-17T14:32`)
- `content`: verbatim text of that turn/segment

Standard pipeline: content → ONNX embedding → LanceDB vector store. No changes
to embedding or storage layer.

### Query API

#### Existing `/search` Endpoint (extended)

New filter parameters added to existing search:

| Parameter | Type | Description |
|-----------|------|-------------|
| `language` | string | Filter by language (e.g., `transcript`) |
| `after` | ISO date | Only chunks dated after this |
| `before` | ISO date | Only chunks dated before this |
| `channel` | string | Filter by source channel |

Maps to metadata filters on LanceDB vector search — no architectural change.

#### Dedicated `/archive/search` Endpoint

```text
GET /archive/search?q=bobbin+deployment&after=2026-02-01&channel=telegram&limit=5
```

Response:

```json
{
  "query": "bobbin deployment",
  "results": [
    {
      "id": "chunk-abc123",
      "content": "Deploy bobbin to luvu, not the old CT. Make sure traefik points to the new host.",
      "source": "telegram",
      "timestamp": "2026-02-15T09:14:00Z",
      "score": 0.87,
      "file_path": "transcripts/2026-02-15_telegram_session-xyz.txt"
    }
  ],
  "total": 1
}
```

Convenience wrapper — pre-filtered to `language=transcript` with archive-specific
response formatting.

#### Recent Input Feed

```text
GET /archive/recent?after=2026-02-17T00:00:00Z&limit=50
```

Chronologically ordered entries since timestamp. No semantic search — time-ordered
feed for maldoon's session-start check.

#### Specific Entry by ID

```text
GET /archive/entry/{id}
```

Returns a single Intent Record by ID. Used for referencing specific decisions
or transcripts in beads, docs, and discussions. The `id` field (ULID) is the
canonical reference for citation.

### Index Freshness

**Push model (preferred)**: Storage layer notifies Bobbin via webhook when new
files land. `POST /webhook/archive` with file list. Latency: seconds.

**Pull model (fallback)**: Periodic scan every 5 minutes. Same mechanism Bobbin
uses for git repos.

**Target**: New input searchable within 60 seconds (push) or 5 minutes (pull).

### Implementation Scope

~250 lines of Rust. No core architecture changes:

1. Transcript language detector (~50 lines)
2. Transcript chunker (~100 lines)
3. Archive search endpoints (~60 lines)
4. Archive webhook handler (~30 lines)
5. Config extension (~10 lines)

### Interface Contracts

| From | To | Interface |
|------|----|-----------|
| ellie (capture) | arnold (storage) | Raw transcript files with frontmatter |
| arnold (storage) | ian (bobbin) | Files at `archive_path` + webhook notification |
| ian (bobbin) | maldoon (consumer) | `/archive/search`, `/archive/entry/{id}`, `/archive/recent` |
| ian (bobbin) | any agent | Same HTTP API — no special access needed |

### Bobbin Context Integration

Configurable option: include the intent archive as part of `bobbin context`
output. When crew sessions start, they automatically receive recent human intent
as context — no explicit query needed.

Configuration (bobbin config):

```toml
[context.sources]
intent_archive = true       # Include intent archive in context output
intent_archive_days = 7     # How many days of recent intent to include
intent_archive_limit = 20   # Max records in context
```

This means every crew member starts their session knowing what Stiwi has said
recently. Reduces the "ask before searching" anti-pattern.

---

## 5. Consumer Workflows (maldoon)

### Primary Use Cases

#### 5.1 Directive Search — "Has Stiwi said anything about X?"

Before filing beads or setting priorities, search the archive first.

**Pattern**: keyword/semantic search → verbatim quotes with source
**When**: Before any strategic decision, priority change, or new initiative
**Result format**: Verbatim text + timestamp + channel source

#### 5.2 Priority Inference — "What does Stiwi care about most right now?"

Frequency analysis across recent input. If Stiwi mentions IRC 5 times in 2
days but Plex once, IRC is the higher priority.

**Pattern**: Recent input (7 days), ranked by topic frequency
**Result format**: Topic clusters with count and recency

#### 5.3 Contradiction Detection — "Did Stiwi change his mind?"

Surface chronological evolution of stance on a topic.

**Pattern**: Search topic, results sorted chronologically
**Result format**: All mentions with timestamps, newest first

#### 5.4 stiwi-wants.md Provenance — "What's the source for this entry?"

Every entry in stiwi-wants.md should cite an archive record.

**Pattern**: Link archive record IDs to document entries
**Result format**: Archive record ID/path as citation

### stiwi-wants.md Sync Workflow

Maldoon's warden patrol adds these steps:

1. **Every session**: Query archive for new input since last check (cursor)
2. **Diff against stiwi-wants.md**: New guidance not yet captured?
3. **Update stiwi-wants.md**: Add entries with archive citation
4. **Flag contradictions**: If new input contradicts existing entries, note it

### Consumer Interface Requirements

In priority order:

1. **Bobbin API**: `GET /archive/search?q=<query>` — semantic + keyword search
2. **Recent feed**: `GET /archive/recent?after=<timestamp>` — session-start check
3. **Record lookup**: `GET /archive/entry/{id}` — citation resolution
4. **Named commands**: `GET /cmd/intent-search?q=...` — pre-registered shortcuts (see §6)
5. **Structured output**: JSON with timestamp, source, verbatim text, record ID

### What Consumers DON'T Need

- Web UI (Tapestry adds later)
- Deduplication (consumers handle near-dupes)
- Sentiment analysis (verbatim is the point)
- Summarization (that's the agent's job, not the archive's)

---

## 6. Query Interface: Bobbin Named Commands

**No new `gt` command. No external wrappers.** (Stiwi directives — convenience
commands belong inside Bobbin, not as Justfile recipes or standalone tools.)

### Bobbin API (canonical)

All queries go through Bobbin's HTTP API:

```text
GET /archive/search?q=IRC+bidirectional&limit=5
GET /archive/recent?after=2026-02-17T00:00:00Z
GET /archive/entry/hi-01ARYZ6S41
```

Agents call these directly via HTTP or through MCP tools. This is the
canonical query interface — system-agnostic, works for any consumer.

### Named Commands (convenience)

Bobbin's **named commands** feature provides user-extensible aliases for common
query patterns, registered via API and invoked as `GET /cmd/{name}`.

See: `docs/designs/bobbin-commands.md` for the full commands design.

Pre-registered intent archive commands ship in config:

```toml
[commands.intent-search]
description = "Search human intent archive for a topic"
endpoint = "/archive/search"
required = ["q"]
[commands.intent-search.pinned]
language = "transcript"
[commands.intent-search.defaults]
mode = "semantic"
limit = "10"

[commands.intent-check]
description = "Check if Stiwi has given guidance on a topic"
endpoint = "/archive/search"
required = ["q"]
[commands.intent-check.pinned]
language = "transcript"
mode = "semantic"
[commands.intent-check.defaults]
limit = "3"
threshold = "0.75"

[commands.recent-input]
description = "Human input since a timestamp"
endpoint = "/archive/recent"
required = ["after"]
[commands.recent-input.defaults]
limit = "50"
```

Usage:

```bash
curl -s "search.svc/cmd/intent-search?q=IRC+deployment" | jq .
curl -s "search.svc/cmd/intent-check?q=dolt+security" | jq .
curl -s "search.svc/cmd/recent-input?after=2026-02-17T00:00:00Z" | jq .
```

Users and agents can register their own commands via `POST /cmd` without
restarting Bobbin. MCP tools get intent search for free.

---

## 7. Implementation Phases

### Phase 1: Foundation (P1)

1. Define Intent Record schema (this doc)
2. Create ZFS dataset + directory structure
3. Implement Telegram adapter (extract from existing beads)
4. Bobbin: add transcript language type + chunker
5. Bobbin: add `/archive/search`, `/archive/entry/{id}`, `/archive/recent`
6. Bobbin named commands for common queries (see bobbin-commands.md)
7. Backfill from existing `from:overseer` beads

**Outcome**: Maldoon can query "what has Stiwi said about X?" against all
Telegram history via Bobbin API.

### Phase 2: Multi-Channel (P2)

1. IRC adapter (ellie's aegis-irc integration)
2. Session transcript harvester (provenance marking via Gas Town)
3. Webhook push integration (capture → bobbin re-index)
4. stiwi-wants.md auto-sync workflow

**Outcome**: All input channels captured, semantically searchable.

### Phase 3: Ecosystem (P3)

1. Tapestry visualization (browse archive, see lineage chains)
2. Live capture hooks (real-time, not batch)
3. Cross-deployment support (other Gas Town hometowns)

---

## Risks

1. **Session transcript noise** — Phase 2's hardest problem. Start with
   Telegram (clean) to prove value before tackling transcripts.
2. **Bobbin readiness** — If Bobbin isn't ready, fall back to ripgrep over
   the archive directory. Not as good, but functional.
3. **Volume** — IRC may produce high volume. Date partitioning + catalog.jsonl
   index keeps file count manageable per directory.
4. **Human input sovereignty** — This archive stores what a human said. It
   must NEVER be modified by agents. Append-only is enforced by the interface.
   ZFS snapshots provide tamper evidence.
