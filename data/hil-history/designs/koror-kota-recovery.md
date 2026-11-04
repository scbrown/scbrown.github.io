# P0 Recovery Runbook: koror → kota Migration

> **STALENESS (2026-07-23, aegis-5jue):** every `luvu` below is HISTORICAL — luvu
> was decommissioned and its WSL image purged (Stiwi 2026-07-20, aegis-pxdm).
> ⚠️ In particular, the '5 repos only preserved as local clones on luvu' claim:
> if it was still true at purge time, those backup clones NO LONGER EXIST —
> re-verify backup coverage for those repos before relying on this plan.

**Date**: 2026-03-27
**Incident**: koror (192.168.4.18) hardware failure
**Target**: Rebuild LXC fleet on kota (192.168.4.48)
**Status**: IN PROGRESS
**Decision pending**: Proxmox (reuse TF templates) vs Incus/Docker on kota

## Situation

koror is the Proxmox hypervisor hosting ~25 LXC containers. Hardware failure
has taken down all containers. Plan: stand up LXC on kota (20 cores, 31GB RAM,
~900GB NVMe — massive spare capacity). Dolt already restored on luvu.

## kota Current State (verified 2026-03-27 20:40)

- **OS**: Ubuntu 25.10, kernel 6.17.0-14-generic
- **Resources**: 30GB RAM (28GB free), 784GB disk, 20 cores
- **GPU**: NVIDIA (persistenced running)
- **Docker**: v29.2.1 installed, no containers running
- **Incus**: NOT installed
- **Already running**: Bobbin (:3000), Jellyfin (:8096), Plex (:32400),
  node-exporter (:9100), promtail (:9080), rclone-hla mount
- **Network**: Pingable, SSH works (braino@)

### Platform Decision Factors

| Factor | Proxmox | Incus/Docker |
|--------|---------|--------------|
| Reuse existing TF templates | YES | Need new templates |
| Requires OS reinstall | YES (PVE replaces Ubuntu) | NO (runs on current Ubuntu) |
| Existing services (Plex/Jellyfin/Bobbin) | Must migrate into CTs | Keep running as-is |
| GPU passthrough | PVE GPU passthrough | Native NVIDIA access |
| Time to first container | Hours (install PVE first) | Minutes (Docker/Incus ready) |
| Long-term IaC alignment | Matches goldblum Ansible/TF | New patterns needed |

### What's Still Up (on luvu, unaffected)

- Gas Town (mayor, crew, deacon, polecats)
- Bobbin search (migrated to luvu earlier)
- Dolt (restored on luvu per hammond)
- gastown-api, gastown-dashboard, gastown-mcp, shanty

### What's Down (was on koror)

Every LXC container: CTs 121, 200-230+. All `.lan` and `.svc` DNS names
that resolve to koror containers are unreachable. Forgejo (git.lan) is down —
no git push/pull, no CI/CD.

---

## Tier 0: Infrastructure Foundation (must be first)

These must come up before anything else can function.

| CT | Name | Services | Backup? | Why First |
|----|------|----------|---------|-----------|
| 210 | dns | AdGuard Home (53, 3000) | YES | All `.lan`/`.svc` resolution depends on this |
| 221 | traefik-v2 | Traefik reverse proxy (443) | YES | All `.svc` HTTPS routing; 6 cores, 2GB |
| 206 | git | Forgejo (3000) | YES | Source control, CI/CD — everything deploys from here |
| 214 | secrets | Infisical (8080) | YES | Services need secrets to start |

**Dependency chain**: DNS → Traefik → Forgejo → Infisical

### Forgejo Preservation (CRITICAL)

Forgejo (CT 206) holds ALL source repos. **Good news: local clones exist for all repos.**

**Forgejo repos with local clones on luvu (distributed backup):**
| Repo | Most Recent Local Clone | Commit |
|------|------------------------|--------|
| stiwi/aegis | aegis/crew/stryder | 38a21fa (2026-03-25) |
| stiwi/goldblum | goldblum/crew/goldblum | 789251f (2026-03-23) |
| stiwi/bucket | bucket/crew/gibby | 8cdf399 (2026-03-13) |
| stiwi/den | den rig | check freshness |
| stiwi/hometown | hometown rig | check freshness |
| stiwi/shanty | shanty rig | check freshness |

**GitHub-hosted repos (safe, not on koror):**
- bobbin, gastown, tapestry, desire-path, ai-gardener, pixelsrc

**Restoration plan:**
1. Stand up fresh Forgejo on kota (CT 206 or new CT)
2. Restore PostgreSQL (CT 203) first — Forgejo needs it
3. Push all repos from local clones to new Forgejo instance
4. Verify all branches/tags match pre-failure state
5. Re-create CI runners, webhooks, tokens

**Garage S3 (CT 230)** is also down — check if vzdump backups or Forgejo DB
dumps were stored there. If so, those are inaccessible until Garage is restored.

**Risk**: Any commits pushed between the most-recent local clone and the failure
that weren't pulled by any agent are lost. The gap is small (hours to days).

### S3 Backup Inventory (koror-backups-501843416807)

S3 contains 23 repos under `forgejo/repositories/stiwi/`:
bobbin, buckleup, chronicle, cv, dotfiles, goldblum, goldblum.wiki, gt,
homelab-mcp, homelab-mcp.wiki, idad, ideas, kickstop, leansoft,
orchestrator, patreoff, pulse, reckoning, resume, storeprofithub,
tambour, ttp, webb

Also: `postgres/14/`, `forgejo/data/` (avatars, indexers, JWT),
`radarr/`, `sonarr/`, `zfs/` backups.

### CRITICAL: Repos NOT in S3

These 5 repos are **only** preserved as local git clones on luvu:
- **aegis** (freshest: crew/hammond, 2026-03-27)
- **bucket** (freshest: crew/gibby, 2026-03-13)
- **den** (freshest: mayor/rig, 2026-03-17)
- **hometown** (freshest: mayor/rig, 2026-02-21)
- **shanty** (freshest: mayor/rig, 2026-02-18)

**Action**: Push these FIRST to new Forgejo. Add to S3 backup rotation post-recovery.

### Repos Safe on GitHub (no action needed)

bobbin, gastown, tapestry, desire-path, ai-gardener, pixelsrc

### Recovery Push Script

`scripts/forgejo-repo-push.sh` — Creates repos via API and pushes all
branches/tags from freshest local clones. Needs `FORGEJO_TOKEN` env var.

---

## Tier 1: Core Data Services

| CT | Name | Services | Backup? | Notes |
|----|------|----------|---------|-------|
| 203 | persistence | PostgreSQL 14 (5432) | YES | Forgejo + other apps depend on this |
| 204 | message | RabbitMQ (5672, 15672) | YES | Message queue for service communication |
| 121 | goldblum | Ansible control node | YES | IaC — needed to deploy everything else. 854GB ZFS, SSH from luvu |

**Note**: Dolt (CT 236) is already restored on luvu per hammond's mail.

---

## Tier 2: Operations & Comms

| CT | Name | Services | Backup? | Notes |
|----|------|----------|---------|-------|
| 202 | monitoring | Prometheus, Grafana, Alertmanager, Loki, ntfy, Uptime Kuma, VictoriaMetrics, PVE exporter | YES (partial) | Observability — need this to validate recovery |
| 205 | automation | aegis-tg, den-tg, alert-comms-bridge, MCP servers, PR review, voice-svc, n8n | NO | Gas Town comms hub — Stiwi's Telegram bridge |
| 201 | bot | aegis-irc, message-router, The Lounge, Ergo IRC, aegis-webhook | YES (partial) | IRC infrastructure |

---

## Tier 3: Applications

| CT | Name | Services | Backup? | Notes |
|----|------|----------|---------|-------|
| 200 | matrix | Conduit + Element | NO | Matrix chat |
| 213 | seeker2 | Sonarr, Radarr, NZBGet, Overseerr, Tautulli, Recommendarr, Agregarr | YES (partial) | Media automation |
| 230 | garage | Garage S3 (3900) | NO | Object storage (pensieve, hla, backups, bobbin-indexes) |
| 229 | bucket | Bucket app (8080) | NO | Homepage |
| 227 | tapestry | Tapestry (8070) | NO | |
| 222 | dashy | Dashy dashboard (4040) | NO | Docker |
| 207 | librechat | LibreChat (3080) | NO | Docker |
| 208 | litellm | LiteLLM proxy (4000) | NO | Docker |

---

## Tier 4: Low Priority / Skip

| CT | Name | Reason |
|----|------|--------|
| 209 | traefik-legacy | COWBOY — skip, CT 221 is primary |
| 211 | probe | RTL433 — non-critical |
| 212 | terraria | Game server |
| 215 | wireguard | VPN — check if external access needed |
| 224 | pages | Already BROKEN before incident |
| 228 | hla | DECOMMISSIONED |

---

## Standup Procedure (per container)

### Prerequisites on kota
1. Install Proxmox VE (or LXC directly if not using PVE)
2. Configure networking: bridge for 192.168.7.0/22 (vmbr6 container network)
3. Ensure storage for container rootfs

### Per-Container Steps
1. Create LXC container with matching CT ID (or new IDs if needed)
2. Restore from backup (vzdump) if available, OR fresh install + Ansible deploy
3. Update DNS in AdGuard to point to new container IPs
4. Update Traefik routes if IP scheme changes
5. Verify service health

### Ansible Deployment (via goldblum)
Once goldblum (CT 121) is up:
```bash
# From goldblum, deploy common role first
ansible-playbook -l <container> site.yml --tags common

# Then service-specific role
ansible-playbook -l <container> site.yml --tags <service>
```

---

## Coordination

| Who | Role |
|-----|------|
| **Stiwi** (overseer) | Hardware, Proxmox install on kota, network |
| **goldblum** (CT 121) | Ansible control node — deploy services |
| **hammond** (crew) | Coordination lead, dispatched P0 |
| **ellie** (crew) | This runbook, Forgejo preservation, service triage |

---

## Recovery Checklist

- [x] kota hardware verified and booted (2026-03-27 ~20:30)
- [ ] Proxmox VE (or LXC host) installed on kota — **DECISION: Docker emergency first, Incus later**
- [ ] Network bridge configured (192.168.7.0/22)
- [x] Backup inventory completed — S3 has 23 repos + PG + ZFS (2026-03-27 ~21:35)
- [ ] **Tier 0**: DNS (210) up
- [ ] **Tier 0**: Traefik (221) up
- [x] **Tier 0**: Forgejo — Docker on kota:3001, 28/28 repos restored (2026-03-27 ~21:40)
- [ ] **Tier 0**: Infisical (214) up
- [ ] **Tier 1**: PostgreSQL (203) up — Docker on kota (Forgejo has its own PG)
- [ ] **Tier 1**: RabbitMQ (204) up
- [ ] **Tier 1**: goldblum (121) up — Ansible ready
- [ ] **Tier 2**: Monitoring (202) up
- [ ] **Tier 2**: Automation (205) up — aegis-tg/den-tg working
- [ ] **Tier 2**: Bot (201) up — IRC working
- [ ] **Tier 3**: Remaining services stood up
- [ ] DNS records updated for any IP changes
- [ ] Traefik routes verified
- [x] All Gas Town agent git remotes updated to kota (29 clones, 2026-03-27 ~21:45)
- [ ] All services health-checked
