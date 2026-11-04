# Design: HLA as MCP Tools (§54)

> Stiwi directive (2026-02-19): "I want a proper tool integrated with homelab
> MCP, this is a first class primitive of our homelab and should be enabled as
> such and highly accessible across all agents to ensure their activity is
> highly aligned with human input."

## Context

The Human-Level Alignment archive (HLA) is designed in `human-intent-archive.md`
as a filesystem-backed archive of human input. Currently, no implementation exists.
Stiwi wants HLA as first-class MCP tools — same level as `container_status` or
`service_health`.

## Tools

Three tools added to homelab-mcp:

### `hla_store` — Record Human Input

```python
@mcp.tool()
def hla_store(
    content: str,
    channel: str,
    author: str = "stiwi",
    context: str = "",
    adapter: str = "",
) -> str:
    """Record human input to the Human-Level Alignment archive.
    Store verbatim human directives, decisions, and guidance for
    retrieval by any agent. Append-only — agents cannot modify
    existing records."""
```

**Parameters:**
| Param | Required | Description |
|-------|----------|-------------|
| content | yes | Verbatim human input text |
| channel | yes | Source channel: telegram, irc, session, manual |
| author | no | Human identity (default: stiwi) |
| context | no | Channel-specific context (dm, #channel, session:arnold) |
| adapter | no | Which adapter captured this (aegis-tg, aegis-irc, etc.) |

**Returns:** Record ID (hi-{ulid}) + confirmation.

**Implementation:**

1. Generate ULID for record ID
2. Compute SHA-256 content hash for dedup
3. Write YAML frontmatter + body to `{archive}/records/YYYY/MM/DD/hi-{ulid}.md`
4. Append to `{archive}/index/catalog.jsonl`
5. Return record ID

**Security:** Only records with `author_type: human` are accepted. Agents call
this tool on behalf of humans (channel adapters), not to record their own output.

### `hla_query` — Search the Archive

```python
@mcp.tool()
def hla_query(
    query: str,
    channel: str = "",
    after: str = "",
    before: str = "",
    limit: int = 10,
) -> str:
    """Search the Human-Level Alignment archive for human directives
    and decisions. Use this before any strategic decision to check
    if the human has given guidance on the topic."""
```

**Parameters:**
| Param | Required | Description |
|-------|----------|-------------|
| query | yes | Search terms (keyword match against content + metadata) |
| channel | no | Filter by source channel |
| after | no | Only records after this date (YYYY-MM-DD or RFC3339) |
| before | no | Only records before this date |
| limit | no | Max results (default: 10) |

**Returns:** Matching records with: id, timestamp, channel, content snippet.

**Implementation (v0.1 — no Bobbin dependency):**

1. Read `{archive}/index/catalog.jsonl`
2. Filter by date range and channel
3. Grep content files for keyword matches
4. Return formatted results

**Implementation (v0.2 — with Bobbin):**

1. Call `GET search.svc/archive/search?q={query}&channel={channel}&after={after}&limit={limit}`
2. Format and return results

v0.1 uses direct file access. v0.2 upgrades to semantic search when Bobbin
archive endpoints are ready. The tool interface stays identical.

### `hla_recent` — Latest Directives

```python
@mcp.tool()
def hla_recent(
    limit: int = 10,
    channel: str = "",
) -> str:
    """Get the most recent human directives from the HLA archive.
    Use this at session start to check for recent human guidance."""
```

**Parameters:**
| Param | Required | Description |
|-------|----------|-------------|
| limit | no | Number of recent records (default: 10, max: 50) |
| channel | no | Filter by source channel |

**Returns:** Last N records, newest first, with: id, timestamp, channel, content.

**Implementation:**

1. Read last N lines from `{archive}/index/catalog.jsonl`
2. Filter by channel if specified
3. Read content from matching files
4. Return formatted, newest first

## Architecture

```text
Channel adapters (aegis-tg, aegis-irc, session hooks)
         │
         ▼ hla_store (MCP tool)
   ┌─────────────┐
   │  Archive FS  │  /mnt/hla/ on automation.lan (rclone FUSE → Garage S3)
   │  (S3-backed) │  records/, index/, .state/
   └──────┬──────┘
          │
          ▼ hla_query / hla_recent (MCP tools)
   ┌─────────────┐
   │  All agents  │  via homelab-mcp (port 3002)
   └─────────────┘
```

homelab-mcp runs on automation.lan (CT 215). Archive lives on Garage S3 (CT 241),
accessed via rclone FUSE mount at `/mnt/hla` on automation.lan. Tools use direct
filesystem I/O — no SSH to remote containers.

> **DEPRECATED (2026-03-05)**: CT 228 (hla.lan) previously hosted the archive at
> `/opt/hla/`. Data migrated to Garage S3 bucket `hla` (goldblum commit 3a92029c,
> 2026-03-02). CT 228 is marked for decommission (aegis-iq7f82).

## Agent Access

All agents get HLA tools. No role restriction in agent-mcp — this is a universal
primitive per Stiwi's directive.

Agent-mcp tool allowlists (DONE):

- L1 Tech: hla_query, hla_recent (read-only)
- DevOps: hla_query, hla_recent (read-only)
- Project Manager: hla_query, hla_recent, hla_store (PM records directives)
- Owner/Reviewer: hla_query, hla_recent, hla_store

Hammond (human-interactive) gets all three tools via direct homelab-mcp access.

## Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| ~~hla.lan container (CT 228)~~ | **Deprecated** | Decommissioned — data on Garage S3 now |
| Archive directory structure | **Done** | `/mnt/hla/{records,index,.state}` via rclone FUSE on automation.lan |
| ~~SSH from automation.lan→hla.lan~~ | **Deprecated** | No longer needed — direct FUSE mount |
| python-ulid on automation.lan | **Done** | `pip install python-ulid` (v3.1.0) |
| Bobbin /archive endpoints | Not yet | v0.2 upgrade for semantic search |
| ZFS mount permissions fix | Pending | Host-level chown needed for /var/lib/hla |

## Implementation Beads

1. **aegis-ojwnx**: Create ZFS dataset + archive directory structure — REVISED: directory structure created at /opt/hla on CT 228 (now deprecated; live data on Garage S3)
2. **aegis-xxdze**: Implement hla_store, hla_query, hla_recent in homelab-mcp — DONE
3. **aegis-si2oo**: Agent-mcp allowlists — DONE (homelab-mcp branch polecat/chrome/hla-allowlists, deployed+restarted on CT 215)
4. Wire aegis-tg adapter to call hla_store — pending

## Token Efficiency

Tool responses follow homelab-mcp compact patterns:

- hla_query: max 200 chars per result snippet, truncate long content
- hla_recent: max 150 chars per record, focus on actionable content
- hla_store: minimal response — just record ID + confirmation

## Coordination

- **ian (bobbin)**: v0.2 upgrade needs `/archive/search` endpoint in Bobbin.
  v0.1 is independent — no Bobbin dependency.
- **ellie (capture)**: Channel adapters (aegis-tg, aegis-irc) need to call
  hla_store tool after capturing human input.
- **hammond**: Direct MCP access for manual directive recording.
