# Design: IRC Agent Conversation + Human Lineage Pipeline

**Beads**: aegis-wer1n (IRC conversation), aegis-isc9s (Human Lineage Archive)
**Author**: ellie (Comms & Observability PO)
**Date**: 2026-02-18
**Status**: Draft v1

## Problem

Two connected gaps:

1. **Agents can't converse on IRC.** Stiwi types in `#aegis` and nobody responds.
   Agents only receive `gt nudge` messages, not channel activity.

2. **Stiwi's IRC input isn't captured.** Everything Stiwi types in IRC should flow
   into the Human Lineage Archive for searchability and crew reference.

The same infrastructure that enables (1) also feeds (2).

## Architecture

```text
                     ┌──────────────┐
                     │    Stiwi     │
                     │  (The Lounge)│
                     └──────┬───────┘
                            │ IRC messages
                            ▼
                     ┌──────────────┐
                     │    Ergo      │
                     │  (irc.lan)   │
                     └──────┬───────┘
                            │
              ┌─────────────┼──────────────┐
              │             │              │
              ▼             ▼              ▼
       ┌────────────┐ ┌──────────┐ ┌──────────────┐
       │ aegis-irc  │ │  Ergo    │ │  The Lounge  │
       │   (bot)    │ │ log files│ │  SQLite logs │
       │            │ │          │ │              │
       └─────┬──────┘ └──────────┘ └──────────────┘
             │
    ┌────────┼────────────┐
    │        │            │
    ▼        ▼            ▼
┌────────┐ ┌──────┐ ┌──────────┐
│ Route  │ │Dolt  │ │ Lineage  │
│to agent│ │store │ │ files    │
│via mail│ │      │ │ → Bobbin │
└────────┘ └──────┘ └──────────┘
```

## Part 1: Agent Conversation on IRC

### The aegis-irc Bot

A lightweight Go bot (similar to aegis-tg) that:

- Connects to ergo as a service account
- Monitors all configured channels
- Routes messages to agents based on rules
- Posts agent responses back to channels

**Not a full IRC bouncer per agent.** Individual agent IRC connections
(irc-connect/irc-send) work for posting status updates, but conversation
requires a centralized router that understands context.

### Routing Model

When Stiwi sends a message in `#aegis`:

1. **Direct address** (`ellie: what's the IRC status?`) → Route to named agent
   via `gt mail send aegis/crew/ellie` with IRC context
2. **Channel command** (`!status`, `!beads`) → Execute command, reply in channel
3. **General conversation** (no address, no command) → Route to **duty agent**
4. **Keyword match** (mentions a domain: "monitoring", "security") → Route to
   relevant PO, CC duty agent

### Duty Agent & Response Priority (Stiwi directive 2026-02-19)

One agent responds to each IRC message. **No duplicates.**

**Priority chain**: hammond (primary) → dearing (5min backup) → goldblum (tertiary)

- Duty agent (hammond) receives all unrouted Stiwi messages
- Observer CC is DISABLED — no other agent gets automatic copies
- When hammond routes work internally, recipients mail results BACK to hammond
- Hammond posts ONE synthesized response to IRC
- Other agents only respond on IRC if directly addressed by name

**Full spec**: `specs/irc-response-priority.md`

### Agent Response Flow

```text
Stiwi types in #aegis
  → aegis-irc bot sees message
  → Bot determines target agent (direct address / keyword / duty)
  → Bot sends: gt mail send <agent> -s "IRC #aegis from stiwi" -m "<message>"
  → Bot also sends: gt nudge <agent> "IRC message from Stiwi in #aegis"
  → Agent reads mail, processes, responds via gt mail
  → gt mail triggers aegis-irc to post response to #aegis
```

**Or simpler**: Agent responds by calling `irc-send #aegis "response text"`
from their session. The bot doesn't need to relay responses — agents already
have IRC send capability.

### Channel History for Context

Agents need recent context when responding. Options:

- **Ergo CHATHISTORY**: IRC protocol extension. Agents can request last N
  messages via `CHATHISTORY LATEST #aegis * 20`. Ergo supports this natively.
- **Bot maintains buffer**: aegis-irc keeps last 50 messages per channel in
  memory. Passes recent context in the mail to the agent.

**Recommendation**: Bot maintains buffer and includes last 5-10 messages in
the mail body. Agent doesn't need to make a separate IRC query.

### Response UX for Stiwi

- **Latency**: 30-60 seconds for agent response (agent must be nudged, read
  mail, think, respond). Set expectations via channel topic.
- **Typing indicator**: Not possible in IRC. Bot could post "ellie is thinking..."
  but that's noisy. Skip it.
- **Multi-agent**: If multiple agents need to respond, they each post. Stiwi
  sees a natural chat flow.
- **Offline**: If no agents are active, bot responds: "No agents currently active.
  Message logged — they'll see it next session."

## Part 2: Human Lineage Pipeline

### Capture Layer

Three potential sources, in order of preference:

1. **aegis-irc bot** (recommended) — Already processing messages. Easiest to
   add logging. Can filter to Stiwi-only messages. Has structured metadata
   (nick, channel, timestamp).

2. **Ergo server-side logging** — Ergo can log to files, but format is
   IRC-protocol raw, not clean. Harder to parse.

3. **The Lounge SQLite** — Only logs what the stiwi user sees, which is good
   for completeness. But The Lounge SQLite schema is internal and fragile.

**Recommendation**: aegis-irc bot captures all messages, tags with provenance,
writes to lineage storage. Single source of truth.

### Storage Format

```text
data/lineage/irc/
├── 2026-02-18.md    # One file per day
├── 2026-02-19.md
└── ...
```

Each file:

```markdown
# IRC Lineage — 2026-02-18

## #aegis

### 02:50 stiwi
well done on the promo ellie! 🫸

### 02:55 stiwi
what's the status of the monitoring dashboard?

### 02:56 ellie
Grafana is up at grafana.svc. Claude limits dashboard deployed.

## #ops

### 14:22 stiwi
can someone check why kota disk alerts keep firing?
```

**Why markdown**: Bobbin indexes markdown natively. Each message gets full-text
search. Provenance (who said it, when, which channel) is preserved in headers.

### Indexing Pipeline

```text
aegis-irc bot
  → captures message
  → appends to data/lineage/irc/YYYY-MM-DD.md
  → git add + commit (batched, every 5 min or on threshold)
  → git push
  → Bobbin indexes on next crawl
```

**Query pattern** (for maldoon and other crew):

```bash
curl "http://search.svc/search?q=stiwi+monitoring+dashboard&limit=10"
```

### Privacy and Provenance

- **Capture everything** in channel (not just Stiwi). Context matters — a
  response only makes sense with the question.
- **Tag provenance**: `stiwi` messages get `[human]` tag. Agent messages get
  `[agent:<name>]` tag.
- **Lineage files are append-only**. Never edit or delete human input.
- **maldoon** uses lineage to maintain `stiwi-wants.md` and answer "has Stiwi
  already given guidance on X?"

## Implementation Phases

### Phase 1: aegis-irc Bot (Core)

- Go binary, similar structure to aegis-tg
- Connects to ergo, monitors #aegis, #ops, #planning
- Writes all messages to lineage markdown files
- Routes Stiwi messages to duty agent via gt mail + gt nudge
- Handles direct address routing (name: message)
- Deploy on bot.lan alongside ergo and The Lounge

### Phase 2: Agent Response Integration

- Agents respond via irc-send (already exists)
- Bot tracks which agent was routed a message
- Bot includes channel history buffer in mail context
- Duty agent rotation (label-based or config-based)

### Phase 3: Bobbin Integration

- Lineage files committed to aegis repo
- Bobbin indexes data/lineage/irc/
- Crew members query via search.svc
- maldoon workflow: search before asking Stiwi

### Phase 4: Channel Commands

- `!status` → system health summary
- `!beads` → ready work items
- `!ask <agent> <question>` → route question to specific agent
- `!decisions` → pending decision queue

## Coordination

| Person | Responsibility |
|--------|---------------|
| **ellie** | Bot development, IRC capture, routing design |
| **arnold** | Storage architecture review, Bobbin indexing config |
| **maldoon** | Lineage query workflow, stiwi-wants.md integration |
| **ian** | Bobbin search tuning for lineage queries |
| **goldblum** | Duty agent rotation policy, cross-PO coordination |

## Open Questions

1. **Capture scope**: All channels or just ones Stiwi participates in?
   Recommendation: All channels — agent coordination in #ops is also valuable.

2. **Commit frequency**: Real-time (noisy git history) or batched (5-min delay)?
   Recommendation: Batched every 5 minutes. Lineage isn't real-time critical.

3. **Bot identity**: Should aegis-irc be a visible nick in channels or invisible?
   Recommendation: Visible as `aegis-bot` — transparency about what's listening.

4. **Response threading**: IRC doesn't have threads. If multiple conversations
   happen simultaneously, how do agents track which they're responding to?
   Recommendation: Include last 5 messages as context. Agents figure it out.
