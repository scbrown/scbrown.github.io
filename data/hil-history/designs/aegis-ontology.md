# Aegis Homelab Ontology

**Status**: Migrated (Graphiti→Quipu, aegis-l4z0, 2026-04-05)
**Author**: goldblum
**Date**: 2026-03-30
**Bead**: aegis-l4z0

## Problem

Aegis homelab knowledge is scattered across dozens of sources:

- **Ansible inventory** defines containers and hosts but not service relationships
- **Service rubric** scores services but doesn't capture dependencies
- **CLAUDE.md / memory files** hold tribal knowledge per-agent but aren't queryable
- **HLA** (115 records) captures Stiwi directives in S3 but isn't linked to the entities they affect
- **Pensieve** (145 records) captures agent observations but they're ephemeral — not reviewable by the full crew
- **Beads** track work items but don't model the infrastructure they refer to
- **Design docs** (55+) describe systems in prose but machines can't traverse them

No agent can answer "what services depend on the host that just went down?" without
reading multiple files and synthesizing manually. During the koror P0, this knowledge
gap cost recovery time — every agent had to reconstruct the dependency graph from
scratch.

## Proposal

Build a **JSON-LD ontology** that models the aegis homelab as a connected graph of
typed entities. Store it in Dolt for versioning and queryability. Surface it through
Bobbin for semantic search and Tapestry for visualization.

Additionally, promote **HLA directives** and **Pensieve observations** to persistent
beads that remain open for crew review, creating a navigable institutional memory
that every agent can reference.

## Why JSON-LD

| Criterion | JSON-LD | Plain JSON | RDF/Turtle | OWL |
|-----------|---------|------------|------------|-----|
| Human-readable | Yes | Yes | Somewhat | No |
| Machine-semantic | Yes | No | Yes | Yes |
| Stores in Dolt | Yes (TEXT/JSON col) | Yes | Needs triple store | Needs triple store |
| AI agent friendly | Excellent (native JSON) | Good | Poor | Poor |
| Entity linking | Built-in (`@id` refs) | Manual | Built-in | Built-in |
| Incremental adoption | Add `@context` to existing JSON | N/A | Full rewrite | Full rewrite |

JSON-LD is JSON that carries semantic meaning. Every document is simultaneously
valid JSON (query with SQL/jq) and valid RDF (query with SPARQL if needed). LLMs
tokenize JSON natively — no parsing friction.

## Ontology Schema

### Context Definition

A shared context file defines the vocabulary. All ontology documents reference it:

```json
{
  "@context": {
    "@vocab": "https://aegis.lan/ontology#",
    "schema": "http://schema.org/",
    "prov": "http://www.w3.org/ns/prov#",

    "name": "schema:name",
    "description": "schema:description",
    "url": "schema:url",

    "comment": "--- Infrastructure ---",
    "LXCContainer": "aegis:LXCContainer",
    "ProxmoxNode": "aegis:ProxmoxNode",
    "BareMetalHost": "aegis:BareMetalHost",
    "SystemdService": "aegis:SystemdService",
    "WebApplication": "aegis:WebApplication",
    "DatabaseService": "aegis:DatabaseService",
    "ReverseProxyRoute": "aegis:ReverseProxyRoute",
    "ZFSDataset": "aegis:ZFSDataset",
    "NetworkSegment": "aegis:NetworkSegment",

    "comment2": "--- Agent Platform ---",
    "AgentTool": "aegis:AgentTool",
    "CLI": "aegis:CLI",
    "Rig": "aegis:Rig",
    "CrewMember": "aegis:CrewMember",
    "Polecat": "aegis:Polecat",
    "Plugin": "aegis:Plugin",
    "Skill": "aegis:Skill",
    "Formula": "aegis:Formula",
    "MCPServer": "aegis:MCPServer",

    "comment3": "--- People & Family ---",
    "Person": "schema:Person",
    "FamilyMember": "aegis:FamilyMember",
    "GoogleAccount": "aegis:GoogleAccount",

    "comment4": "--- Media & Entertainment ---",
    "MediaLibrary": "aegis:MediaLibrary",
    "Movie": "schema:Movie",
    "TVSeries": "schema:TVSeries",
    "Watchlist": "aegis:Watchlist",
    "ThemePark": "aegis:ThemePark",
    "ThemeParkVisit": "aegis:ThemeParkVisit",
    "Attraction": "aegis:Attraction",

    "comment5": "--- Knowledge ---",
    "Directive": "aegis:Directive",
    "Observation": "aegis:Observation",
    "DecisionRecord": "aegis:DecisionRecord",
    "DesignDoc": "aegis:DesignDoc",
    "Probe": "aegis:Probe",

    "comment6": "--- Properties ---",
    "ctId": { "@id": "aegis:ctId", "@type": "xsd:integer" },
    "ipAddress": "aegis:ipAddress",
    "hostname": "aegis:hostname",
    "port": { "@id": "aegis:port", "@type": "xsd:integer" },
    "runsService": { "@id": "aegis:runsService", "@type": "@id", "@container": "@set" },
    "runningOn": { "@id": "aegis:runningOn", "@type": "@id" },
    "dependsOn": { "@id": "aegis:dependsOn", "@type": "@id", "@container": "@set" },
    "managedBy": { "@id": "aegis:managedBy", "@type": "@id" },
    "memberOf": { "@id": "aegis:memberOf", "@type": "@id" },
    "reportsTo": { "@id": "aegis:reportsTo", "@type": "@id" },
    "healthScore": { "@id": "aegis:healthScore", "@type": "xsd:integer" },
    "appliesTo": { "@id": "aegis:appliesTo", "@type": "@id", "@container": "@set" },
    "issuedBy": { "@id": "aegis:issuedBy", "@type": "@id" },
    "familyOf": { "@id": "aegis:familyOf", "@type": "@id" },
    "googleAccount": "aegis:googleAccount",
    "sourceRepo": "aegis:sourceRepo",
    "providesCommand": "aegis:providesCommand",
    "installedIn": { "@id": "aegis:installedIn", "@type": "@id" },
    "plexId": "aegis:plexId",
    "rating": "schema:aggregateRating",
    "visitDate": { "@id": "aegis:visitDate", "@type": "xsd:date" },
    "derivedFrom": "prov:wasDerivedFrom",
    "generatedBy": "prov:wasGeneratedBy",
    "attributedTo": "prov:wasAttributedTo"
  }
}
```

**File**: `ontology/aegis-context.jsonld` (checked into aegis repo)

Compact IRIs keep documents terse: `"ct:236"` expands to
`https://aegis.lan/ontology/container/236`. These are identifiers, not live URLs.

### Entity Classes

The ontology covers the full scope of aegis — not just infrastructure, but the
agent platform, the people it serves, the media it manages, and the institutional
knowledge it accumulates. Everything in the homelab's world is a first-class entity.

```
Infrastructure
├── ProxmoxNode          (nodeId, containers[])
├── BareMetalHost        (ipAddress, hostname, role)
├── LXCContainer         (ctId, ipAddress, hostname, runsService[], host)
├── SystemdService       (port, logPath, runningOn, healthEndpoint, healthScore)
│   ├── WebApplication   (externalUrl, reverseProxyRoute)
│   └── DatabaseService  (dataPath, storageBackend)
├── ReverseProxyRoute    (hostname, backend, authEnabled, tlsStatus)
├── ZFSDataset           (pool, mountpoint, quota)
└── NetworkSegment       (subnet, gateway, purpose)

Agent Platform
├── AgentTool            (sourceRepo, version, providesCommand[])
│   ├── CLI              (binary, installPath, configPath)
│   └── MCPServer        (port, tools[], resources[])
├── Rig                  (prefix, purpose, repo, crews[], polecats[], witness, refinery)
├── CrewMember           (role, tier, domain, shield, reportsTo, characterRef)
├── Polecat              (rig, status, hookedBead, spawnedBy)
├── Plugin               (pluginType, triggers[], installedIn)
├── Skill                (skillName, description, triggers[], installedIn)
└── Formula              (formulaName, legs[], pipeline)

People & Family
├── Person (schema:Person)
│   ├── FamilyMember     (relationship, googleAccount, interests[])
│   └── Overseer         (pronouns, contactMethods[])
└── GoogleAccount        (email, owner, services[])

Media & Entertainment
├── MediaLibrary         (platform, host, contentCount)
├── Movie (schema:Movie) (title, year, rating, plexId, watchedBy[])
├── TVSeries             (title, seasons, status, plexId, watchedBy[])
├── Watchlist            (owner, items[], source)
├── ThemePark            (name, location, visits[])
├── ThemeParkVisit       (park, visitDate, attendees[], notes)
└── Attraction           (name, park, type, rating)

Knowledge
├── Directive            (rule, appliesTo[], issuedBy, issuedDate, priority)
├── Observation          (content, observedBy, observedDate, domain, confidence)
├── DecisionRecord       (decision, rationale, madeBy, date, affects[], supersedes)
├── DesignDoc            (title, status, author, beadId, forgejoUrl)
└── Probe                (title, domain, findings[], date)
```

### Example Entities

**Container + Service**:
```json
{
  "@context": "ontology/aegis-context.jsonld",
  "@id": "ct:236",
  "@type": "LXCContainer",
  "name": "dolt.lan",
  "ctId": 236,
  "ipAddress": "192.168.7.236",
  "hostname": "dolt.lan",
  "host": "pve:koror",
  "runsService": ["svc:dolt-server", "svc:reactor"],
  "storage": {
    "@type": "ZFSDataset",
    "pool": "fastpool",
    "mountpoint": "/var/lib/dolt"
  }
}
```

**Service with dependencies**:
```json
{
  "@id": "svc:tapestry",
  "@type": "WebApplication",
  "name": "Tapestry",
  "runningOn": "ct:238",
  "port": 8070,
  "externalUrl": "http://tapestry.svc",
  "healthScore": 33,
  "managedBy": "crew:ian",
  "dependsOn": ["svc:dolt-server", "svc:forgejo"],
  "reverseProxyRoute": {
    "@type": "ReverseProxyRoute",
    "hostname": "tapestry.svc",
    "backend": "svc:tapestry",
    "authEnabled": false
  }
}
```

**Crew member**:
```json
{
  "@id": "crew:ellie",
  "@type": "CrewMember",
  "name": "ellie",
  "role": "Steward",
  "tier": "steward",
  "domain": "Comms & Observability",
  "shield": 3,
  "reportsTo": "crew:goldblum",
  "memberOf": "rig:aegis",
  "manages": [
    "svc:prometheus", "svc:alertmanager", "svc:grafana",
    "svc:pushgateway", "svc:matrix", "svc:irc", "svc:telegram"
  ]
}
```

**Directive (from HLA)**:
```json
{
  "@id": "directive:no-dolt-auth",
  "@type": "Directive",
  "name": "Never change dolt_server_user",
  "rule": "dolt_server_user in metadata.json must stay root. Do NOT re-enable beads auth without explicit Stiwi approval.",
  "issuedBy": "agent:stiwi",
  "issuedDate": "2026-03-22",
  "priority": "P1",
  "appliesTo": ["svc:dolt-server"],
  "generatedBy": "decision:dolt-auth-rollback",
  "prov:wasAttributedTo": "agent:stiwi"
}
```

**Agent tool**:
```json
{
  "@id": "tool:beads",
  "@type": "CLI",
  "name": "beads",
  "description": "Issue tracking and work management for Gas Town",
  "providesCommand": ["bd"],
  "sourceRepo": "http://git.svc/stiwi/beads",
  "githubRepo": "https://github.com/scbrown/beads",
  "language": "Go",
  "dependsOn": ["svc:dolt-server"],
  "installPath": "/home/braino/.local/bin/bd",
  "configPath": ".beads/metadata.json"
}
```

**Rig**:
```json
{
  "@id": "rig:aegis",
  "@type": "Rig",
  "name": "aegis",
  "description": "Stiwi's homelab operations team",
  "prefix": "-",
  "repo": "http://git.svc/stiwi/aegis",
  "crews": ["crew:goldblum", "crew:hammond", "crew:ellie", "crew:arnold",
            "crew:ian", "crew:malcolm", "crew:dearing", "crew:maldoon",
            "crew:sentinel", "crew:stryder", "crew:grant"],
  "dependsOn": ["tool:gastown", "tool:beads"]
}
```

**Family member**:
```json
{
  "@id": "person:stiwi",
  "@type": ["Person", "Overseer"],
  "name": "Stiwi",
  "pronouns": "he/him",
  "role": "Overseer",
  "googleAccount": "<redacted>",
  "familyOf": ["person:spouse", "person:child-1", "person:child-2"],
  "interests": ["theme-parks", "movies", "home-automation", "ai-agents"]
}
```

```json
{
  "@id": "person:spouse",
  "@type": ["Person", "FamilyMember"],
  "name": "<spouse>",
  "relationship": "spouse",
  "familyOf": ["person:stiwi", "person:child-1", "person:child-2"]
}
```

```json
{
  "@id": "person:child-1",
  "@type": ["Person", "FamilyMember"],
  "name": "<child 1>",
  "relationship": "child",
  "familyOf": ["person:stiwi", "person:spouse", "person:child-2"]
}
```

```json
{
  "@id": "person:child-2",
  "@type": ["Person", "FamilyMember"],
  "name": "<child 2>",
  "relationship": "child",
  "familyOf": ["person:stiwi", "person:spouse", "person:child-1"]
}
```

**Media library**:
```json
{
  "@id": "media:plex",
  "@type": "MediaLibrary",
  "name": "Plex Media Server",
  "platform": "Plex",
  "runningOn": "host:kota",
  "port": 32400,
  "managedBy": "crew:grant",
  "users": ["person:stiwi", "person:child-1", "person:child-2"],
  "relatedServices": ["svc:sonarr", "svc:radarr", "svc:overseerr", "svc:tautulli"]
}
```

**Theme park**:
```json
{
  "@id": "park:disney-world",
  "@type": "ThemePark",
  "name": "Walt Disney World",
  "location": "Orlando, FL",
  "trackedBy": "crew:dearing",
  "visits": ["visit:disney-2026-spring"]
}
```

```json
{
  "@id": "visit:disney-2026-spring",
  "@type": "ThemeParkVisit",
  "park": "park:disney-world",
  "visitDate": "2026-04-15",
  "attendees": ["person:stiwi", "person:spouse", "person:child-1", "person:child-2"],
  "planningBead": "aegis-68akc0",
  "plannedBy": "crew:dearing"
}
```

**Decision record**:
```json
{
  "@id": "decision:koror-to-kota",
  "@type": "DecisionRecord",
  "decision": "Migrate services from koror to kota due to hardware failure",
  "rationale": "koror Proxmox host has hardware failure, down until parts sourced. kota has Incus LXC capability.",
  "madeBy": "agent:stiwi",
  "date": "2026-03-27",
  "affects": ["host:koror", "host:kota", "svc:forgejo", "svc:bobbin"],
  "derivedFrom": "bead:hq-wisp-hrg1e"
}
```

## Persistence Layer: Dolt

### Schema

```sql
CREATE TABLE ontology_entities (
  id          VARCHAR(128) PRIMARY KEY,   -- "ct:236", "svc:dolt-server", "crew:ellie"
  type        VARCHAR(64) NOT NULL,       -- "LXCContainer", "SystemdService"
  name        VARCHAR(128),               -- denormalized for fast queries
  domain      VARCHAR(64),                -- keeper domain: "comms", "tooling", "search", "infra"
  jsonld      TEXT NOT NULL,              -- full JSON-LD document
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ontology_relations (
  subject_id  VARCHAR(128),               -- "svc:tapestry"
  predicate   VARCHAR(64),                -- "dependsOn", "runningOn", "managedBy"
  object_id   VARCHAR(128),               -- "svc:dolt-server"
  PRIMARY KEY (subject_id, predicate, object_id)
);

CREATE TABLE ontology_directives (
  id          VARCHAR(128) PRIMARY KEY,   -- "directive:no-dolt-auth"
  rule        TEXT NOT NULL,
  issued_by   VARCHAR(64),
  issued_date DATE,
  priority    VARCHAR(4),
  jsonld      TEXT NOT NULL,
  bead_id     VARCHAR(64),               -- link to persistent bead
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ontology_decisions (
  id          VARCHAR(128) PRIMARY KEY,
  decision    TEXT NOT NULL,
  rationale   TEXT,
  made_by     VARCHAR(64),
  date        DATE,
  jsonld      TEXT NOT NULL,
  bead_id     VARCHAR(64),
  created_at  TIMESTAMP DEFAULT NOW()
);
```

**Why Dolt specifically**:
- Every change is versioned — `dolt diff` shows exactly what changed in the ontology
- Branch/merge workflow — test ontology changes in a branch before merging
- SQL queries — no special tooling, every agent already has `bd` which speaks Dolt
- Already deployed (CT 236, dolt.lan:3306)

### Denormalized Relations Table

The `ontology_relations` table extracts relationships from JSON-LD into a flat,
joinable format. This enables graph traversal queries without JSON parsing:

```sql
-- What services depend on dolt (direct)?
SELECT r.subject_id, e.name
FROM ontology_relations r
JOIN ontology_entities e ON e.id = r.subject_id
WHERE r.predicate = 'dependsOn' AND r.object_id = 'svc:dolt-server';

-- What runs on the container that just went down?
SELECT e.name, e.type
FROM ontology_relations r
JOIN ontology_entities e ON e.id = r.subject_id
WHERE r.predicate = 'runningOn' AND r.object_id = 'ct:236';

-- Who manages services affected by a directive?
SELECT DISTINCT e2.name AS keeper
FROM ontology_directives d
JOIN ontology_relations r1 ON r1.object_id = JSON_EXTRACT(d.jsonld, '$.appliesTo[0]')
JOIN ontology_relations r2 ON r2.subject_id = r1.object_id AND r2.predicate = 'managedBy'
JOIN ontology_entities e2 ON e2.id = r2.object_id;
```

## HLA & Pensieve as Persistent Beads

### Current State

HLA and Pensieve records live in Garage S3 buckets, accessible only through
`hla_query` and `pensieve_query` MCP tools on homelab-mcp (CT 205). They're
invisible to most crew workflows — you have to know they exist and use specific
tools to access them.

### Proposed: Ontology-Linked Beads

Promote high-value HLA directives and Pensieve observations to **persistent beads**
that stay open for crew review:

```
HLA Record (S3)                    Ontology Directive              Persistent Bead
┌─────────────────┐   harvest    ┌───────────────────┐   link    ┌──────────────┐
│ directive:       │ ──────────► │ @type: Directive   │ ───────► │ aegis-xxxxx  │
│ no-dolt-auth     │             │ rule: "never..."   │          │ status: open │
│ authority: admin │             │ appliesTo: [dolt]  │          │ type: ref    │
│ source: stiwi    │             │ issuedBy: stiwi    │          │ pinned: true │
└─────────────────┘              └───────────────────┘          └──────────────┘
```

**Bead type: `ref` (reference)**. These beads:
- Stay **open/pinned** indefinitely — they're living reference material, not work items
- Link to the ontology entity via the bead's metadata
- Are discoverable via `bd list --type=ref` — **not** via `bd search`, which matches TITLES ONLY
  and so cannot see the directive text these beads exist to carry (aegis-07wep). Search the
  corpus (`bd --readonly export --all`) or `scripts/directive-search.sh` instead.
- Carry the full directive/observation text in the bead description
- Have the `ontology` label for filtering

**Harvest workflow**:
1. Cron job queries HLA/Pensieve for new records (runs daily or on-demand)
2. For each new record, creates an ontology entity (Directive or Observation)
3. Creates a persistent bead linked to the entity
4. Bead stays open — crew can comment, link related beads, add context

**Why beads and not just the ontology table?**
- Beads are the unit of crew attention — agents already check `bd list` and `bd ready`
- Comments on beads capture crew discussion about directives
- Bead dependencies link directives to the work they spawned
- The ontology provides structure; beads provide workflow

### Pensieve as Crew-Reviewable Records

Pensieve observations become `Observation` entities in the ontology, linked to beads:

```json
{
  "@id": "obs:dolt-orphan-processes",
  "@type": "Observation",
  "content": "101 orphan Dolt processes consuming 10.7GB RAM found on luvu",
  "observedBy": "crew:goldblum",
  "observedDate": "2026-03-06",
  "domain": "infrastructure",
  "confidence": "high",
  "appliesTo": ["host:luvu", "svc:dolt-server"],
  "ledTo": "decision:dolt-killall-command"
}
```

Any crew member can query: "what observations exist about dolt?" and get structured
results with links to the decisions and directives that followed.

## Bobbin Integration

### Current: Text Search Only

Bobbin indexes code files and returns text matches. It has no understanding of
entity types, relationships, or infrastructure topology.

### Proposed: Ontology-Aware Search

Three integration paths, in order of complexity:

**Level 1: Index the ontology files** (immediate, no Bobbin changes)

Store ontology entities as JSON-LD files in `ontology/entities/`:
```
ontology/
  aegis-context.jsonld
  entities/
    ct-236.jsonld
    svc-dolt-server.jsonld
    svc-tapestry.jsonld
    crew-ellie.jsonld
    directive-no-dolt-auth.jsonld
    ...
```

Bobbin indexes these files naturally. Search "dolt" returns the entity file alongside
code references. The JSON-LD structure gives Bobbin's LLM-powered search enough
context to understand relationships.

**Level 2: Ontology-enriched search results** (moderate, Bobbin enhancement)

When Bobbin returns search results, cross-reference entity IDs against the ontology
to enrich results with context:

```
Query: "tapestry deploy"
Results:
  1. ansible/roles/tapestry/tasks/main.yml (code match)
  2. ontology: svc:tapestry → runs on ct:238, depends on [dolt, forgejo],
     managed by ian, health: 33%, directive: "auth removed from Traefik"
```

This requires Bobbin to load the ontology as a lookup table and annotate results.
Could be implemented as a Bobbin plugin or post-processor.

**Level 3: Graph-aware queries** (advanced, new Bobbin capability)

Bobbin accepts natural language queries that resolve against the ontology graph:

```
"what services are affected if dolt.lan goes down?"
→ Traverses dependsOn graph from svc:dolt-server
→ Returns: tapestry, beads, gastown-daemon, reactor, all crew mail
→ Plus: code files that reference these services
```

This requires Bobbin to maintain an in-memory graph of ontology relations and
use it during query planning. Significant work but high payoff.

### Implementation Recommendation

Start with Level 1 (free — just add files to the repo). Plan Level 2 as a Bobbin
enhancement bead. Evaluate Level 3 after Levels 1-2 prove the value.

## Tapestry Integration

### /ontology Page

A new Tapestry route that renders the ontology as a navigable graph:

- **Graph view**: Nodes = entities, edges = relationships. Click a node to see its
  JSON-LD, linked beads, directives, and recent observations.
- **Table view**: Filterable list of entities by type, domain, keeper, health score.
- **Impact view**: Select an entity, see everything that depends on it (transitive).
  Critical for P0 response — "what breaks if CT 236 goes down?"
- **Timeline view**: Decisions and directives over time, linked to the entities
  they affected. The institutional memory as a narrative.

Data source: Graphiti knowledge graph (FalkorDB). Query via Graphiti REST API
or MCP tools (`search_nodes`, `search_memory_facts`). Dolt ontology tables are
**deprecated** — all ontology data now lives in Graphiti/FalkorDB.

## Additional Persistence: Decision Log

Beyond HLA (directives from Stiwi) and Pensieve (agent observations), add a
**Decision Log** — a structured record of architectural and operational decisions
with full provenance:

```
Decision Record
├── What was decided
├── Why (rationale, constraints, tradeoffs)
├── Who decided (Stiwi, crew consensus, keeper judgment call)
├── What it affects (ontology entity links)
├── What it supersedes (previous decision, if any)
├── Evidence (beads, incidents, data that informed it)
└── Status (active, superseded, under-review)
```

This uses W3C PROV-O (Provenance Ontology) for the lineage model:
- `prov:Activity` — the decision-making event
- `prov:Entity` — the decision record itself
- `prov:Agent` — who made it
- `prov:wasGeneratedBy` — links decision to the activity
- `prov:wasDerivedFrom` — links to prior decisions it builds on

**Storage**: `ontology_decisions` Dolt table + persistent beads (type: `ref`).

**Why this matters**: During the koror P0, multiple agents had to reconstruct
*why* things were set up a certain way. A decision log makes that instant —
query "decisions affecting koror" and get the full rationale chain.

## Entity Inventory (Initial Population)

Based on current infrastructure audit:

### Infrastructure Entities

| ID | Type | Name | Host | Keeper |
|----|------|------|------|--------|
| `ct:210` | LXCContainer | matrix.lan | koror | ellie |
| `ct:211` | LXCContainer | bot.lan | koror | ellie |
| `ct:212` | LXCContainer | monitoring.lan | koror | ellie |
| `ct:213` | LXCContainer | persistence.lan | koror | malcolm |
| `ct:214` | LXCContainer | message.lan | koror | malcolm |
| `ct:215` | LXCContainer | automation.lan | koror | arnold |
| `ct:216` | LXCContainer | git.lan | koror | arnold |
| `ct:217` | LXCContainer | librechat.lan | koror | arnold |
| `ct:218` | LXCContainer | litellm.lan | koror | arnold |
| `ct:220` | LXCContainer | dns.lan | koror | malcolm |
| `ct:222` | LXCContainer | secrets.lan | koror | malcolm |
| `ct:229` | LXCContainer | traefik.lan | koror | malcolm |
| `ct:230` | LXCContainer | garage.lan | koror | malcolm |
| `ct:232` | LXCContainer | probe.lan | koror | - |
| `ct:233` | LXCContainer | dashy.lan | koror | - |
| `ct:234` | LXCContainer | seeker2.lan | koror | grant |
| `ct:235` | LXCContainer | pages.svc | koror | arnold |
| `ct:236` | LXCContainer | dolt.lan | koror | ian |
| `ct:238` | LXCContainer | tapestry.lan | koror | ian |
| `host:luvu` | BareMetalHost | luvu | - | - |
| `host:kota` | BareMetalHost | kota | - | - |
| `host:koror` | ProxmoxNode | koror | - | malcolm |

### Service Entities (35+)

| ID | Type | Port | Container | Health |
|----|------|------|-----------|--------|
| `svc:prometheus` | SystemdService | 9090 | ct:212 | 64% |
| `svc:alertmanager` | SystemdService | 9093 | ct:212 | 57% |
| `svc:grafana` | WebApplication | 3000 | ct:212 | 50% |
| `svc:pushgateway` | SystemdService | 9091 | ct:212 | 64% |
| `svc:matrix` | SystemdService | 6167 | ct:210 | 43% |
| `svc:irc` | SystemdService | 6667 | ct:211 | 27% |
| `svc:telegram` | SystemdService | - | ct:215 | 20% |
| `svc:postgresql` | DatabaseService | 5432 | ct:213 | 62% |
| `svc:rabbitmq` | SystemdService | - | ct:214 | 50% |
| `svc:traefik` | SystemdService | 80/443 | ct:229 | 42% |
| `svc:adguard` | WebApplication | 53/80 | ct:220 | 42% |
| `svc:infisical` | WebApplication | 8080 | ct:222 | 35% |
| `svc:garage` | SystemdService | 3900 | ct:230 | 35% |
| `svc:forgejo` | WebApplication | 3000 | ct:216 | 46% |
| `svc:homelab-mcp` | SystemdService | 3002 | ct:215 | 36% |
| `svc:agent-mcp` | SystemdService | 3003 | ct:215 | 27% |
| `svc:litellm` | WebApplication | 4000 | ct:218 | 42% |
| `svc:dolt-server` | DatabaseService | 3306 | ct:236 | 50% |
| `svc:reactor` | SystemdService | - | ct:236 | - |
| `svc:tapestry` | WebApplication | 8070 | ct:238 | 33% |
| `svc:bobbin` | WebApplication | 3000 | host:kota | 30% |
| `svc:plex` | WebApplication | 32400 | host:kota | - |
| `svc:sonarr` | WebApplication | 8989 | ct:234 | - |
| `svc:radarr` | WebApplication | 7878 | ct:234 | - |
| `svc:overseerr` | WebApplication | 5055 | ct:234 | - |
| `svc:gastown-daemon` | SystemdService | 3307 | host:luvu | 36% |

### Organization Entities

| ID | Type | Role | Domain | Reports To |
|----|------|------|--------|------------|
| `crew:goldblum` | CrewMember | Orchestrator | all | stiwi |
| `crew:hammond` | CrewMember | Orchestrator | all | stiwi |
| `crew:ellie` | CrewMember | Steward | Comms & Observability | goldblum |
| `crew:stryder` | CrewMember | Steward | Bobbin & Desire Path | goldblum |
| `crew:arnold` | CrewMember | Keeper | Tooling & DX | goldblum |
| `crew:ian` | CrewMember | Keeper | Search & Context | goldblum |
| `crew:malcolm` | CrewMember | Keeper | Infrastructure | goldblum |
| `crew:dearing` | CrewMember | Marshal | Admin & Strategy | goldblum |
| `crew:maldoon` | CrewMember | Warden | QA & SRE | goldblum |
| `crew:sentinel` | CrewMember | Sentinel | Security | goldblum |
| `crew:grant` | CrewMember | Ranger | Media | ellie |

### Network Entities

| ID | Type | Subnet | Purpose |
|----|------|--------|---------|
| `net:containers` | NetworkSegment | 192.168.7.0/24 | Proxmox LXC containers |
| `net:baremetal` | NetworkSegment | 192.168.4.0/24 | Bare metal hosts |
| `net:wireguard` | NetworkSegment | 192.168.4.223 | VPN tunnel |

### Agent Platform Entities

| ID | Type | Name | Repo | Commands |
|----|------|------|------|----------|
| `tool:gastown` | CLI | Gas Town | git.svc/stiwi/gastown | `gt` |
| `tool:beads` | CLI | Beads | git.svc/stiwi/beads | `bd` |
| `tool:bobbin` | CLI | Bobbin | github.com/scbrown/bobbin | `bobbin` |
| `tool:desire-path` | CLI | Desire Path | github.com/scbrown/desire-path | `dp` |
| `tool:tapestry` | WebApplication | Tapestry | git.svc/stiwi/tapestry | - |
| `tool:homelab-mcp` | MCPServer | Homelab MCP | - | MCP tools |
| `tool:agent-mcp` | MCPServer | Agent MCP | - | MCP tools |

| ID | Type | Name | Prefix | Repo |
|----|------|------|--------|------|
| `rig:aegis` | Rig | aegis | `-` | git.svc/stiwi/aegis |
| `rig:gastown` | Rig | gastown | `gt-` | git.svc/stiwi/gastown |
| `rig:bobbin` | Rig | bobbin | `bob-` | github.com/scbrown/bobbin |
| `rig:beads` | Rig | beads | `bd-` | git.svc/stiwi/beads |
| `rig:den` | Rig | den | `den-` | git.svc/stiwi/den |
| `rig:desire-path` | Rig | desire-path | `dp-` | github.com/scbrown/desire-path |

### People & Family Entities

| ID | Type | Name | Relationship | Google Account |
|----|------|------|-------------|----------------|
| `person:stiwi` | Overseer | Stiwi | - | <redacted> |
| `person:spouse` | FamilyMember | <spouse> | spouse | <redacted> |
| `person:child-1` | FamilyMember | <child 1> | child | - |
| `person:child-2` | FamilyMember | <child 2> | child | - |

### Media & Entertainment Entities

| ID | Type | Name | Host/Platform | Managed By |
|----|------|------|---------------|------------|
| `media:plex` | MediaLibrary | Plex | host:kota | crew:grant |
| `media:jellyfin` | MediaLibrary | Jellyfin | host:kota | crew:grant |
| `svc:sonarr` | WebApplication | Sonarr | ct:234 | crew:grant |
| `svc:radarr` | WebApplication | Radarr | ct:234 | crew:grant |
| `svc:overseerr` | WebApplication | Overseerr | ct:234 | crew:grant |
| `svc:tautulli` | WebApplication | Tautulli | ct:234 | crew:grant |
| `svc:recommendarr` | WebApplication | Recommendarr | ct:234 | crew:grant |

Theme parks, movies, shows, and watchlists are populated dynamically — dearing
manages theme park planning (bead: aegis-68akc0), and the media stack (Sonarr/Radarr/
Overseerr/Plex) is the source of truth for movie/show entities. The ontology captures
what's important to the family, not a complete media database.

## Implementation Plan

### Phase 1: Foundation (Week 1)

1. Create `ontology/aegis-context.jsonld` — the shared vocabulary
2. Create `ontology/entities/` directory with JSON-LD files for all infrastructure entities
3. ~~Create Dolt tables (`ontology_entities`, `ontology_relations`)~~ **DONE & DEPRECATED** — migrated to Graphiti/FalkorDB
4. ~~Write `ontology-populate.sh` — script to load JSON-LD files into Dolt~~ **DEPRECATED** — use Graphiti `/episodes/complete` API instead
5. Bobbin Level 1: entities indexed automatically (they're just files in the repo)

### Phase 2: Knowledge Capture (Week 2)

1. Ingest knowledge into Graphiti via `/episodes/complete` API (replaces HLA→Dolt harvest)
2. ~~Harvest Pensieve observations into ontology~~ — Graphiti episodes replace this
3. Create persistent reference beads for high-value directives
4. ~~Write `ontology-harvest.sh` — cron job for ongoing HLA/Pensieve → ontology sync~~ **DEPRECATED**
5. Decision log: backfill major decisions from beads and memory files

### Phase 3: Integration (Week 3-4)

1. Tapestry `/ontology` page — graph visualization
2. Tapestry impact view — "what breaks if X goes down?"
3. Bobbin Level 2: ontology-enriched search results
4. `bd` integration: `bd show` displays linked ontology entities
5. SHACL validation shapes for entity types (optional, add when agents write entities)

### Phase 4: Advanced (Future)

1. Bobbin Level 3: graph-aware natural language queries
2. Automated ontology updates from Ansible runs / service discoveries
3. P0 response automation: "host down" → traverse ontology → alert affected keepers
4. Cross-rig ontology federation (gastown, bobbin, den rigs)

## Open Questions

1. **Ontology ownership**: Should a keeper own the ontology, or is it shared infrastructure?
   Recommendation: ian (Search & Context) owns it, since it's a knowledge graph.

2. **Update cadence**: How often do we refresh entity data? Options:
   - Manual (crew updates entities when things change)
   - Cron harvest (daily sync from Ansible inventory + service health)
   - Event-driven (Ansible playbook run → ontology update)
   Recommendation: Start manual, add cron harvest in Phase 2.

3. **Bead volume**: If every HLA record becomes a bead, that's 115+ new beads.
   Filter to high-value directives only? Or create all and tag with `ontology-ref`?
   Recommendation: Filter — only `authority: admin` HLA records (Stiwi directives)
   become beads. Agent observations stay in Pensieve unless promoted.

4. **Schema evolution**: What happens when we add new entity types?
   JSON-LD handles this gracefully — unknown properties are ignored. Add new types
   to the context file and existing documents remain valid.

## References

- [W3C JSON-LD 1.1](https://www.w3.org/TR/json-ld11/)
- [W3C PROV-O](https://www.w3.org/TR/prov-o/) — Provenance Ontology
- [W3C SHACL](https://www.w3.org/TR/shacl/) — Shapes Constraint Language
- [Schema.org](https://schema.org/) — base vocabulary
- [Service Rubric Baseline](../plans/service-rubric-baseline.md) — current health scores
- [Org Hierarchy](org-hierarchy.md) — crew structure
- [HLA Extraction Evaluation](../investigations/hla-extraction-evaluation.md) — HLA architecture
