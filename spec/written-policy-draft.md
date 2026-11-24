# CITY OF CABOT, ARKANSAS

# Policy for the Capture, Retention, Use, Disclosure, and Destruction of Captured Plate Data

## Automated License Plate Reader (ALPR) System

**DRAFT — FOR CITY ATTORNEY REVIEW**

**This document is a draft. It has not been adopted by the Cabot City Council, it is not City policy, and it authorizes nothing. It is prepared so the City Attorney, the Citizens Commission on a City-Controlled ALPR System, and the City Council can review, revise, and — if they choose — adopt a written policy of the kind Ark. Code § 12-12-1805(a)(3) requires *before* any captured plate data is obtained. Under the design this policy accompanies, no camera governed by it may capture a plate until this policy (or a successor adopted in its place) is in force and the roles in §4 are filled by name.**

|  |  |
|---|---|
| Draft prepared | November 23, 2026 |
| Companion documents | Cabot Open-Source ALPR Pilot — Design Specification v2 (Project NOCTUA), Nov. 23, 2026; Draft Tiered Judicial Authorization for Access to ALPR Data, Nov. 19, 2026 |
| Statutory basis | Ark. Code §§ 12-12-1801 to -1808 (Act 668 of 2025). All statutory references are to be verified by the City Attorney against the official code before adoption. |
| Branding | None. This is unbranded city business. |

---

## §1. Purpose and adoption

1.1 **Purpose.** This Policy states the rules of the City of Cabot for **obtaining, retaining, using, disclosing, and destroying captured plate data**, as Ark. Code § 12-12-1805(a)(3) requires a governmental entity to adopt and make available for public inspection. Failure to comply with the policy requirement is grounds for a court to exclude evidence obtained under the subchapter; this Policy is therefore legal infrastructure, not paperwork, and it is adopted before the system it governs captures anything.

1.2 **Adoption and availability.** This Policy takes effect only upon adoption by resolution or ordinance of the Cabot City Council. Upon adoption, the City Clerk/Treasurer shall (a) file the adopted text, (b) post it on the City's public website, and (c) provide a copy to any person on request, as the statute's public-inspection requirement provides. Any amendment follows the same route: no provision of this Policy may be waived, suspended, or amended administratively.

1.3 **No capture before adoption and staffing.** No ALPR camera governed by this Policy — including any test or pilot camera, on any site, including a City lot — may be operated to capture plate data until (a) this Policy is adopted and in effect, and (b) every role in §4.2 is filled by a named individual. A test using only City-owned and volunteer vehicles is still capture under this Policy and is governed by it in full.

1.4 **Order of authority.** Where this Policy is stricter than state law, this Policy controls City conduct. Where state or federal law is stricter, the law controls. Nothing in this Policy authorizes anything Ark. Code §§ 12-12-1801 to -1808 forbids.

## §2. Definitions

2.1 **Captured plate data** — as defined by Ark. Code § 12-12-1802: the GPS coordinates, date and time, photograph, license plate number, and any other data captured by or derived from an automatic license plate reader system. Plate *text appearing in a log* is captured plate data; for that reason the audit log under §11 records keyed plate references, never plate text.

2.2 **Read** — a single capture event: plate text (or partial text), issuing jurisdiction as read, camera site, date and time, and the associated plate-crop image.

2.3 **Hit** — a read that matches a hot-list entry. A hit is a lead, not proof (§7.3).

2.4 **Hot list** — a list of plate numbers against which reads are compared: official lists (stolen vehicles and plates, arrest warrants, missing and endangered persons, including AMBER and Silver alerts) received through ACIC/NCIC channels, and custom lists created under §7.4.

2.5 **Front Door** — the single software interface through which every query of captured plate data is made and logged. There is no other authorized query path.

2.6 **Legal hold** — a documented instruction, recorded in the system, that identified records are preserved notwithstanding the retention schedule, because they are tied to an investigation or criminal action (§9.4).

2.7 **Outcome record** — a record containing no plate data, created when a hit is resolved, used for the statistical reporting required by §13.

## §3. The system governed by this Policy

3.1 **Description.** The system consists of City-owned ALPR cameras at locations approved under §6.2; a recognition component that produces reads; a City-owned read store on a City-controlled network; the Front Door; a hash-chained, append-only audit log with external witnessing (§11); and automated retention and reporting jobs (§§9, 13). All components run on City hardware or City-controlled infrastructure. No vendor cloud service stores captured plate data under this Policy.

3.2 **Recognition component lockdown.** The recognition component is a sensor, not a query path. Its user interface and API shall not be reachable by any human account in normal operation; it writes reads to the read store through authenticated ingest only; its own media retention shall not exceed the retention period in §9.2; cameras shall operate on an isolated network segment with no internet route; camera onboard storage and vendor cloud or peer-to-peer features shall be disabled; camera and system clocks shall be synchronized to a reliable time source.

3.3 **Cameras.** Cameras shall be compliant with § 889 of the John S. McCain National Defense Authorization Act for Fiscal Year 2019 (NDAA § 889), regardless of the funding source for any purchase.

3.4 **No additional functions.** The system shall not be configured or used for facial recognition, vehicle-fingerprint or make/model/color searching as a standalone function, bulk export of reads, or connection to any regional or national plate-lookup network, except hot-list comparison conducted under §7.

## §4. Roles and responsibilities

4.1 **Principle.** Every function under this Policy belongs to a named individual. A function assigned to "the Department," "IT," or "the City" without a name is unassigned, and the system does not operate with an unassigned function.

4.2 **Named roles.** The following roles shall be filled by name in an appendix to this Policy at adoption, and kept current by the City Clerk/Treasurer on every change:

| Role | Filled by | Core duties under this Policy |
|---|---|---|
| System Administrator | [TO BE NAMED] | Day-to-day operation; accounts; updates; retention and witness verification support; incident response (§15) |
| Backup System Administrator | [TO BE NAMED] | Same training as the Administrator; has performed at least one update and one log review under observation; acts in the Administrator's absence |
| Outside Auditor | [TO BE NAMED] | Independent verification of the audit log (§11); relevance sampling (§8.7); monthly audit reports. Designated by the City Council; outside the Police Department chain of command; serves as a paid or contracted role |
| TAC Liaison | [TO BE NAMED] | The Police Department's Terminal Agency Coordinator, or designee, as the liaison to ACIC for hot-list and CJIS matters |
| Custodian of Records | City Clerk/Treasurer (office) | Holds witness checkpoints (§11.3); receives dead-man alarm notices (§11.5); maintains this Policy and its public availability (§1.2) |

4.3 **Succession.** If the System Administrator or the Backup System Administrator position becomes vacant and no trained successor is named within 30 days, the system shall be suspended from operation until the role is filled. A system with a bus factor of one is not operated.

4.4 **On-call.** The Administrator and Backup Administrator carry a stated on-call rotation for system incidents, set out in the appendix. The rotation and its compensation treatment are part of this Policy's public record.

## §5. Authorized and prohibited uses

5.1 **Authorized uses — exhaustive.** Captured plate data may be obtained and used **only** for:

(a) automated comparison against hot lists under §7 (Tier 1);
(b) contemporaneous queries under §8.3 (Tier 2);
(c) historical searches under §8.4 (Tier 3) and emergency searches under §8.5;
(d) system administration, auditing, accuracy measurement, and reporting under §§9–13, by the named roles and within their access limits.

No other use is authorized. A use not listed here requires an amendment to this Policy adopted under §1.2 before the use occurs.

5.2 **Prohibited uses.** Captured plate data shall never be used:

(a) for any personal purpose, including looking up a vehicle associated with a family member, acquaintance, neighbor, public figure, or any other person outside an authorized use;
(b) to build or maintain a record of any person's movements, associations, or presence at any place, except as a Tier 3 search expressly authorizes;
(c) for immigration enforcement, parking enforcement, code enforcement, tax or revenue collection, or any civil infraction enforcement;
(d) on the basis of race, ethnicity, national origin, religion, sex, sexual orientation, gender identity, disability, or the exercise of any constitutional right, including presence at a lawful assembly, house of worship, or medical facility as such;
(e) to circumvent this Policy — including asking another agency, a vendor, a database, or a private network to obtain or search data this Policy forbids the City to obtain or search directly, and sharing data for the purpose or effect of such circumvention.

5.3 **Statutory floor.** The City shall not sell, trade, or exchange captured plate data (Ark. Code § 12-12-1804(d)), beyond the statute's law-enforcement exception for data indicating evidence of an offense, and during any pilot period the sharing limits of §10.4 apply, which are stricter.

## §6. Obtaining captured plate data

6.1 **Capture is a governed act.** Reads may be obtained only by cameras operated under this Policy, at approved locations, by the system described in §3. No employee may deploy a personal or borrowed ALPR device, application, or service to obtain plate data for City purposes outside this Policy.

6.2 **Locations.** Camera locations are approved by the City Council (for a pilot, in the authorizing vote) and listed in the appendix to this Policy. No camera may be added, moved, or re-aimed to cover a new area without the same approval. The location list is public.

6.3 **Tests.** Any test capture — including a bench or lot test using City-owned and volunteer vehicles — requires: (a) this Policy in effect; (b) operation by the Police Department; (c) written consent of each volunteer vehicle owner, retained with the test record; (d) no public-road capture, no hot-list comparison, and no enforcement use of test data; and (e) test reads retained no longer than the test requires and in no case longer than §9.2, and destroyed with the destruction logged.

6.4 **Notice.** The existence of this Policy, the camera location list, and the statistical reports under §13 are public. The City shall post signage or public notice at or near camera locations where the City Attorney advises it is required or prudent.

6.5 **Data minimization at capture.** The system captures reads as defined in §2.2. Continuous video recording is not a function of the system and is not retained by it.

## §7. Hot-list comparison; verification before action

7.1 **Comparison.** Reads are compared against hot lists automatically (Tier 1). The sources of official hot lists, the agreement under which they are received, and the CJIS status of the system are as determined in writing by ACIC and confirmed by the City Attorney; those determinations are attached to the appendix. If the determination is that only state-approved vendors may receive hot-list data, hot-list comparison under this Policy does not begin.

7.2 **Currency.** Captured plate data shall be updated against the lists as Ark. Code § 12-12-1804(c) requires — within 24 hours where updates are available. The appendix states who owns this duty under the architecture in force (Department, ACIC, or system operator), and a missed update cycle is an alarm event under §11.5.

7.3 **A hit is a lead, not proof.** No stop, detention, arrest, or other enforcement action may be based solely on a hit. Before any action on a hit, the officer shall: (a) visually verify the plate characters **and the issuing jurisdiction** against the hot-list entry — plate-text agreement alone is not verification; (b) verify the hit through dispatch or ACIC/NCIC channels; and (c) where the entry concerns a wanted person, compare the vehicle's occupants, so far as observable, with the wanted-person description. An uncertain jurisdiction read shall not be treated as a confirmed match.

7.4 **Custom hot lists.** A custom list entry requires one of: stolen vehicle or plate; missing or endangered person; arrest warrant; court order; or a supervisor's written approval stating documented facts of imminent risk. Every entry records its factual basis, its author, and an expiration not more than 30 days out. Supervisor-approved entries expire in 24 hours unless judicial authorization is obtained. Expired entries are removed automatically and the removal is logged.

7.5 **Misreads.** A hit determined to be a misread or a non-match is recorded as such in the outcome record (§13.2) and counted in the statistical report as a match that did not correlate to an alert. Misread patterns by camera or condition are reported to the Administrator for correction.

## §8. Access to captured plate data — users, cases, and tiers

8.1 **Named accounts only.** Access is by individual, named account with multi-factor authentication. Shared, generic, service, or vendor accounts for human users are prohibited and shall not be created. Accounts are disabled immediately on role change or separation. Five failed login attempts lock an account.

8.2 **Every search requires a validated case and a stated justification.** A query through the Front Door requires (a) a case or incident number **validated against a real case record** in the Department's records system — an invalid, closed (where closure bars the search type), or missing number returns no results — and (b) the user's own-words **justification**: what the plate is wanted for and how it connects to that case. Free-text reasons are not a substitute for validation, and a validated case number without a justification is refused. **Catch-all case numbers are prohibited**: no standing or generic case identifier may be used for searches, and the system flags any case number used across unrelated plates or users for auditor review.

8.3 **Tier 2 — contemporaneous query.** For a plate directly observed in an encounter, a named user with a validated case/incident number (or a recorded direct-observation statement) and justification may query the system. The system returns **current status only** — whether the plate is on a hot list or subject to a live alert — and **no historical location data**. One plate at a time. Using Tier 2 to scan a parking lot, gathering, or neighborhood for later use is prohibited.

8.4 **Tier 3 — historical search.** A search of stored reads requires **prior judicial authorization**: a search warrant or court order, on a sworn application showing probable cause, with particularity as to the plate, vehicle, or person; the date-and-time range, as narrow as the facts permit and never beyond the retention period or 30 days per authorization; and the cameras or data set covered. *The operative instrument is the one Arkansas law provides, as confirmed by the City Attorney; until that confirmation is recorded in the appendix, Tier 3 functionality remains locked.* Execution requires two keys: the search is run by the System Administrator or a designee who is not the applicant. A return is filed within 10 days. Denied applications are logged; a renewed application to a different judicial officer must disclose the prior denial. **Reverse searches** (by place and time, to identify unknown vehicles) require a heightened showing, return de-identified results first, and release identifying data only on a further authorization.

8.5 **Emergency search.** A historical search without prior authorization is permitted only on specific, recorded facts of an imminent threat of death or serious bodily injury (including kidnapping and missing or endangered persons), or a flight or evidence-destruction risk for a felony involving death or serious bodily injury. It requires approval of a supervisor or the Chief or designee; a log entry within 4 hours; and judicial notice or application within 48 hours. **Every emergency search receives post-hoc review** by the Outside Auditor and, where a judicial officer is engaged, by that officer. If an emergency search is found unjustified, its data is quarantined, shall not be used, and is destroyed when the matter resolves; the use is counted in the statistical report.

8.6 **Case-list failure.** If the case-validation feed has not refreshed within its configured window, the Front Door **fails closed**: searches stop until a documented refresh. The failure is logged and alarmed under §11.5. No standing override may be created.

8.7 **Relevance sampling.** The Outside Auditor shall monthly sample searched plates against the case files they purportedly relate to and report the rate of searches whose plate never appears in the case file. The rate is included in the statistical report (§13).

8.8 **Auditor and Commission access.** The Outside Auditor's access is read-only and limited to the audit log, redacted records, keyed plate references, aggregates, and summaries. Citizens Commission members receive summaries and redacted reports. Oversight access does not include raw captured plate data, which is disclosed only as §10 permits.

## §9. Retention and destruction

9.1 **Rule.** Captured plate data is retained for the shortest period this Policy states, and destroyed automatically when the period ends. Retention is by schedule and by hold — never by default, accumulation, or inattention.

9.2 **Non-hit reads.** Reads that produce no hit are **destroyed automatically at 14 days** from capture. This period is the City's policy choice and is far inside the 150-day ceiling Ark. Code § 12-12-1804(a)(2) sets for a governmental entity; the statutory ceiling is not the City's operating period and shall not be quoted as such.

9.3 **Recognition media.** Snapshots, clips, and other media held by the recognition component are subject to the same 14-day maximum (§3.2).

9.4 **Legal hold.** Records tied to an ongoing investigation or a criminal action are preserved as Ark. Code § 12-12-1804(b) permits and requires, under a legal hold recorded in the system with its case basis. The automated destruction job **never destroys a held record**. A suspicion, a query, or a bulk designation is not an investigation and does not support a hold.

9.5 **Evidence export.** When held data is needed as evidence, it is exported to the Department's records or evidence system, **hashed at the time of export, with chain-of-custody documentation**. After export, the system copy is governed by the hold on the original record.

9.6 **Destruction of held records.** A held record is destroyed when the investigation concludes without charges or the criminal action concludes, as § 12-12-1804(b) provides, and only on **written disposition sign-off under the disposition schedule approved by the prosecuting attorney** — not on a timer, and not on any single user's say-so. The destruction is logged. Potentially exculpatory material is handled under the same sign-off, with the prosecutor's direction recorded.

9.7 **Deletion is real.** Destruction means the data is not recoverable from the live system: deletion uses secure-delete semantics and file rewrite so destroyed records do not persist in database free pages or journals. **Backups follow this same schedule** — backup media and snapshots rotate so that no backup retains captured plate data materially beyond the period the live system would have; a backup practice that keeps everything indefinitely voids this section and shall be reported as a policy violation.

9.8 **Audit log.** The audit log (§11) is preserved at least 3 years. Audit log entries record keyed plate references, not plate text (§2.1). The retention job never deletes audit log entries.

9.9 **Outcome records.** Outcome records (§2.7) contain no plate data, are preserved **18 months**, and are exempt from the destruction schedule in §9.2 (§13.3).

9.10 **Proof of destruction.** A weekly retention report is generated automatically: records destroyed, oldest remaining read timestamp, holds in force, and exceptions. "Nothing older than the §9.2 period survives outside a logged hold" is a standing compliance measure reported under §13.

## §10. Disclosure and sharing

10.1 **General rule.** Captured plate data shall not be disclosed except as this section and Ark. Code § 12-12-1808 permit. Every disclosure is logged with the recipient, the basis, and the authorizing person, and disclosures are named in the statistical report in aggregate.

10.2 **Registered-owner requests.** A vehicle's registered owner is a permitted recipient of data on their own vehicle. Process: written request to the Custodian of Records; verification of identity and registration; response through the Front Door by a named user; the request, the verification, and the disclosure are logged. **Exception — protection orders (§10.3) controls over this section.**

10.3 **Protection-order suppression.** When a protection order concerning a vehicle is presented to the Department or the Custodian of Records, that vehicle is flagged in the system, and its captured plate data **shall not be disclosed to any person — including a registered owner — except as the result of a match**, as § 12-12-1808 provides. The suppression flag capability shall be built, tested, and in place **before** the owner-request process in §10.2 is enabled. Flags are applied on presentation of the order, recorded with the order's reference, and reviewed on the order's expiration.

10.4 **Sharing with other agencies.** During any pilot period: no sharing except (a) a specific, case-tied disclosure authorized in writing by the System Administrator, logged, and reported; or (b) a disclosure that state or federal law or a court order compels, likewise logged and reported. After any pilot period, sharing of data indicating evidence of an offense with another law-enforcement agency follows § 12-12-1808 and the statute's terms; bulk or standing sharing arrangements require a written agreement approved by the City Council and listed in the appendix.

10.5 **No sale.** Captured plate data shall not be sold, traded, or exchanged (§5.3).

10.6 **Oversight disclosures.** Disclosures to the Outside Auditor and the Citizens Commission are limited to §8.8 material. No provision of this Policy makes raw captured plate data available to any oversight body by virtue of its oversight role.

## §11. Audit log, witnessing, and review

11.1 **The log.** Every action mediated by the Front Door — queries allowed and refused, validations and validation failures, tier determinations, authorizations, emergency uses, holds, exports, disclosures, administrative actions, and the retention and reporting jobs' own runs — is written to a hash-chained, append-only audit log. Each entry covers the previous entry's hash. Minimum fields are set out in the design specification's Appendix A, as amended.

11.2 **Streaming.** Log entries are transmitted as written to an independent store outside the Police Department's and the System Administrator's control, so that no person who can use or administer the system can also rewrite its history.

11.3 **Daily checkpoints.** A signed checkpoint — the chain's root hash **and entry count** — is published daily to (a) the Custodian of Records and (b) a public repository, so any person can verify the chain was not rewritten after the fact. Checkpoint publication credentials are not held solely by the System Administrator.

11.4 **Independent verification.** The Outside Auditor recomputes the chain from the streamed store and the published checkpoints — independently, not by accepting a verification the system presents — on a weekly cadence, and conducts the monthly sample audit (§8.7) and a monthly review of anomaly flags (bulk or partial-plate sweeps, off-hours use, one user querying many unrelated plates, failed-validation patterns, emergency uses).

11.5 **Dead-man alarms.** The retention job, the recognition ingest path, and the checkpoint publication each carry a dead-man alarm: if the expected event does not occur by its deadline, the System Administrator, the Outside Auditor, and the Custodian of Records are notified the same day. A missed checkpoint publication is recorded as an event in the next successful checkpoint.

11.6 **Response to a verification failure.** A checkpoint mismatch, a broken chain, or an unexplained gap is an incident under §15: access is suspended for the affected functions, the Custodian and the City Attorney are notified, and no data from the affected period is used or disclosed until the discrepancy is explained in writing. Detection without a response protocol is not a control, and this section is the protocol.

11.7 **Annual independent audit.** An independent audit of compliance with this Policy is conducted annually (and at the close of any pilot period), by an auditor other than the System Administrator, and reported to the City Council in public session.

## §12. Accuracy and measurement

12.1 **Measured, not claimed.** System accuracy is established by hand-checked sampling against ground truth, under the protocol in the design specification's Appendix C: a human reviewer reads a random sample of vehicle passes before seeing the system's reads; results are scored as correct full-plate read, partial read, missed plate, or misread; **plate-text accuracy and jurisdiction (state) accuracy are scored and reported as separate rates**; results are split by site, by day/night, and by condition (including rain), never reported only as a blended average.

12.2 **No tuning on the test.** Any camera or model change made to improve a score is logged, and the sample is re-drawn after the change.

12.3 **Publication.** Sampling counts and rates are included in the statistical report (§13), with sample sheets published in redacted form.

## §13. Statistical reporting

13.1 **Six-month report.** Every six months, the City shall compile and preserve the usage report Ark. Code § 12-12-1805 requires, in the statute's categories:

(a) the number of license plates scanned;
(b) the names of the lists against which captured plate data was checked;
(c) for each list, the number of confirmed matches;
(d) the number of matches that were subsequently determined not to correspond to an alert (non-correlating matches);
(e) the number of matches resulting in arrest; and
(f) the number of matches resulting in prosecution.

13.2 **Outcome tracking.** Categories (e) and (f) depend on events that conclude after reads are destroyed under §9.2. They are therefore tracked in **outcome records** (§2.7) — no plate data — created when a hit is resolved and updated as the case concludes, including through a standing feedback arrangement with the prosecuting attorney's office for prosecution outcomes.

13.3 **Preservation and exemption.** The six-month reports and the underlying outcome records are preserved **18 months**, as the statute requires, and are exempt from the destruction schedule in §9.2.

13.4 **Public record.** The six-month report is a public record and shall be published on the City's website and filed with the Custodian of Records. During any pilot period, a monthly pilot report (volumes, alerts and outcomes, emergency uses, retention compliance under §9.10, audit findings, staff hours, and costs) is additionally filed with the City Council in public session, and a final public report is filed at the pilot's close.

## §14. Public records

14.1 **FOIA posture.** Records of the system are handled under the Arkansas Freedom of Information Act (Ark. Code § 25-19-101 et seq.). The compiled statistical reports are public (§13.4). Raw captured plate data is disclosed only as §10 permits.

14.2 **Audit log productions.** A public-records production that includes audit log extracts follows a redaction process confirmed by the City Attorney before the system operates: case numbers of open investigations and other exempt material are redacted; plate references are keyed hashes in any event (§2.1). Redaction of an extract does not affect the published checkpoints (§11.3), against which any person can verify that the chain itself was not rewritten.

## §15. Incidents

15.1 **Incidents include:** a verification failure under §11.6; unauthorized access or attempted access, including any attempt to reach plate data other than through the Front Door; loss or suspected loss of credentials; a missed dead-man alarm event (§11.5); destruction of data contrary to §9; and any use for a prohibited purpose (§5.2).

15.2 **Response.** On discovery: contain (suspend affected accounts or functions), preserve the log and related records, and notify the System Administrator, the Outside Auditor, the Custodian of Records, and the City Attorney the same business day. An incident report is filed with the City Council within 10 days, in a form that protects open investigations.

15.3 **Bypass attempts are findings, not embarrassments.** An attempt to access data around the Front Door — whether it succeeds or is blocked — is recorded, investigated, and reported. A blocked bypass is evidence the controls work and is reported as such.

## §16. Training

16.1 No person receives an account until they have completed training on this Policy, the tier rules, verification-before-action (§7.3), and the sanctions in §17, and the completion is recorded. Refresher training is annual. Where the system is a CJIS system under the ACIC determination (§7.1), CJIS security training and any fingerprint and Security Addendum requirements apply as ACIC directs, to administrators, the Backup Administrator, the Outside Auditor (for log access), and any contractor with maintenance access.

## §17. Sanctions for misuse

17.1 **Users.** Violation of this Policy by a City user results in discipline up to and including termination. A willful violation — including any use for a personal purpose (§5.2(a)) or any circumvention (§5.2(e)) — results in permanent revocation of access, in addition to any discipline.

17.2 **Contractors.** Violation by a contractor or vendor with system access is grounds for termination of the contract for cause.

17.3 **Referral.** Suspected criminal misuse is referred to the appropriate prosecuting authority. Misuse of criminal justice information may carry penalties under Ark. Code § 12-12-212 and federal law, independent of this Policy.

17.4 **Evidence questions are for courts.** Whether evidence obtained in violation of this Policy or of the ALPR subchapter is excluded is a question for a court under Ark. Code § 12-12-1805 and § 12-12-1806. This Policy neither requires nor forbids exclusion, and no City representative shall represent otherwise to a court.

## §18. Review, amendment, and sunset of authority

18.1 **Review.** This Policy is reviewed by the City Attorney and the Outside Auditor annually, and at the close of any pilot period, with the review reported to the City Council.

18.2 **Amendment.** Only as §1.2 provides: by the City Council, in public, with the amended text filed and posted. Operational documents (appendices listing locations, role-holders, and technical configurations) may be updated administratively, but no appendix update may expand a use, a retention period, or a disclosure permitted by the body of this Policy.

18.3 **No implied continuation.** Authority to operate the system derives from the Council action that grants it (for a pilot, a time-limited authorization with an automatic sunset). Expiration of that authority suspends capture; data already held is destroyed on the §9 schedule regardless of any later decision, and a decision not to continue the system — including a decision to discontinue ALPR use entirely — is a complete and valid outcome that requires no further justification.

---

## Adoption block (to be completed on adoption)

Adopted by the City Council of the City of Cabot, Arkansas, on ______________, by [Resolution / Ordinance] No. __________.

|  |  |
|---|---|
| Mayor | ______________________________ |
| City Clerk/Treasurer | ______________________________ |
| Effective date | ______________________________ |

**Appendix A — Named roles (§4.2):** System Administrator [TO BE NAMED]; Backup System Administrator [TO BE NAMED]; Outside Auditor [TO BE NAMED]; TAC Liaison [TO BE NAMED].

**Appendix B — Approved camera locations (§6.2):** [TO BE COMPLETED at authorization]

**Appendix C — ACIC / CJIS determination (§7.1):** [TO BE ATTACHED when received in writing]

---

*End of draft policy. DRAFT — FOR CITY ATTORNEY REVIEW. Not adopted, not City policy, and not a statement of current law. All statutory references to be verified by the City Attorney against the official code before adoption.*
