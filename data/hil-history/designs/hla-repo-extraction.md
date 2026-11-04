# Investigation: HLA — Evaluate Extracting to Own Repo

**Bead**: aegis-qqhhsw
**Date**: 2026-03-01
**Investigator**: hammond
**Status**: Complete — recommendation provided

## Current State

HLA (Human-Level Alignment / Human Intent Archive) is currently embedded inside
`homelab-mcp` — a monolithic Python MCP server at `/home/braino/workspace/homelab-mcp/homelab_mcp.py`
(~2,918 lines). HLA occupies roughly lines 1510-1720 (3 tools, ~210 lines of implementation).

### What "HLA" actually consists of today

| Component | Location | Lines | Coupling |
|-----------|----------|-------|----------|
| `hla_store_impl()` | homelab_mcp.py:1543-1637 | ~95 | Filesystem + Bobbin API |
| `hla_query_impl()` | homelab_mcp.py:1640-1683 | ~44 | Bobbin API |
| `hla_recent_impl()` | homelab_mcp.py:1686-1719 | ~34 | Bobbin API |
| ULID generation | homelab_mcp.py:1524-1535 | ~12 | python-ulid library |
| Config/helpers | homelab_mcp.py:1510-1540 | ~30 | Env vars, Bobbin client |
| MCP tool decorators | homelab_mcp.py:2127-2150 | ~24 | FastMCP framework |
| **Total implementation** | | **~240 lines** | |

### Storage backend

- Records: `/mnt/hla/records/YYYY/MM/DD/hi-<ulid>.md` (YAML frontmatter + body)
- Index: `/mnt/hla/index/catalog.jsonl` (one JSON line per record)
- Container: ~~CT 228 (hla.lan)~~ **Deprecated** — now on Garage S3 via `/mnt/hla/` on automation.lan
- Search: Bobbin (`http://search.svc`) for semantic queries

### Companion system: Pensieve

Pensieve (agent memory archive) shares the same architecture:

- Records: `/mnt/pensieve/records/<agent>/pm-<ulid>.md`
- Index: `/mnt/pensieve/index/catalog.jsonl`
- Same backend (Garage S3 via rclone FUSE on automation.lan), same Bobbin integration
- ~200 lines of implementation in homelab_mcp.py

Together HLA + Pensieve are ~440 lines embedded in a ~2,918 line monolith.

## Design docs (6 total, replicated across all crew workspaces)

| File | Purpose |
|------|---------|
| `human-intent-archive.md` | Core v2 schema + capture pipeline (599 lines) |
| `human-lineage-archive.md` | Data model, extraction from existing sources (243 lines) |
| `hla-mcp-tools.md` | Tool specification + dependencies (195 lines) |
| `hla-two-tier-authority.md` | Authority tiers (admin vs user) (246 lines) |
| `hla-broadcast.md` | Broadcast/notification pattern |
| `hla-auto-update-stiwi-wants.md` | Auto-sync to stiwi-wants.md |

## Analysis: Should HLA become its own repo?

### Arguments FOR extraction

1. **The design says it should be system-agnostic** — the very first design doc
   states: "Not a homelab feature. Not a Gas Town feature. A foundational layer."
   Being embedded in `homelab-mcp` contradicts this.

2. **Reuse potential** — HLA + Pensieve are applicable to any multi-agent system.
   Extracting makes them portable (other deployments, open source, etc.).

3. **Clean separation of concerns** — homelab-mcp is an MCP server for homelab
   infrastructure (containers, Prometheus, networking). HLA is a human intent
   archive. They have no architectural relationship.

4. **Independent deployment** — HLA could be deployed as a lightweight standalone
   service (its own MCP server, REST API, or CLI tool) without pulling in all
   of homelab-mcp's dependencies.

5. **Testing** — HLA has zero tests today. A standalone repo would make unit/integration
   testing natural rather than requiring the full homelab-mcp context.

### Arguments AGAINST extraction

1. **It's only ~240 lines** — extraction overhead (CI, packaging, deployment,
   MCP registration) may exceed the code itself.

2. **MCP tool registration** — currently free via homelab-mcp's existing FastMCP
   server. A separate repo means either a separate MCP server process or a
   plugin/import mechanism.

3. **Bobbin dependency** — both HLA and Pensieve depend on Bobbin's search API.
   This dependency exists regardless of where the code lives, but it's worth
   noting the code isn't truly standalone.

4. **Deployment complexity** — one more service to manage, monitor, and update.
   Currently it deploys as part of homelab-mcp (systemd unit on CT 215).

5. **Low churn** — HLA's implementation is stable. It's not changing frequently
   enough to benefit from independent release cycles.

## Recommendation

**Extract HLA + Pensieve together into a single new repo**, but as a **library
with an optional standalone MCP server**, not just a server.

### Proposed structure: `stiwi/intent` (or `stiwi/hla`)

```text
intent/
├── cmd/
│   └── intent-mcp/         # Standalone MCP server (optional deployment)
├── pkg/
│   ├── hla/                 # HLA core: store, query, recent
│   ├── pensieve/            # Pensieve core: store, query, recent
│   └── catalog/             # Shared catalog.jsonl index
├── mcp/                     # MCP tool definitions (importable)
├── docs/
│   ├── human-intent-archive.md
│   ├── pensieve.md
│   └── ...                  # Consolidated design docs
├── tests/
└── README.md
```

### Why this structure

- **Library-first**: homelab-mcp can import the package and re-export the tools
  (zero deployment change initially)
- **Standalone option**: `intent-mcp` binary can run independently when needed
- **Design docs consolidated**: all 6 HLA design docs move from aegis to the
  authoritative location
- **Language**: Python (matches homelab-mcp for easy initial integration) or Go
  (matches Gas Town ecosystem). Python is pragmatic since the existing code is
  Python.

### Migration path

1. Create `stiwi/intent` repo on git.svc
2. Move HLA + Pensieve implementation (extract from homelab_mcp.py)
3. homelab-mcp imports from intent package (no external change)
4. Move design docs from aegis to intent repo
5. Add tests (currently zero)
6. Optional: deploy as standalone MCP server alongside homelab-mcp

### What NOT to do

- Don't create separate repos for HLA and Pensieve — they share storage patterns,
  Bobbin integration, and record format. One repo, two packages.
- Don't rewrite in Go just for consistency — the existing Python works fine and
  matches homelab-mcp's import path.
- Don't change the storage format or location — filesystem + catalog.jsonl is
  correct and working.

## Status of HLA implementation

| Component | Status |
|-----------|--------|
| Core tools (store/query/recent) | Done, working |
| Two-tier authority (admin/user) | Done |
| Storage (Garage S3, was CT 228) | Done |
| Bobbin semantic search integration | Partial (v0.1 keyword, v0.2 pending) |
| Channel adapters (IRC, Telegram) | Partial (manual + session working) |
| stiwi-wants.md auto-sync | Pending |
| Tests | None |
| Standalone deployment | Not started |
