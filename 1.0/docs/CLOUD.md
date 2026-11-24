# NOCTUA 1.0 — The Cloud-Vendor Audit

*What this document is: a function-by-function answer to the question "won't you need a vendor for that?" — for every function a city might assume requires a cloud service. What it is not: a claim that the internet is never touched. Connectivity is transport; the audit below is about who holds, processes, or can read the City's data.*

**Conclusion, stated first: NOCTUA requires zero cloud data vendors. No plate, read, image, hot list, audit entry, or backup ever has to exist on a computer the City does not own or directly control. Every function below has an on-premises answer that is already in the design — not a roadmap item.**

---

## The audit

| Function a city might assume needs a vendor | The assumption | NOCTUA's on-prem answer |
|---|---|---|
| **Plate storage** | "Reads have to live in the vendor's cloud — that's the product." | Reads live in Janus's database (SQLite in the reference build) on a city-owned server, in a city facility, on a city-controlled network segment. 14 days for non-hits, then hard-deleted. There is no other copy except the backups in the row below — also city-held. |
| **Hot-list matching** | "Matching against NCIC/ACIC requires the vendor's network." | Under the design's planning assumption (Path A, spec v2 §5), matching against official lists stays on the ACIC/dispatch side, through the Department's existing ACIC-connected workflow — a government system the Department already uses, not a vendor cloud. The city server holds only the Department's own local list. If ACIC's answer is Path B, the hot list is held on the city server under CJIS rules — still no vendor. Path C (approved vendors only) stops the pilot; it does not quietly convert it into a vendor deployment. |
| **Audit witness** | "Tamper-evidence needs a third-party logging service." | Sentinel entries stream as written to a sink on storage controlled by the City Clerk / outside auditor — a different part of the same city government, deliberately outside the Police Department and the system administrator's control. Daily signed checkpoints (root hash + entry count) are published to the Clerk and to a public git repository. A public git host stores **hashes and counts only** — no plate data, no log contents; if the City prefers, the same checkpoint file can be published on the City's own website or read into the minutes. The witness function needs an *independent holder*, not a vendor. |
| **Time sync** | "Devices get time from public NTP / vendor servers." | The city server runs its own NTP service for the camera VLAN (NETWORK.md §5). Cameras and site routers sync to the server. Upstream, the server disciplines its clock from standard time sources the way every city server already does — a time signal is not custody of data. |
| **Software updates** | "Updates come from the vendor's cloud, on the vendor's schedule." | All components are open source (Frigate, Janus, Sentinel, the OS, Docker). Updates are pulled as ordinary open-source packages/images by the administrator, staged on the Stage 0 / test feed first, and applied on the City's schedule (spec v2 §13) — never pushed by an outside party, never auto-applied to a live evidence system. A city that wants a fully offline posture can mirror the needed images/packages to city storage and update from the mirror; the design does not require any component to phone home, and camera firmware updates are administrator-initiated files, applied locally, with vendor cloud/P2P features disabled on the cameras themselves. |
| **Alerting** | "Dead-man alarms and outage alerts need a paging service." | The alert mechanism is deliberately vendor-free: `scripts/alert_check.py` runs on a host timer and reports overdue jobs (retention, checkpoint, sink health) by **local mail to named city addresses and/or a webhook to a city-controlled endpoint** (INTERFACE.md). City email is a city system. If a city additionally wants SMS paging, that is a notification convenience layered on top — the alert content is "job X is overdue," never plate data, and the system works without it. |
| **Backups** | "Backup means a cloud backup subscription." | `scripts/backup.py` writes an encrypted backup (SQLite online backup + config tarball + SHA-256 manifest) to **city storage** — a second city machine, a city NAS, or offline media rotated by staff (INSTALL.md §7). Backup retention follows the same schedule as the data classes inside them, so a backup can never become a way to keep reads past 14 days. Restore verifies the manifest before restoring and refuses on hash mismatch. |
| **Recognition / OCR** | "Plate reading is an AI cloud service." | Frigate's built-in LPR (or fast-alpr) runs on the city server / edge, on city hardware, with models stored locally. No image leaves the building for inference. This is the entire point of the open-source stack (spec v2 §4). |
| **The console / user access** | "Officers log in through the vendor's portal." | The console is a static page served from city infrastructure; it talks only to Janus, on the office LAN, through the City's TLS proxy. No external identity provider, no vendor account, no per-seat license. Accounts are provisioned locally with `scripts/provision.py`. |
| **Hot-list *content* (the lists themselves)** | "The vendor curates and distributes the lists." | Official lists reach the Department through ACIC — a state government channel — exactly as they do today for the Department's existing workflow. Local lists are created by named Department users inside Janus, with facts, author, and expiration on every entry (spec v2 §8, Tier 1). No commercial list broker is in the design. |

## The one honest nuance: LTE carriers

Sites on LTE backhaul (NETWORK.md §3, Option 3) rent transport from a commercial carrier. Stated precisely:

- The carrier carries **WireGuard-encrypted tunnel traffic** between the site router and the city server. It sees encrypted packets, their timing, and their volume — the same metadata it sees for any VPN.
- The carrier **never holds plate data**: it stores nothing for the City, processes nothing, has no account relationship with the system, no credentials, no API, and no ability to read the payload. If the carrier disappeared tomorrow, the City would lose connectivity to those sites (store-and-forward covers the gap, NETWORK.md §6) and nothing else — no data migration, no export negotiation, no hostage.
- This is the same relationship the City already has with the carrier that carries its ordinary encrypted traffic. **Connectivity is not custody.** Where even carrier metadata is unacceptable for a site, Options 1 and 2 (city fiber, point-to-point wireless) remove the carrier entirely; the design's preference order already puts them first.

A second, smaller nuance, for completeness: camera and server hardware is *purchased* from vendors, and open-source components are *downloaded* from public repositories. A purchase is not a data relationship. The test this audit applies is the one that matters: **does any outside party store, process, or have the technical ability to read the City's plate data, hot lists, or audit records? For NOCTUA the answer is no — by architecture, not by contract language.**

## What this buys, stated plainly

- There is no vendor to breach, subpoena for the City's data, sell access, change terms, raise prices, or discontinue the product.
- There is also no vendor to blame. The obligations a contract would normally carry — uptime, patching, verification, the runbook — belong to the City, named person by named person (OPERATIONS.md). Zero cloud vendors is a governance achievement and an operational commitment; this document claims the first and does not hide the second.

*End of CLOUD.md.*
