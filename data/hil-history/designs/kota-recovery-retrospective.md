# Koror → Kota Recovery Retrospective

**Incident**: koror (192.168.4.18) hardware failure — 1 drive lost, no data loss
**Duration**: 2026-03-27 to 2026-03-29
**Outcome**: No data loss. 1 drive lost (warranty replacement pending). Full service recovery on kota as failover.

---

## Timeline

| When | What |
|------|------|
| 2026-03-27 ~20:00 | koror hardware failure detected — all 25+ LXC containers down |
| 2026-03-27 ~20:30 | kota identified as recovery host (20 cores, 31GB RAM, 784GB NVMe) |
| 2026-03-27 ~21:00 | Docker emergency standup: AdGuard + Traefik on kota |
| 2026-03-27 ~21:40 | Forgejo restored via Docker — 28/28 repos pushed from S3 + local clones |
| 2026-03-27 ~21:45 | All 29 agent git remotes updated to kota Forgejo |
| 2026-03-28 | Incus container fleet: 22 containers provisioned via Terraform |
| 2026-03-28 | Docker→Incus migrations: Forgejo, PostgreSQL, Prometheus, Grafana, Loki |
| 2026-03-28 | Backup script deployed (per-db PG dumps, Dolt, S3 sync) |
| 2026-03-29 | Ansible inventory + playbook, common baseline on all containers |
| 2026-03-29 | Role-specific provisioning: traefik, message, tapestry, dashy, terraria, matrix |
| 2026-03-29 | Cloud-init fixes, agent remotes re-pointed to Incus Forgejo (192.168.7.216:3000) |
| 2026-03-29 | koror back online — 1 drive lost, no data loss |

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Time to first service restored | ~1 hour (Forgejo) |
| Time to DNS/routing operational | ~1.5 hours (AdGuard + Traefik) |
| Total repos restored | 28/28 (0 lost) |
| Containers provisioned on kota | 22 Incus containers |
| Services fully provisioned | ~10 (git, persistence, monitoring, dolt, secrets, traefik, tapestry, dashy, terraria, matrix) |
| Services with common baseline only | ~12 (awaiting role-specific provisioning or secrets) |
| Data loss | None confirmed |

---

## Ellie

### What I worked on

- **Recovery runbook** (`docs/runbooks/koror-kota-recovery.md`) — full triage of all ~25 LXC containers, tiered by criticality (Tier 0: DNS/Traefik/Forgejo/Infisical → Tier 4: skip)
- **Forgejo restoration** — stood up Forgejo on kota:3001 via Docker, restored all 28 repos from S3 backups and local clones. Wrote `scripts/forgejo-repo-push.sh` for API-driven repo creation + push
- **S3 backup inventory** — audited koror-backups S3 bucket, identified 5 repos missing from backup rotation (aegis, bucket, den, hometown, shanty)
- **Git remote migration** — updated 29 agent git clones across Gas Town to point to kota Forgejo
- **Docker Compose emergency stack** — DNS (AdGuard), Traefik reverse proxy, Prometheus/Grafana/Loki monitoring
- **Incus TF templates** (aegis-ors) — rewrote all 20 Proxmox container definitions as Incus resources with cloud-init profiles
- **ytdl-sub media archival** — extended recovery stack with computing history YouTube archiver per Stiwi's request

### What went well

1. **Distributed git clones saved us.** Every Gas Town agent clone is a full repo backup. We had fresh copies of all 5 repos missing from S3. Multi-agent architecture accidentally created a robust backup strategy.
2. **S3 backups were comprehensive.** 23/28 repos already backed up. PostgreSQL dumps, Forgejo data, ZFS snapshots all present.
3. **Tiered triage was the right call.** Prioritizing DNS → Traefik → Forgejo → everything else gave a clear execution order and prevented thrashing.
4. **Docker as emergency platform.** Not reinstalling the OS (Proxmox) and running Docker directly on kota's Ubuntu meant minutes to first container instead of hours.
5. **The runbook became the single source of truth** — every crew member and the overseer could see exactly what was up, what was down, and what the plan was.

### What was painful or could be improved

1. **No automated Forgejo backup validation.** We discovered the 5 missing repos only during the incident. A periodic `forgejo dump` + S3 sync with repo count assertion would have caught this earlier.
2. **Git credential chaos.** Agent clones had a mix of credential helpers — some token-based, some password-based, some for the old URL, some for the new. Took multiple attempts to get pushes working. Need a standard credential provisioning pattern.
3. **No runbook existed before the incident.** We wrote the recovery plan under pressure. Having even a skeleton DR runbook with container inventory and backup locations would have saved the first hour.
4. **Container IP addresses scattered across configs.** DNS records, Traefik routes, Ansible inventory, Terraform variables, Prometheus targets — the same IPs are hardcoded in 5+ places. One IP change means updating all of them.
5. **Incus TF templates are untested.** We wrote them during recovery but never actually applied them. They may have issues that only surface during `terraform apply`.

### Suggestions for future resilience

1. **Daily backup validation cron** — `forgejo dump` on kota, upload to S3, assert repo count matches expected. Already started with `scripts/kota-recovery/backup.sh`.
2. **Centralize container metadata** — single YAML/TOML file mapping container name → IP → services → DNS names. Generate Ansible inventory, Terraform vars, DNS records, and Prometheus targets from it.
3. **DR runbook as living doc** — keep `docs/runbooks/koror-kota-recovery.md` updated as the template for future hardware failures. Add a "last verified" date and periodic review bead.
4. **Standardize git credentials across agents** — single token per agent, stored in `~/.git-credentials`, provisioned by a setup script.
5. **Test the Incus migration path** — apply the TF templates on a non-production node before koror's next failure forces our hand.

---

## Hammond

### What I worked on
- Overall recovery coordination and triage
- Emergency Docker standup (AdGuard, Traefik, Forgejo) on kota
- S3 repo restore script — pushed all 28 repos to new Forgejo
- Updated all 30 agent git remotes (twice — Docker then Incus)
- Terraform templates for 22 Incus containers (full rewrite from Proxmox)
- Docker→Incus migrations for 5 services (Forgejo, PostgreSQL, Prometheus, Grafana, Loki)
- Backup script with per-db postgres dumps, Dolt fallback, S3 sync
- Ansible inventory + playbook + common baseline on all containers
- Role-specific provisioning (traefik, message, tapestry, dashy, terraria, matrix)
- Cloud-init template fixes (yamlencode → YAML template, DNS config, SSH)
- Traefik dynamic config updates for Incus container IPs

### What went well
- **S3 backups saved us**: Having 23 repos + PG dumps in S3 meant Forgejo was back in under an hour
- **Local git clones as distributed backup**: The 5 repos NOT in S3 were preserved across agent clones on luvu
- **Kota had massive spare capacity**: 20 cores, 31GB RAM — zero resource contention
- **Two-phase approach worked**: Docker emergency first (services in minutes), then proper Incus migration
- **Ansible roles pre-existed**: goldblum already had roles for every service, just needed inventory + playbook
- **Dolt on luvu was unaffected**: Beads/Gas Town coordination never went down

### What was painful
- **Agent remotes needed updating twice**: Once for Docker Forgejo (kota:3001), again for Incus Forgejo (192.168.7.216:3000). Should have gone straight to Incus.
- **Cloud-init yamlencode**: Terraform's yamlencode quoted keys like `"addresses"` broke Netplan parsing. Had to rewrite as YAML templates.
- **Docker-in-Incus complexity**: Dashy needed security.privileged, security.nesting, raw.lxc apparmor overrides, and syscall intercepts. Not obvious.
- **No automated DNS updates**: Manually updated AdGuard entries and Traefik configs for every IP change.
- **Secrets scattered**: Credentials in Infisical, env vars, ansible vaults — no single source of truth during recovery.
- **Container static IPs drifted**: Cloud-init didn't apply static IPs correctly on some containers, requiring manual TF template alignment.

### Suggestions for future resilience
1. **Automated failover for git remotes**: A single script/config that all agents read for Forgejo URL, updatable in one place
2. **Incus as primary from the start**: Skip Proxmox — Incus + Terraform is lighter and kota proved it works
3. **DNS-based service discovery**: Use DNS names (git.lan) consistently so IP changes only need DNS updates, not config changes everywhere
4. **Secrets consolidation**: All secrets in Infisical, all services read from there, no env var scattering
5. **Backup validation**: Regular restore drills — we got lucky that S3 backups were current
6. **Keep kota as warm standby**: Now that it's provisioned, maintain it as a failover site

---

## Research: Dedicated Critical Systems Host

### The Problem

When koror went down, **everything** went down — including DNS (AdGuard) and
reverse proxy (Traefik). These are foundational services that every other service
depends on. They shouldn't share fate with the hypervisor running application
workloads.

### Proposal: Raspberry Pi (or similar) as Critical Infrastructure Host

A dedicated low-power host running only services that must survive any single
hypervisor failure:

**Candidate services for critical host:**

| Service | Why Critical | Resource Needs | Pi-Compatible? |
|---------|-------------|----------------|----------------|
| **AdGuard Home (DNS)** | All .lan/.svc resolution — nothing works without it | ~128MB RAM, minimal CPU | Yes |
| **Traefik (reverse proxy)** | All HTTPS routing to services | ~64MB RAM, minimal CPU | Yes |
| **NTP (chrony)** | Time sync for certs, logs, Dolt | Negligible | Yes |
| **Uptime Kuma** | Monitoring/alerting — needs to outlive what it monitors | ~256MB RAM | Yes |
| **WireGuard** | External access — should survive internal failures | Negligible | Yes |

**NOT candidates** (too resource-heavy or not foundational):
- Forgejo, PostgreSQL, Dolt, Prometheus/Grafana, application services

### Hardware Options

| Option | Cost | RAM | Storage | Power | Notes |
|--------|------|-----|---------|-------|-------|
| **Raspberry Pi 5 (8GB)** | ~$80 | 8GB | microSD + USB SSD | 5W | Proven, huge community |
| **Raspberry Pi 4 (4GB)** | ~$55 | 4GB | microSD + USB SSD | 3-5W | More than enough for DNS+proxy |
| **Orange Pi 5** | ~$70 | 4-16GB | eMMC + NVMe | 5-10W | Faster storage, smaller community |
| **Intel N100 mini PC** | ~$120 | 8-16GB | NVMe | 10-15W | x86, overkill but future-proof |
| **Old laptop** | Free | Varies | Built-in | 15-30W | Battery = built-in UPS |

### Architecture

```
[Critical Pi] ─── DNS (AdGuard), Traefik, WireGuard, Uptime Kuma
     │
     ├── [koror] ─── Primary hypervisor (Proxmox LXC fleet)
     │
     └── [kota]  ─── Failover hypervisor (Incus containers)
```

**Key design principles:**
- Critical host runs bare-metal services (Docker at most), no hypervisor
- Static IP, hardcoded in router DHCP — not dependent on its own DNS
- Ansible-managed like everything else (add `critical_host` to inventory)
- UPS-backed if possible (Pi + USB UPS lasts hours)
- Traefik on critical host becomes the single entry point, proxying to whichever
  hypervisor is active — simplifies failover to "update Traefik backends"

### DNS Failover Pattern

**With DNS on the Pi:**
1. koror goes down → services on koror are unreachable
2. DNS still resolves (Pi is up) → clients get connection refused, not NXDOMAIN
3. Update DNS records to point to kota failover containers
4. Services recover without touching client configs

**Without DNS on Pi (what happened this time):**
1. koror goes down → DNS goes down → **everything** unreachable by name
2. Must reconfigure DNS elsewhere before anything else can recover
3. Recovery blocked on standing up DNS first, using raw IPs

### Open Questions

- [ ] Does Stiwi have a spare Pi or want to acquire one?
- [ ] Should Traefik on the Pi be the primary, or only a failover Traefik?
- [ ] DHCP server on the Pi too? (currently on router, but worth considering)
- [ ] How to handle Pi failure? (secondary DNS on router as fallback?)

---

## Action Items

| # | Action | Owner | Status |
|---|--------|-------|--------|
| 1 | Centralize Forgejo URL config for all agents | hammond | TODO |
| 2 | Consolidate all secrets into Infisical | hammond | TODO |
| 3 | Automate DNS record updates when container IPs change | hammond | TODO |
| 4 | Add the 5 local-only repos to S3 backup rotation | hammond | TODO |
| 5 | Regular backup restore drills (quarterly) | stiwi | TODO |
| 6 | Document Docker-in-Incus requirements | hammond | DONE |
| 7 | Draft koror switch-back plan | hammond | IN PROGRESS |
| 8 | Evaluate keeping kota as permanent failover | stiwi | TODO |
| 9 | Research + procure dedicated critical systems host (Pi) | stiwi/hammond | TODO |
| 10 | Design DNS/Traefik failover architecture for critical host | hammond | TODO |
| 11 | Daily backup validation cron | hammond | TODO |
| 12 | Centralize container metadata (single source → generate configs) | hammond | TODO |
| 13 | Standardize git credentials across agents | hammond | TODO |
| 14 | DR runbook as living doc with periodic review | hammond | TODO |
