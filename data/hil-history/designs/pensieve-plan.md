# Pensieve — Agent Memory Archive

## Context

Agents instinctively write `MEMORY.md` files capturing infrastructure facts, debugging lessons, operational patterns, and gotchas. These 11 files (~846 lines, ~30K tokens) are currently siloed per-agent. The same lessons get rediscovered independently (DNS routing, auth gotchas, bead routing policy — each found by 3+ agents).

Pensieve aggregates, deduplicates, and makes agent memories searchable across all agents. It's the Claude-side counterpart to HLA (Human Lineage Archive): HLA captures what Stiwi says, Pensieve captures what agents learn.

**Key property:** Zero behavior change. Agents write MEMORY.md as they already do. Bobbin indexes Pensieve. Other agents receive cross-agent knowledge via Bobbin injection automatically.

## Architecture

```text
Agent writes MEMORY.md (instinctive, unchanged)
        |
        v
pensieve-harvest (cron, every 2hr on automation.lan)
  - splits MEMORY.md into sections by ## headings
  - deduplicates by content hash
  - writes records to /mnt/pensieve/records/ on automation.lan (Garage S3 via rclone FUSE)
        |
        v
rsync to kota.lan (part of bobbin reindex timer)
        |
        v
bobbin index --repo pensieve
        |
        v
Bobbin UserPromptSubmit hook injects relevant memories
        |
        v
Agent receives cross-agent knowledge without knowing Pensieve exists
```

## Decisions

| Decision | Choice |
|----------|--------|
| Repo | **Own repo** (`pensieve`) on git.svc — harvester script, MCP tools, design docs |
| Data storage | Garage S3 via `/mnt/pensieve/` on automation.lan (was CT 228) |
| Collection | Cron harvest every 2hr on automation.lan (CT 215) |
| Record format | YAML frontmatter + markdown body (mirrors HLA pattern) |
| Record prefix | `pm-{ulid}` (pensieve memory) |
| Schema | `pensieve/v1` |
| Dedup | Content-hash exact dedup (Phase 1). Semantic canon layer (Phase 2, future) |
| Search | Bobbin indexes records. MCP tools for direct queries. |
| Agent store tool | **None** — agents don't call Pensieve. They write MEMORY.md. |

## Storage Layout (Garage S3 via automation.lan, was CT 228)

```text
/opt/pensieve/
  records/{agent}/pm-{ulid}.md     # Individual memory entries
  snapshots/{agent}/{YYYY-MM-DD}.md # Full MEMORY.md snapshots
  index/catalog.jsonl               # Append-only index
  .state/last-harvest.json          # Per-agent harvest timestamps
```

## Record Format

```yaml
---
schema: pensieve/v1
id: pm-01JNKX7GHB...
timestamp: 2026-02-27T14:30:00Z
agent: malcolm
section: "DNS .svc vs .lan (P0 fix, 2026-02-19)"
content_hash: sha256:a1b2c3...
source_file: .../-home-braino-gt-aegis-crew-malcolm/memory/MEMORY.md
---

- `*.svc` DNS wildcard resolves ALL .svc hostnames to Traefik
- Node_exporter targets MUST use `.lan:9100`, NOT `.svc:9100`
```

## Repo Structure (`pensieve`)

```text
pensieve/
  CLAUDE.md
  harvest/
    pensieve-harvest.py            # Core harvester (~200 lines Python)
  mcp/
    pensieve_tools.py              # MCP tool implementations (query, recent)
  docs/
    design.md                      # This design
  README.md
```

## MCP Tools (added to homelab-mcp)

- **`pensieve_query(query, agent="", limit=10)`** — Search agent memories
- **`pensieve_recent(limit=10, agent="")`** — Latest harvested memories

No `pensieve_store` — collection is passive via harvest.

## Implementation Plan

### Phase 0: Repo + Bootstrap

1. Create `pensieve` repo on git.svc
2. Register as Gas Town rig (`gt rig add pensieve`)
3. ~~Create `/opt/pensieve/` directory structure on CT 228~~ Done (now on Garage S3)
4. Write `pensieve-harvest.py` — the core harvester script
5. Backfill all 11 existing MEMORY.md files (~80-100 sections)
6. Deploy cron on automation.lan: `0 */2 * * * pensieve-harvest.py`

### Phase 1: Search Integration

1. ~~Add rsync step to Bobbin reindex timer (kota syncs from hla.lan)~~ Replaced by Garage S3 FUSE mount
2. Add `--repo pensieve` to reindex script
3. Add `pensieve_query` and `pensieve_recent` to homelab-mcp
4. Deploy updated homelab-mcp

### Phase 2: IaC (future)

1. Ansible role for pensieve directory provisioning (goldblum)
2. Ansible role for harvest cron (automation.lan)
3. rsync step in bobbin_server role

### Phase 3: Canon Layer (future, when overlap is painful)

1. Semantic clustering via Bobbin + Claude
2. Canonical fact entries in `canon/` directory
3. `pensieve_canon` MCP tool

## Files to Modify

| File | Change |
|------|--------|
| `homelab-mcp/homelab_mcp.py` | Add pensieve_query, pensieve_recent MCP tools |
| Bobbin reindex script on kota | Add rsync + `--repo pensieve` |
| ~~CT 228 filesystem~~ | ~~Create `/opt/pensieve/` directory tree~~ Done (Garage S3) |
| CT 215 crontab | Add harvest cron entry |

## Verification

1. Run harvester manually — verify records appear in `/opt/pensieve/records/`
2. `pensieve_query "DNS routing"` returns malcolm's entry
3. `pensieve_recent` shows latest harvested memories
4. `bobbin search "DNS routing" --repo pensieve` finds the entries
5. New agent session gets Pensieve context injected when asking about DNS
