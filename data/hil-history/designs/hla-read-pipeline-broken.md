# HLA Read Pipeline Broken — Investigation (aegis-3y667e)

> **Date**: 2026-03-02
> **Investigator**: maldoon
> **Status**: Root cause identified, fix beads filed, parent bead closed
> **Note (2026-03-05)**: CT 228 (hla.lan) has been deprecated. HLA data migrated
> to Garage S3, accessed via rclone FUSE on automation.lan. The sync chain
> described below is no longer the live architecture.

## Summary

All `hla_query` and `hla_recent` MCP calls return stale data (only 7 records
from Feb 23) despite 125 records existing in Garage S3. The original hypothesis
(subagent MCP transport issue) was **incorrect**.

## Architecture

```text
hla_store (write) ──► automation /mnt/hla (rclone FUSE → Garage S3)
                       ↓ (unknown sync mechanism)
                      hla.lan CT 228 /opt/hla/records/
                       ↓ (rsync in bobbin-reindex.sh, daily 3am)
                      kota /var/lib/bobbin/repos/hla-records/
                       ↓ (bobbin index)
hla_query (read) ◄── Bobbin /archive/search|recent endpoints
```

## Record Counts (as of 2026-03-02)

| Location | Records | Latest | Status |
|----------|---------|--------|--------|
| Garage S3 (via automation /mnt/hla) | 125 | 2026-03-02 | OK |
| hla.lan CT 228 /opt/hla/records/ | 108 | 2026-02-28 | Stale |
| kota /var/lib/bobbin/repos/hla-records/ | 7 | 2026-02-23 | Broken |

## Root Cause: Two Breaks in Sync Chain

### Break 1: hla.lan → kota rsync (CRITICAL)

The daily full reindex script (`/opt/bobbin/reindex.sh` on kota) runs:

```bash
sudo -u bobbin rsync -a --no-compress --delete root@hla.lan:/opt/hla/records/ "$REPO_DIR/hla-records/"
```

This fails because:

1. **sudo-rs denies bobbin user** — `sudo-rs: I'm sorry bobbin. I'm afraid I can't do that`
2. **SSH key not authorized** — bobbin@kota cannot authenticate to <root@hla.lan>

Evidence: `journalctl -u bobbin-reindex --since '2026-03-02 03:05' --until '2026-03-02 03:06'`

Additionally, the **incremental reindex** (every 15 min) skips hla-records entirely
because it only processes git repos (`git fetch`/`git pull`), and hla-records is not
a git repository.

### Break 2: S3 → hla.lan sync (SECONDARY)

hla.lan (CT 228) has 108 of 125 records, with the latest from Feb 28.
No sync timer, cron, or service was found on CT 228. The `.state/adapters/`
and `.state/consumers/` directories are empty. It's unclear how records
ever got to hla.lan — possibly a one-time manual seed or a mechanism that
stopped working.

## Fix Beads

- **aegis-xfcwl7** (P1): Fix bobbin rsync hla.lan → kota
  - Remove unnecessary `sudo -u bobbin` wrapper
  - Set up SSH key auth for bobbin@kota → <root@hla.lan>
  - Add rsync step to incremental-reindex.sh
- **aegis-2sio9h** (P2): Investigate and fix S3 → hla.lan sync

## Impact

Every agent's `hla_query` and `hla_recent` calls return only 7 records from
Feb 23 instead of 125. Human directives from Feb 24 onward are invisible to
all agents. `hla_store` continues to work (writes directly to S3).
