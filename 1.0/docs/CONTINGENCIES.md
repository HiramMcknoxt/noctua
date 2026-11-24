# NOCTUA 1.0 — Contingencies

*What this document is: everything we could construct going wrong, decided in advance — what happens, what the system does by itself, what a human must do, and what risk remains after both. Deciding these on a calm day is the entire point; a contingency first discussed during the incident will be decided by the incident.*

*Format per entry: **Scenario / Automatic / Human / Residual.** "Automatic" means the system does it without being asked. If a step needs a person, it is under Human, with the role named.*

---

## A. Field failures

### A1. Camera vandalism or theft

- **Scenario:** A pole camera is smashed, spray-painted, shot, or stolen outright.
- **Automatic:** The site's stream stops; the server flags the silent site on the next heartbeat check and `/health` shows it down. Nothing else is affected — sites are independent, and cameras hold no stored data (onboard storage disabled) and no credentials beyond their own (per-camera credentials, camera-VLAN isolation).
- **Human:** Administrator logs the outage window and files the maintenance ticket; Department decides on a police report for the damage itself (ordinary property crime). Replacement follows the camera-replacement runbook (INSTALL.md §4): new unit, **new credentials**, same site key/address only after the old camera's credentials are revoked. If a *Frigate edge buffer* device (LTE/PtP sites) is stolen with it, treat the buffered events as potentially exposed: the buffer is encrypted at rest, but the incident is recorded, the auditor is notified, and the site's WireGuard key is revoked and reissued.
- **Residual:** The coverage gap until replacement — reported honestly as downtime, never papered over. A determined attacker with physical access and time can extract an edge device's storage despite encryption; the mitigation is that the buffer holds days of crops at most, drains-or-deletes, and the theft itself is loud (the site goes silent immediately).

### A2. Backhaul outage — hours

- **Scenario:** Carrier outage, PtP fade, fiber cut. One site or several, for part of a day.
- **Automatic:** Store-and-forward (NETWORK.md §6): detection continues at buffered sites, events queue with true camera timestamps. The server marks the site silent. Fiber sites without an edge buffer simply pause detection.
- **Human:** None for the first hours — this is the designed case. Administrator notes it; if a carrier is involved, a carrier ticket is ordinary IT work.
- **Residual:** Hot-list matching for buffered reads happens on arrival, not at capture — a wanted vehicle may be hours gone before its hit surfaces. The hit is presented *as* late. This is a real capability limit, stated in CANT-DO.md.

### A3. Backhaul outage — weeks

- **Scenario:** A site is dark for weeks: infrastructure damage, a carrier dispute, a pole replacement queue.
- **Automatic:** The buffer keeps draining-or-deleting discipline: **events that would age past the 14-day cap are deleted at the edge, unsent.** The retention promise outranks completeness — an outage never extends data life. The dead site stays visibly down in every health report and monthly report.
- **Human:** Administrator escalates the repair as infrastructure, with a date; the Commission/Council reporting shows the site as non-operational (uptime is a pilot metric, and a site at 40% uptime is a finding, not a footnote). If the outage is a carrier dispute, the site migrates to another backhaul option (NETWORK.md §3) rather than waiting indefinitely.
- **Residual:** Reads from the outage's first days that were deleted at the edge are gone by design — including, possibly, a read that would have mattered. That is the price of a retention cap that means something, chosen in advance and stated here so nobody has to choose it mid-incident.

## B. Server and data failures

### B1. Server disk failure

- **Scenario:** A drive dies; or the array degrades; or (the bad version) the volume corrupts.
- **Automatic:** The mirror (INSTALL.md §1 — the one hardware shortcut the guide forbids is a single unmirrored disk) keeps the system running on the surviving drive. SMART/array monitoring raises a maintenance alarm.
- **Human:** Replace the drive, resilver, then **verify**: `/audit/verify` over the full chain and one published checkpoint against the Clerk's copy. If the volume is lost entirely, restore from backup via `scripts/restore.py` (manifest verified first; refusal on hash mismatch is the correct behavior, not an obstacle) and reconcile the gap between the backup point and the last published checkpoint — the checkpoint's entry count bounds exactly what could be missing.
- **Residual:** Reads captured after the last backup and before the failure may be lost. The audit chain's *integrity* is not at risk — the outside sink and published checkpoints establish what existed — but *completeness* of recent reads is bounded by backup cadence. That trade is accepted and stated.

### B2. Server compromise

- **Scenario:** An attacker (or malware) gains the server: credentials phished, an unrelated service exploited, a malicious update.
- **Automatic:** Very little, honestly — and what does exist matters: the Sentinel sink already holds a streamed copy of every chain entry up to the moment of compromise, on storage the server cannot rewrite; the last published daily checkpoint fixes the chain's root and entry count outside the building. Camera-VLAN isolation means the compromise does not automatically reach cameras' networks beyond the Frigate host's pull access.
- **Human:** Incident response, same day: take the server offline (stopping capture is always preferable to doubtful capture), preserve images/logs for investigation, notify Chief/designee, City Attorney, and the outside auditor. Establish the trustworthy history **from the outside copies inward** — sink + checkpoints define what the log provably said; anything in the server copy beyond the last checkpoint is treated as unverified until reconciled. Rotate **all** user keys via `provision.py` and all camera credentials before the rebuilt system captures again. Public disclosure follows the City Attorney's advice and any applicable breach law; the incident and its scope appear in the next public report regardless — a concealed compromise discovered later is worse than a disclosed one.
- **Residual:** A compromise caught late means a window in which reads may have been viewed or copied by the intruder; the chain proves the *log* wasn't rewritten past the last checkpoint, but no log can prove data *wasn't read*. If the audit key lived on the server (custody option (a)), a fully privileged attacker could also re-sign forged checkpoints *going forward* — which is why custody options (b)/(c) exist and why the choice is made explicitly at go-live (INSTALL.md §6).

### B3. Checkpoint mismatch

- **Scenario:** The auditor's recomputation, or a checkpoint verification, does not match: root hash differs, or the entry count differs from the published checkpoint.
- **Automatic:** Verification fails loudly — `/audit/verify` reports the exact position of the first broken entry; the mismatch is itself recorded. Nothing auto-corrects; there is no "repair" button, by design.
- **Human:** Treat as a **K4 event** (spec v2 §11): any witness-hash mismatch that cannot be explained as a documented clerical error is a kill condition. Freeze: no deletions, no exports, no "fixing" the chain. The auditor leads; the Administrator's job is preservation and access, not explanation. Compare three copies — server chain, streamed sink, published checkpoints — to localize whether the divergence is in the server copy (tampering or corruption on the server), the sink (transmission), or the checkpoint (publication error). Each has a different meaning and the comparison distinguishes them. The finding, whatever it is, is reported to the Commission and Council in public session.
- **Residual:** The chain can prove *that* something diverged and *where*; it cannot always prove *who* or *why*. A mismatch with an innocent cause (disk corruption, a botched restore) still costs public trust, and the only currency that repays it is the disclosure itself. Note the asymmetry the design accepts: under custody option (a), a privileged insider who rewrites the whole chain *and* re-signs can defeat the checkpoint for entries after their rewrite — detection then rests on the streamed sink, which is why the sink's independence is not optional.

## C. Misuse and integrity threats

### C1. Insider misuse

- **Scenario:** A credentialed user searches for a person, not a case — the ex-partner lookup; or runs a catch-all case; or browses out of curiosity. This is the most likely serious incident in any ALPR system, ahead of every external threat in this document.
- **Automatic:** The front door refuses what it can refuse mechanically: no justification, no search; banned catch-all patterns refused and logged; suppressed plates return stubs. What it cannot refuse, it makes visible: every query carries a person, a validated case, and an own-words justification into the chain; more than 8 distinct plate fragments on one case in a day fires a `CASE_FLAG` for the auditor; anomaly flags catch bulk sweeps and off-hours patterns.
- **Human:** The auditor's monthly **relevance sample** — searched plates checked against the case files they claim to belong to — is the control that catches the well-formed lie (valid case, plausible text, wrong purpose). Findings go to the Chief and, per the policy's sanctions section, discipline runs up to termination and access revocation for willful violation. A confirmed misuse is disclosed in the public report in aggregate (count, disposition) — the system's credibility with residents depends on misuse being *seen* to have consequences.
- **Residual:** Stated without varnish: a determined insider with a real case and a plausible justification can make a search the door cannot distinguish from legitimate work. The design's answer is not prevention — it is that the search is permanently attributed, sampled against case files, and punishable, and that no search can be made *unlogged*. Any vendor or design claiming to have solved this outright is claiming more than software can do (CANT-DO.md).

### C2. Hot-list staleness

- **Scenario:** The list is old: a recovered car still listed (innocent driver stopped), or a newly stolen car not yet listed (a pass that should have hit).
- **Automatic:** Janus records list provenance and age for every hit decision; verification step 2 (OPERATIONS.md §3) checks currency through dispatch/ACIC before any action — the stop decision never rests on the local list alone.
- **Human:** The Department's list hygiene is a weekly Administrator task (spec v2 §13): source checks, custom-list documentation audit, expirations enforced (custom entries expire ≤30 days; imminent-risk entries ≤24 h without judicial authorization). Every stale-list incident — a stop or a near-stop caused by a dead entry — is logged, counted, and reported; the § 12-12-1804(c) 24-hour update duty's ownership on the Path A design is one of the written questions put to ACIC (spec v2 §5, question 10), and until ACIC answers, the Department's existing update workflow owns it by default.
- **Residual:** Some staleness is inherent: lists are snapshots of a changing world. The system's defense is procedural (verify before action) plus honest counting — it cannot make a list entry true.

## D. Institutional contingencies

### D1. ACIC says no — Path C

- **Scenario:** ACIC answers that only state-approved vendors may receive hot-list data, and no approval path is available to this system. Kill condition **K1**.
- **Automatic:** Nothing to automate — the gate does its work by existing. Stage 1 does not proceed; no purchase order is issued; hot-list data is never routed to the system "to make the pilot work" (spec v2 §5: that is a kill-condition violation, not ingenuity).
- **Human:** The Commission reports Path C to the Council, asks ACIC how a system gets approved, and publishes the Stage 0 accuracy results anyway — they remain useful for judging any vendor's claims. The Council's options stay the full set: pursue approval, adopt the purchase model, or have no ALPR. **A failed pilot does not default to renewing the current vendor** (spec v2 §1, amendment 13).
- **Residual:** The work product (spec, policy, code) remains public and reusable if the state's posture changes. The political risk — Path C read as "the project failed" rather than "the gate worked" — is managed by having said, in advance and in writing, that this is one of the designed outcomes.

### D2. ACIC requires CJIS — Path B

- **Scenario:** ACIC answers that a city server holding the hot-list extract *is* a CJIS system.
- **Automatic:** This build stops being the build. NOCTUA 1.0 makes **no Path B claim** (INTERFACE.md); nothing in the package represents itself as CJIS-compliant.
- **Human:** Path B is priced **before** any Stage 1 authorization: CJIS audit across the 13 policy areas, FIPS-validated encryption, fingerprint checks for administrators and any vendor with access, CJIS training, hosting on a department-controlled segment, recurring audits. Kill condition **K2** then applies with real numbers: if the priced CJIS burden pushes the honest 5-year projection to the November 16 purchase model's break-even band (~$13,600–$16,700/year in unpriced lines), the open-source route's cost case is gone and the Commission says so.
- **Residual:** Schedule. CJIS pricing and any audit cycle run on the state's clock, not the pilot's; the timeline (spec v2 §14) moves by Council resolution rather than silently detaching.

### D3. Council defunds mid-pilot

- **Scenario:** Appropriations are pulled, or the Council votes the pilot down at day 40 of 90.
- **Automatic:** The sunset machinery is already built: accounts and hot-list access are revocable in minutes (`provision.py disable-user`, list removal); the retention job keeps running on whatever data exists — defunding stops capture, it does not orphan data.
- **Human:** Orderly shutdown, in this order: (1) cameras disabled in `cameras.yaml` and ingest stopped; (2) user accounts disabled; (3) data disposition per the policy — held evidence completes its lifecycle (holds, export, prosecutor sign-off) because a defunded system does not get to shred evidence; non-hit reads delete on the normal 14-day schedule or faster by documented direction; (4) the audit log and outcome records are preserved per their schedules (log ≥3 years, outcomes 18 months) under the Clerk's custody; (5) a closing report — including why it ended — is filed and published. Hardware is city property and is inventoried for reuse or surplus.
- **Residual:** A shutdown done in anger rather than in order is the risk; the checklist above exists so that the order survives the politics. Evidence under legal hold is the one thing that must never be collateral damage of a budget vote.

### D4. The maintainer quits

- **Scenario:** The System Administrator leaves, is reassigned, or is hit by the proverbial bus. Kill condition **K6**.
- **Automatic:** The dead-man alarms keep working — they page the auditor and Clerk too, so a silent system announces itself even with nobody minding it.
- **Human:** The named backup steps in — this is why the backup exists, has run an update and a log review under observation, and why the runbook (this document set) is written to be sufficient without the author. If **neither** Administrator nor backup is available and no trained successor is designated within **30 days**, K6 fires: the system does not expand, and the Commission reports whether it should pause capture until staffing is restored. A system with a bus factor of one is a system that rots when its owner leaves (spec v2 §11).
- **Residual:** Tacit knowledge still walks out the door; the runbook bounds the loss, it does not zero it. Credential custody (disk passphrase, audit key under the chosen option) must have a sealed-copy path (Clerk) or a departure can become a lockout — that copy's existence is a go-live checklist item, and its use is a logged, two-person event.

### D5. Lawsuit / FOIA flood

- **Scenario:** Litigation over the system (a § 12-12-1807 private action carries $1,000 liquidated damages plus costs per injured person — the downside is priced in the statute), a § 12-12-1806 evidence-exclusion fight, or a volume of FOIA requests aimed at the audit log and records.
- **Automatic:** The design's preparations fire without anyone improvising: published daily checkpoints make chain integrity publicly verifiable **without disclosing log contents**; chain entries contain keyed plate references, never plate text, so a produced log extract does not itself leak plates; the redaction process (open-investigation case numbers, exempt officer identifiers) was confirmed by the City Attorney **before go-live** (spec v2 §9), not invented during the request.
- **Human:** The City Attorney owns the legal response; the Administrator's job is preservation and production support — **litigation hold overrides retention**: on notice of a claim, affected records go under legal hold immediately, and the retention job skips them (a shredder that keeps shredding after a hold notice is spoliation with a cron schedule). FOIA volume is answered with the designed artifacts first (checkpoints, statutory reports, redacted extracts) rather than raw system access for requesters — nobody outside the front door gets a login because they asked loudly.
- **Residual:** Litigation cost and staff time are real and unbudgeted by the pilot; the design reduces *merit* exposure (every action logged, every deletion provable) but cannot reduce *volume* exposure. A court may also order broader disclosure than the policy prefers; the system complies with orders — that is what orders are — and logs the disclosure.

### D6. Evidence challenged in court

- **Scenario:** Defense challenges a read, an image, or the audit trail: "the machine misread it," "the log was edited," "the timestamp is wrong."
- **Automatic:** The artifacts answer in order: the plate-crop image (what the camera saw, human-readable); the read's timestamps with clock-skew flags (NETWORK.md §5) showing the time discipline in force; the evidence-export bundle with per-file SHA-256 and the chained `EVIDENCE_EXPORT` manifest hash; the Sentinel chain verified against the streamed sink and the published checkpoint for that date — a verification the **auditor** can perform independently, not a screenshot the Administrator provides.
- **Human:** The verifying officer testifies to the workflow (verify-before-action, OPERATIONS.md §3) — the system's evidence posture is that a read is a lead that a human verified, and the court presentation should say exactly that, no more. The accuracy protocol's measured error rates (spec Appendix C) are public pilot data; counsel should expect them in cross-examination and the honest numbers are the defense against the dishonest-sounding ones.
- **Residual:** A read can still be wrong — OCR error rates are measured, not zero (CANT-DO.md) — and a chain can prove a log wasn't rewritten without proving the original entry was *true*. The design's court posture is deliberately modest: corroborated leads and provable records, not machine certainty.

## E. Performance and pressure

### E1. OCR accuracy below threshold

- **Scenario:** Stage 0 or Stage 1 measurement shows read rates below the Metric 1 thresholds (≥90% correct full-plate on the slow site, ≥85% high-speed, false-positive rate <1%), or jurisdiction (state) accuracy is poor even where plate text reads well.
- **Automatic:** Nothing automatic — measurement is the mechanism. Accuracy is scored against the hand-checked sample (spec Appendix C), plate-text and jurisdiction scored **separately**, day/night and per site class.
- **Human:** Tune first, documented in the log: camera geometry, shutter, IR, site lighting — the cheap fixes. Re-measure. If thresholds still fail, kill condition **K3** fires: the pilot reports the failure with its numbers and stops or descopes (e.g., slow sites only) by Commission recommendation. The bake-off's second candidate (Frigate LPR vs. fast-alpr) and the paid on-prem fallback may be *benchmarked* — adopting the paid fallback converts the project to the purchase model and must be reported as such, not smuggled in as a patch.
- **Residual:** Night, rain, plate condition, and speed degrade any OCR (CANT-DO.md lists the unreadable cases). A system tuned to threshold on the measured sample can still underperform on unmeasured conditions; the monthly sampling cadence exists to catch drift, and the thresholds are the Commission's to tighten — never to loosen mid-pilot without a public vote (spec v2 §11).

### E2. Mission-creep pressure

- **Scenario:** Requests arrive — from inside or outside the Department — to add facial recognition, to run immigration-enforcement queries, to share data with a regional network, to search for parking or code enforcement, to keep data "just in case" past the cap. Each arrives sounding reasonable and small.
- **Automatic:** The software refuses what it has no function for: there is no facial-recognition capability to turn on, no national-lookup feature, no bulk export, no sharing interface. Adding any of them is a code change, a procurement, and a policy amendment — three public acts, not a settings toggle. The no-circumvention rule is enforced structurally: Janus has no "ask another agency's database" button.
- **Human:** The policy answers, and they are short: permitted uses are listed **exhaustively** in the governing policy (Act 668 of 2025 limits lawful uses; the policy narrows further); a use not on the list is not a judgment call for any operator, supervisor, or administrator — it requires the Council to amend the policy in public, and several requests (facial recognition, immigration enforcement, movement-record building) are named prohibited purposes in the tier draft, where a violation means discipline up to termination and access revocation. Sharing requests follow §9 exactly: case-tied, Administrator-authorized in writing, logged, named in the public report — or compelled by law/court order, likewise logged. The person who receives the pressure does not have to win the argument; they have to point at the list.
- **Residual:** Policy binds the willing. A future Council can amend the policy, vote a different system, or repeal the ordinance — no architecture can prevent a government from changing its mind in the open. What the design prevents is the change happening *quietly*: every path from "system as authorized" to "system as expanded" runs through a public act, a code change visible in a public repository, or a chain entry. Creep that must announce itself is creep the public can answer.

### E3. Emergency-flag normalization (the exception becoming the rule)

- **Scenario:** Tier 3 emergencies, designed for imminent-threat facts, start being used for investigative convenience — the council review identified this as the tier system's most likely death.
- **Automatic:** Every emergency use is flagged, chained, and queued for mandatory post-hoc review — 100%, not sampled. Frequency is computed monthly against the Metric 10 threshold.
- **Human:** Post-hoc review of **every** use (auditor in all cases; reviewing judge where engaged). If a use is found unjustified: the data is quarantined, not used, deleted when the matter resolves, and counted in the public report. On threshold breach or an auditor-judged routine pattern, **K8** fires: Tier 3/emergency functionality stops pending Commission and Council review.
- **Residual:** Post-hoc review punishes the pattern after individual uses have already occurred. The compensating controls are the 48-hour judicial filing, the review queue that must be worked to zero, and a threshold set before the pilot starts — but the honest statement is that this control is cultural as much as technical, and it is the first one the auditor should report on.

### E4. Case-list feed failure (fail-closed event)

- **Scenario:** The records-system case feed stops refreshing — an export breaks, a server moves, a vendor updates a schema.
- **Automatic:** Janus **fails closed**: past the configured staleness window, searches stop, the failure is logged, and the Administrator and auditor are alarmed the same day. There is no override that becomes permanent; return requires an Administrator-documented refresh.
- **Human:** Fix the feed with the records unit; document the outage window; searches that didn't happen are reported as an availability gap, not worked around by phone-and-notebook queries (a workaround search is an unlogged search — K4 territory).
- **Residual:** Fail-closed trades availability for integrity, deliberately. A long feed outage during an active investigation is a real operational cost, accepted in advance because the alternative — a door that fails open — teaches everyone to expect the override.

*End of CONTINGENCIES.md.*
