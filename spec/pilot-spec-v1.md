# CITY OF CABOT, ARKANSAS

# Cabot Open-Source ALPR Pilot — Design Specification

## Project NOCTUA

*Codename (working title only — the formal document title above is what appears in any packet): **NOCTUA** — Athene noctua, the little owl of Athena/Minerva: a sentinel that watches one post and ignores everything it is not there for. Backronym, for packet use if wanted: **N**o **O**utsourcing, **C**ity-**T**racked, **U**nshared **A**ccess. Component names in this spec: the Front Door API is **Janus** (the Roman god of doors and thresholds — nothing passes except through him), and the outside-witness checks are the **Sentinels** (§10).*

**A city-owned, open-source automated license plate reader pilot, adapted from the Clark County, Arkansas county-owned design**

|  |  |
|---|---|
| Prepared for | The Citizens Commission on a City-Controlled ALPR System; the Mayor, the City Attorney, and the Members of the Cabot City Council |
| Sponsor draft | Corey Spangler, Council Member, Ward 1 Position 2 |
| Status | **DRAFT — for Commission discussion. Not introduced, not a vendor quote, not a procurement award, and not an appropriation. Nothing in this spec authorizes a system by itself.** |
| Date | November 23, 2026 |
| Companion documents | (1) Draft Ordinance — Third-Party ALPR Ban and Citizens Commission (Nov. 16–17, 2026); (2) Cabot City-Controlled ALPR Plan — Technical and Cost Proposal (Nov. 16, 2026, rev. Nov. 17); (3) Draft Tiered Judicial Authorization for Access to ALPR Data (Nov. 19, 2026) |
| Principal source adapted | Brayden Sanders, *Flock Alternatives: A Research Hub* — Clark County, Arkansas (GitHub: TiredofSleep/flock-alternatives, Oct. 2026): `design/architecture.md`, `design/sentinels.md`, `research/02-audit-log-models.md`, `research/04-build-path-cjis.md`, `research/07-arkansas-state-police-lpr.md`, `docs/action-plan.md`. Cited below as "Clark County design," with section names so any reader can check it. |
| No branding note | This is unbranded city business. It carries no project or campaign branding of any kind. |

*How to read the labels: **[Source: …]** = a figure or rule taken from a named record. **"Applied arithmetic"** = a verified per-unit figure multiplied by a Cabot count, inputs shown. **"Estimate / allowance"** = a planning figure procurement or the Commission must confirm or replace. **"Commission decision"** = a threshold or choice this spec proposes but the Commission may change, stating its reasons.*

---

## 1. Purpose — what this pilot is, and what it is not

The November 16 City-Controlled ALPR Plan proved a *purchase* model on the record: buy Axis cameras outright, license recognition software (the Quincy / OdinEye route), own the data. This spec adds the route that plan listed but did not design in full: **recognition software the City does not rent at all** — open-source software, running on city hardware, with every search forced through one logged front door that someone outside the Police Department can check.

No U.S. city has put such a system into production. OpenALPR, the original open-source engine, is effectively unmaintained since Rekor acquired it in 2019 (last open release 2.5.103, March 2018). The current open stack — Frigate NVR's built-in LPR and fast-alpr — is proven in homes, parking lots, and HOAs, not in a police system. The Clark County hub is, like this spec, "research and planning, not a product." This pilot is therefore designed as a **test with kill conditions**, not as a promise.

**The pilot answers five questions, in order:**

1. **CJIS/ACIC:** Can a city-owned box match plates against hot lists without itself becoming an unmanaged CJIS system — or, if it does become one, what does compliance actually cost?
2. **Accuracy:** Can open-source recognition read Arkansas plates at Cabot road speeds, day and night, well enough to be a lead generator — measured against a hand-checked sample, not a vendor claim?
3. **Accountability:** Can every search be forced through one front door, tied to a real person and a validated case number, into a tamper-evident log that an outside witness actually verifies?
4. **Deletion:** Does data delete on schedule, automatically, and can the City *prove* nothing older than the cap survives?
5. **Maintenance:** How many staff hours does this really take, week to week — the cost every vendor comparison hides?

**What the pilot is not:** not an expansion (no camera beyond the locations in §3), not a replacement decision (the full-system decision stays where the companion ordinance puts it — a separate Council ordinance, after public hearing, on the Commission's June 2027 recommendations), and not a back door around that vote. If the pilot fails its gates, the purchase model in the November 16 plan remains the fallback, and the no-ALPR outcome remains on the table.

---

## 2. Design principles — borrowed from Clark County, tightened for Cabot

1. **One logged front door.** "All reads come through one API. There is no direct DB access for users and no national-lookup feature." [Source: Clark County design, architecture §3] Every documented ALPR abuse in the research — a DEA agent searching under a local officer's password, free-text reasons like "idk" — happened because there was a side door or an unreviewed log.
2. **The log is only real if an outsider checks it.** A hash chain nobody verifies is, in the Clark County phrase, "tamper-evident to nobody." The root hash is published on a schedule to a place the City operating the system does not control, and a named outside auditor verifies it on a short cadence. [Source: Clark County design, architecture §3; audit-log research §§ "Tamper-evident logging," "Design requirements"]
3. **A case number is validated, not typed.** Each query requires a case number **validated against a real case record** (RMS or case list). "No valid open case means no search." Free text is not a reason. [Source: Clark County design, architecture §3]
4. **Policy before cameras.** The Clark County action plan's hard gate is adopted verbatim in substance: "nothing gets built until ACIC confirms how hotlist access works and the [governing body] passes the ordinance." For Cabot: nothing that captures a public-road plate is built until (a) the ACIC answer in §5 is in writing, and (b) the Council has adopted the governing policy — including the tiered judicial-authorization rules in §8.
5. **Government ownership already works in Arkansas.** The Arkansas State Police own their "LPR systems, equipment, databases and data" (ASP Rule 5(d)), retain no more than 150 days, log deletions and every disclosure, and report quarterly to the Legislative Council. [Source: Clark County research 07, ASP LPR Rules 130.01.24 Ark. Code R. 002] Cabot's design copies ASP's structure and goes further where ASP is silent: ASP defines query logs but does not specify their contents or a review schedule; this spec does both.
6. **Open-source all of it.** Code, configuration (minus credentials and hot-list data), runbooks, and audit tooling are published, "so the [city] is never locked to any one maintainer." [Source: Clark County design, architecture §7] This is also the license test in §6.
7. **Begin from the limits, not the capabilities** — the charge the companion ordinance already gives the Commission. No component is procured because it *can* do something the policy does not ask for.

---

## 3. Pilot scope

| Item | Pilot spec |
|---|---|
| Stage 0 — bench / lot test | 1 camera, on City property (e.g., a city lot), City-owned and volunteer vehicles only. **No public-road capture, no hot list, no enforcement use.** Runs during the Commission's work (spring 2027) to answer the accuracy question cheaply and lawfully. |
| Stage 1 — road pilot | **3 cameras**, at 3 of the 9 existing Flock locations, chosen by the Commission with the Department for (a) an entry/exit chokepoint, (b) a higher-speed site (the hard case for open-source OCR), and (c) a slow-approach site (the easy case). No new locations. No increase in citywide camera count at any point. |
| Duration | **90 days** of live operation, following the Clark County action plan's pilot length, then a public report and automatic shutdown unless the Council affirmatively extends it. [Source: Clark County action plan §5] |
| Users | Named, individually credentialed users only, designated in the governing policy. Planning assumption: the System Administrator, one backup administrator, the Chief's designee, and the outside auditor (read-only, log-only). No other accounts in the pilot. |
| Data in scope | Plate reads (plate text, site, date/time, plate-crop image) at the 3 pilot sites only. Raw video is not a function of this system and is not retained. |
| Data out of scope | No regional or national lookup network. No facial recognition. No vehicle-fingerprint / make-model-color search product. No bulk export. No immigration, parking, code-enforcement, or revenue use — Act 668 of 2025 (Ark. Code §§ 12-12-1801 to -1808) already limits lawful uses; the governing policy lists the pilot's permitted uses exhaustively. |
| Sunset | Pilot authority, accounts, and hot-list access expire at day 90. Data collected is deleted on the §9 schedule regardless of what the Council later decides. |

---

## 4. Architecture — one front door, an outside witness, and a retention job

Adapted directly from Clark County design, architecture §1, with Cabot's retention and tier rules substituted:

```
[LPR cameras x3] --RTSP--> [Edge / NVR: Frigate LPR *or* fast-alpr]
                                  |  plate reads only
                                  v
                           [Read store (Postgres) — city hardware,
                            city-controlled network segment]
                                  |
                   every query goes through — no exceptions
                                  v
[Users: named officers] --MFA--> [FRONT DOOR API] --> [Audit log:
                                  |                     hash-chained,
                                  |                     append-only]
                                  |
                     signed root hash, weekly --> [EXTERNAL WITNESS:
                                  City Clerk/Treasurer + public repo]

[Retention job] --hard-deletes past cap, logs itself--> read store + audit log
[Report job]    --> monthly pilot report + final public report
                    (Ark. Code § 12-12-1805 stats + query volume
                     + sharing recipients + anomalies)
[Hot-list matching] --> ON THE ACIC SIDE if ACIC confirms it (§5, Path A)
```

**Components**

| Component | Spec | Notes / source |
|---|---|---|
| Cameras | Dedicated LPR/ANPR, native RTSP/ONVIF, shutter at least 1/1000s (1/2000s at night / speed), IR with focus-shift compensation, motorized varifocal; target ~100 pixels-per-foot on the plate. Two camera classes are tested head-to-head in Stage 0: (a) commodity LPR (Clark County example: Dahua/EmpireTech ITC215 class, ~$300–$450) and (b) the AXIS Q1800-LE from the November 16 plan ($1,779 MSRP). | Camera requirements and commodity price: Clark County research 04, "Cameras." Axis price: November 16 plan §3, named retailers, Nov. 2026. **NDAA §889 warning:** Hikvision/Dahua-class cameras are barred if federal or federally funded money is used — see §12, Risk 4. If any federal dollar touches the pilot, class (a) must be an NDAA-compliant equivalent, priced in procurement. |
| Recognition — candidate A | **Frigate NVR built-in LPR:** YOLOv9 plate detector + PaddleOCR; needs at least 4 GB RAM and an AVX/AVX2 CPU. Frigate's own docs warn, in substance, "if a human can't read the characters, Frigate usually can't either," and publish no accuracy numbers. | Clark County research 04, "Software stack"; design architecture §7. |
| Recognition — candidate B | **fast-alpr:** MIT license, ONNX models, swappable detector/OCR backends. | Clark County research 04; architecture §7. Cabot's November 16 plan records fast-alpr as actively versioned (v0.4.0, March 2026). |
| Bake-off rule | Stage 0 runs A and B on the *same* camera feeds and the *same* hand-checked sample (Appendix C). The Commission picks one for Stage 1 on measured read rate, not preference. The loser is documented, not quietly dropped. Paid on-prem fallback (Plate Recognizer, ~95% claimed, Docker) may be benchmarked for comparison only; adopting it converts this from an open-source pilot to the purchase model and must be reported as such. | Fallback and claim: Clark County research 04. |
| Read store | Postgres (or equivalent open-source store) on a city-owned server, on a network segment controlled by the City, encrypted at rest and in transit. No vendor cloud. No general-purpose city file share. | CJIS conditions if this store ever holds CJI: §5, Path B. |
| Front Door API | The *only* query path. Enforces: individual account + MFA; validated case number (§7); tier rules (§8); result minimization; canary stripping (§10). Direct database access for users is technically disabled, not just policy-prohibited. | Clark County architecture §§1, 3. |
| Audit log | Hash-chained, append-only, on WORM / object-lock backup. Minimum fields at Appendix A. Retention and report jobs write their own entries. | Clark County architecture §4; audit-log research §"Tamper-evident logging" (WORM + hash chain is the "small-shop-feasible" pattern). |
| External witness | Signed root hash published **weekly** during the pilot to (a) the City Clerk/Treasurer, who is outside the Police Department chain of command, and (b) a public git repository, so any resident, journalist, or defense attorney can verify the chain did not change after the fact. | Clark County architecture §3 (witness = "clerk, public git repo"); sentinels §"Who controls what." |
| Retention job | Scheduled hard delete past the §9 cap; every run logs rows deleted and the oldest remaining timestamp; a run that fails alerts the Administrator and the auditor the same day. | Clark County architecture §§1, 5. |
| Report job | Generates the monthly pilot report and the day-90 public report from the log itself — counts are computed, not hand-tallied. | Clark County architecture §§1, 6 (report contents). |

---

## 5. The CJIS / ACIC boundary — the decision gate that comes first

This is the single most important section. Capturing plates is not CJIS-regulated. **Crossing them against NCIC/ACIC hot lists is.** [Source: Clark County research 04, "CJIS and ACIC"]

**Step 1 — the joint ACIC call (February 2027, Commission's first task).** Through the Police Department's Terminal Agency Coordinator (TAC), the Commission asks ACIC, in writing where ACIC will give it in writing, the questions at Appendix B. The Clark County plan's framing question is adopted: *how do LPR systems in Arkansas receive hot-list data, what agreement does it take, and does a city server holding the hot list become a CJIS system?* ACIC's published contact in the Clark County plan is (501) 682-2222 — verify before use. Small Arkansas agencies usually hold **ACIC Indirect Access** (they can receive criminal-justice information but cannot run transactions directly; recipients need an FBI-assigned ORI). [Source: Clark County research 04]

**Step 2 — build only the version ACIC's answer permits:**

| Path | ACIC answer | What gets built | Compliance burden |
|---|---|---|---|
| **A — Preferred** | Hot-list matching can stay on the ACIC / dispatch side | City box stores plate reads + a *local* (department-created, documented) list only. NCIC/ACIC checks run through the Department's existing ACIC-connected workflow (dispatch / TAC terminal), as ASP's verify-before-a-stop rule already assumes. The pilot box is **not** a CJIS system. | Lightest lawful path. Still requires: MFA, individual accounts, audit log, training — all already in this spec. |
| **B — CJIS system** | A city server holding a hot-list extract *is* a CJIS system | Same build, hosted on a Police-Department-controlled network, plus a CJIS IT audit across the 13 policy areas: MFA, FIPS-validated encryption in transit and at rest, audit review, lockout after 5 failed attempts, fingerprint check for every administrator (and any vendor with access), CJIS security training, and an FBI Security Addendum for any vendor contract, filed with ACIC. | Priced *before* Stage 1 — see the kill condition at §11. CJIS audits recur (at least every 3 years for direct-access agencies, with action plans due within 30 days of findings). [Source: Clark County architecture §2; research 04] |
| **C — Approved vendors only** | Only state-approved vendors may receive hot-list data | **Pilot does not proceed to Stage 1.** The Commission reports Path C to the Council, asks ACIC how a system gets approved, and the open-source route pauses. Stage 0 accuracy results are still published — they remain useful for judging any vendor's claims. | No workaround. Routing hot-list data to an unapproved system to "make the pilot work" is a kill-condition violation, not ingenuity. |

No Stage 1 purchase order is issued before the City Attorney confirms, in writing, which path applies. That confirmation joins the November 16 plan's existing gating items (hosting route, OdinEye-type terms if the purchase model is later used, contract expiration dates).

---

## 6. Cameras, sites, power, and connectivity

The November 16 plan's Phase 1 site-survey discipline applies unchanged, per site, before any install: (1) mount — what the camera attaches to and who owns it (Flock's poles/mounts are Flock's; reusability is **not** assumed); (2) power — source and whether it is City-controlled, including PoE/midspan needs the camera price excludes; (3) connectivity — how reads reach the read store and the recurring price, which was the largest unpriced line in the purchase model and must not be unpriced here; (4) honest "new pole" sites, priced at the top of the allowance, not discovered mid-install.

Planning figures [Source: Clark County architecture §7; research 04]:

- Off-grid pole site (camera + edge compute + LTE modem + solar + battery): **~$800–$2,500 per site, estimate.**
- LTE / connectivity: **~$20–$50 per camera per month, estimate**, plus storage and replacements — and staff time, identified in both the Clark County hub and the November 16 plan as the real recurring cost.
- Existing powered, wired city sites should price materially below the off-grid figure; the survey, not this spec, establishes which of the 3 pilot sites is which.

Stage 0 deliberately starts on a powered city lot so the accuracy question is answered before any pole, solar, or LTE money is spent.

---

## 7. Identity, case validation, and the front door in operation

1. **Individual accounts only.** No shared, generic, service, or vendor accounts for human users. Hardware-backed MFA where the front door supports it; MFA in all cases. [Source: Clark County architecture §3 — the DEA/password failure is the stated reason]
2. **Case-number validation.** The front door checks the entered case/incident number against the Department's case list / RMS before executing a search. An invalid, closed (where closure bars the search type), or missing number returns no results and writes a log entry. This replaces free-text "reasons," which the research shows degrade to "idk" / "TBD" and, in one documented case, a single vague search touching 82,413 cameras. [Source: Clark County architecture §3]
3. **Tier check.** The front door applies §8 mechanically: Tier 2 queries return current status only and cannot display history; Tier 3 functions are locked by default and unlock only on an entered judicial-authorization number with the signed authorization uploaded (two-key execution by the Administrator or a designee who is not the applicant), or on a logged emergency entry. Paper rules the software does not enforce are treated in this spec as no rules.
4. **Anomaly flags, automatic.** The log system flags, for the auditor's weekly review: bulk or partial-plate sweeps, off-hours use, a single user querying many unrelated plates, any canary hit (§10), any failed-validation attempt pattern, and any missed retention or witness checkpoint. [Source: Clark County architecture §3 — "automated anomaly flags: bulk searches, off-hours use, one user with many plates"]
5. **Lockout and removal.** Five failed login attempts lock the account (CJIS pattern, §5 Path B — applied in the pilot on both paths as good practice). Accounts are disabled at role change, not at the next quarterly review (November 16 plan §9 rule, retained).

---

## 8. Access tiers — the sponsor's tiered judicial-authorization draft, built into the software

This spec incorporates the November 19, 2026 *Tiered Judicial Authorization* draft as the pilot's access law. The Commission may adopt, amend, or reject it, stating its reasons — but the front door must enforce *some* adopted version of it, configured before go-live, not promised for later.

| Tier | Access | Rule (summary of the Nov. 19 draft) |
|---|---|---|
| **Tier 1** | Automated hot-list comparison | No prior judicial authorization. Official lists only (stolen vehicles/plates, arrest warrants, missing/endangered incl. AMBER/Silver). An alert is a lead, not proof: before a stop, visually verify plate + state, verify through dispatch or ACIC/NCIC, compare occupants to any wanted-person description (ASP Rule 6(a) pattern). Custom hot lists are gated: stolen / missing / warrant / court order, or supervisor's written approval on documented imminent-risk facts, expiring in 24 hours without judicial authorization; every entry states its facts, author, and an expiration no more than 30 days out. |
| **Tier 2** | Contemporaneous query | No prior judicial authorization. Plate directly observed in an encounter; case/incident number (or direct-observation statement) and an own-words reason recorded; system returns **current status only, no historical location data**. One plate at a time. Scanning a lot, gathering, or neighborhood for later use is prohibited. |
| **Tier 3** | Historical search | **Prior judicial authorization required** — search warrant or court order on a sworn application showing probable cause, with particularity (plate/vehicle/person, date-time range as narrow as the facts permit and never beyond the retention period or 30 days per authorization, cameras/data set). Two-key execution. Return filed within 10 days. Denials logged; no judge-shopping without disclosing the prior denial. **Reverse searches** (by place/time, to identify unknown vehicles): heightened showing, de-identified results first, identifying data only on a further authorization. |
| **Emergency** | Historical search without prior authorization | Only on specific, recorded facts of imminent threat of death/serious bodily injury (incl. kidnapping, missing/endangered), or flight/destruction risk for a felony involving death/serious bodily injury. Supervisor (or Chief/designee) approval; log entry within 4 hours; judicial notice or application within **48 hours**. If found unjustified: data quarantined, not used, deleted when the matter resolves, and counted in the public report. |
| **Always** | No circumvention (§8 of the Nov. 19 draft) | No asking another agency, vendor, database, or private network to do what this policy forbids Cabot to do directly, and no sharing for the purpose or effect of evading it. No prohibited purposes (personal, discriminatory, movement-record building). Violations: discipline up to termination, willful violation = access revoked; contractor violation = termination for cause. Whether evidence is suppressed is a court's question — the policy neither requires nor forbids it, and must not be represented to a court as doing either. |

Open questions flagged in the November 19 draft for the City Attorney and the judges who would actually receive applications (form — warrant vs. order; issuing court and after-hours route; prosecutor review; 48-hour period; reverse-search offense list; records/FOIA treatment) are **pre-go-live gates for Stage 1**, not footnotes. A rule that cannot be used at 2 a.m. will be bypassed at 2 a.m.

---

## 9. Retention and deletion

| Bucket | Pilot rule | Basis |
|---|---|---|
| Non-hit plate reads | **Automatic hard delete at 14 days.** | Cabot's chosen policy in the November 16 plan (following Quincy's planned 14 days), far inside the state ceiling. A pilot that cannot keep a short promise has no business asking for a longer one. |
| Verified hit preserved for an investigation | Preserved only under Ark. Code § 12-12-1804(b) (ongoing investigation), destroyed at its conclusion, **and the deletion is logged** — ASP Rule 6(e) pattern. A suspicion, a query, or a bulk hold is not an investigation. | November 16 plan §8; Clark County research 07. |
| State ceiling (context, never the pilot's operating number) | 150 days for a governmental entity, § 12-12-1804(a)(2). The three numbers in Cabot's record — 30 days (current Flock vendor cloud), 150 days (statute / CPD-preserved), 14 days (this pilot) — govern three different buckets and must never be merged in public presentation. | November 16 plan §8, with primary sources there. |
| Audit log | Preserved at least **3 years** [bracketed floor in the Nov. 19 draft, §7(b) / §10 — Commission and City Attorney to conform to the applicable records schedule]. Log entries are never deleted by the retention job. | Nov. 19 draft. |
| Deletion proof | Weekly retention report, generated by the report job: rows deleted, oldest remaining read timestamp, exceptions. "Nothing older than cap" is a headline pilot success metric. | Clark County architecture §5. |

Arkansas's floor applies throughout: a governmental entity may not sell, trade, or exchange captured plate data (§ 12-12-1804(d)), with the statute's law-enforcement exception for data indicating evidence of an offense. This pilot goes beyond the floor by policy: **no sharing at all during the pilot** except (a) a specific, case-tied disclosure authorized in writing by the Administrator, logged, and named in the public report, or (b) a disclosure state or federal law or a court order compels, likewise logged and reported.

---

## 10. Sentinels and canaries — what is in the pilot, and what is deliberately deferred

The Clark County design adds two controls on top of the hash chain. This spec phases them honestly instead of promising all of them at once:

**In the pilot (Stage 1, from day one):**
- **Hash-chained log + weekly external witness** (§4). Simple, proven pattern, highest value per unit of complexity.
- **Missed-checkpoint alarm.** If a scheduled witness publication or retention run does not happen, the Administrator and the outside auditor are alerted. Silence is treated as an incident, not as "probably fine."

**Deferred to a post-pilot phase, with reasons stated:**
- **Forward-secure sentinel agents** (per-epoch Ed25519 keys, each checkpoint committing to the next epoch's public key, prior private keys destroyed, hourly epochs, outbound-only agents, silence-as-alarm per machine). Clark County's own build order puts full sentinels first among its *post-architecture* items and the hardware data diode last; for a 3-camera, 90-day pilot, weekly witnessed hash publication captures most of the tamper-evidence value at a fraction of the key-ceremony burden. If the Council authorizes a full system, the sentinel design (Clark County `design/sentinels.md`, including in-person pinning of each machine's first public key by the outside auditor, and its 3-of-5 key ceremony model in `design/ceremony-protocol.md`) is the Commission's starting text. [Source: Clark County sentinels §§A–B, "Build order"]
- **Canary records** (fake plate reads no legitimate query should ever return; any hit = a dragnet, bulk export, or exfiltration, alerted immediately). Deferred for the Clark County reason: a canary must **never be a real plate** — seeding requires confirming a non-issuable Arkansas plate format with the DFA, excluding canaries from § 12-12-1805 statistics, public reports, and any evidence export (with a test proving it), and seeding by the outside auditor, not City IT. That groundwork is a Commission task during the pilot; canaries go live only when it is done. [Source: Clark County sentinels §B, "Hard rules"]

Deferring a control is a disclosed design choice in this spec, not a silent omission. The day-90 report must state what the pilot's log could and could not detect, in plain language.

---

## 11. Success metrics and kill conditions — decided before the pilot starts

Following the Clark County action plan §5 ("must prove / how you show it"), expanded with Cabot's tier and cost questions. **Thresholds marked [Commission decision] are proposed starting points; the Commission sets the final numbers in its June 2027 report, before Stage 1 is authorized — and may not loosen them mid-pilot without a public vote of the Commission recorded in its minutes.**

| # | Must prove | How it is shown | Proposed threshold |
|---|---|---|---|
| 1 | Plates read at road speed | Read-rate report against a hand-checked sample (Appendix C), reported separately for day / night and for the high-speed vs. slow site | ≥ 90% correct full-plate reads on the slow site and ≥ 85% on the high-speed site, with false-positive (misread-as-a-different-valid-plate) rate < 1% **[Commission decision]** |
| 2 | Every search logged, with a person and a validated case | Auditor's sample audit of the full log; count of searches without a validated case number | **Zero** unlogged or unvalidated searches. One is a kill condition, not a rounding error. |
| 3 | The log cannot be quietly edited | Weekly witness publications all verify; one live verification demo for the Council, run by the auditor, not the Administrator | 100% of weekly root hashes verify against the witness copies |
| 4 | No shared accounts | Account list vs. log user list, audited monthly | Zero shared / generic / dormant accounts |
| 5 | Data deletes on schedule | Weekly retention reports (§9) | Zero reads older than 14 days (outside a logged § 1804(b) hold) at any weekly check |
| 6 | Hot-list alerts work end-to-end | Count of Tier 1 alerts, verification outcome for each, and time from capture to alert | Every alert either verified through dispatch/ACIC or documented as a misread; alert latency reported, threshold set after the ACIC call **[Commission decision]** |
| 7 | Tier rules hold in practice | Tier 3 log vs. authorizations on file (monthly Administrator review + auditor spot-check, per Nov. 19 draft §10(c)); emergency searches and their 48-hour follow-ups counted | Zero Tier 3 searches without a matching authorization or a timely emergency filing |
| 8 | Maintenance is real and bounded | Administrator + backup log hours weekly (task-level, §13 table) | Sustained load reported as-is; **> 10 staff-hours/week sustained over any 4 pilot weeks is a scale-blocker** — the full-system recommendation must then price a position or a support contract, not absorb it silently **[Commission decision]** |
| 9 | Cost stays inside the envelope | Actuals vs. §12 table, reported monthly | Pilot actuals within the §12 high case; any line exceeding it is reported to the Council that month, not at day 90 |

**Kill conditions — any one stops Stage 1 (or ends it early), and the Commission reports the stop and the reason to the Council in public session:**

- **K1. ACIC Path C** (§5): only approved vendors may receive hot-list data, and no approval path is available to this system.
- **K2. CJIS cost erasure:** Path B applies *and* the priced CJIS compliance burden (audit, hosting move, training, fingerprinting, Administrator time) pushes the pilot's honest 5-year projection at or above the November 16 purchase model's margin — i.e., the unpriced lines together approach the ~$13,600–$16,700/year break-even band that plan computed (standard case ~$15,800/year). The Commission recomputes this with pilot actuals; it does not reuse the purchase model's numbers as if they were the pilot's.
- **K3. Accuracy failure:** After site tuning documented in the log, read rates remain below Metric 1 thresholds, or the false-positive rate exceeds its threshold — because a misread is not a statistic; in March 2026 a family was stopped at gunpoint after an apparent Flock misread, which is exactly what ASP's verify-before-a-stop rule exists to prevent. [Source: Clark County research 07, "Wider Arkansas context"]
- **K4. Any unlogged access, any shared-account use, or any witness-hash mismatch that cannot be explained as a documented clerical error** — verified by the auditor, not self-certified.
- **K5. Any sharing outside §9**, any Tier 3 search without authorization, or any use for a purpose outside the governing policy's exhaustive list.
- **K6. No maintainer, no system:** the named Administrator or the named backup leaves and no fingerprint-cleared (Path B) / trained successor is designated within 30 days. A system with a bus factor of one is, in the Clark County phrase, a system that "rots when its one owner leaves." [Source: Clark County research 04, "The real risk: maintenance"]
- **K7. Vendor-lock creep:** any component adopted mid-pilot whose license, format, or terms would prevent the City from exporting its own reads and log in open formats, or from replacing that component — reported by the Administrator or auditor. Open-source licenses are checked before adoption (e.g., Frigate/fast-alpr stack licenses, YOLO's AGPL-3.0-or-commercial terms where applicable), not assumed.

---

## 12. Pilot budget — estimates, labelled, with the unknowns named

**Basis and honesty note.** No figure below is a quote to Cabot. Camera and site figures are the Clark County hub's October 2026 estimates and the November 16 plan's sourced Axis figure, applied to a 3-camera pilot. The November 16 purchase model's qualified 5-year estimate ($53,829–$69,579 for 9 cameras, Axis + OdinEye, *provided* connectivity, CJIS hosting, PoE power, and administration stay below ~$15,800/year in the standard case) is a **different model** and is not restated here as this pilot's cost. This pilot exists in part to price the lines that model could not.

| Line | Low case | High case | Basis |
|---|---|---|---|
| Cameras ×3 | $900 | $5,337 | Low: commodity LPR at ~$300/camera [Clark County research 04]. High: 3 × $1,779 AXIS Q1800-LE MSRP [Nov. 16 plan §3]. Stage 0 tests both classes; Stage 1 may mix them by site, so the actual will likely land between. |
| Edge / server hardware | $1,500 | $3,500 | **Estimate / allowance.** One city-owned server / edge box meeting Frigate's floor (≥4 GB RAM, AVX/AVX2 CPU) with storage for 14 days of reads + plate crops at 3 sites and 3 years of audit log. Procurement prices the actual specification; storage sizing is a Commission technical task (read volume at Cabot sites is not yet measured — Flock-volume figures from other systems must not be imported as Cabot facts). |
| Installation ×3 sites | $450 | $5,700 | **Allowance.** The November 16 plan's installation schedule applied to 3 sites: 3 × $150 (existing infrastructure) to 3 × $1,900 (new pole with solar), standard case 3 × $650 = $1,950. It is Flock's published cooperative schedule used as an allowance for non-Flock hardware, to be replaced by the §6 site survey. Off-grid sites may instead price inside the Clark County ~$800–$2,500/site all-in estimate — do not double-count both; the survey picks one basis per site. |
| Recognition software licenses | $0 | $0 | Open-source stack. $0 is a *license* figure only — see Administrator time below. Any paid fallback converts the model (§4, bake-off rule). |
| Connectivity, pilot period (~4 months incl. Stage 0) | $240 | $600 | **Estimate.** $20–$50/camera/month [Clark County research 04] × 3 cameras × 4 months, where a site is not already wired. Wired city sites price lower; the survey establishes it. |
| **Pilot hardware + install + connectivity subtotal** | **~$3,090** | **~$15,137** | Sum of the lines above. Standard-install, Axis-camera midpoint is roughly $9,000–$10,000. |
| Administrator + backup time | *Not $0 — recorded as hours* | *Not $0 — recorded as hours* | No new hire is proposed for the pilot. Time is logged weekly against the §13 task table and reported in hours and in loaded-cost terms in the day-90 report, so the full-system decision prices labour from Cabot actuals for the first time. |
| CJIS compliance (Path B only) | *Unpriced — gate, §5* | *Unpriced — gate, §5* | Audit, hosting, training, and fingerprinting costs are obtained after the ACIC call and **before** Stage 1 authorization. Path A carries no such line beyond training time. |
| Outside auditor | *Unpaid citizen role, by design* | — | The auditor is a Commission / Council-designated role outside the Police Department chain of command (cf. Nov. 19 draft §10(c), annual independent audit). If the Council prefers a paid auditor, that is a separate appropriation decision, stated openly. |
| Contingency | — | — | No percentage contingency is invented here. The known contingency in Cabot's existing record — a $4,500 Flock termination-for-convenience fee ($500 × 9 units, Agreement §6.2) — belongs to the *contract-exit* decision, not to this pilot, and must not be double-counted into pilot costs. [Source: Nov. 16 plan §3] |

**Comparison, for scale only (applied arithmetic):** 3 cameras on Cabot's current Flock terms pro-rate to ~$9,167/year ($27,500 invoiced in 2026 for 9 units ÷ 9 × 3 — *invoiced, not proven paid; staggered tranches, not a single annual bill*, per the November 16 plan §1 precision limits). The pilot's entire hardware subtotal is therefore on the order of **four months to twenty months of what 3 leased cameras cost** — and at the end of the pilot the City owns the hardware either way. That comparison does not include staff time or any Path B costs, and must always be quoted with that sentence attached.

---

## 13. Staffing, maintenance, and the runbook — the real cost, made visible

The Clark County hub and the November 16 plan agree on the finding: none of the switch reports collected mentioned a new hire, administration was absorbed by existing personnel where government infrastructure carried hosting — **and** staff time is still the real recurring cost. This pilot does not promise "no new hire" and does not cost labour at $0. It measures it.

| Recurring task | Owner | Pilot cadence |
|---|---|---|
| User accounts, role changes, account review | System Administrator | On change + monthly pilot review (quarterly in a full system) |
| Case-list / RMS validation feed health | Administrator, with Department records | Weekly check, logged |
| Hot-list source checks; custom-list documentation audit | Administrator, with the Department | Weekly |
| Audit-log review; anomaly-flag disposition | Administrator (weekly) **and** Outside Auditor (weekly witness verification, monthly sample audit) | Weekly / monthly |
| Tier 3 authorization file vs. log reconciliation | Administrator | Monthly, per Nov. 19 draft §10(c) |
| Camera health, failure triage, replacement logistics | Administrator, with installer / supplier support priced in procurement | On failure + weekly health report |
| Software / firmware updates on city components | Administrator; backup observes at least one update cycle | As released, staged: Stage 0 feed first, never all sites at once untested |
| Retention-job and witness-publication verification | Auditor (independent of Administrator) | Weekly |
| Public-records response for system records; monthly + day-90 reports | Administrator, with City Clerk/Treasurer | Monthly |
| Accuracy sampling (Appendix C) | Commission designee + auditor | Stage 0: weekly; Stage 1: monthly |

**Named people, before go-live:** (1) System Administrator, by name, in the governing policy; (2) a **named backup** who has completed the same training (and, on Path B, the same fingerprint check) and has run at least one update and one log review under observation; (3) Outside Auditor, designated by the Council, outside the Police Department chain of command; (4) Department TAC as ACIC liaison. A pilot with only item (1) filled does not start (kill condition K6).

**Runbook requirement.** Before Stage 1, the Administrator delivers a written runbook — install, update, backup/restore, account on/off-boarding, retention failure, witness failure, camera replacement, incident disclosure — sufficient for the backup, or a successor, to run the system without the author. The runbook is part of the published open-source repository (credentials and hot-list data excepted). "Don't expand past the pilot until someone besides you can keep it running" is adopted as a scale gate. [Source: Clark County action plan §6]

---

## 14. Timeline — Commission first, pilot second, full decision last

All dates are planning targets tied to the companion ordinance's sequence (Commission convenes first week of February 2027, written recommendations June 2027, implementation target December 1, 2027 only if the Council separately authorizes after public hearing). If the written contract-expiration confirmation the companion ordinance directs moves the full-system target, this timeline moves with it by Council resolution — it does not silently detach.

| When | Step | Gate |
|---|---|---|
| Feb. 2027, wk. 1 | Commission convenes; adopts this spec (as amended) as a working text | — |
| Feb. 2027 | **Joint ACIC call** via Department TAC (Appendix B); City Attorney begins CJIS/path review | Answers documented and sent to the Commission in writing |
| Feb.–Mar. 2027 | Hosting route identified **by name, verified, and priced** (city server vs. any Arkansas CJIS-compliant host) — the November 16 plan's gating item, carried over | No named, priced hosting route = no Stage 1 recommendation |
| Mar.–Apr. 2027 | Stage 0 bench/lot test: 1 camera, both recognition candidates, both camera classes, Appendix C protocol | Accuracy results published to the Commission, pass or fail |
| Apr.–May 2027 | Governing policy drafted, incorporating §8 tiers; City Attorney + judicial-officer questions from the Nov. 19 draft put to the judges who would receive applications | Policy text complete before any road camera is authorized |
| June 2027 | Commission's written recommendations to the Council, **including a pilot go / no-go recommendation with the final §11 thresholds** | Commission report is public |
| June–July 2027 | Council public hearing; **separate vote** authorizing (or declining) the Stage 1 road pilot, its 3 sites, its budget, and its 90-day sunset | No hearing + vote, no pilot. Commission work alone authorizes nothing. |
| July 2027 | Procurement (quotes against §12), site surveys (§6), runbook, accounts, training, fingerprint checks if Path B | §13 named-people checklist complete |
| Aug.–Oct. 2027 | **Stage 1: 90-day live pilot** at 3 sites; weekly witness publications; monthly reports to the Council in public session | Kill conditions §11 live throughout |
| Nov. 2027 | Day-90 public report: every §11 metric, all failures and misreads, actual hours, actual costs, sentinel/canary readiness statement (§10) | Report filed with City Clerk/Treasurer and published |
| Nov.–Dec. 2027 | Council decision on a full city-controlled system (open-source, purchase model, hybrid, or none), in time for the December 1, 2027 target **if** that is the decision | Separate ordinance + appropriation, as the companion ordinance requires |

---

## 15. Risks and mitigations

| # | Risk | Mitigation in this spec |
|---|---|---|
| 1 | **Accuracy at speed / at night.** Open-source OCR is "good for driveways and slow approaches, marginal at highway speed" on current evidence; no vendor-style accuracy guarantee exists. [Clark County research 04, verdict] | Two-stage testing; site-class thresholds (§11 Metric 1); camera shutter/IR/varifocal spec (§4); verify-before-a-stop on every alert (§8 Tier 1). Failure is a kill condition, not a public-relations problem. |
| 2 | **Maintenance rot / bus factor of one.** "As few as 13% of large government IT projects succeed"; ~80% of federal IT spend is legacy maintenance. A one-person system rots when that person leaves. [Clark County research 04] | Named backup, runbook, open-source publication, hours measurement, scale gate (§13), kill condition K6. |
| 3 | **Log that nobody reviews.** California's mandated ALPR logs got "little to no auditing"; CJIS audits run on a 3-year cycle — detection measured in years. [Clark County audit-log research] | Weekly outside-auditor verification, weekly witness publication, monthly sample audit, anomaly flags (§7). Review is a named person's dated task, not an aspiration. |
| 4 | **NDAA §889.** Hikvision/Dahua-class cameras are barred for federal / federally funded purchases. | No federal money for the pilot unless the Commission confirms compliant cameras; camera class (a) is re-priced with a compliant equivalent if any federal dollar is involved. Verify in procurement. [Clark County research 04] |
| 5 | **Key custody defeats the hash chain.** Whoever holds the signing key can rewrite and re-sign. | Witness copies held by the Clerk and a public repo (§4); in a full system, the Clark County sentinel/key-ceremony design (in-person pinning by the auditor; split custody) is the starting text (§10). Pilot limitation disclosed in the day-90 report. |
| 6 | **Function creep.** A working pilot invites new uses (parking, code enforcement, school zones) one quiet request at a time. | Permitted uses are exhaustive in the governing policy; any new use is a new public Council decision. Sharing and circumvention bans (§§8–9) have no administrative waiver. |
| 7 | **Public-records / litigation exposure.** Reads, logs, and reports will be requested and, where the law requires, produced. A system designed assuming secrecy will fail in daylight. | Design assumes publication: aggregate reports are generated from the log itself; target-identifying details of pending investigations are handled as the Nov. 19 draft §10 provides (de-identified public reporting), with FOIA treatment confirmed by the City Attorney before go-live. |
| 8 | **Evidence challenges.** Defence counsel will attack an open-source system's accuracy and log integrity in any case a pilot read touches. | Hand-checked accuracy record (Appendix C), witnessed hash chain, verify-before-stop documentation, and ASP-style verification create the record a court will ask for. The pilot makes no claim that a read is proof — it is a lead (§8). |
| 9 | **Alert fatigue from sentinel/witness alarms** on flaky LTE sites (a Clark County warning). | Per-site alert thresholds; every alert and its disposition logged, so an auditor who starts ignoring alarms leaves a record of doing so. [Clark County sentinels, "How each piece fails"] |
| 10 | **Cost creep in the unpriced lines** — the exact failure the November 16 plan disclosed for the purchase model. | §12 names them, §5 gates Path B pricing before authorization, kill condition K2 recomputes break-even with pilot actuals. |

---

## 16. Open questions — assigned, not left floating

| Question | Owner | Needed by |
|---|---|---|
| Which CJIS path (A / B / C) applies, and on what ACIC agreement? | City Attorney, via Dept. TAC, from ACIC | Mar. 2027 — gates everything |
| Is there an Arkansas CJIS-compliant hosting route available to Cabot, by name and price — or is it a city server? | City Attorney + Administrator-designee | Mar. 2027 |
| Judicial-authorization open questions (form, issuing court, after-hours, prosecutor review, 48 hours, reverse-search list, records treatment) | City Attorney, with the receiving judges | May 2027 — gates Stage 1 |
| Non-issuable Arkansas plate format for future canaries — DFA confirmation | Outside Auditor-designee, via City Attorney | During pilot; gates canaries only |
| Exact Flock expiration / non-renewal dates per order form (companion ordinance §4 direction) | Mayor + City Attorney | Feb. 2027 — sets the Dec. 1 target's firmness |
| Storage sizing from measured Cabot read volume at pilot sites | Administrator, from Stage 0/1 actuals | Day-90 report |
| Who supplies ASP's cameras/software, and do ASP's quarterly Legislative Council reports include query counts and sharing recipients? (FOIA if needed) | Commission research task | June 2027 report — a model, or a gap, for Cabot's reporting |
| Insurance / risk-pool position on a self-hosted law-enforcement system | City Attorney / Clerk-Treasurer with the City's insurer | Before Stage 1 appropriation |

---

## Appendix A — Audit log: minimum fields

From Clark County architecture §4, with Cabot's tier fields added (marked †):

`seq · timestamp_utc · user_id (individual) · auth_method · case_number · case_validated (bool) · query_type (†tier) · query_params (plate / partial / description) · result_count · requesting_agency · shared_with (if any) · legal_basis (warrant / court order / hotlist / emergency† / none) · †authorization_number + issuing officer (Tier 3) · †canary_hit (bool) · prev_hash · entry_hash`

Retention and deletion runs also write entries: `job_id · rows_deleted · oldest_remaining_ts`.
Witness publications write entries: `witness_target · root_hash_published · verified_by · verification_date`.

## Appendix B — The ACIC call: questions to ask, in order

Adapted from Clark County research 05 (call-prep) and action plan §3, for Cabot's TAC to put jointly with a Commission designee:

1. How do LPR systems in Arkansas receive NCIC/ACIC hot-list data today? What agreement, ORI status, and approvals does it take?
2. Does a city server that *stores plate reads only* — with hot-list matching done through our existing dispatch/TAC workflow — stay outside CJIS system status? (Path A confirmation)
3. If the city server holds a hot-list *extract*, does it become a CJIS system? Which of the 13 CJIS policy areas then apply, and what does the IT audit process and timeline look like for a city of Cabot's size?
4. What fingerprint, training, and Security Addendum requirements apply to (a) the System Administrator, (b) a backup administrator, (c) an outside citizen auditor with log-only access, (d) any contractor with maintenance access?
5. How does the Arkansas State Police system receive its hot lists — and could ASP-side matching ever be available to a municipal system, so the city box never holds CJI?
6. Are there state-approved-vendor requirements for ALPR systems receiving hot-list data? If so, how does a system obtain approval? (Path C test)
7. What audit cadence will ACIC apply to Cabot under each path, and what corrective-action timelines follow a finding?
8. Who at ACIC is our named contact for the pilot, and will ACIC put the answers to 1–7 in writing?

## Appendix C — Hand-checked accuracy protocol (Stage 0 and Stage 1)

Vendor and library accuracy claims are not evidence. The pilot measures its own:

1. **Sample.** For each measurement period, a human reviewer hand-reads a random sample of at least 500 vehicle passes per site class (or all passes, if fewer), from the camera's own plate crops plus a ground-truth view, *before* seeing the system's reads.
2. **Score.** Per pass: correct full-plate read / partial read / missed plate / misread (system returned a different, plausible plate). Misreads are reported separately from misses — a miss wastes time; a misread can stop an innocent person.
3. **Split.** Results are reported by site, by day/night, and by candidate (Stage 0 bake-off), never only as a blended average that hides a failing site.
4. **Publish.** The sample sheets (plate values redacted in the public version; unredacted sample retained by the auditor under the governing policy), the counts, and the computed rates go into the Commission's record and the day-90 report.
5. **No tuning on the test.** Camera or model changes made to improve a score are logged, and the sample is re-drawn after any change. A score earned on a sample the system was tuned against is not reported as a measurement.

## Appendix D — Sources

- Sanders, B., *Flock Alternatives: A Research Hub* (Clark County, Arkansas), GitHub `TiredofSleep/flock-alternatives`, Oct. 2026 — README; `design/architecture.md`; `design/sentinels.md`; `research/02-audit-log-models.md`; `research/04-build-path-cjis.md`; `research/07-arkansas-state-police-lpr.md`; `docs/action-plan.md`. Status, in its own words: "research and planning, not a product."
- Cabot City-Controlled ALPR Plan — Technical and Cost Proposal, Nov. 16, 2026 (rev. Nov. 17, Hostile QA Round 2) — Cabot invoice figures ($27,500 invoiced in 2026 for 9 units; staggered tranches; invoiced ≠ paid), Axis Q1800-LE MSRP $1,779, installation allowance schedule, 14-day retention proposal, break-even band for unpriced lines (~$13,600–$16,700/yr; standard case ~$15,800/yr), disclosed unknowns.
- Draft Ordinance — Third-Party ALPR Ban and Citizens Commission, Nov. 16–17, 2026 — Commission composition and charge, Feb./June/Dec. 1, 2027 sequence, separate-authorization rule, contract-date confirmation direction.
- Draft Tiered Judicial Authorization for Access to ALPR Data, Nov. 19, 2026 — §§1–13 and appendices, summarized at §8 of this spec.
- Ark. Code §§ 12-12-1801 to -1808 (Act 668 of 2025, as cited in the Clark County legal reference and the November 16 plan) — 150-day governmental ceiling (§ 1804(a)(2)), ongoing-investigation exception (§ 1804(b)), no sale/trade/exchange by a governmental entity (§ 1804(d)), semiannual statistics (§ 1805). *Verify against the official code before filing or quoting in an ordinance.*
- Arkansas State Police License Plate Reader Rules, 130.01.24 Ark. Code R. 002, as digested in Clark County research 07 — ownership (Rule 5(d)), retention and logged deletion (Rules 6(d)–(e)), dissemination log (Rules 6(b)–(c)), verify-before-stop (Rule 6(a)), quarterly Legislative Council reporting (Rule 5(e)).

---

*End of draft spec. Prepared for Commission discussion — not introduced, not filed, and not a statement of current City policy or of current law. All statutory references to be verified by the City Attorney against the official code before any use in an ordinance.*
