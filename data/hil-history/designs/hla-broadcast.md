> **RETIRED 2026-07-23 (aegis-o29s design triage).** Not implemented and not to be built from this doc — see docs/design-status-inventory.md for the classification and evidence. Kept as a historical record.

# §70: HLA Broadcast System

**Status:** Design complete (Stiwi requested design only — no implementation)
**Date:** 2026-02-23
**Origin:** Stiwi via IRC #aegis: "purposely tag, or have reading decide, which
crew is effected by any given hla and broadcast a message and or bead for that
crew to act on"

## Problem

When Stiwi gives a directive, there's no automatic mechanism to notify the
affected crew members. Currently, goldblum manually reads the directive,
determines who's affected, and sends mail. This is slow, error-prone, and
doesn't scale.

## Design Goals

1. When a human directive is stored in HLA, determine which crew/rigs are affected
2. Broadcast actionable notifications to those crews (mail and/or beads)
3. Support both explicit tagging (human says who) and inference (system decides)

## Architecture

```text
Stiwi directive
    ↓
hla_store(content, channel, ...)
    ↓
┌──────────────────────────┐
│  HLA Broadcast Service   │
│                          │
│  1. Store record (done)  │
│  2. Determine audience   │
│  3. Generate actions     │
│  4. Broadcast            │
└──────────────────────────┘
    ↓              ↓              ↓
gt mail send    bd create      IRC notify
(affected crew) (action beads) (#aegis)
```

## Audience Determination

Two modes, as Stiwi specified:

### Mode 1: Explicit Tagging

The human (or capturing agent) tags affected crews in the hla_store call.

**Option A: New parameter on hla_store**

```python
hla_store(
    content="Fix the tapestry links",
    channel="irc",
    tags=["tapestry", "arnold"],  # NEW: explicit audience
)
```

**Option B: Inline tags in content** (parsed by convention)

```text
@arnold @tapestry Fix the tapestry links
```

**Recommendation:** Option A (explicit parameter) — cleaner, no content mutation,
and the capturing agent (hammond/ellie) can add tags based on conversation context.

### Mode 2: Inference (system decides)

When no explicit tags are provided, the broadcast service infers affected crews
using keyword matching against a routing table.

**Routing Table** (`/opt/hla/.config/broadcast-routes.yaml`):

```yaml
routes:
  - keywords: [tapestry, briefing, dashboard, archivist]
    audience: [aegis/crew/arnold, tapestry]

  - keywords: [mcp, homelab-mcp, tool, agent-mcp]
    audience: [aegis/crew/arnold]

  - keywords: [bobbin, search, indexing, injection]
    audience: [aegis/crew/ian, bobbin]

  - keywords: [goldblum, ansible, deploy, infrastructure, IaC]
    audience: [aegis/crew/goldblum, goldblum]

  - keywords: [irc, telegram, comms, notification, alert]
    audience: [aegis/crew/ellie]

  - keywords: [security, credential, secret, audit]
    audience: [aegis/crew/sentinel]

  - keywords: [plex, media, movie, radarr, sonarr]
    audience: [aegis/crew/ellie]  # or dedicated media crew

  - keywords: [gastown, gt, polecat, witness, deacon]
    audience: [gastown]

  - keywords: [monitoring, prometheus, alertmanager, grafana]
    audience: [aegis/crew/malcolm]

defaults:
  # If no keywords match, broadcast to goldblum (chief of staff)
  fallback_audience: [aegis/crew/goldblum]

  # Always notify these (in addition to matched audience)
  always_notify: []
```

**Matching Algorithm:**

1. Lowercase the directive content
2. Check each route's keywords against content (substring match)
3. Union all matched audiences
4. If no matches, use fallback_audience
5. Deduplicate
6. Add always_notify list

### Confidence Scoring

For inference mode, assign confidence based on match quality:

- **High**: 3+ keyword matches → broadcast immediately
- **Medium**: 1-2 keyword matches → broadcast with "[inferred]" flag
- **Low**: 0 matches, fallback only → broadcast to goldblum for manual triage

## Broadcast Actions

For each affected crew member/rig, the broadcast service takes one of three
actions based on directive priority:

### Tier 1: Critical (P0/P1 directives, or Stiwi used urgent language)

- **Mail**: `gt mail send {crew} --permanent -s "HLA: {summary}" -m "{content}"`
- **Bead**: `bd create --rig {rig} -t task -p 1 "{summary}" -d "..."`
- **IRC**: Post to #aegis with mention
- **Nudge**: `gt nudge {crew} "New Stiwi directive — check mail"`

### Tier 2: Standard (P2 directives)

- **Mail**: `gt mail send {crew} --permanent -s "HLA: {summary}" -m "{content}"`
- **IRC**: Post to #aegis (no mention)

### Tier 3: Informational (P3, or FYI-type directives)

- **Mail only**: `gt mail send {crew} -s "FYI: {summary}" -m "{content}"`

### Priority Detection

Infer priority from content signals:

- **P0**: "now", "immediately", "urgent", "broken", "down"
- **P1**: "fix", "need", "should", "want", imperative verbs
- **P2**: "consider", "think about", "eventually", "would be nice"
- **P3**: "fyi", "observation", informational tone

## Implementation Plan

### Phase 1: Explicit tagging (implement first)

1. Add `tags: list[str]` parameter to `hla_store`
2. Store tags in record frontmatter and catalog.jsonl
3. Post-store: if tags present, broadcast via `gt mail send` to each tag
4. Simple: tag → mail. No inference, no bead creation.

### Phase 2: Keyword inference

1. Deploy broadcast-routes.yaml to automation.lan (HLA now on Garage S3, not CT 228)
2. When no explicit tags: run keyword matching
3. Broadcast with [inferred] flag so recipients know it's automated

### Phase 3: Bead creation + priority inference

1. Add priority detection from content signals
2. For P0/P1: create beads in target rig automatically
3. For P0: add nudge to wake target crew member

### Phase 4: Feedback loop

1. Track broadcast → action latency (did the crew member respond?)
2. Tune keyword routes based on actual directive→crew mapping history
3. Add "did this reach the right person?" confirmation mechanism

## Open Questions (for Stiwi)

1. **Bead creation**: Should broadcasts auto-create beads, or just notify?
   Creating beads is more actionable but adds noise. Mail-only is lighter.
2. **IRC integration**: Should every directive post to #aegis? Or only P0/P1?
3. **Goldblum role**: Should goldblum always be CC'd on broadcasts (as chief
   of staff), or only when he's explicitly tagged?
4. **Override mechanism**: Can Stiwi say "don't broadcast this" for some
   directives? (e.g., private notes, thinking-out-loud)

## Dependencies

- aegis-fjsnsc: HLA SSH auth must be fixed first (blocks all HLA tools)
- hla_store must be working before broadcast can trigger from it
- gt mail must be reliable for broadcast delivery (known ephemeral issues)

## Non-Goals

- This design does NOT replace goldblum's orchestration role. Goldblum still
  triages, prioritizes, and creates formal Strategic Priority entries.
- This is a notification system, not a delegation system. The crew member
  receives a notification and decides what to do.
- No AI interpretation of directives in Phase 1-2. Pure keyword matching.
  LLM-based intent classification can come in Phase 4.
