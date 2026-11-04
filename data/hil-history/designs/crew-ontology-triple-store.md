# Crew Ontology System — Design Document

> Created: 2026-03-31, crew/dearing session
> Updated: 2026-04-03 — fork plan: ingest_extracted_episode() + durable async pattern
> Status: APPROVED DIRECTION
> ⚠️ 2026-07-23 (aegis-xegx): the Graphiti/FalkorDB stack this doc describes was SUPERSEDED —
> quipu is now RDF/SPARQL on SQLite. Its old `/docs` (Swagger) and `/mcp/` endpoints no longer
> exist; live endpoints are quipu.svc `/query`, `/search`, `/episode`, `/stats`, `/report`.
> URLs below are kept schemeless as historical record.

## Vision

Gas Town is a multi-agent system with 14+ crew members, polecats, witnesses, and
infrastructure agents. Today, coordination is manual: the overseer assigns work,
the watchdog nudges idle agents, tribal knowledge lives in scattered files.

The crew ontology system is **Gas Town's shared brain** — a knowledge graph that
all agents read from and write to. It enables:

- **Situational awareness**: Who is idle? Who is blocked? What's the fleet state?
- **Impact reasoning**: "If this host goes down, which services and crew are affected?"
- **Institutional memory**: What happened during the last P0? What decisions were made and why?
- **Self-orchestration**: Agents react to graph state, not just hook assignments

The idle detection problem is the **first use case**, not the whole story. The
architecture must support a growing flywheel of knowledge sources.

## The Flywheel

```
    ┌──────────────────────────────────────────┐
    │           Knowledge Graph                 │
    │        (Graphiti + FalkorDB)              │
    └──────┬───────────────────────┬───────────┘
           │ query                 │ ingest
           ▼                      ▲
    ┌──────────────┐      ┌──────────────────┐
    │  Crew makes  │      │  Crew extracts   │
    │  better      │──────│  knowledge from  │
    │  decisions   │      │  episodes        │
    └──────┬───────┘      └────────┬─────────┘
           │                       ▲
           │ richer observations   │ raw episodes
           └───────────────────────┘
```

**Phase 1**: Patrol emitter feeds crew state → agents query it
**Phase 2**: Crew agents extract knowledge from episodes (incidents, handoffs, observations)
**Phase 3**: More episode sources plug in (IRC, PR reviews, patrol findings, mail)
**Phase 4**: Agents self-orchestrate based on graph state

Each phase makes the graph more valuable, which makes crew more effective, which
produces richer episodes, which feeds back into the graph.

---

## Constraint: No External LLM API

Claude Code Max plan does not allow API key usage with the Anthropic API. This
means:
- ❌ Anthropic API (`ANTHROPIC_API_KEY`) — not available
- ❌ LiteLLM proxy to Claude — same constraint
- ❌ Ollama local models — quality too low for reliable extraction
- ✅ **Crew agents ARE the LLM** — already running, full context, zero cost

This is not a compromise. Crew-as-extractor is the **correct architecture**:
- Crew members understand Gas Town domain (better extraction than generic model)
- Crew sessions are already running (zero marginal cost)
- Extraction work builds crew knowledge (they learn by reading episodes)
- The pattern works for any future episode source

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Consumers                              │
│  crew agents · overseer · patrols · hooks · just CLI · IRC    │
└─────┬──────────────────────┬──────────────────────┬──────────┘
      │ triples CLI          │ MCP server            │ REST API
      │ (bash wrapper)       │ (agent sessions)      │ (Tapestry)
      ▼                      ▼                       ▼
┌────────────────────────────────────────────────────────────┐
│                     Graphiti Server                          │
│                                                              │
│  FastAPI REST: quipu.svc/docs (historical)                │
│  MCP endpoint: quipu.svc/mcp/ (historical)                │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Entities    │  │ Facts        │  │ Episodes          │  │
│  │ (nodes)     │  │ (edges)      │  │ (provenance)      │  │
│  │             │  │              │  │                   │  │
│  │ crew members│  │ hasState     │  │ raw text stored   │  │
│  │ services    │  │ dependsOn    │  │ crew extracts     │  │
│  │ containers  │  │ managedBy    │  │ entities & facts  │  │
│  │ hosts       │  │ blockedBy    │  │ via add_fact_     │  │
│  │ rigs        │  │ memberOf     │  │ triple()          │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│                                                              │
│  Temporal: facts have t_valid / t_invalid windows           │
│  Search: semantic + BM25 + graph traversal (~300ms P95)     │
│  Note: Graphiti's built-in LLM extraction NOT used —        │
│        crew agents handle extraction instead                 │
└────────────────────┬─────────────────────────────────────────┘
                     │ Backend
                     ▼
┌────────────────────────────────────────────────────────────┐
│                      FalkorDB                                │
│                                                              │
│  Redis protocol (port 6379)    DNS: falkordb.svc            │
│  Cypher queries                Sub-millisecond              │
│  pub/sub for reactive events   ~512 MB RAM                  │
│  Persistence: appendonly.aof   SSPL license                 │
│                                                              │
│  LXC container on Proxmox, deployed via goldblum Ansible    │
└────────────────────────────────────────────────────────────┘
```

### Crew-Driven Episode Extraction

Instead of Graphiti calling an LLM API for `add_episode()`, crew agents do the
extraction work:

```
1. Raw episode arrives (incident report, handoff mail, observation)
   └→ Stored as bead or queued in Graphiti as raw episode

2. Extraction bead created: "Extract knowledge from episode X"
   └→ Slung to a crew agent (or picked up from bd ready)

3. Crew agent reads the episode, extracts entities and facts
   └→ Uses their Claude session (zero API cost)
   └→ Writes back via add_fact_triple() — structured triples

4. Knowledge graph updated with extracted entities and facts
   └→ Temporal validity set (t_valid = now)
   └→ Contradictions auto-invalidate old facts
```

**Why this is better than an LLM API call**:
- Crew has full Gas Town context — knows what "koror" means, who "stiwi" is
- Crew can ask clarifying questions or cross-reference other knowledge
- Extraction beads are tracked work — auditable, retryable
- Builds crew domain knowledge as a side effect

### Episode Sources (growing over time)

| Source | Phase | Ingestion Path |
|--------|-------|---------------|
| Crew state patrol | 1 | `add_fact_triple()` direct — no extraction needed |
| JSON-LD entity files | 1 | `add_fact_triple()` direct — structured data |
| Handoff mail | 2 | Extraction bead → crew agent → `add_fact_triple()` |
| Incident postmortems | 2 | Extraction bead → crew agent → `add_fact_triple()` |
| HLA directives | 2 | Extraction bead → crew agent → `add_fact_triple()` |
| Pensieve observations | 2 | Extraction bead → crew agent → `add_fact_triple()` |
| IRC messages | 3 | Filter → extraction bead → crew → `add_fact_triple()` |
| PR reviews | 3 | Webhook → extraction bead → crew → `add_fact_triple()` |
| Patrol findings | 3 | Patrol → extraction bead → crew → `add_fact_triple()` |
| Beads lifecycle events | 3 | Hook → `add_fact_triple()` direct (structured) |

Structured data (patrol state, JSON-LD, beads events) goes direct. Unstructured
data (prose, mail, observations) routes through crew extraction.

---

## Deployment Stack

### FalkorDB (graph database)

- **Container**: LXC on Proxmox
- **Ansible role**: `goldblum/ansible/roles/falkordb/`
- **Terraform**: CTID + IP in `goldblum/terraform/locals.tf`
- **DNS**: `falkordb.svc`
- **Port**: 6379 (Redis protocol)
- **RAM**: ~512 MB
- **Persistence**: AOF + periodic RDB snapshots
- **Monitoring**: Redis INFO metrics → Prometheus exporter

### Graphiti Server (knowledge graph API)

- **Container**: Docker on same or separate LXC
- **Image**: `zepai/graphiti:latest`
- **DNS**: `quipu.svc`
- **Port**: 8000 (REST + MCP)
- **Config**:
  ```env
  GRAPH_DB_PROVIDER=falkordb
  GRAPH_DB_URI=bolt://falkordb.svc:6379
  # No LLM config — extraction handled by crew agents
  # Graphiti used for storage, search, and temporal management only
  ```
- **Note**: Graphiti may require an LLM provider to start. If so, configure a
  minimal Ollama instance or stub. The key insight is we bypass `add_episode()`'s
  LLM pipeline — we use `add_fact_triple()` exclusively, where crew does the
  thinking.

### No Ollama Required

The architecture eliminates the need for a local LLM service:
- Structured data: `add_fact_triple()` (no LLM)
- Unstructured data: crew extracts → `add_fact_triple()` (crew IS the LLM)
- If Graphiti requires an LLM to initialize, use a minimal stub or disable
  the extraction pipeline

---

## Crew State: First Use Case

### Predicates

| Predicate | Object Values | Meaning |
|-----------|--------------|---------|
| `hasState` | `working`, `idle`, `permission-blocked`, `stuck`, `offline`, `rate-limited` | Composite crew state |
| `blockedBy` | `permission-prompt`, `rate-limit`, `context-full` | What's blocking |
| `heartbeatAge` | seconds (int) | Staleness of heartbeat file |
| `paneHash` | md5 hex | For idle detection across cycles |
| `idleSince` | ISO timestamp | When idle state began |
| `lastToolUse` | ISO timestamp | Last tool execution (from hook) |

### Permission Prompt Detection

```bash
pane=$(tmux capture-pane -t "$SESSION" -p 2>/dev/null | tail -30)
if echo "$pane" | grep -qE '(Allow|Deny|allow once|Always allow)'; then
  # Combined with stale heartbeat (>120s) = genuinely blocked
fi
```

### Composite State Derivation

| Heartbeat | Pane | Result |
|-----------|------|--------|
| Fresh (<120s) | Any | `working` |
| Stale + permission dialog | Any | `permission-blocked` |
| Stale + pane unchanged 2+ cycles | No dialog | `stuck` |
| Stale + rate limit text | Any | `rate-limited` |
| No tmux session | N/A | `offline` |

---

## Components to Build

### 1. Infrastructure (goldblum)

- FalkorDB Ansible role + Terraform resource
- Graphiti server deployment (Docker)
- DNS entries: `falkordb.svc`, `quipu.svc`
- Prometheus monitoring for FalkorDB

### 2. `triples` CLI (`~/.local/bin/triples`)

Bash wrapper that talks to Graphiti REST API:

```
triples emit <subject> <predicate> <object> [--ttl N] [--src S]
triples query <subject> [predicate]
triples query --predicate <pred>
triples fleet                    # summary table of all crew states
triples gc                       # invalidate expired facts
triples watch <pattern>          # subscribe via Redis pub/sub
triples ingest <file.jsonld>     # bulk ingest JSON-LD entities
```

### 3. `crew-state-patrol.sh` (the emitter)

Runs every 3 minutes via cron. For each crew tmux session:

1. Heartbeat staleness → emit fact triple
2. Permission prompt detection → emit fact triple
3. Pane hash idle detection → emit fact triple
4. Composite state derivation → emit `hasState` fact
5. Publish state change to Redis pub/sub channel

### 4. Extraction Bead Pattern

For unstructured episode ingestion:

```bash
# 1. Create extraction bead
bd new --type task "Extract knowledge: koror P0 incident report" \
  --label ontology-extraction

# 2. Attach the raw episode text as bead description or link

# 3. Sling to a crew agent
gt sling <bead-id> aegis

# 4. Crew reads episode, extracts entities/facts, writes via:
triples emit crew:dearing hasState "working-on-koror-recovery" --src "crew:agent"
triples emit svc:dolt-server wasAffectedBy "koror-network-outage" --src "crew:agent"
# ... etc

# 5. Close extraction bead
bd close <bead-id>
```

### 5. Hook Integration (`triples-inject.sh`)

UserPromptSubmit hook:
- Emit proof-of-life to FalkorDB
- Query for actionable state → inject as `<system-reminder>`

### 6. MCP Server Integration

Add Graphiti MCP to crew agent configs:
```json
{
  "mcpServers": {
    "quipu": {
      "url": "quipu.svc/mcp/ (historical — endpoint removed)"
    }
  }
}
```

Gives agents tools: `search_entities`, `search_facts`, `get_entity`,
`add_fact_triple` (crew writes directly to graph from their session)

### 7. Entity Harvest Script

Reads `ontology/entities/*.jsonld`, converts to `add_fact_triple()` calls.
Run on JSON-LD file changes. Populates FalkorDB with infrastructure topology.

### 8. Goldblum just module (`just.d/triples.just`)

- `just triples fleet` — crew state summary
- `just triples query <subject>` — query facts
- `just triples gc` — manual GC
- `just triples deploy` — Ansible deploy
- `just triples ingest` — bulk load JSON-LD entities

---

## Reactive Capabilities

FalkorDB's Redis protocol enables reactive patterns:

### State Change Notifications
```bash
# Patrol publishes on state change
redis-cli -h falkordb.svc PUBLISH crew:state:change \
  '{"crew":"dearing","state":"permission-blocked"}'

# Daemon/watchdog subscribes
redis-cli -h falkordb.svc SUBSCRIBE crew:state:change
```

### Hook-Based Injection
When an agent's UserPromptSubmit hook fires, query the graph for fleet state
and inject actionable context (e.g., "3 crew idle, work available on bd ready").

---

## Relationship to Existing Systems

| System | Current Role | After Ontology System |
|--------|-------------|----------------------|
| ~~Dolt `ontology_*` tables~~ | ~~Infrastructure ontology~~ | **Deprecated** — all ontology data now lives in Quipu |
| JSON-LD entity files | Source of truth for entities | Human-editable, ingested into Quipu via `/episodes/complete` |
| `crew_watchdog.sh` | Respawn dead crew, nudge idle | Continues; reads from graph later |
| Heartbeat files | Raw state snapshots | Input to patrol emitter |
| Tapestry | Ontology visualization | Queries Graphiti (FalkorDB) — no Dolt ontology dependency |
| HLA / Pensieve | Directives / observations | Ingested as episodes via crew extraction |
| Beads / Dolt | Issue tracking | Unchanged — beads stays in Dolt |

---

## Implementation Order

### Phase 1: Infrastructure + Crew State
1. Deploy FalkorDB (goldblum Ansible + Terraform)
2. Deploy Graphiti server (Docker)
3. DNS: `falkordb.svc`, `quipu.svc`
4. Build `triples` CLI
5. Build `crew-state-patrol.sh`
6. Install cron entries (patrol */3)
7. Ingest JSON-LD entities (infrastructure topology)
8. Test: `triples fleet` shows crew states

### Phase 2: Crew-Driven Extraction
9. Define extraction bead pattern (label: `ontology-extraction`)
10. Build extraction workflow (bead → crew → add_fact_triple)
11. Ingest HLA directives via crew extraction
12. Ingest Pensieve observations via crew extraction
13. Ingest handoff mail history via crew extraction

### Phase 3: Flywheel Expansion
14. Hook integration (`triples-inject.sh`)
15. Add Graphiti MCP to crew configs
16. Goldblum just module
17. IRC message ingestion pipeline
18. PR review ingestion pipeline
19. Patrol findings → extraction beads

### Phase 4: Self-Orchestration
20. Agents query graph for work decisions
21. Reactive pub/sub drives assignment
22. Graph state informs priority and dispatch

---

## Verification

1. `redis-cli -h falkordb.svc PING` → PONG
2. `curl quipu.svc/docs` → Swagger UI (historical — endpoint removed; use `curl http://quipu.svc/stats`)
3. `triples fleet` → all crew with states
4. Permission-blocked crew detected correctly
5. `triples watch crew:state:change` → reactive events flow
6. Crew extraction bead completes → facts appear in graph
7. MCP query from agent session → knowledge graph results
8. `triples ingest ontology/entities/services.jsonld` → entities in graph

---

## Appendix: Why FalkorDB

| Factor | FalkorDB | Oxigraph | SurrealDB |
|--------|----------|----------|-----------|
| Graphiti backend | ✅ Native | ❌ No | ❌ No |
| Reactive (pub/sub) | ✅ Redis | ❌ Polling | ✅ LIVE SELECT |
| Multi-agent isolation | ✅ Built-in | ❌ Manual | ❌ Manual |
| Footprint | ~512 MB | ~256 MB | ~100 MB |
| License | SSPL | MIT | Apache 2.0 |

FalkorDB wins because it's Graphiti's recommended multi-agent backend. Following
the recommended path avoids integration friction.

## Appendix: Why Crew-as-Extractor (not LLM API)

| Factor | Crew Extraction | LLM API |
|--------|----------------|---------|
| Cost | Zero (sessions already running) | Per-token API cost |
| API key required | No | Yes (not available on Max plan) |
| Domain knowledge | Full Gas Town context | Generic model |
| Quality | High (crew understands domain) | Variable |
| Auditability | Tracked via beads | Fire-and-forget |
| Side effects | Crew learns by reading | None |
| Scalability | Bounded by crew capacity | Bounded by API rate limits |

The constraint (no API key) leads to the better architecture. Crew-as-extractor
builds the flywheel: extraction work IS crew work, and crew work produces more
knowledge to extract.

## Appendix: Graphiti Fork Plan — Async Crew Extraction

> Added: 2026-04-03, crew/dearing session (aegis-70z research)

### Problem

Graphiti's `add_episode()` pipeline makes 5+ LLM calls per episode:
1. `extract_nodes()` — LLM extracts entities from text
2. `resolve_extracted_nodes()` — LLM deduplicates against existing nodes
3. `extract_edges()` — LLM extracts relationships
4. `resolve_extracted_edges()` → `resolve_extracted_edge()` — LLM dedup + invalidation
5. `extract_attributes_from_nodes()` — LLM extracts node attributes

We can't use this pipeline because crew agents ARE the LLM — they can't call
themselves via an API. We need a write path that accepts pre-extracted data.

### Source Analysis

```
graphiti_core/graphiti.py:
  add_episode()            [line 916]  — full pipeline, 5+ LLM calls
  _process_episode_data()  [line 629]  — graph write only, 0 LLM calls ★
  add_triplet()            [line 1574] — 0-2 LLM calls (node resolution)

graphiti_core/utils/maintenance/node_operations.py:
  resolve_extracted_nodes() [line 490] — similarity first, LLM fallback

graphiti_core/utils/maintenance/edge_operations.py:
  resolve_extracted_edge()  [line 495] — LLM dedup + invalidation

graphiti_core/utils/bulk_utils.py:
  add_nodes_and_edges_bulk() [line 128] — pure graph write + embeddings
```

**`_process_episode_data()` is the key.** It takes pre-extracted `EntityNode[]`
and `EntityEdge[]`, builds episodic edges, and writes everything to FalkorDB in
a single transaction. Zero LLM calls. Only dependency: embedder (for semantic
search vectors on nodes/edges).

### Fork Strategy: Single-Write via Beads Queue

#### Why Not Two-Phase Graphiti Writes

An earlier design considered using stock `add_episode()` with a `NoOpLLMClient`
to store raw episodes, then writing extractions later. This fails because:

1. **Pydantic validation crash**: `add_episode()` passes LLM output to
   `ExtractedEntities(**response)` where `extracted_entities` is a required
   field. Returning `{}` from NoOpLLMClient raises `ValidationError`.
2. **Orphan episodes**: Episodes with no nodes/edges are disconnected graph
   nodes — invisible to graph traversal and entity search.
3. **Double-write complexity**: `_process_episode_data()` would run twice
   (once empty, once with data), relying on MERGE semantics to not corrupt.

#### The Simpler Design: Beads ARE the Queue

Graphiti has no existing endpoint that accepts pre-extracted episode data.
Every public method (`add_episode`, `add_episode_bulk`, `add_triplet`) runs
through the LLM pipeline. The only LLM-free write path is the private method
`_process_episode_data()` (graphiti.py:629).

The fork exposes this as a single public endpoint. Raw episode text lives in
beads (Dolt) until extraction is complete, then one write puts everything into
Graphiti at once — episode, nodes, and edges together. No incomplete data in
the graph, no NoOpLLMClient hacks.

```
Episode arrives          Crew extracts             One write to Graphiti
──────────────          ─────────────             ────────────────────
gt handoff ──→ bead     crew picks up bead        POST /episodes/complete
IRC bot    ──→ bead     reads episode from bead   { episode + nodes + edges }
incident   ──→ bead     extracts knowledge        → embeddings (local model)
                        resolves against graph    → _process_episode_data()
                                                  → FalkorDB
```

#### Fork Method: `ingest_extracted_episode()`

Single new public method on the `Graphiti` class, wrapping `_process_episode_data()`:

```python
async def ingest_extracted_episode(
    self,
    name: str,
    episode_body: str,
    source_description: str,
    reference_time: datetime,
    nodes: list[EntityNode],       # crew-extracted entities
    edges: list[EntityEdge],       # crew-extracted relationships
    source: EpisodeType = EpisodeType.message,
    group_id: str | None = None,
    saga: str | SagaNode | None = None,
) -> AddEpisodeResults:
    """Ingest an episode with pre-extracted nodes and edges.

    Writes the episode, nodes, and edges to the graph in a single
    transaction. No LLM calls — the caller (crew agent) has already
    performed extraction and resolution. Only the embedder is used
    (for semantic search vectors on node names and edge facts).
    """
    now = utc_now()
    episode = EpisodicNode(
        name=name,
        group_id=group_id,
        source=source,
        content=episode_body,
        source_description=source_description,
        created_at=now,
        valid_at=reference_time,
    )

    # Generate embeddings (local model, no API calls)
    for node in nodes:
        if node.name_embedding is None:
            await node.generate_name_embedding(self.embedder)
    for edge in edges:
        if edge.fact_embedding is None:
            await edge.generate_embedding(self.embedder)

    episodic_edges, episode = await self._process_episode_data(
        episode, nodes, edges, now, group_id, saga,
    )

    return AddEpisodeResults(
        episode=episode, nodes=nodes, edges=edges,
        episodic_edges=episodic_edges,
    )
```

#### REST Endpoint

```
POST /episodes/complete
{
  "name": "koror-p0-incident",
  "episode_body": "koror went down at 03:00, dolt-server was affected...",
  "source_description": "crew/dearing extraction from handoff mail hq-3wmc",
  "reference_time": "2026-04-03T10:00:00Z",
  "group_id": "gastown",
  "nodes": [
    {"name": "koror", "summary": "Host in aegis rig", "labels": ["Host"]},
    {"name": "dolt-server", "summary": "Dolt database service", "labels": ["Service"]}
  ],
  "edges": [
    {
      "name": "runs_on",
      "fact": "dolt-server runs on koror",
      "source_node_name": "dolt-server",
      "target_node_name": "koror"
    }
  ]
}
```

#### The Flow

```
1. Episode arrives (handoff mail, incident report, observation)
   └→ Ingestion hook creates extraction bead in Dolt:
      bd new --type task "Extract knowledge: <summary>"
        --label ontology-extraction --body "<raw episode text>"
   └→ Bead is durable (survives crashes, restarts, crew turnover)
   └→ Slung to crew via gt sling, or picked up from bd ready

2. Crew agent picks up extraction bead (could be hours/days later)
   └→ Reads raw episode text from bead description
   └→ Queries existing graph via MCP: search for related entities
   └→ Extracts entities and relationships (crew IS the LLM)
   └→ Resolves against existing graph (crew decides dedup)

3. Crew writes to Graphiti — one call, everything at once
   POST /episodes/complete { episode + nodes + edges }
   └→ Local embedder generates vectors (no API calls)
   └→ _process_episode_data() writes to FalkorDB in one transaction
   └→ Episode arrives complete — nodes, edges, episodic links, all connected

4. Crew closes extraction bead
   bd close <bead-id>
   └→ Extraction is tracked, auditable, retryable
```

Every step is durable: beads survive in Dolt, the graph write is transactional.
If crew dies mid-extraction, the bead stays open for retry. Graphiti never
contains incomplete episodes.

### Embedder Strategy: Local Model

The `EmbedderClient` ABC is minimal — just `create()` and `create_batch()`.
A local sentence-transformers implementation avoids any API dependency:

```python
from sentence_transformers import SentenceTransformer
from graphiti_core.embedder.client import EmbedderClient, EmbedderConfig

class LocalEmbedder(EmbedderClient):
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
        self.config = EmbedderConfig(embedding_dim=self.model.get_sentence_embedding_dimension())

    async def create(self, input_data) -> list[float]:
        if isinstance(input_data, str):
            return self.model.encode(input_data).tolist()
        return self.model.encode(input_data[0]).tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return [e.tolist() for e in self.model.encode(input_data_list)]
```

Model options:
- `all-MiniLM-L6-v2` — 384 dims, 80 MB, fast, good quality
- `all-mpnet-base-v2` — 768 dims, 420 MB, best quality for size
- `BAAI/bge-small-en-v1.5` — 384 dims, 130 MB, strong benchmark scores

Runs on the Graphiti server container. No API keys, no external calls.
Set `EMBEDDING_DIM` env var to match the model's output dimension.

### LLM Client: Not Needed

Since we bypass `add_episode()` entirely (crew does extraction, not Graphiti),
no LLM client is required. The Graphiti server only needs:
- `LocalEmbedder` — for generating search vectors
- `GraphDriver` (FalkorDB) — for graph storage
- No LLM client configured — `add_episode()` is never called

If Graphiti's `__init__` requires an LLM client to instantiate, pass a stub
that raises on any call — a safety net to catch accidental LLM path usage:

```python
class NoOpLLMClient(LLMClient):
    async def _generate_response(self, *args, **kwargs):
        raise RuntimeError("LLM pipeline disabled — use /episodes/complete")
```

### Community Detection: Not Initially, Crew-Driven Later

Graphiti has an opt-in community feature (`update_communities=True` on
`add_episode()`). When a new entity is added, it finds the most common
community (cluster) among its graph neighbors and assigns the entity to it,
then uses the LLM to re-summarize the community name and description.

**Initial fork: not supported.** Communities require LLM calls for summary
generation (`summarize_pair`, `generate_summary_description`). We skip this.

**Future support: crew assigns communities during extraction.** The crew
agent already queries the graph during extraction to resolve entities. They
can also query existing communities and decide where new nodes belong:

```
POST /episodes/complete
{
  ...
  "nodes": [
    {
      "name": "dolt-server",
      "labels": ["Service"],
      "community": "database-infrastructure"  ← crew assigns this
    }
  ]
}
```

The endpoint would:
1. Look up or create the named community
2. Wire `HAS_MEMBER` edge from community to node
3. Optionally accept a community summary from crew

This keeps the single-write model — community assignment is just another
field in the node payload. Crew decides the clustering (they have context),
Graphiti handles the graph wiring.

For bulk reorganization (merging communities, re-clustering), a separate
"community gardening" bead type where crew reviews the graph structure and
submits community changes.

### What We DON'T Fork

Keep upstream Graphiti intact for:
- **Search** (`search()`, `_search()`) — semantic + BM25 + graph traversal works without LLM
- **Temporal management** — `valid_at`, `invalid_at`, contradiction detection
- **Graph operations** — node/edge CRUD, bulk writes
- **MCP server** — expose search tools to crew agents as-is

Only additions (no upstream modifications needed):
1. `ingest_extracted_episode()` method on `Graphiti` class
2. `POST /episodes/complete` REST endpoint
3. `LocalEmbedder` — sentence-transformers `EmbedderClient` implementation
4. `NoOpLLMClient` — safety stub (raises if LLM pipeline is accidentally invoked)

### Ingestion Hooks (Episode Sources → Beads)

Hooks create extraction beads with the raw episode text. They don't touch
Graphiti — beads are the durable queue:

| Source | Hook/Trigger | Bead Creation |
|--------|-------------|---------------|
| Handoff mail | `gt handoff` hook | `bd new --label ontology-extraction --body "<mail body>"` |
| IRC messages | IRC bot filter | Bot creates extraction bead with message text |
| Incident reports | Manual or bd hook | Crew creates bead from report text |
| Patrol findings | `crew-state-patrol.sh` | Direct `add_fact_triple()` — no episode needed |
| Beads lifecycle | `bd close` hook | Creates bead with close context |
| HLA directives | Manual | Crew creates bead with directive text |

Structured data (patrol state, beads events) goes direct via `add_fact_triple()`
— no episode, no extraction, no bead needed.

### Context Feedback Loop

> Added: 2026-04-03, Stiwi directive

After an episode is ingested into the graph, the extracted ontology context is
pushed **back** into the bead and the assigned agent. This closes the knowledge
loop: the agent working on a bead benefits from the ontology's understanding of
the entities involved, and when the bead closes, the closure extraction is
richer because the creation context is already annotated.

```
Bead created
  │
  ▼
Cron trigger → polecat extracts intent/entities → POST /episodes/complete
  │
  ▼ (on success)
Context feedback:
  ├─ bd comments add <bead-id>    ← rich comment with entities + relationships
  ├─ gt mail send <assignee>      ← agent gets ontology context while working
  └─ bd label add ontology-context-injected
  │
  ▼ (agent works on bead with ontology context available)
Bead closed
  │
  ▼
Cron trigger → polecat extracts results/learnings → POST /episodes/complete
  │                                                  (closure episode links to
  │                                                   creation episode entities)
  ▼
Context feedback (closure):
  ├─ bd comments add <bead-id>    ← closure entities + what changed
  └─ bd label add ontology-closed-context-injected
```

#### What gets injected into the bead

The formula's close step writes a structured comment:

```
🧠 Ontology context (creation):
Entities: koror (Host), dolt-server (DatabaseService), FalkorDB (DatabaseService)
Relationships:
  - dolt-server runs_on koror
  - FalkorDB depends_on koror
  - Graphiti depends_on FalkorDB
Episode: bead-aegis-xyz (5 nodes, 4 edges)
```

This comment is visible to any agent (or human) reading the bead, and critically
to the **closure extraction polecat** — which can reference existing entities
instead of creating duplicates.

#### What gets mailed to the assignee

The formula sends `gt mail send <assignee>` with:
- Subject: `Ontology context for <bead-id>`
- Body: same structured entity/relationship summary
- Purpose: agent working on the bead has situational awareness of what the
  ontology knows about the entities involved

If no assignee is set, the mail is skipped (the bead comment still persists).

#### Labels tracking lifecycle

| Label | Meaning |
|-------|---------|
| `ontology-ingested` | Creation episode extracted |
| `ontology-context-injected` | Context fed back to bead + agent |
| `ontology-closed-ingested` | Closure episode extracted |
| `ontology-closed-context-injected` | Closure context fed back to bead |

### Implementation Sequence

1. **Fork Graphiti** to `git.svc` (shallow clone already in `graphiti-src/`)
2. Add `LocalEmbedder` — `graphiti_core/embedder/local.py`
3. Add `NoOpLLMClient` — `graphiti_core/llm_client/noop.py`
4. Add `ingest_extracted_episode()` — method on `Graphiti` class
5. Add `POST /episodes/complete` — REST endpoint
6. Update server config — use `NoOpLLMClient` + `LocalEmbedder`
7. Deploy + test: POST a complete episode, verify in FalkorDB
8. Build `triples` CLI wrapper for crew extraction workflow
9. Define extraction bead label + schema in beads
10. Wire first ingestion hook (`gt handoff` → extraction bead)
11. **Context feedback in formula** — close step writes rich comment + mails assignee
12. **Cron log fix** — `/home/braino/.local/log/` (not `/var/log/`)
