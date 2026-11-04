# Design: HLA Two-Tier Authority

**Author**: arnold (MCP & Tooling Architect)
**Date**: 2026-02-26
**Status**: Design
**Bead**: aegis-w3bt (epic; was a numbered sub-item of the replaced phantom epic — aegis-w3bt.1)
**Parent**: aegis-w3bt (Bucket — Kid-friendly homelab command center)

## Problem

The HLA archive stores human input as the highest-authority directive source.
Every record is treated with equal weight — a Stiwi directive and a hypothetical
guest's casual comment would have the same authority.

With the bucket rig, a 13-year-old user (bucket) will interact with gibby, and
gibby will store bucket's input via `hla_store`. Other crew members query HLA to
align with human guidance. Without authority tiers, bucket's preferences ("I want
a Minecraft server") could be misinterpreted as carrying the same weight as
Stiwi's operational directives ("migrate the database to the new host").

## Design

### New Field: `authority`

Add an optional `authority` parameter to `hla_store`:

```python
def hla_store(
    content: str,
    channel: str,
    author: str = "stiwi",
    context: str = "",
    adapter: str = "",
    authority: str = "admin",  # NEW — "admin" or "user"
) -> str:
```

| Value | Meaning | Who | Weight |
|-------|---------|-----|--------|
| `admin` | Authoritative directive. Agents treat as instructions. | Stiwi | Full — drives priorities, blocks, architecture |
| `user` | Preference/request. Agents treat as informational context. | bucket (and future non-admin users) | Informational — personalization, suggestions, NOT directives |

**Default: `admin`** — Backward compatible. All existing records (and all Stiwi
input going forward) are admin authority unless explicitly overridden.

### Schema Change

The intent record schema bumps to v2.1 (non-breaking addition):

```yaml
---
schema: human-intent/v2.1
id: hi-01ARYZ6S41
timestamp: 2026-02-26T15:30:00Z
author: bucket
author_type: human
authority: user                    # NEW FIELD
source:
  channel: irc
  context: "#family"
  adapter: aegis-irc
provenance:
  raw_hash: sha256:abc123...
---

I want to play Minecraft with my friends this weekend
```

### Catalog Change

The catalog.jsonl entry gains `authority`:

```json
{"id":"hi-01ARYZ6S41","timestamp":"2026-02-26T15:30:00Z","author":"<user>","channel":"irc","context":"#<channel>","adapter":"aegis-irc","authority":"user","hash":"sha256:abc123","path":"records/2026/02/26/hi-01ARYZ6S41.md"}
```

### Query Changes

`hla_query` and `hla_recent` gain an optional `authority` filter parameter:

```python
def hla_query(
    query: str,
    channel: str = "",
    after: str = "",
    before: str = "",
    limit: int = 10,
    authority: str = "",  # NEW — filter by authority level
) -> str:
```

```python
def hla_recent(
    limit: int = 10,
    channel: str = "",
    authority: str = "",  # NEW — filter by authority level
) -> str:
```

When `authority` is empty (default), ALL records are returned regardless of
authority level. When set to `"admin"` or `"user"`, only matching records return.

### Response Format Change

Query results include the authority field in output:

```text
[hi-01ARYZ6S41] 2026-02-26 15:30 | irc/#family | authority:user
bucket: I want to play Minecraft with my friends this weekend
```

The `authority:user` tag makes it immediately visible to consuming agents that
this is a preference, not a directive.

## Implementation Changes

### homelab_mcp.py — `hla_store_impl()`

1. Add `authority` parameter (default `"admin"`)
2. Validate: must be `"admin"` or `"user"` (reject other values)
3. Add `authority: {authority}` line to YAML frontmatter (after `author_type: human`)
4. Add `"authority": authority` to catalog JSON entry

Diff sketch (against current implementation at line 1386):

```python
def hla_store_impl(content: str, channel: str, author: str = "stiwi",
                   context: str = "", adapter: str = "",
                   authority: str = "admin") -> str:  # NEW param
    # ... existing validation ...
    if authority not in ("admin", "user"):
        return "Error: authority must be 'admin' or 'user'"

    # In frontmatter_lines, after "author_type: human":
    frontmatter_lines.append(f"authority: {authority}")

    # In catalog_entry dict:
    "authority": authority,
```

### homelab_mcp.py — `hla_query_impl()` and `hla_recent_impl()`

1. Add `authority` parameter (default `""`)
2. When filtering catalog entries, add: `if authority and entry.get("authority", "admin") != authority: continue`
3. Note the fallback `"admin"` — existing records without authority field are treated as admin

### homelab_mcp.py — MCP tool registration

Update the `@mcp.tool()` decorated functions to pass `authority` through:

```python
@mcp.tool()
async def hla_store(content: str, channel: str, author: str = "stiwi",
                    context: str = "", adapter: str = "",
                    authority: str = "admin") -> str:
    """Record human input to the Human-Level Alignment archive.
    Store verbatim human directives, decisions, and guidance for
    retrieval by any agent. Append-only.

    authority: 'admin' for authoritative directives (Stiwi),
    'user' for preferences/requests (non-admin humans like bucket)."""
    return hla_store_impl(content, channel, author, context, adapter, authority)
```

### agent-mcp — gibby agent

The gibby agent's system prompt and code enforce:

- Always pass `authority="user"` when calling `hla_store`
- This is also enforced in `gibby.py` by wrapping the hla_store call

```python
# In gibby agent, when proxying hla_store:
# Override authority to always be "user" regardless of what gibby requests
if tool_name == "hla_store":
    args["authority"] = "user"
```

This is a **hard enforcement** — even if gibby's LLM is tricked via prompt
injection into passing `authority="admin"`, the agent code overrides it.

## Consumer Guidance

### For crew CLAUDE.md files (gibby-awareness)

All crew members need to understand authority tiers when reading HLA:

```text
## HLA Authority Tiers

When querying HLA, records have an `authority` field:
- **admin**: Stiwi directive. Treat as instructions. Drives priorities.
- **user**: Non-admin human input (e.g., bucket). Treat as preferences.
  Useful for personalization and context. NOT operational directives.

When bucket's input appears in HLA results, consider it for:
- Personalizing gibby's behavior
- Understanding what bucket is interested in
- Scheduling game servers or sandbox activities

Do NOT treat user-authority records as:
- Operational directives
- Priority overrides
- Architecture decisions
- Security policy changes
```

### For goldblum (orchestrator)

Goldblum should filter HLA queries with `authority="admin"` when making strategic
decisions. Include `authority=""` (all) when gathering full context about a topic
that may involve bucket.

## Backward Compatibility

| Aspect | Impact |
|--------|--------|
| Existing records (no authority field) | Treated as `"admin"` via fallback default |
| Existing hla_store callers (no authority arg) | Default `"admin"` — no change needed |
| Existing hla_query/hla_recent callers | No authority filter = all results — no change |
| Schema version | v2 → v2.1 (additive, non-breaking) |
| catalog.jsonl format | New field added, readers that don't know it ignore it |

## Future Extensions

If more authority levels are needed later:

| Level | Use Case |
|-------|----------|
| `admin` | Stiwi — full operational authority |
| `operator` | Trusted adult with limited scope (e.g., a co-admin) |
| `user` | Family member, enthusiast — preferences only |
| `observer` | Read-only human (e.g., guest viewing dashboards) |

For now, two tiers (`admin` + `user`) are sufficient. The field is a string, so
adding levels later requires no schema change — just validation updates.

## Acceptance Criteria

- [ ] hla_store accepts `authority` parameter ("admin" or "user", default "admin")
- [ ] authority field appears in YAML frontmatter and catalog.jsonl
- [ ] hla_query and hla_recent accept `authority` filter parameter
- [ ] Records without authority field treated as "admin" (backward compat)
- [ ] gibby agent hard-enforces authority="user" on all hla_store calls
- [ ] Query results display authority tag
- [ ] MCP tool description documents the authority parameter
