# NOCTUA 1.0 — shared interface spec (all build tracks build to this)

Product: **Project NOCTUA** — city-owned, open-source ALPR system for cities.
Names are fixed: the front-door service is **Janus**, the witnessed audit chain is **Sentinel**, the edge NVR is Frigate (upstream, not renamed). The owl stays the logo.

## Non-negotiable facts and constants
- Cabot record (Jan 1–Jun 30, 2026, CPD reported): 9 cameras, 8,040,000 reads, 688 matches, 7 recoveries, 19 arrests → 8.56 matches/100k reads; 44,420 reads/day citywide; 4,936/camera/day.
- Retention: non-hit reads 14 days (hard delete, secure_delete + VACUUM); Arkansas ceiling 150 days (Ark. Code §§ 12-12-1801–1808); verified hits follow the legal-hold / evidence-export / prosecutor-sign-off lifecycle, never a flat timer.
- Statutory report: § 12-12-1805 six-month categories; plate-free outcome records preserved 18 months.
- Tiered authorization: Tier 1 hot-list alerts + Tier 2 contemporaneous queries = no prior authorization; Tier 3 historical = judicial authorization gate, configurable, TWO-KEY in 1.0 (requester + approving supervisor/judge designee), 48-hour emergency exception with mandatory post-hoc review of every use.
- Audit: Sentinel chain entries NEVER contain plate text — keyed HMAC plate_ref only. Chain streams to an outside sink; daily signed checkpoints (HMAC) with entry counts; key custody documented honestly.
- Paths: A (matching on dispatch/ACIC side) is the labeled planning assumption; B = CJIS build (out of scope, priced separately); C = pilot stops. Nothing in 1.0 claims Path B compliance.
- No cloud dependency anywhere in the design. Connectivity (LTE/fiber/PtP) is transport only; all data terminates on the city server.

## Janus API (v1 endpoints keep working; 1.0 additions)
Existing: /health /reads /search /hotlist /verify /hits /audit /audit/verify /audit/root /stats /holds /holds/release /suppressions /suppressions/release /outcomes /report.
1.0 additions:
- POST /reads stays the ONLY ingest path; the Frigate bridge authenticates as role system.
- POST /tier3/request {case_id, why, plate_fragment, auth_basis} → creates PENDING request (no search executed); POST /tier3/approve {request_id} by a DIFFERENT user with supervisor role → executes and returns results; POST /tier3/deny {request_id}. Emergency: POST /tier3/emergency executes immediately, flags EMERGENCY, and queues a mandatory post-hoc review item; GET /tier3/pending-reviews lists unreviewed emergency uses; POST /tier3/review {request_id, finding} closes one. Every step chained.
- POST /evidence/export {hit_id, case_id} (detective+supervisor) → writes an export bundle (JSON manifest + hit record + related reads) with SHA-256 per file and a manifest hash chained as EVIDENCE_EXPORT; POST /evidence/release {hit_id, prosecutor_signoff: name/date} supervisor-only, required before a held hit may be deleted.
- Cumulative counters: table `counters` (day, camera_id, reads, alerts) incremented at ingest; /report reads counters for plates_scanned so the six-month report survives retention deletes.
- Dead-man: table `heartbeats` (job, ts, ok, detail); retention and checkpoint jobs POST /heartbeat with the system key; GET /health reports any job overdue (retention >26h, checkpoint >26h) as degraded. scripts/alert_check.py exits nonzero and prints the overdue list (cron/systemd timer mails it or posts to a webhook URL from env — mechanism documented, no vendor assumed).
- Provisioning: scripts/provision.py CLI — add-user (prints the raw key ONCE, stores only its SHA-256), disable-user, list-users, rotate-key. No editing users.json by hand.
- Backup/restore: scripts/backup.py (sqlite online backup + config tarball + SHA-256 manifest, retention of backups follows the same 14-day/18-month schedule as the data classes they contain) and scripts/restore.py (verifies manifest before restoring; refuses on hash mismatch).

## Camera → server (Track B documents this; Track A assumes it)
- Each site: LPR camera (NDAA §889-compliant) + PoE + site router/modem. Backhaul options in preference order: city fiber/muni LAN > licensed PtP wireless > LTE/5G with WireGuard tunnel to the server. Camera VLAN has NO internet route; cameras are never port-forwarded; Frigate pulls RTSP/ONVIF through the tunnel. Store-and-forward: Frigate edge buffer holds events during a backhaul outage and syncs on reconnect; reads carry camera timestamps, server flags clock skew >5s.
- Server: dual-homed (camera VLAN + office LAN), Janus bound to office LAN via TLS-terminating local reverse proxy OR localhost + SSH — pick one in the install guide and say why; Frigate UI not exposed (write-only sensor rule from v0.9 carries forward).

## Simulator (Track C)
Extend noctua_sim.py — do not replace its audited core rates. Add scenario modules: camera outage (random + targeted), backhaul drop with store-and-forward delay, disk-full pressure on retention, clock skew, night/rain OCR degradation curves, hot-list staleness fail-closed, emergency-flag normalization measurement (K8), 9-camera full-volume 6-month run producing the §1805 report, legal-hold lifecycle, evidence export verification. Every scenario outputs observed-vs-expected with the assumption labeled.

## Style rules (all tracks)
- Python stdlib only for Janus/Sentinel/simulator. No new dependencies.
- Every file header states what it is and its limits. No silent assumptions: label them in-line.
- Honest claims only: "every action mediated by Janus is logged" — never "every action is logged."
- No Stoic Opposition branding anywhere. No real credentials, no real plates (synthetic AR-format only).
