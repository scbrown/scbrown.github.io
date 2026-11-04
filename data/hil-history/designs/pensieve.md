# Design: Pensieve — Agent Memory Archive (§72)

**Author**: arnold (MCP & Tooling Architect)
**Date**: 2026-02-27
**Status**: Active — PO: ian (Stiwi directive 2026-03-05). Needs advancement.
**Bead**: aegis-rh8
**HLA ref**: hi-01KJES90V3A2F0F3RKEHR4Q95V

> Stiwi directive: "Pensieve is the Claude-side counterpart to HLA. Agents
> already write MEMORY.md instinctively — aggregate, index, and make searchable."

## The Abstraction

Where HLA captures **human input** (directives, decisions, guidance), Pensieve
captures **agent observations** (discoveries, patterns, debugging insights,
architectural knowledge). Named after Dumbledore's Pensieve — a basin for
extracting and reviewing memories.

Agents already maintain MEMORY.md files instinctively via Claude Code's
auto-memory feature. Today these files are:

- **Isolated**: each agent sees only its own MEMORY.md
- **Unindexed**: no cross-agent search
- **Ephemeral**: lost if project dirs are cleaned up
- **Unstructured**: free-form markdown, no schema

Pensieve formalizes this into a searchable, persistent, cross-agent archive.

### HLA vs Pensieve

| Dimension | HLA | Pensieve |
|-----------|-----|----------|
| **Source** | Human input (verbatim) | Agent observations |
| **Authority** | Canonical (human sovereignty) | Advisory (agent-derived) |
| **Mutability** | Append-only, humans only | Agents can update/supersede |
| **Schema** | `human-intent/v2.1` | `agent-memory/v1` |
| **Location** | Garage S3 via `/mnt/hla/` on automation.lan (was CT 228) | Garage S3 via `/mnt/pensieve/` on automation.lan (was CT 228) |
| **MCP prefix** | `hla_*` | `pensieve_*` |
| **Trust level** | Ground truth | Best-effort knowledge |

**Key principle**: Pensieve records are NEVER authoritative over HLA records.
If an agent memory contradicts a human directive, the human directive wins.

---

## 1. Data Format

### The Memory Record

```yaml
---
schema: agent-memory/v1
id: pm-<ulid>
timestamp: 2026-02-27T01:00:00Z
agent: aegis/crew/arnold
agent_role: crew
rig: aegis
source:
  type: memory_md           # memory_md | session_observation | manual
  file: MEMORY.md           # source file within agent's memory dir
  session: bb57b38d-...     # session ID (if available)
topics:
  - mcp-tools
  - homelab-mcp
  - performance
supersedes: null             # pm-<ulid> of record this replaces (if updated)
confidence: high             # high/medium/low
provenance:
  content_hash: sha256:abc123...
---

## MCP Tool Health (confirmed 2026-02-22)
- All 21+ homelab-mcp tools functional, agent-mcp tools also working
- prometheus_query: FIXED (was 401)
- queue_depth: STABLE (was fragile)
```

### Why This Format

- **Mirrors HLA**: Same YAML frontmatter + body pattern. Agents and tools already
  understand this format. Bobbin's transcript chunker works on it.
- **`supersedes` field**: Unlike HLA (append-only), agent knowledge evolves.
  When an agent updates a memory, the new record points to the old one. Both
  are searchable but consumers see the latest.
- **`topics` array**: Agent memories are topical. HLA records are verbatim
  utterances. Topics enable faceted search ("show me everything agents know
  about Traefik").
- **`confidence`**: Agents should flag uncertain observations. Consumers can
  filter to high-confidence records for decision-making.
- **Agent identity**: Full Gas Town address (`rig/role/name`) so consumers
  can filter by expertise domain.

### File Layout

```text
/opt/pensieve/
├── records/
│   ├── 2026/02/27/
│   │   ├── pm-01KJFX7A01.md
│   │   └── pm-01KJFX7A02.md
│   └── ...
├── index/
│   └── catalog.jsonl        # One JSON line per record (metadata, no body)
└── .state/
    ├── harvest/
    │   ├── arnold.cursor    # Last-harvested position per agent
    │   └── ellie.cursor
    └── consumers/
        └── bobbin.cursor    # Consumer read positions
```

---

## 2. Harvest Pipeline

### Source: Claude Code Auto-Memory

All crew MEMORY.md files live at:

```text
~/.claude-accounts/current/projects/-home-braino-gt-<rig>-<role>-<name>/memory/MEMORY.md
```

**Current inventory** (11 crew agents, ~854 total lines):

| Agent | Rig | Lines | Topics |
|-------|-----|-------|--------|
| ellie | aegis | 184 | IaC, deployment, services |
| gibby | bucket | 93 | messaging, family routing |
| goldblum | aegis | 90 | infrastructure, debugging |
| dearing | aegis | 89 | routing, SSH patterns |
| arnold | aegis | 82 | MCP, performance, formulas |
| strider | bobbin | 75 | build system, search |
| maldoon | aegis | 72 | monitoring, warden patrol |
| malcolm | aegis | 60 | architecture, design |
| ian | bobbin | 41 | Bobbin, Traefik |
| mayor | gastown | 37 | dispatch, patrol |
| sentinel | aegis | 31 | security, monitoring |

### Harvest Modes

#### Mode 1: Cron Harvest (primary)

A cron job on luvu (the host running Gas Town) periodically:

1. Scans `~/.claude-accounts/current/projects/*/memory/MEMORY.md`
2. Parses each file into sections (heading-delimited)
3. Computes content hash per section
4. Compares against last-harvested hash (per-agent cursor)
5. New/changed sections → create Pensieve records via FUSE mount on automation.lan
6. Updates cursor

**Frequency**: Every 15 minutes (crew members update MEMORY.md at session end).

**Section parsing**: MEMORY.md files use `##` headings to delimit topics.
Each heading becomes a separate Pensieve record. This preserves the topical
structure agents already use.

```bash
#!/bin/bash
# /home/braino/gt/scripts/pensieve-harvest.sh
# Runs via cron on luvu every 15 minutes

MEMORY_ROOT="$HOME/.claude-accounts/current/projects"
PENSIEVE_HOST="automation.lan"  # Was CT 228, now local FUSE mount
ARCHIVE="/opt/pensieve"

for memfile in "$MEMORY_ROOT"/*/memory/MEMORY.md; do
    # Extract agent identity from path
    agent_dir=$(basename "$(dirname "$(dirname "$memfile")")")
    # -home-braino-gt-aegis-crew-arnold → aegis/crew/arnold
    agent=$(echo "$agent_dir" | sed 's/^-home-braino-gt-//; s/-/\//g')

    # Parse sections, hash, compare, write new records
    pensieve-harvest --agent "$agent" --file "$memfile" --host "$PENSIEVE_HOST"
done
```

#### Mode 2: Session Hook (future, complementary)

A Claude Code `PostToolUse` or session-end hook that captures memory writes
in real-time. More complex, requires Gas Town integration. Phase 2.

#### Mode 3: Manual Store (via MCP tool)

Agents can explicitly store observations via `pensieve_store` MCP tool.
For ad-hoc discoveries that don't belong in MEMORY.md (e.g., "CT 212 has
a corrupt systemd unit file").

---

## 3. MCP Tools

Three tools, mirroring HLA's pattern. Added to homelab-mcp.

### `pensieve_store` — Record Agent Observation

```python
@mcp.tool()
def pensieve_store(
    content: str,
    agent: str,
    topics: str = "",        # Comma-separated topic tags
    confidence: str = "high",
    supersedes: str = "",    # pm-<ulid> to supersede
) -> str:
    """Record an agent observation to the Pensieve archive.
    Store discoveries, patterns, and learned context for cross-agent retrieval.
    Use for insights that other agents would benefit from knowing."""
```

**Implementation**:

1. Generate ULID → `pm-{ulid}`
2. Compute SHA-256 content hash (dedup)
3. Build YAML frontmatter from parameters
4. Write to `/mnt/pensieve/records/YYYY/MM/DD/pm-{ulid}.md` on automation.lan
5. Append to `{archive}/index/catalog.jsonl`
6. If `supersedes` set, update catalog entry for old record with `superseded_by`
7. Return record ID

### `pensieve_query` — Search Agent Memories

```python
@mcp.tool()
def pensieve_query(
    query: str,
    agent: str = "",         # Filter by agent identity
    topic: str = "",         # Filter by topic tag
    rig: str = "",           # Filter by rig
    after: str = "",
    before: str = "",
    limit: int = 10,
) -> str:
    """Search the Pensieve archive for agent observations and discoveries.
    Use to find what other agents have learned about a topic before
    investigating yourself."""
```

**Implementation** (v0.1 — file-based, same as HLA):

1. Read `catalog.jsonl`, filter by date/agent/topic/rig
2. Grep matching record files for keyword matches
3. Return formatted results (200 char snippets)

**Implementation** (v0.2 — Bobbin):

1. `GET search.svc/pensieve/search?q={query}&agent={agent}&topic={topic}`

### `pensieve_recent` — Latest Agent Observations

```python
@mcp.tool()
def pensieve_recent(
    limit: int = 10,
    agent: str = "",
    rig: str = "",
) -> str:
    """Get recent agent observations from the Pensieve archive.
    Use at session start to see what other agents have recently discovered."""
```

---

## 4. Agent Access

All agents get read access. Write access is role-dependent.

| Role | Tools | Rationale |
|------|-------|-----------|
| All agents | pensieve_query, pensieve_recent | Universal read — everyone benefits from shared knowledge |
| Crew workers | + pensieve_store | Crew members generate insights worth archiving |
| Polecats | pensieve_query, pensieve_recent only | Transient workers read but don't write (harvester captures their MEMORY.md) |
| L1 Tech (agent-mcp) | pensieve_query, pensieve_recent | Diagnostic context from past investigations |
| PM (agent-mcp) | + pensieve_store | PM records coordination insights |

---

## 5. Bobbin Integration (Phase 2)

Same pattern as HLA — Bobbin indexes Pensieve records alongside the intent
archive.

**New language type**: `agent-memory` (chunker recognizes `schema: agent-memory/v1`)

**Endpoints**:

- `GET /pensieve/search?q=<query>&agent=<agent>&topic=<topic>`
- `GET /pensieve/recent?after=<timestamp>&limit=<n>`
- `GET /pensieve/entry/<id>`

**Named commands** (bobbin config):

```toml
[commands.agent-knowledge]
description = "Search what agents have learned about a topic"
endpoint = "/pensieve/search"
required = ["q"]
[commands.agent-knowledge.defaults]
limit = "10"

[commands.agent-recent]
description = "Recent agent discoveries"
endpoint = "/pensieve/recent"
[commands.agent-recent.defaults]
limit = "20"
```

---

## 6. Separation from HLA

**Critical**: Pensieve and HLA MUST remain separate systems sharing infrastructure.

- **Separate directories**: `/mnt/hla/` vs `/mnt/pensieve/` on automation.lan (Garage S3 via rclone FUSE)
- **Separate catalogs**: Each has its own `catalog.jsonl`
- **Separate MCP tool prefixes**: `hla_*` vs `pensieve_*`
- **Separate ID prefixes**: `hi-<ulid>` vs `pm-<ulid>`
- **Separate authority**: HLA = canonical human truth; Pensieve = advisory agent knowledge
- **Same backend**: Garage S3 (CT 241) hosts both, mounted on automation.lan
- **Same patterns**: YAML frontmatter, date-partitioned records, JSONL catalog

An agent searching for guidance should check HLA first, Pensieve second.

---

## 7. Storage Backend

> **Update (2026-03-05)**: Garage S3 backend is now the live implementation.
> CT 228 (hla.lan) has been deprecated. Data lives on Garage S3 (CT 241),
> accessed via rclone FUSE mounts on automation.lan at `/mnt/hla` and `/mnt/pensieve`.

Both HLA and Pensieve use Garage S3 storage, mounted locally via rclone FUSE.
This provides S3 durability with filesystem-level simplicity (grep, ls, cat all work).

---

## 8. Implementation Phases

### Phase 1: Foundation (P2 — design + infrastructure)

1. ~~Create `/opt/pensieve/{records,index,.state}` on CT 228~~ Done — now on Garage S3 via `/mnt/pensieve/` on automation.lan
2. Write `pensieve-harvest.sh` cron script (section parser + SSH writer)
3. Implement `pensieve_store`, `pensieve_query`, `pensieve_recent` in homelab-mcp
4. Add to agent-mcp allowlists
5. Initial harvest of all 11 crew MEMORY.md files
6. Deploy cron on luvu (15-minute interval)

**Outcome**: Agents can query "what do other agents know about X?" via MCP.

### Phase 2: Intelligence (P3)

1. Bobbin `agent-memory` language type + chunker
2. Bobbin `/pensieve/*` endpoints
3. Session hook for real-time capture
4. Topic auto-extraction (parse `##` headings into topic tags)
5. Supersession chain traversal in query results

**Outcome**: Semantic search across all agent knowledge.

### Phase 3: Ecosystem (P3)

1. Tapestry visualization (browse agent knowledge graph)
2. Cross-reference: link Pensieve records to HLA records and beads
3. Knowledge decay: flag stale records (agent hasn't confirmed in N days)
4. Conflict detection: surface contradictions between agent observations

---

## 9. Implementation Beads

Beads to file (Phase 1 scope):

| Bead | Type | Description | Rig |
|------|------|-------------|-----|
| 1 | task | ~~Create `/opt/pensieve/` directory structure on CT 228~~ Done (now on Garage S3) | aegis |
| 2 | task | Implement `pensieve_store/query/recent` in homelab-mcp | homelab-mcp (aegis) |
| 3 | task | Add pensieve tools to agent-mcp allowlists | aegis |
| 4 | task | Write `pensieve-harvest.sh` cron script + deploy | aegis |
| 5 | task | Initial backfill: harvest all crew MEMORY.md files | aegis |

Dependencies: 1 → 2 → 3 (serial); 1 → 4 → 5 (serial); 2 and 4 are parallel after 1.

---

## 10. Token Efficiency

Same compact patterns as HLA:

- `pensieve_query`: max 200 chars per result snippet
- `pensieve_recent`: max 150 chars per record
- `pensieve_store`: minimal response — just record ID + confirmation
- Topic tags in catalog.jsonl enable pre-filtering without reading file content

---

## 11. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Agent MEMORY.md format varies | Section parser handles `##`-delimited and flat formats |
| Harvest misattributes agent identity | Path convention is deterministic; validate against known agents |
| Stale memories archived as current | `confidence` field + `supersedes` chain + harvest timestamps |
| Volume from frequent updates | Content hashing deduplicates; only changed sections create records |
| Confusion with HLA records | Separate prefixes (`pm-` vs `hi-`), separate tools, separate dirs |
| ~~CT 228 load~~ Garage S3 load from both HLA + Pensieve | Text workload is minimal; FUSE mount handles I/O transparently |
