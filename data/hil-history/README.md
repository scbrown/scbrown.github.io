# Human input lineage: the designs that came before Quipu (Feb–Mar 2026)

Supporting material for the blog series on Quipu and agent orientation. These are the original design documents,
copied from the homelab's internal `aegis` repo. The only edits are redactions: a chat user id, a family channel name,
and the family members (names, relationships, email accounts) that the ontology design used as example entities. Hostnames are left as they were; most of these hosts no longer exist in this
form. **No archived human messages are published here**, only counts (see `stats.md`).

## The idea
When a person and a crew of agents work on the same thing, everything merges and you can no longer tell what the
person actually asked for. The human's input should be elevated: stored verbatim, classified, traceable to what it
caused, and hard for an agent to quietly override. Keeping that record current and correctly ordered is where the later
work on typed memory and lifecycles (Quipu) came from.

## Timeline
| date | document | what it introduced |
|---|---|---|
| 2026-02-15 | [`ideas-and-directions.md`](designs/ideas-and-directions.md) | The idea list where both HIL (#13, P1) and a "Knowledge Graph" (#8, P3) first appear: "Beads, commits, services, incidents, and docs are separate." |
| 2026-02-15 | [`human-input-sovereignty.md`](designs/human-input-sovereignty.md) | The principle: human input is elevated and takes further human input to remove. Agents propose changes; they don't make them. |
| 2026-02-15 | [`human-input-lineage.md`](designs/human-input-lineage.md) | `git blame` → commit → `Lineage-Bead` / `Origin-Type` trailers → work item → human origin. Six origin types with weights (directive, idea, review, approval, correction, standing), a human identity registry, Dolt index tables, and protection levels that **block** a commit undoing a human correction or standing rule. Phase 1 shipped. |
| 2026-02-17 | [`human-intent-archive.md`](designs/human-intent-archive.md) | A unified archive of human intent, written as a multi-agent "quorum" design review. |
| 2026-02-17 | [`human-lineage-archive.md`](designs/human-lineage-archive.md) | "Has the human said anything about X?" answered with verbatim, sourced records. |
| 2026-02-17 | [`irc-conversation-and-lineage.md`](designs/irc-conversation-and-lineage.md) | Capturing intent from chat channels (IRC/Telegram) with lineage. |
| 2026-02-19 | [`hla-mcp-tools.md`](designs/hla-mcp-tools.md) | Human-Level Alignment as a first-class MCP primitive: `hla_store`, `hla_query`, `hla_recent`, available to every agent. |
| 2026-02-22 | (code) | The tools shipped in the homelab MCP server. Records are Markdown with YAML frontmatter and ULID ids, plus a `catalog.jsonl` index, stored on CT 228 (`hla.lan`). |
| 2026-02-23 | [`hla-auto-update-stiwi-wants.md`](designs/hla-auto-update-stiwi-wants.md), [`hla-broadcast.md`](designs/hla-broadcast.md) | Keeping a living "what Stiwi wants" document in sync; broadcasting new directives to the crew (broadcast was later retired unbuilt). |
| 2026-02-26 | [`hla-two-tier-authority.md`](designs/hla-two-tier-authority.md) | Two authority tiers: admin vs user, for more than one human. |
| 2026-02-27 | [`pensieve.md`](designs/pensieve.md) | The agent-side counterpart: aggregate and index the agents' own memory files. |
| 2026-03-01 | [`hla-repo-extraction.md`](designs/hla-repo-extraction.md) | Should HLA be its own repo? (~240 lines of HLA plus ~200 of Pensieve inside a ~2,900-line MCP monolith.) |
| 2026-03-02 | [`hla-read-pipeline-broken.md`](designs/hla-read-pipeline-broken.md) | Reads were stale: 125 records stored, 7 searchable. The write path worked; the read path didn't. |
| 2026-03-02 | (infra) | CT 228 decommissioned; data moved to Garage S3, FUSE-mounted on `automation.lan`. |
| 2026-03-27 | [`koror-kota-recovery.md`](designs/koror-kota-recovery.md) | P0: the main Proxmox host (koror) is down; triage and standup on kota. |
| 2026-03-29 | [`kota-recovery-retrospective.md`](designs/kota-recovery-retrospective.md) | The retrospective. Every agent on the recovery had to rebuild the dependency picture from scattered files. |
| 2026-03-30 | [`aegis-ontology.md`](designs/aegis-ontology.md) | The homelab ontology. Its problem list: HLA "captures Stiwi directives … but isn't linked to the entities they affect", next to Pensieve, memory files and 55+ design docs. |
| 2026-03-31 | (harvest) | HLA and Pensieve absorbed into the graph: 322 directives and 434 agent observations become typed entities with provenance, plus 14 backfilled decision records. |
| 2026-04-03 | [`crew-ontology-triple-store.md`](designs/crew-ontology-triple-store.md) | The Graphiti + FalkorDB design: the crew's "shared brain" for situational awareness, impact reasoning and institutional memory, with agents doing the extraction. |
| 2026-04-04 | — | Quipu's first commit: typed, governed, bitemporal memory. |
| 2026-04-05 | — | Graphiti and FalkorDB stopped; the graph moves to Quipu. |

## What became of it
- **Directives ledger** (Aug 2026): an append-only, verbatim record of rulings and what each changed.
- **Declared vs inferred memory** (Oct 2026, camayoc agent-memory design): each memory records whether a human said
  it (`declared`) or an agent concluded it (`inferred`). Recall ranks the human's first. A `verbatim` field keeps
  the words. An agent's lesson is promoted to declared only when a human confirms it.
- The HIL lesson carried forward: **writing the human's input down was easy; getting agents to read it back at the right
  moment was the hard part.** That's why HLA's broken read path is in this folder, and why the March outage, not a design meeting, is what turned HIL into a knowledge graph.

See [`stats.md`](stats.md) for the archive's size and shape.
