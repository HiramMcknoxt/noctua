# NOCTUA 1.0 — Installation Guide

*Audience: the city IT person (or department administrator) installing NOCTUA. This guide alone should be sufficient: hardware, OS, software, configuration, keys, and the go-live checklist. It assumes the design documents (NETWORK.md for sites, CLOUD.md for the vendor posture) and the pilot spec v2 for policy. If this guide and the spec ever disagree, the spec governs and the disagreement is a bug to report.*

*Labels: **[record]** = from the Cabot record / adopted spec. **[estimate]** = planning estimate. **[assumption]** = engineering assumption in this guide, labeled for challenge.*

---

## 0. The gates come first — read before buying anything

Software being installable does not authorize turning it on. NOCTUA installs in a *lab* state freely (bench, test plates, synthetic data). **Capture of any real plate — including a lot test — is gated**, in this order (spec v2 §§2, 5, 14):

1. **Written policy adopted** by the Council under Ark. Code § 12-12-1805(a)(3), incorporating the access tiers. *No adopted policy, no capture of any kind.*
2. **ACIC answer in writing** establishing the path: A (matching on the ACIC/dispatch side — this build's planning assumption), B (CJIS system — **not this build**; separately priced and approved), or C (pilot stops).
3. **Separate Council authorization** after public hearing, for the pilot itself, with its sunset date.
4. **Camera inventory confirmed in writing** (department inventory / FOIA), including the Home Depot Dr / Going Dr ownership question. The locations in `config/cameras.yaml` are community-mapped points, **not** an official inventory; per-site models of the existing leased units are not in the public record and are not asserted anywhere in this package.

The go-live checklist in §8 restates these as checkboxes. An installer who reaches §8 with a gate unchecked stops.

## 1. Hardware sizing — 9 cameras

Basis: **44,420 reads/day citywide; 4,936 reads/camera/day [record — CPD-reported Jan.–Jun. 2026 volume]**. Retention: non-hit reads 14 days; audit log ≥3 years; outcome records 18 months (spec v2 §9).

**Storage math** (per-read sizes are **[assumption]**, to be replaced by Stage 0 measurements):

| Data class | Math | 14-day / retained size |
|---|---|---|
| Read metadata in Janus DB (~1 KB/read incl. indexes) | 44,420 × 1 KB/day | ~0.6 GB per 14 days |
| Plate-crop snapshots (~100 KB/read) | 44,420 × 100 KB/day ≈ 4.4 GB/day | **~62 GB** per 14 days |
| Frigate media buffer (event snapshots/clips at the server, ≤14-day media retention) | Sized generously at 8× the crop store | ~500 GB provisioned |
| Sentinel audit chain (actions, not reads; ~1 KB/entry, generous volume) | A few thousand entries/day worst case | <6 GB over 3 years |
| Outcome records (plate-free, 18 months) | Hundreds of rows/month | Negligible |
| Backups on the backup target (14-day rotation of the above, compressed) | ~70–100 GB per full set, rotating | ~1 TB target |

**Recommended server [estimate — procurement prices the actual specification]:**

- CPU with **AVX/AVX2** (hard floor for Frigate LPR, spec v2 §4); 8+ cores comfortable for 9 streams. An optional detector accelerator (Coral TPU or a modest GPU) improves headroom; it is not required and not in the base price.
- RAM: 16 GB minimum, **32 GB recommended** (Frigate's own floor is 4 GB; 9 cameras plus LPR inference plus Janus want the headroom).
- Storage: **2 × 2 TB SSD/NVMe, mirrored** (RAID-1 or ZFS mirror) for the live volumes — capacity is ~25× the computed need, bought for endurance and mirror safety, not size; plus the separate ~1 TB backup target (second machine, NAS, or rotated offline media — INSTALL §7). A single unmirrored disk is the one hardware shortcut this guide forbids: disk failure is a *when*, and the mirror is what makes it a non-event (CONTINGENCIES.md).
- Dual network interfaces (camera VLAN + office LAN, NETWORK.md §8). A small UPS sized for a clean shutdown.

This is a commodity mini-tower or 1U server. The spec v2 §12 edge/server allowance was $1,500–$3,500 **[estimate]**; procurement prices the real specification.

## 2. Operating system and base setup

1. Install a current long-term-support Linux server OS (Debian 12 or Ubuntu 24.04 LTS — either; pick the one city IT already knows). Full-disk encryption at rest (LUKS) with the passphrase held by the System Administrator and the named backup, sealed copy with the Clerk.
2. Create a dedicated `noctua` service account; disable password SSH; administrator access by individual SSH keys only. Keep the OS on its normal security-update cadence (CLOUD.md: updates are pulled by the administrator, staged, never pushed by a vendor).
3. Install Docker Engine + the Compose plugin from the OS/Docker repositories. Confirm `docker compose version`.
4. Configure the host firewall: camera-VLAN interface accepts only Frigate's camera ports from camera addresses; office-LAN interface exposes only the TLS proxy (§5) and SSH from the management segment; everything else drops. The camera VLAN gets **no internet route** (NETWORK.md §4) — set no NAT and no forwarding for it.
5. Configure NTP: the server disciplines its clock from upstream sources and serves NTP to the camera VLAN (NETWORK.md §5).
6. Configure WireGuard on the server as the hub (NETWORK.md §4): one peer per site, per-site keypairs, spoke access limited to the Frigate ports.

## 3. Install the software

```bash
git clone <city repo> noctua && cd noctua/deploy
cp .env.example .env            # fill in camera credentials + NOCTUA_AUDIT_KEY (§6)
cp config/cases.example.json config/cases.json   # or wire the records-system export
# Edit config/cameras.yaml: per site — address, enabled flag. Credentials NEVER go in the YAML.
docker compose up -d janus frigate
curl localhost:8080/health      # expect {"ok": true, ...} with sentinel_sink status
```

Notes that matter:

- **Frigate image pin:** the compose file pins `ghcr.io/blakeblackshear/frigate:0.16.0` **[verify at deploy time]** — confirm the pinned tag exists and the LPR configuration keys in `config/frigate.config.yml` match that version's documentation before first run. Budget integration time for the Frigate→Janus bridge (it polls Frigate's events API and posts to `POST /reads` as role `system`); the lockdown configuration (localhost bindings, ≤14-day media retention, no human accounts on Frigate) is already in the shipped files.
- **Users are provisioned, not hand-edited (1.0):** use `scripts/provision.py` (§6). Do not hand-edit `users.json` — the v0.9 hand-hash procedure is retired.
- **Cases:** the case list Janus validates against must come from the records-system export, refreshed on the cadence set with the records unit; if the feed goes stale, Janus **fails closed** — searches stop and the failure alarms (spec v2 §7 item 9). A hand-maintained list is acceptable only for the bench/lot phase with test cases.

## 4. Site bring-up (per camera)

Per NETWORK.md §§2–5 and the survey checklist (NETWORK.md §9):

1. Mount camera, PoE, cabinet, surge protection; disable camera onboard storage and cloud/P2P features; replace default credentials (credentials into `.env` as `CAMnn_USER`/`CAMnn_PASS` only).
2. Terminate backhaul (fiber / PtP / LTE), bring up the site's WireGuard spoke with its own keypair.
3. Set the camera's NTP to the server; confirm skew <5 s at the Frigate host.
4. In `config/cameras.yaml`: set the site's address and `enabled: true`. Restart Frigate; confirm the stream pulls and test reads (test plate, bench phase) arrive via `POST /reads`.
5. Drive-by test with a consenting test vehicle: read lands, timestamp sane, crop legible. Only then is the site a site.

## 5. Exposing Janus to officers — the decision

**Decision: Janus stays bound to localhost on the server. A TLS-terminating reverse proxy (Caddy or nginx — city IT's choice) on the same host exposes Janus on the office-LAN interface only, and the console is served from the same proxy.** Why this and not the alternatives:

- *Not* Janus directly on the LAN: Janus is stdlib Python; letting a maintained proxy own TLS, headers, and connection handling keeps Janus's attack surface at its API logic, and gives the City one place for certificates.
- *Not* SSH tunnels per officer: tunnels don't scale past a handful of users, and the predictable workaround is a shared account on a shared workstation — the exact failure the account rules exist to prevent.
- The proxy is **office-LAN only** — never internet-facing, never port-forwarded. Janus's own named-user + key authentication still applies behind the proxy; the proxy adds transport encryption, not a second identity system. Certificates: city internal CA or a publicly issued cert for an internal hostname — either is fine; an expired cert is a dead-man item (OPERATIONS.md).

## 6. Keys and provisioning

**User keys** — `scripts/provision.py`:

```bash
python3 scripts/provision.py add-user det.okafor --role detective   # prints the raw key ONCE
python3 scripts/provision.py list-users
python3 scripts/provision.py rotate-key det.okafor
python3 scripts/provision.py disable-user det.okafor                 # at role change, immediately
```

The raw key is shown once, at issuance, in person. Only its SHA-256 is stored. There are no shared accounts, and "no shared accounts exist" is a go-live checkbox, not an aspiration. Roles: `detective`, `patrol`, `supervisor`, `auditor` (read-only), `system` (the Frigate bridge only — never a human).

**The audit key (`NOCTUA_AUDIT_KEY`) and checkpoint custody — decide explicitly.** Sentinel checkpoints are HMAC-signed with this key. Three custody options, in increasing strength:

| Option | What it means | Honest limit |
|---|---|---|
| (a) Key on the server (shipping default) | Checkpoints are signed automatically; tampering by outsiders and by anyone without the key is detectable | Does **not** stop a fully privileged insider who holds both the chain and the key — they can rewrite and re-sign (see CANT-DO.md) |
| (b) Key held Clerk/auditor-side | The checkpoint job runs where the Clerk/auditor controls the key; the server side cannot produce a valid signature alone | Strongest practical option; costs a small operational step each day, automatable on Clerk-controlled hardware |
| (c) Split custody | Key split between Administrator and Clerk (e.g., sealed halves / two-person ceremony at setup) | Strong against lone insiders; recovery if a holder leaves must be rehearsed, not improvised |

The Commission chooses; the choice and its limit are recorded in the go-live minutes. Whichever option: the sink path (`NOCTUA_SENTINEL_SINK`) must be a mount the Clerk/auditor side controls — a sink only the server can write is a weaker witness (v0.9 README, carried forward).

**Camera credentials** live only in `.env` (mode 0600, never committed). **WireGuard keys** live in the router and server configs. **Disk-encryption passphrase** per §2. Losing the audit key or the disk passphrase is a contingency with a procedure (CONTINGENCIES.md), not a surprise.

## 7. Backups

1. Install `scripts/backup.py` on a nightly timer: SQLite online backup of the Janus database + config tarball + SHA-256 manifest, written to the backup target (city storage the Police Department does not solely control, where the City's structure allows).
2. **Backup retention follows the data:** backups containing reads rotate out on the same 14-day schedule; backup sets kept for audit-log preservation follow the 3-year log schedule with reads already expired out of them by the retention job's own schedule. A backup must never become a shadow archive that defeats the 14-day promise.
3. Test restore quarterly with `scripts/restore.py` — it verifies the manifest first and **refuses on hash mismatch**. An untested backup is a hope, not a backup (OPERATIONS.md §7).

## 8. Go-live checklist

**Gates (all four, minuted):**

- [ ] Written policy adopted (§ 12-12-1805(a)(3)), tiers configured in Janus to match the adopted text — including which Tier 3 authorization instrument the City Attorney confirmed
- [ ] ACIC answer in writing; path recorded (A: proceed · B: **stop — this build is not the CJIS build** · C: **stop**)
- [ ] Council authorization after public hearing, with sunset date on the calendar
- [ ] Camera inventory confirmed in writing, Home Depot / Going Dr ownership resolved; `cameras.yaml` matches the confirmed inventory

**People:**

- [ ] System Administrator and named backup, by name, in the policy; backup has run one update and one log review under observation
- [ ] Outside auditor designated (paid/contracted role), auditor account issued, sink + checkpoint verification demonstrated by the auditor
- [ ] TAC liaison named; prosecutor disposition schedule for evidence approved (spec v2 §9)
- [ ] All user keys issued in person via `provision.py`; **zero shared accounts**; Frigate holds no human accounts

**System:**

- [ ] Retention timer installed (nightly) and a forced test run deleted test reads past cap, with `secure_delete` + VACUUM verified
- [ ] Checkpoint job installed (daily); Clerk received a test checkpoint; sink shows `ok: true` at `/health`
- [ ] Dead-man alerting tested end-to-end: stop a job, watch the alarm arrive (Administrator, Auditor, Clerk)
- [ ] Backup taken and `restore.py` verified it; restore test scheduled quarterly
- [ ] Case-list feed live and fail-closed behavior tested (stale feed ⇒ searches stop)
- [ ] Checkpoint key custody option chosen (§6) and recorded
- [ ] Accuracy protocol (spec Appendix C) ready; day-90 report template ready
- [ ] Adversarial verification of the data-access boundary completed with no unresolved critical bypass (spec v2 §14)

*End of INSTALL.md.*
