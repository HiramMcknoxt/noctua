# NOCTUA 1.0 — Operations Runbook

*Audience: the System Administrator, the named backup, supervisors, and the outside auditor. This is the day-to-day book: what happens on a normal day, what happens on a bad one, and who does it. Policy citations are to the adopted written policy and spec v2; where this runbook and the policy disagree, the policy governs.*

*Standing rule for everything below: if a step isn't in Janus, it didn't happen. Workarounds that bypass the front door are incidents, not initiative.*

---

## 1. Roles in one place

| Role | Person | Can | Cannot |
|---|---|---|---|
| System Administrator (+ named backup) | Named in the policy | Provision/disable users, place holds (with supervisor), run jobs, maintain | Approve their own Tier 3 request; hold the checkpoint key alone under custody options (b)/(c) |
| Detective / Patrol | Named officers | Search (Tier 2 rules), verify hits, request Tier 3 | Execute their own Tier 3 request; release holds |
| Supervisor | Named | Approve/deny Tier 3 (never their own), release holds, manage suppressions, prosecutor sign-off intake | — |
| Outside Auditor | Designated by Council, outside the PD chain of command | Read-only: audit chain, reports, redacted records; independent chain recomputation | Touch data, hold credentials to change anything |
| Prosecuting attorney's office | External | Approves evidence disposition schedule; supplies prosecution outcomes | — |

## 2. Daily rhythm

- **Morning check (Administrator, ~10 min):** `/health` green — chain root present, `sentinel_sink.ok: true`, no overdue heartbeats, no camera flagged with clock skew >5 s, no site silent past its heartbeat. Yesterday's checkpoint published; if it wasn't, that's §6, not a shrug.
- **Hit queue (§3):** PENDING hits reviewed same business day.
- **Weekly:** retention report reviewed (rows deleted, oldest remaining read, held-skips) — "zero reads older than 14 days outside a logged hold" is the headline check (spec v2 §11, Metric 5). Case-list feed health confirmed. Administrator hours logged against the task table (staff time is a measured cost, not a free good — spec v2 §§12–13).
- **Monthly:** anomaly-flag disposition (bulk sweeps, off-hours use, one-case-many-plates flags), auditor's relevance sample (searched plates vs. case files, spec v2 §7 item 8), Tier 3 log vs. authorizations on file reconciled, account list vs. log user list compared (zero shared/dormant accounts).
- **Daily, without exception:** the checkpoint goes out. A missed publication is recorded as an event in the next checkpoint — the gap is part of the public record.

## 3. Hit verification workflow

A hot-list match opens a PENDING hit. An alert is a lead, never proof.

1. **Look.** Open the hit: plate text, plate-crop image, site, timestamp, list name. Visually compare the crop against the plate text — OCR misreads are the common case, and a wrong-state lookalike is a rejection, not a match.
2. **Verify through the official channel.** Before any stop or action, verify through dispatch / ACIC-NCIC per the Department's existing workflow (ASP Rule 6(a) pattern, spec v2 §8 Tier 1): the list entry is current, the plate *and state* match, occupants compared against any wanted-person description where applicable.
3. **Decide in Janus.** `POST /verify` — confirm or reject, against a validated case number. The decision writes the plate-free outcome record that feeds the statutory report. A hit left PENDING is an unfinished obligation, not a neutral state.
4. **Act outside the system.** Any stop, recovery, or arrest happens under ordinary department policy. NOCTUA's job ends at a verified lead.
5. **Outcomes land later.** Arrest/prosecution updates go in via `POST /outcomes` as the case develops — prosecution figures come from the prosecutor feedback loop, and an outcome nobody updates is a report error in the making (§5).

Failure modes to know: OCR-miss (the wanted vehicle passed unread — invisible by nature; measured only by the accuracy protocol), wrong-state lookalike (rejected at step 1–2), stale list entry (rejected at step 2; feed the staleness back to the list owner — see CONTINGENCIES.md).

## 4. Tier 3 (historical search) requests

1. **Request.** Requester files `POST /tier3/request` {case, why, plate fragment, authorization basis}. **No search runs.** The request is PENDING and chained.
2. **Approve or deny — a different person.** A supervisor (never the requester) approves via `POST /tier3/approve`; approval executes the search and returns results, chained end to end. Denial via `POST /tier3/deny` is also chained, and a later application elsewhere must disclose the denial (spec v2 §8 — no judge-shopping without disclosure).
3. **Emergency.** `POST /tier3/emergency` executes immediately on recorded imminent-threat facts, flags EMERGENCY, and queues a **mandatory post-hoc review item**. Judicial notice/application follows within 48 hours; the log entry within 4 hours (spec v2 §8). Every emergency use is reviewed — by the reviewing judge where engaged, and by the outside auditor in all cases (`GET /tier3/pending-reviews` is worked to zero, not sampled).
4. **Watch the rate.** Emergency frequency is a pilot metric with a kill threshold (spec v2 Metric 10 / K8): sustained use above the Commission's threshold — proposed starting point, more than 2 in any rolling 30 days, or any pattern the auditor judges routine — stops Tier 3/emergency functionality pending Commission and Council review. If the exception is becoming the road, the road closes until the vote reopens it.

## 5. Legal holds and evidence export

**Holds.** When a hit or case becomes evidence: `POST /holds` (detective + supervisor) on a documented case basis. The retention job **never deletes a held record** and reports `held_skipped` on every run. Reads carry no case link and still delete by age — holds live at the hit/evidence layer, where § 12-12-1804(b) bites. Holds are released only by a supervisor (`POST /holds/release`), and for held hits only after the evidence step below.

**Evidence export.** `POST /evidence/export` {hit, case} (detective + supervisor) writes the bundle — JSON manifest + hit record + related reads, SHA-256 per file, manifest hash chained as `EVIDENCE_EXPORT` — into the Department's records/evidence system. From that moment the *evidence system* holds the evidence; NOCTUA holds a copy on borrowed time.

**Release.** The NOCTUA copy is destroyed only after `POST /evidence/release` records the **prosecutor sign-off (name + date)** — the disposition schedule is the prosecuting attorney's, approved before go-live; no administrator deletes evidence on their own judgment. Every hold, export, release, and destruction is a chain entry. Destruction at the conclusion of the investigation/criminal action is logged (ASP Rule 6(e) pattern).

**The Brady note, once, plainly:** a held record may be exculpatory. Deleting on a timer is how systems destroy discovery material; that is why this lifecycle has no timer in it — only holds, exports, sign-offs, and logs.

## 6. The six-month statutory report

Ark. Code § 12-12-1805 requires a report every six months in the statute's categories. NOCTUA builds it from two sources designed to survive retention:

- **Plates scanned** comes from the cumulative `counters` table (day × camera, incremented at ingest) — *not* from counting reads currently in the store. (The v0.9 report counted live reads, which silently shrank as the 14-day deletes landed; 1.0 fixes that — the compilation no longer needs to be snapshotted at period close to be right.)
- **Matches, confirmations, non-corresponding matches, arrests, prosecutions** come from the plate-free `outcomes` table, preserved 18 months, never touched by the retention job.

Procedure: at period close, the Administrator runs `GET /report?from=&to=`; the auditor independently recomputes the chain over the same period and spot-checks outcome rows against case dispositions; prosecution numbers are reconciled with the prosecutor's office **before** filing (a prosecution count nobody confirmed is a guess wearing a uniform). The report is filed as the statute directs and published per the policy. The monthly pilot report and the day-90 public report come from the same machinery — counts are computed, never hand-tallied.

## 7. Dead-man alarms — silence is an incident

Three jobs heartbeat into Janus (`POST /heartbeat`, system key): **retention** and **checkpoint** (overdue at >26 h per INTERFACE.md), plus sink health at `/health`. `scripts/alert_check.py` runs on a host timer; on any overdue job it exits nonzero and reports the overdue list by local mail / city webhook to the **Administrator, the outside auditor, and the City Clerk** — all three, every time, because an alarm only the alarmed-about can see is not an alarm.

Response, in order:

1. **Acknowledge** to the other two recipients (so the silence is broken by a human voice, not just a log line).
2. **Diagnose the job, not the alarm:** did retention fail, or did it not run? Host down, disk full, container stopped, timer broken, cert expired on the proxy — the cause taxonomy is in CONTINGENCIES.md.
3. **Run the job manually** once the cause is fixed; confirm the chain entry for the late run records the gap (the retention job logs rows deleted and oldest remaining timestamp every run — a late run that quietly catches up is fine; a late run nobody can see happened is not).
4. **If data outlived its cap because retention was down:** that is a reportable event — it goes in the monthly report and to the auditor the same day, with the count of over-age reads and when they were deleted. The 14-day promise is kept by disclosure when it cannot be kept by the clock.

A missed **checkpoint** additionally becomes an event recorded in the next successful checkpoint. A missed **retention** run repeated twice in 30 days is a maintenance finding, not bad luck.

## 8. Failure responses (quick cards; full treatment in CONTINGENCIES.md)

**Disk filling / full.** Symptoms: ingest errors, `/health` degraded. Do: check the retention job first (a stopped shredder fills disks); check Frigate media (its ≤14-day media retention should self-limit — if it didn't, that's a finding); free space by completing retention, never by hand-deleting rows (hand deletion is unaudited deletion). The mirror (§INSTALL 1) means a single disk *failure* is a replacement ticket, not data loss: replace, resilver, verify chain.

**Camera down.** `/health` flags the silent site. Triage order: power at the pole → backhaul (carrier status / PtP alignment / fiber) → camera itself. Log the outage window; the day-90 report counts uptime per site, gaps included. A camera that is down is not "covered by the others" — coverage claims in reports use actual uptime.

**Server compromise suspected.** Stop. Preserve. Call it in: Administrator → Chief/designee → City Attorney → auditor, same day. Do not "clean up" first. The Sentinel sink and the last published checkpoint — held outside — are what let anyone establish what the log said before the compromise; verification proceeds from the outside copies inward. User keys are rotated via `provision.py` once the box is trusted again, and every step lands in the incident record (CONTINGENCIES.md has the full card).

**Key person unavailable.** The backup *is* the response — if neither Administrator nor backup is reachable for a critical alarm, the Clerk and auditor know (they got the alarm too) and the escalation is to the Chief's designee, whose authority is accounts-off and jobs-documented, not improvisation.

## 9. Backups — verification, not faith

- Nightly backup runs automatically (INSTALL.md §7). **Weekly:** confirm last night's manifest exists and the backup job heartbeat is current.
- **Quarterly:** restore test — `scripts/restore.py` onto the spare/bench machine; it verifies the manifest and refuses on hash mismatch; then boot Janus against the restored database and verify the chain (`/audit/verify`) and one checkpoint against the Clerk's copy. Record the test, its date, and its result in the chain-side operations log. A quarter without a restore test is reported as such in the monthly report.
- Backup media leaving the building follows the City's ordinary records-custody practice, and backup retention follows the data classes (INSTALL.md §7) — an old backup tape is not an archive of plates.

## 10. Accounts and access hygiene

- Role change = same-day `disable-user` or role correction (spec v2 §7 item 5). Departure = disable first, paperwork second.
- Five failed logins lock the account (CJIS pattern, applied on both paths). Unlocks are Administrator actions and are chained.
- Suppressions (protection orders) are supervisor-only to place and release, case-validated, and a suppressed plate returns a bare stub to everyone below supervisor — including in hit review. If a suppression request arrives without the underlying order, it does not get entered "temporarily."
- The auditor's monthly relevance sample is scheduled like maintenance, because it is: searched plates checked against case files, non-match rate reported. A month the sample didn't happen is stated in the report, not smoothed over.

*End of OPERATIONS.md.*
