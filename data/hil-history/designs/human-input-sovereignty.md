# Human Input Sovereignty

> **Stiwi directive (2026-02-15):** Human input must be elevated and require
> further human input to remove.

This is a governance principle that applies system-wide. All crew and polecats
must understand and follow it.

## The Principle

Human input is the highest authority in the system. Agents serve human intent —
they cannot override, remove, or weaken it.

## Four Pillars

### 1. Provenance

All input carries a source tag: **human (overseer)** or **agent**.

| System | How provenance is tracked |
|--------|--------------------------|
| Beads | `actor` field — `overseer` vs crew/polecat name |
| Beads labels | `human-originated` label for human-created directives |
| CLAUDE.md | `<!-- human-authored -->` markers on Stiwi-written sections |
| Mail | `from` field distinguishes overseer from agent |
| Git | Commit author — Stiwi vs aegis |
| Guardrails | Protected file — agent changes require human PR approval |

### 2. Elevation

Human directives override agent decisions, always. When conflict exists between
human instruction and agent reasoning, **human wins**.

Examples:

- Stiwi says "use JWT" but agent prefers API keys → use JWT
- Standing directive contradicts agent optimization → follow directive
- Human-created bead says X, agent analysis says Y → follow bead

### 3. Protection

Removing or modifying human input **requires further human input**.

| Action | Agent CAN | Agent CANNOT |
|--------|-----------|--------------|
| Human-created bead | Add comments, propose changes | Close, delete, or weaken |
| Human-authored guardrail | Suggest updates via PR | Modify directly |
| Human config/directive | File follow-up bead | Override or remove |
| Standing directive | Read and follow | Unhook, close, or ignore |

### 4. Audit Trail

Changes to human directives must be logged with justification:

- **Git history** — all file changes are tracked
- **Bead history** — all bead modifications are logged with actor
- **Mail** — all agent-to-human communication is preserved

## Practical Patterns

### Filing beads about human directives

When you discover an issue with a human directive:

```bash
bd create --title "Suggestion: update <directive>" --type task \
  --description "Current directive says X. Proposing Y because Z. Requires Stiwi approval."
```

Do NOT modify the directive directly.

### Labeling human-originated work

When creating beads from human instructions:

```bash
bd create --title "..." --labels human-originated
```

### Marking human-authored doc sections

Use HTML comments to mark sections authored by Stiwi:

```markdown
<!-- human-authored: stiwi 2026-02-15 -->
## Section Title
Content here was written by Stiwi and requires human approval to modify.
<!-- /human-authored -->
```

### The standing directive pattern

Bead `aegis-0a9` is the reference pattern: a human-originated bead that is
hooked permanently, never closed by agents, and represents a standing
instruction from Stiwi.

## Reference

- `guardrails.md` — Human Input Sovereignty section and Golden Rule #16
- Bead `aegis-hz3q` — The directive that established this principle (labeled `human-originated`)
