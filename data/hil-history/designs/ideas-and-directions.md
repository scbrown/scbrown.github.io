# Aegis Ideas & Directions

> Generated 2026-02-15 by goldblum. Living document — update as ideas evolve.

## Where We Are

Horizon 1 (Reliability Foundation) is largely complete:

- Alert pipeline working (Alertmanager → bead auto-creation)
- Backup automation live (8 jobs, freshness monitoring)
- World model MCP operational (15/17 containers tracked)
- Telegram bot live for bidirectional comms
- Claude account auto-switching preventing session freezes
- Security audit in progress (sentinel working rotations)
- 6 crew members + witness + refinery + polecats running

Horizon 2 (Predictive & Preventive) is starting:

- Tautulli data available for usage pattern analysis
- Disk/cert/latency monitoring in place
- Maintenance windows identified from Plex data

## New Directions to Explore

### 1. Configuration Drift Detection (P1 — Reliability)

**Problem**: goldblum IaC defines desired state, but we don't verify containers match. Ad-hoc SSH changes silently drift from Ansible.

**Solution**: Periodic drift-patrol that compares Ansible role expectations against live container state. Report divergences as beads.

**Implementation**: Run `ansible --check --diff` against all roles, parse output, create beads for drift. Could be a patrol plugin.

**Value**: Prevents "works in Ansible, broken in prod" surprises. Catches manual changes.

### 2. Service Dependency Map (P2 — Intelligence)

**Problem**: We know what services exist but not their dependencies. When Traefik goes down, what breaks? When RabbitMQ restarts, who's affected?

**Solution**: Auto-discover dependencies from Traefik routes, Prometheus targets, network connections, and Ansible role dependencies. Visualize as a graph.

**Implementation**: Query Traefik API for routes, Prometheus for scrape targets, parse Ansible role deps. Generate Mermaid diagram stored in docs, updated weekly.

**Value**: Impact analysis before changes. Faster incident triage.

### 3. Resource Forecasting (P2 — Predictive Ops)

**Problem**: Disk fills, CPU spikes, and memory pressure are discovered reactively. We have Prometheus data but don't project trends.

**Solution**: Weekly forecast using PromQL rate() and predict_linear() for disk growth, CPU trend, memory trend per container. Alert when projected exhaustion < 30 days.

**Implementation**: PromQL predictions + custom alert rules. Weekly digest section showing projected resource exhaustion dates.

**Value**: Prevents P0 disk-full incidents. Guides capacity planning decisions.

### 4. Self-Documenting Infrastructure (P2 — Knowledge)

**Problem**: Baseline.md and service docs go stale. Manual updates miss changes.

**Solution**: Auto-generate infrastructure documentation from live state: container inventory, service versions, network topology, resource allocation. Compare against baseline.md and flag differences.

**Implementation**: Extend batch_probe to collect versions, configs, resource allocation. Template into markdown. Diff against baseline.md.

**Value**: Documentation never goes stale. Baseline always accurate.

### 5. Automated Runbook Library (P2 — Self-Healing)

**Problem**: Auto-remediation handles simple restarts. Complex failures (database corruption, network partition, certificate renewal) need structured multi-step procedures.

**Solution**: Formalize runbooks as executable YAML: steps, checks, rollback points, escalation triggers. Auto-execute for known incident classes.

**Implementation**: Runbook YAML format, runner script, integration with alert-to-bead pipeline. Start with top 5 incident classes from historical data.

**Value**: Consistent incident response. Reduced MTTR. Knowledge capture.

### 6. Media Intelligence (P3 — User Context)

**Problem**: Plex/Jellyfin usage data exists (Tautulli) but isn't used for operational decisions.

**Solution**: Analyze viewing patterns to optimize: maintenance windows (avoid active viewing), storage management (hot/cold media), recommendation quality. Daily sync to Dolt.

**Implementation**: Tautulli API → daily cron → Dolt table. Dashboard view in Tapestry. Maintenance window enforcement in patrol.

**Value**: No maintenance during movie night. Smart storage tiering.

### 7. Multi-Host Agent Distribution (P2 — Architecture)

**Problem**: All Gas Town agents run on luvu (gaming PC). Resource contention, single point of failure.

**Solution**: Run crew members on kota (30GB RAM, 20 cores, always-on). Requires Docker setup (in progress — aegis-6wmo) and Claude CLI deployment.

**Implementation**: After kota Docker setup, containerize Gas Town agent environment. Run non-gaming-sensitive agents on kota.

**Value**: Eliminates gaming contention. Higher availability. Uses idle kota capacity.

### 8. Knowledge Graph (P3 — Intelligence)

**Problem**: Beads, commits, services, incidents, and docs are separate. No way to query "what changes affected monitoring this week?" or "show me all work related to Traefik."

**Solution**: Build a queryable graph connecting: beads → commits → services → containers → incidents. Bobbin semantic search + structured relationships.

**Implementation**: Extend bobbin to index beads with relationship links. Add service tags to beads. Query interface via MCP tool.

**Value**: "Show me everything about monitoring" returns beads, commits, configs, incidents. Full context for any domain.

### 9. Chaos Engineering Lite (P3 — Resilience)

**Problem**: We don't know if self-healing actually works until a real failure. No way to test resilience safely.

**Solution**: Controlled failure injection: stop services, simulate disk pressure, break network routes. Verify auto-remediation triggers and recovery succeeds.

**Implementation**: Test harness that injects failures, monitors remediation, verifies recovery. Run during safe maintenance windows.

**Value**: Confidence in self-healing. Discovers gaps before real incidents.

### 10. Public Voice: ai-gardener Content Pipeline (P1 — Active)

**Problem**: Blog exists (scbrown.github.io/ai-gardener) but only has 1 post. Rich operational knowledge isn't being shared.

**Solution**: Regular blog posts on homelab AI operations. Draw from real experience, abstract away private details.

**Topics ready to write**:

- Golden Rules of Autonomous Agent Operations (aegis-2o5u)
- Building a Multi-Agent Homelab: Lessons from Gas Town
- The Archivist Pattern: How AI Agents Remember
- Self-Healing Infrastructure: From Alerts to Auto-Remediation
- Beads: Issue Tracking Designed for AI Agents
- Configuration as Code: When Your Homelab Writes Itself

**Implementation**: Crew member writes draft, review cycle, push to GitHub, auto-deploys.

**Value**: Knowledge sharing. Community building. Portfolio for Stiwi.

### 11. Ambient Security Posture (P1 — Active)

**Problem**: Security is project-based (rotate this token, fix that exposure). Should be continuous background behavior.

**Solution**: sentinel crew member runs continuous security patrol. TLS monitoring, secret scanning, access control audit, CVE tracking.

**Implementation**: sentinel already created and working. Need to formalize patrol cadence and automate recurring scans.

**Value**: Security maintenance becomes invisible. No security debt accumulates.

### 12. Voice/Chat Interface Evolution (P2 — UX)

**Problem**: Telegram bot works but is basic. No conversational context, no rich formatting, limited commands.

**Solution**: Evolve toward natural language interaction. Stiwi says "what broke today?" and gets a useful answer. Agent can ask clarifying questions.

**Implementation**: Integrate Telegram with a persistent agent session. Use bobbin for context retrieval. Support multi-turn conversations.

**Value**: Lower barrier for Stiwi to interact with the system. Faster status checks and decisions.

### 13. Human Input Lineage (P1 — Active)

**Problem**: When agents modify artifacts (code, configs, docs), there's no way to trace changes back to the human decision that caused them. A polecat could silently overwrite Stiwi's directive without anyone knowing.

**Solution**: Git trailers as source of truth. Every commit carries `Lineage-Bead`, `Origin-Type`, `Origin-Human`, `Origin-Channel`, `Origin-Message` trailers tracing the chain back to human input. Six levels of human guidance (standing, directive, correction, approval, idea, review) with different protection weights.

**Implementation**: Phase 1 is convention (trailers on commits). Enforcement via ZFC-compliant pre-commit hook (gather context → model decides → enforce). Derived indexes in Dolt + Bobbin for querying. Tapestry visualization.

**Design**: docs/designs/human-input-lineage.md (v3 with enforcement). ZFC review pending (aegis-xyut4).

**Value**: Human Input Sovereignty becomes enforceable. Full audit trail from artifact to decision.

### 14. Async Decision Queue (P1 — Active)

**Problem**: goldblum blocks on `AskUserQuestion` waiting for Stiwi. Stiwi might be on mobile, away, or batching decisions.

**Solution**: Post decisions as beads to multiple channels (Telegram inline keyboards, Tapestry /decisions, IRC). Stiwi responds from any channel, response routes back. Deadlines with auto-escalation or defaults.

**Implementation**: 5 phases — convention → Telegram keyboards → Tapestry /decisions → deadline automation → IRC. Phase 1 requires zero code.

**Design**: docs/designs/async-decision-queue.md. Implementation beads: aegis-uxgou (Telegram), aegis-hl6gd (Tapestry).

**Value**: No more blocked sessions. Stiwi decides from wherever is convenient.

### 15. Zero Framework Cognition (ZFC) Compliance (P1 — Active)

**Problem**: Framework code makes decisions that should be delegated to models — hardcoded rules, pattern matching, keyword routing. This makes systems brittle.

**Solution**: ZFC principle adopted as core charter value. All decision points delegate to models. Framework code is pure IO, plumbing, structural safety, policy enforcement.

**Implementation**: ZFC added to charter.md and docs/principles/zfc.md. Design-review convoy formula (6 legs including ZFC check) drafted. ZFC review pass on existing designs (aegis-xyut4).

**Value**: Resilient system design. Decisions adapt when context changes.

### 16. Design Review Formula (P1 — Active)

**Problem**: No systematic process to review designs against aegis principles before implementation. Code gets reviewed, but design compliance is ad-hoc.

**Solution**: Convoy formula with 6 parallel specialized reviewers: ZFC, charter, lineage, security, feasibility, IaC. Each leg evaluates the design document independently, then a synthesis step produces unified PASS/CONDITIONAL PASS/FAIL.

**Implementation**: Draft formula at .beads/formulas/design-review.formula.toml. Needs integration into gastown repo (aegis-gomr2). 4 presets: full, zfc-focused, infra, gate.

**Value**: Systematic principle compliance. Catches violations before implementation begins.

## Priority Matrix

| Idea | Priority | Horizon | Blocked By | Crew Owner |
|------|----------|---------|------------|------------|
| Human Input Lineage | P1 | H1 | ZFC review (xyut4) | ian (impl), malcolm (review) |
| Async Decision Queue | P1 | H1 | Nothing (Phase 1 is convention) | ian (Telegram/Tapestry) |
| ZFC Compliance | P1 | H1 | Nothing | malcolm (review), all (adopt) |
| Design Review Formula | P1 | H1 | gomr2 → gastown | ian |
| ai-gardener Content | P1 | Now | Nothing | ellie |
| Ambient Security | P1 | H1 | Nothing | sentinel |
| Config Drift Detection | P1 | H1 | Nothing | arnold |
| Resource Forecasting | P2 | H2 | Prometheus data | arnold |
| Service Dependency Map | P2 | H2 | Nothing | malcolm |
| Self-Documenting Infra | P2 | H2 | Nothing | ellie |
| Automated Runbooks | P2 | H2 | Incident catalog | goldblum |
| Multi-Host Agents | P2 | H2 | kota Docker (aegis-6wmo) | goldblum |
| Voice/Chat Evolution | P2 | H2 | Nothing | ellie |
| Media Intelligence | P3 | H2 | Tautulli sync | ellie |
| Knowledge Graph | P3 | H3 | Bobbin v2 | ian |
| Chaos Engineering | P3 | H3 | Self-healing maturity | goldblum |

## Cross-Rig Status

| Rig | Status | Active Work | Gap |
|-----|--------|-------------|-----|
| aegis | Healthy | 7 crew + witness + refinery active | ZFC compliance pass needed |
| ai_gardener | Active | Golden Rules blog post LIVE | Content pipeline executing |
| tapestry | Active | Bead links fixed, commit links done | /decisions and /briefing views pending |
| bobbin | Active | Hooks 4/4 deployed, eval gap resolved | Need kota deployment (blocked) |
| desire_path | Healthy | Baseline telemetry bead | Low priority, self-maintaining |
| pixelsrc | Healthy | v0.2.0, 1843 tests | No aegis attention needed |
| goldblum (IaC) | Healthy | CI/CD working | Need drift detection |
| gastown | Healthy | Mayor operational, all formulas deployed | Design-review formula pending |
