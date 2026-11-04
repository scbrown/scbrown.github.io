# HLA Extraction Evaluation

**Bead**: aegis-gnve63
**Date**: 2026-03-01
**Investigator**: ian

## Where HLA Lives

| Component | Location | Notes |
|-----------|----------|-------|
| MCP tools (hla_store/query/recent) | `/opt/homelab-mcp/homelab_mcp.py:1505-1835` on automation.lan (CT 205) | ~330 lines |
| Pensieve tools (pensieve_store/query/recent) | `/opt/homelab-mcp/homelab_mcp.py:1836-2090` on automation.lan | ~255 lines |
| HLA storage | Garage S3 via rclone FUSE at `/mnt/hla` on automation.lan | 115 records, 106K |
| Pensieve storage | Garage S3 via rclone FUSE at `/mnt/pensieve` on automation.lan | 145 records, 158K |
| Pensieve harvester | `/opt/pensieve/harvest/pensieve-harvest.py` on automation.lan | Standalone cron script |
| Legacy filesystem | `/opt/hla/` on CT 228 (hla.lan) — **DEPRECATED** | Stale copy, CT 228 pending decommission |
| Terraform | `goldblum/terraform/main.tf` — `hla_server` resource (CT 228) | Marked deprecated, started=false |
| Ansible inventory | `goldblum/ansible/inventory.ini` — `[hla_servers]` group | No dedicated role |
| Design docs | `aegis/crew/*/docs/designs/hla-*.md` | Replicated across all crew dirs |

## How It's Structured

- **Schema**: `human-intent/v2.1` (HLA), `pensieve/v1` (Pensieve)
- **Storage format**: YAML frontmatter + markdown body, one file per record
- **Directory layout**: `records/YYYY/MM/DD/hi-{ulid}.md` (HLA), `records/{agent}/pm-{ulid}.md` (Pensieve)
- **Index**: `catalog.jsonl` for HLA (append-only); Pensieve uses filesystem grep (no index)
- **Search**: `grep -rli` on FUSE-mounted files — no semantic/vector search
- **Authority tiers**: `admin` (Stiwi directives) vs `user` (non-admin preferences)
- **Shared helpers**: `_generate_ulid()`, `_parse_pensieve_frontmatter()`, `_validate_hla_channel()`

## What Depends on It

1. **All agents** via MCP tool allowlists — L1 Tech, DevOps get read-only; PM, Owner get read+write
2. **Pensieve harvester** — cron job collects MEMORY.md sections from all Claude Code agents
3. **Operating model** (`goldblum/docs/plans/operating-model.md`) — HLA is the source-of-truth for human directives
4. **stiwi-wants.md** — designed to auto-sync from hla_store (not yet implemented)
5. **Planned**: HLA broadcast (§70), Bobbin semantic search (v0.2), channel adapters (aegis-tg, aegis-irc)

## Coupling Analysis

The HLA/Pensieve code is embedded in `homelab_mcp.py` (3136 lines, 92 functions). The 6 archive tools account for ~585 lines (~19% of the file). They share:

- **Import dependencies**: `hashlib`, `json`, `os`, `subprocess`, `re`, `datetime` — all stdlib
- **Shared patterns**: ULID generation, YAML frontmatter parsing, safe-name regex validation
- **Registration**: Same FastMCP `@mcp.tool()` pattern and lambda dispatch table as all other tools
- **Transport**: No network calls — direct filesystem I/O on local FUSE mounts

The tools do NOT depend on any other homelab-mcp functionality (no container inventory, no SSH, no Prometheus). The coupling is purely structural (same file, same MCP server process).

## Recommendation: Do NOT Extract

**HLA should stay in homelab-mcp.** Extraction would add operational complexity without sufficient benefit.

### Why Not

1. **Small footprint**: 585 lines for 6 tools + helpers. Not large enough to justify a separate service.
2. **Pure file I/O**: The tools just read/write FUSE-mounted files. A standalone service would need its own HTTP API, auth, health checks, monitoring — all overhead for what's currently `open()` + `write()`.
3. **Single consumer**: Only homelab-mcp exposes these tools. No other service calls HLA directly.
4. **Deployment simplicity**: One service (homelab-mcp.service), one deploy, one monitoring target. A separate repo means a separate systemd unit, CI pipeline, Ansible role, and Prometheus scrape.
5. **No multi-instance need**: All agents access HLA through the same homelab-mcp on automation.lan. No per-rig deployment scenario exists.

### What Would Change This

- HLA growing beyond grep to need its own database or Bobbin integration service
- Multiple services needing direct HLA write access (not through MCP)
- homelab_mcp.py becoming unmanageable (it's approaching the threshold at 3136 lines)

### Better Near-Term Actions

1. **Modularize homelab_mcp.py** — split into `hla.py`, `pensieve.py`, `containers.py`, etc. within the same repo. This gives clean boundaries without deployment overhead.
2. **Codify rclone/Garage FUSE mounts in IaC** — currently ad-hoc on automation.lan, not in goldblum Ansible.
3. **Reconcile dual storage** — CT 228 has stale `/opt/hla/` filesystem; live data is on Garage S3 mounts. Either deprecate CT 228 or make it the canonical store.
4. **Add Pensieve catalog index** — HLA has `catalog.jsonl`, Pensieve doesn't. This makes Pensieve queries slower (full filesystem grep).
