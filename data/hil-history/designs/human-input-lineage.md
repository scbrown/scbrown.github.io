# Human Input Lineage Tracking

**Bead**: aegis-9vxu
**Status**: Phase 1 SHIPPED (basic lineage tracking). Phases 2-4 (propagation, search, visualization) NOT IMPLEMENTED — need follow-up work.
**Author**: aegis/crew/goldblum

## Problem

When you `git blame` a line in any repo, you see which agent committed it.
But you can't answer: "Why does this exist? What human input caused it? Was
this Stiwi's idea, a patrol finding, or an agent's initiative?"

The problem goes beyond beads. Every artifact the system produces — docs,
code, configs, blog posts — has an origin story. That story starts with human
input (an idea, a directive, a review, a correction) and flows through agents
to become committed content. Today that chain is invisible.

## Goals

1. `git blame` any line → commit → trailers → bead → human origin (full chain)
2. Distinguish levels of human guidance: idea, directive, review, approval, correction
3. Support multiple humans with different authority scopes
4. Source of truth lives in Git (trailers on commits) — survives clones, forks, mirrors
5. Derived indexes in Dolt + Bobbin for structured queries and semantic search
6. No metadata added directly to files — files stay clean
7. Answer: "What % of our codebase is human-directed vs agent-initiated?"

## Architecture

```text
Human input (Telegram, IRC, Tapestry, direct)
  │
  ▼
Bead (captures origin: who, what, when, channel, exact words)
  │
  ▼
Agent work (crew plans, polecats execute)
  │
  ▼
Git commits (carry lineage trailers linking back to bead + human)
  │
  ├──▶ Dolt index (structured queries: "show all Stiwi directives")
  ├──▶ Bobbin index (semantic search: "what did Stiwi say about IRC?")
  └──▶ Tapestry (visualization: blame → chain → origin)
```

**Source of truth**: Git (commits + trailers)
**Index layers**: Dolt (structured), Bobbin (semantic)
**Visualization**: Tapestry

## Design

### 1. Git Trailers as Source of Truth

Every commit from an agent carries lineage trailers:

```bash
fix: update Traefik routing for irc.svc

Added TLS termination and WebSocket proxy for ergo IRC.

Lineage-Bead: aegis-xgfnu
Origin-Type: human-correction
Origin-Human: stiwi
Origin-Channel: telegram
Origin-Message: lets use irc.svc as the traefik link
Origin-Timestamp: 2026-02-16T01:15:00Z
Planning-Doc: docs/plans/architecture-roadmap.md
Planned-By: aegis/crew/goldblum
Executed-By: aegis/polecats/rust
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Trailers are part of the commit message — they survive rebases, cherry-picks,
and mirror pushes. `git log --format='%(trailers)'` extracts them.

### 2. Levels of Human Guidance

Not all human input is equal. The `Origin-Type` trailer classifies how the
human influenced this work:

| Origin-Type | Description | Weight | Example |
|-------------|-------------|--------|---------|
| `human-directive` | Explicit instruction to do something | Highest | "get the mayor running" |
| `human-idea` | Suggestion or direction, agent interprets | High | "i like where we were headed with marshal" |
| `human-review` | Feedback that changes the approach | High | "do you not think OTel is needed?" |
| `human-approval` | Explicit sign-off on proposed work | Medium | "this is good, go ahead" |
| `human-correction` | Fixes agent's approach mid-flight | Highest | "lets use irc.svc not irc.lan" |
| `human-standing` | Persistent rule affecting all work | Permanent | "planner/orchestrator ONLY" |
| `crew-planning` | Crew strategic planning doc drives work | High | architecture-roadmap.md defines implementation phases |
| `agent-patrol` | Automated patrol discovered the need | Low | Drift patrol finds config mismatch |
| `agent-initiative` | Agent's own idea, no human trigger | Lowest | goldblum files improvement bead |
| `system` | Automated trigger (alert, webhook, cron) | Low | Alert fires, triggers remediation |

**Weight** determines priority when multiple origins compete. Human-correction
and human-directive override agent-initiative. Human-standing applies
permanently until a human revokes it (Golden Rule 16).

### 3. The Traceability Chain

Starting from any line of code:

```bash
git blame docs/patrols/marshal.md
  → commit ece8e45 by aegis/crew/goldblum
    → trailer: Lineage-Bead: aegis-ht19
      → bead aegis-ht19: origin_human=stiwi, origin_type=human-idea
        → origin_message: "i like where we were headed with this marshal idea"
          → Stiwi said this on Telegram at 2026-02-15T23:05:00Z
```

Every link in the chain is a concrete, queryable artifact:

- **Line → Commit**: `git blame` (already works)
- **Commit → Bead**: `Lineage-Bead` trailer (new)
- **Bead → Human**: `origin_human` + `origin_type` in bead metadata (new)
- **Bead → Related beads**: `caused-by` / `delegated-from` dependencies (exists)
- **Human → Identity**: Human registry with authority + channels (new)

### 4. Bead Origin Metadata

Beads capture the human input at the point of creation. This is the bridge
between human words and git commits:

```json
{
  "lineage": {
    "origin_type": "human-idea",
    "origin_human": "stiwi",
    "origin_channel": "telegram",
    "origin_timestamp": "2026-02-15T23:05:00Z",
    "origin_message": "i like where we were headed with this marshal idea",
    "planned_by": "aegis/crew/goldblum",
    "designed_by": "aegis/crew/goldblum",
    "executed_by": "aegis/crew/goldblum"
  }
}
```

The `origin_message` field preserves **Stiwi's exact words**. This is the
data — the specific human input that caused the work to exist.

### 5. Human Identity Registry

A Dolt table for registered humans (unchanged from v1):

```yaml
human_id:     "stiwi"
display_name: "Stiwi"
authority:    "overseer"        # overseer | operator | observer
trust_level:  100               # 0-100, used for priority weighting
channels:
  telegram: 8360797693
  irc: stiwi
  tapestry: true
security_scope:
  repos: ["*"]
  rigs: ["*"]
  can_approve: true
  can_escalate: true
```

### 6. Trailer Injection

Agents don't manually write trailers. The tooling injects them automatically:

**Option A: gt commit wrapper**
`gt commit` reads the current bead context (from `BD_BEAD` env var or
hooked work) and appends trailers automatically. The bead's lineage
metadata provides origin_type, origin_human, etc.

**Option B: Pre-commit hook**
A git pre-commit hook in every repo checks for required trailers. If
missing, it reads the current bead context and appends them. Rejects
commits without a `Lineage-Bead` trailer (except for trivial commits
flagged with `--no-lineage`).

**Option C: Post-commit indexer**
A Forgejo webhook or git post-receive hook on git.svc reads new commits,
extracts trailers, and writes them to the Dolt lineage index. This is the
indexing step, not the injection step — injection must happen at commit time.

Recommendation: **A + C**. `gt commit` injects trailers at creation time.
Post-receive hook indexes them into Dolt for querying.

### 7. Derived Indexes

**Dolt index** (structured queries):

```sql
CREATE TABLE lineage_commits (
  repo          VARCHAR(100),
  commit_sha    VARCHAR(40),
  commit_date   DATETIME,
  author        VARCHAR(100),
  bead_id       VARCHAR(20),
  origin_type   VARCHAR(30),
  origin_human  VARCHAR(50),
  origin_channel VARCHAR(20),
  origin_message TEXT,
  planned_by    VARCHAR(100),
  executed_by   VARCHAR(100),
  PRIMARY KEY (repo, commit_sha)
);
```

Queries:

- `SELECT * FROM lineage_commits WHERE origin_human='stiwi' AND commit_date > '2026-02-15'`
- `SELECT origin_type, COUNT(*) FROM lineage_commits GROUP BY origin_type`
- `SELECT * FROM lineage_commits WHERE bead_id='aegis-ht19'`

**Bobbin index** (semantic search):

- Index trailer content alongside code content
- "What did Stiwi say about IRC?" → finds commits with Origin-Message
  mentioning IRC
- "Show me all human corrections" → finds Origin-Type: human-correction

### 8. Tapestry Visualization

**Blame view**: Click any file → see annotated blame with origin badges:

```text
[stiwi/idea]     # Marshal Patrol
[stiwi/idea]     **Bead**: aegis-ht19
[goldblum/plan]  ## Patrol Steps
[goldblum/plan]  ### 1. Crew Health Scan
```

**Chain view**: Click a commit or bead → see full lineage chain as a graph:

```text
stiwi (idea, telegram) ──▶ aegis-ht19 ──▶ commit ece8e45
                                        ──▶ commit 8f3c3ef
                                        ──▶ commit e07ebec
```

**Origin dashboard**: Pie chart of work by origin type across all repos.

**Directive tracker**: All human inputs with their downstream status
(planned, in-progress, completed, stale).

## Enforcement: Protecting Human-Originated Content

> **ZFC REVIEW NEEDED**: The enforcement mechanisms below contain ZFC
> violations (hardcoded protection level tables, bash pattern matching on
> trailers, content hash heuristics). These need to be redesigned so that
> all decision-making is delegated to models. The framework should be a
> thin shell: gather context (blame, trailers, diff) → call model for
> decision → enforce mechanically. See `docs/principles/zfc.md`.

Tracking lineage is passive. Enforcement makes it active — preventing agents
from silently overwriting human decisions.

### The Problem

A polecat is working a bead, editing `guardrails.md`. Line 42 says "Services
go into Proxmox LXC containers, NOT luvu." That line traces back to a
`human-directive` from Stiwi. The polecat has no idea. It just sees markdown.

Agents can't intrinsically know which lines are human-protected. The system
must catch mutations at multiple layers — some preventive, some detective.

### Protection Levels

Different origin types warrant different enforcement:

| Origin-Type | Protection | Behavior |
|-------------|------------|----------|
| `human-standing` | **block** | Commit rejected. Cannot modify without human approval. |
| `human-correction` | **block** | Commit rejected. Human specifically fixed this — don't undo it. |
| `human-directive` | **review** | Commit allowed, but flagged. Held for human review before merge. |
| `human-approval` | **review** | Human approved this state. Verify before changing. |
| `human-idea` | **warn** | Commit allowed, warning logged. Agent interpretation can evolve. |
| `human-review` | **warn** | Feedback incorporated. May be refined by agents. |
| `agent-*` | **none** | Freely modifiable. |
| `system` | **none** | Auto-generated, freely modifiable. |

This directly encodes Golden Rule 16: `block` and `review` levels require
human input to remove human input. `warn` allows evolution but creates an
audit trail.

### Layer 1: Pre-Commit Hook (the guardrail)

The hard stop. Installed in every repo via goldblum IaC:

```bash
#!/bin/bash
# .git/hooks/pre-commit (or global githooks)
# For each modified line in staged changes:

git diff --cached --unified=0 | while read file line; do
  # Get the original commit that last touched this line
  sha=$(git blame -L "$line,$line" --porcelain "$file" | head -1 | cut -d' ' -f1)

  # Skip uncommitted lines (0000000...)
  [[ "$sha" == 0000000* ]] && continue

  # Check for human-origin trailers on that commit
  origin=$(git log -1 --format='%(trailers:key=Origin-Type,valueonly)' "$sha")

  case "$origin" in
    human-standing|human-correction)
      human=$(git log -1 --format='%(trailers:key=Origin-Human,valueonly)' "$sha")
      echo "LINEAGE BLOCK: $file:$line originated from $human ($origin)"
      echo "  This content is protected. To modify:"
      echo "  1. Create an escalation bead: bd create 'Override: ...' -t task"
      echo "  2. Get human approval"
      echo "  3. Recommit with: --lineage-override=<bead-id>"
      exit 1
      ;;
    human-directive|human-approval)
      human=$(git log -1 --format='%(trailers:key=Origin-Human,valueonly)' "$sha")
      echo "LINEAGE REVIEW: $file:$line originated from $human ($origin)"
      echo "  This commit will be held for human review before merge."
      # Don't block — flag for refinery
      touch .lineage-review-required
      ;;
    human-idea|human-review)
      echo "LINEAGE WARN: $file:$line traces to human input ($origin)"
      # Log but allow
      ;;
  esac
done
```

When a polecat hits a block:

```text
LINEAGE BLOCK: guardrails.md:42 originated from stiwi (human-directive)
  Content: "Services go into Proxmox LXC containers, NOT luvu."
  This content is protected. To modify:
  1. Create an escalation bead: bd create 'Override: ...' -t task
  2. Get human approval
  3. Recommit with: --lineage-override=<bead-id>
```

The `--lineage-override=<bead-id>` flag requires a bead that:

- Has `origin_type: human-approval` or `human-directive`
- References the original bead being overridden
- Was created after the human approved the change

### Layer 2: Proactive Index (the cheat sheet)

Agents can query protection status *before* editing:

```bash
gt lineage check guardrails.md
```

```text
guardrails.md lineage protection:
  L12-15: human-standing (stiwi) — BLOCKED
  L28-30: human-directive (stiwi) — REVIEW
  L42:    human-directive (stiwi) — BLOCKED
  L55-60: agent-initiative (goldblum) — free to modify
```

Backed by a Dolt table rebuilt from git blame + trailers:

```sql
CREATE TABLE lineage_protected (
  repo           VARCHAR(100),
  file_path      VARCHAR(500),
  line_start     INT,
  line_end       INT,
  commit_sha     VARCHAR(40),
  origin_type    VARCHAR(30),
  origin_human   VARCHAR(50),
  protection     VARCHAR(10),   -- block | review | warn | none
  content_hash   VARCHAR(64),   -- SHA-256 of the protected content
  updated_at     DATETIME,
  PRIMARY KEY (repo, file_path, line_start)
);
```

The `content_hash` tracks the actual content, not line numbers. If lines
shift due to insertions above, the hash lets the system re-locate the
protected content. The index is rebuilt periodically by a patrol or
post-push hook.

Polecat CLAUDE.md instructions include:

```text
Before modifying any file, run: gt lineage check <file>
If any lines show BLOCKED or REVIEW, do not modify those lines.
Instead, create an escalation bead and note which lines need changing.
```

### Layer 3: Refinery Safety Net

When the refinery processes a merge request:

1. Run blame analysis on the full diff
2. If any `block`-protected content was modified:
   - Reject the merge
   - File an escalation bead automatically
   - Notify the human: "Polecat attempted to modify protected content"
3. If any `review`-protected content was modified:
   - Hold the merge
   - Post to async decision queue (Telegram + Tapestry)
   - Human approves or rejects
4. If only `warn`-protected content was modified:
   - Merge proceeds
   - Audit entry created in Dolt

This catches anything that bypassed the pre-commit hook (e.g., `--no-verify`
or direct push).

### Layer 4: Lineage Patrol (detective)

A periodic patrol (new plugin or extension of drift-patrol):

- Scans recent commits across all repos
- Extracts trailers, checks for lineage violations
- Verifies that any `--lineage-override` usage has a valid approval bead
- Detects commits without lineage trailers (missing attribution)
- Files beads for violations
- Reports to marshal for goldblum's status briefing

### The Override Flow

When legitimate modification of human-protected content is needed:

```text
Polecat hits LINEAGE BLOCK on guardrails.md:42
  │
  ▼
Polecat creates escalation bead:
  bd create "Override: update container placement policy" \
    --caused-by aegis-0a9
  │
  ▼
goldblum routes to async decision queue:
  → Telegram: "Polecat needs to modify stiwi's directive on container
     placement (guardrails.md:42). Current: 'Services go into Proxmox
     LXC containers, NOT luvu.' Proposed change: [reason]"
  → Tapestry: /decisions view shows the request
  │
  ▼
Stiwi approves (from any channel):
  → Bead updated with human-approval
  │
  ▼
Polecat recommits with override:
  git commit --lineage-override=aegis-xxxx
  │
  ▼
New commit trailers record the override:
  Origin-Type: human-approval
  Origin-Human: stiwi
  Lineage-Override: aegis-0a9 (original directive)
  Lineage-Approval: aegis-xxxx (approval bead)
```

The override itself becomes part of the lineage. You can trace: original
directive → override request → human approval → new content. Nothing is lost.

### Critical Files: Bootstrap Protection

Some files are human-protected by definition, even before lineage tracking
begins:

- `guardrails.md` — safety-critical, human-approved changes only
- `charter.md` — identity document, human-directed
- `CLAUDE.md` — core harness, human-approved
- Standing directive beads (aegis-0a9) — permanent rules

For these files, a one-time bootstrap tags all existing content as
`human-standing` or `human-directive`. This is a manual annotation:

```bash
gt lineage bootstrap guardrails.md --origin-type=human-directive \
  --origin-human=stiwi --reason="Pre-lineage content, all human-directed"
```

This creates a synthetic trailer entry in the lineage index (not in git
history — it's a Dolt-only annotation for content that predates the system).

## Implementation Phases

### Phase 1: Convention (no code changes)

- Define trailer schema (this doc) ✓
- Define protection levels (this doc) ✓
- goldblum starts adding trailers to commits manually
- Bead origin metadata populated on new beads
- Validate: can we trace a commit back to human input?

### Phase 2: Trailer Tooling (gt changes)

- `gt commit` auto-injects lineage trailers from bead context
- `gt lineage check <file>` queries protection status
- `--no-lineage` escape hatch for trivial/housekeeping commits
- `--lineage-override=<bead-id>` for approved overrides

### Phase 3: Enforcement Hooks

- Pre-commit hook checks staged changes against lineage index
- Block/review/warn behavior per origin type
- Override flow with escalation bead + human approval
- Bootstrap critical files (guardrails.md, charter.md, CLAUDE.md)

### Phase 4: Indexing (Dolt + Bobbin)

- Post-receive hook on git.svc extracts trailers → lineage_commits table
- Periodic blame rebuild → lineage_protected table
- Bobbin indexes trailer content for semantic search
- `bd lineage <id>` command traces bead → commits → origin

### Phase 5: Refinery Integration

- Merge queue checks for lineage violations
- Auto-hold merges that touch review-protected content
- Auto-reject merges that touch block-protected content
- Async decision queue integration for human approval

### Phase 6: Human Registry

- Dolt humans table with authority levels
- `gt human register` / `gt human list`
- Per-human security scoping
- Channel verification (Telegram ID, IRC hostmask)

### Phase 7: Visualization (Tapestry)

- Annotated blame view with origin + protection badges
- Lineage chain graph viewer
- Origin dashboard (pie chart, trends)
- Directive tracker (Stiwi's inputs → status)
- Override history (who approved what, when)

### Phase 8: Lineage Patrol

- Plugin: aegis-lineage-patrol (runs every 2h)
- Scans for missing trailers, unauthorized overrides
- Verifies protection index freshness
- Reports to marshal

## Security Considerations

- Git trailers are immutable once pushed (agents cannot rewrite history)
- Human identity verified via channel (Telegram ID, SSH key, IRC auth)
- Origin-Type: human-* entries cannot be added by agents without a verified
  human channel event (prevents agents fabricating human attribution)
- Golden Rule 16: Human entries in lineage cannot be removed by agents
- `block`-protected content requires human approval to modify (enforced)
- Override beads create an immutable audit trail of who approved what
- Dolt index is append-only — new commits add rows, never delete
- Authority scoping enforced at query level (Tapestry, Bobbin)
- Pre-commit hooks can be bypassed with `--no-verify` but refinery catches it

## What This Replaces

| Before | After |
|--------|-------|
| `git blame` shows agent name | Same, but trailers reveal human origin |
| Bead shows `created_by: agent` | Bead metadata shows `origin_human: stiwi` |
| "Who asked for this?" → unknown | Full chain: line → commit → bead → human words |
| No distinction between human types | Overseer / operator / observer with scoped access |
| No distinction between idea/directive/review | 6 human guidance levels with weights |
| Lineage data in beads only | Lineage in git (truth) + Dolt/Bobbin (index) |
| Agents can silently overwrite human decisions | Pre-commit hook blocks, refinery catches, patrol audits |
| No override audit trail | Override bead → human approval → new trailers → full chain |
