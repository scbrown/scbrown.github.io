# §68: HLA Auto-Update stiwi-wants.md

**Status:** Superseded — stiwi-wants.md deprecated 2026-03-03. HLA tools (hla_store/hla_query) are the replacement. No further implementation needed.
**Date:** 2026-02-23
**Origin:** Stiwi directive via hammond: "seems pointless to always do both"
**Blocked on:** ~~aegis-fjsnsc (HLA SSH auth to hla.lan broken)~~ RESOLVED. Note: stiwi-wants.md deprecated 2026-03-03. May need redesign — auto-update HLA query integration instead.

## Problem

When Stiwi gives a directive, it currently requires two separate manual actions:

1. An agent calls `hla_store()` to record the verbatim input in the HLA archive
2. An agent manually updates `stiwi-wants.md` with a summarized entry

Stiwi's position: this is redundant. Storing in HLA should automatically
propagate to stiwi-wants.md.

## Current Architecture

```text
Stiwi speaks (IRC/Telegram/session)
    ↓
Agent calls hla_store(content, channel, ...)
    ↓ Write to /mnt/hla/ on automation.lan (Garage S3 via rclone FUSE)
Archive: /mnt/hla/records/YYYY/MM/DD/hi-{ulid}.md
    ↓ (MANUAL, separate step)
Agent edits stiwi-wants.md → git commit → git push
```

## Design: Post-Store Hook

Add a **post-store hook** to `hla_store` that triggers stiwi-wants.md update.

### Option A: Inline in hla_store (Recommended)

After writing the archive record, `hla_store` also:

1. Reads the current stiwi-wants.md from the aegis repo
2. Appends a new entry to the Solicitation Log table
3. Commits and pushes

**Pros:** Single atomic action, no polling delay, no extra infrastructure.
**Cons:** hla_store becomes slower (~5s for git ops), couples MCP to git.

### Option B: Async via RabbitMQ

After writing the archive record, `hla_store` publishes to a `hla.updates`
queue. A consumer (maldoon deacon plugin) picks it up and updates the file.

**Pros:** hla_store stays fast, decoupled.
**Cons:** More infrastructure, eventual consistency, maldoon must be running.

### Option C: Deacon polling (already designed)

The `aegis-warden-intent-sync` plugin polls HLA every 5-10 min, diffs against
stiwi-wants.md, and updates. Already spec'd in human-intent-archive.md.

**Pros:** No MCP changes needed.
**Cons:** Up to 10min stale, requires deacon plugin to be built, maldoon dependency.

## Recommendation: Option A (inline) with fallback to C

Option A gives Stiwi the experience he wants — one action, both systems updated.
If it proves too slow, degrade to Option C.

### Implementation Spec (Option A)

In `hla_store_impl()` (homelab_mcp.py ~line 1460), after the archive write succeeds:

```python
# Post-store hook: update stiwi-wants.md
try:
    _update_stiwi_wants(record_id, content, channel, context, timestamp)
except Exception as e:
    # Log but don't fail the store — archive is the source of truth
    logger.warning(f"stiwi-wants.md auto-update failed: {e}")
```

The `_update_stiwi_wants()` function:

1. **SSH to luvu** (the Gas Town host, not hla.lan):

   ```bash
   cd /home/braino/gt/aegis/crew/arnold  # or goldblum's copy
   git pull --rebase
   ```

2. **Parse stiwi-wants.md** — find the Solicitation Log table:

   ```python
   # Find the table, get the highest §N, compute next §N
   # Append row: | {date} | {channel} | {summary} — (§{N+1}) |
   ```

3. **Generate summary** — first sentence of content, truncated to 80 chars,
   with `(§{N})` suffix and `hi-{record_id}` citation.

4. **Write, commit, push**:

   ```bash
   git add docs/plans/stiwi-wants.md
   git commit -m "docs: capture §{N} {brief} (auto-synced from HLA)"
   git push
   ```

### Edge Cases

- **Git conflicts**: If push fails (another agent pushed), retry once with
  `git pull --rebase`. If still fails, log warning and skip — the deacon
  plugin (Option C) can catch up later.
- **Duplicate detection**: Check if content hash already exists in
  Solicitation Log (grep for `hi-{id}`) before appending.
- **Section numbering**: Parse existing entries to find max §N, increment.
  The § number is assigned at write time, not by the human.
- **Full entry vs. log entry**: The Solicitation Log gets a one-line summary.
  Full "Strategic Priorities" entries (with Source/Priority/Intent Records
  fields) are created by a human or goldblum review — the auto-sync only
  appends to the log.

### Scope Boundary

This auto-update ONLY appends to the **Solicitation Log** table at the bottom
of stiwi-wants.md. It does NOT:

- Create full Strategic Priority entries (that's goldblum's job)
- Modify existing entries (human input sovereignty)
- Assign priorities (goldblum triages)

## Acceptance Criteria

- When hla_store succeeds, stiwi-wants.md Solicitation Log has a new row within 10s
- Row format: `| {date} | {channel} | {summary} — (§{N}) |`
- Failure to update stiwi-wants.md does NOT fail the hla_store call
- No duplicate entries for the same hi-{id}
- Git commit message references the §N and hi-{id}

## Beads

- Blocked on aegis-fjsnsc (HLA SSH auth fix)
- Implementation bead to be filed when aegis-fjsnsc is resolved
