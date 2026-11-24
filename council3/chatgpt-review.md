- receipts:
  - None
- report:
  - status: completed
  - summary: MODEL/EFFORT USED: GPT-6.2, High
    
    NOCTUA 1.1 — Round 3 hostile review
    
    Council seat: ChatGPT | November 24, 2026
    
    Deployment rejected
    
    Static source-code verification
    
    NOCTUA 1.1 is substantially better than 1.0, but it is not ready for operational deployment. The remaining defects are not merely institutional questions, theoretical attacks by a root administrator, or disagreements over the appropriate scope of municipal surveillance. Several are ordinary application-level correctness failures reachable through legitimate accounts and supported maintenance procedures.
    
    The most consequential discovery is that the new Tier 3 retrieval mechanism creates a persistent secondary store of captured plate data that the retention script does not purge. The system can delete every expired row from its primary reads table, report healthy retention, pass its standalone retention audit, and still return historical plate movements that should have been destroyed.
    
    The Compact introduces a separate class of problems: it verifies the existence of recent attestations rather than independently establishing that the underlying audits occurred, succeeded, and remain valid.
    
    Neither finding is contradicted by the reported 184 passing checks. Both expose deficiencies in what those checks establish.
    
    0. Proof of reading and verification scope
    
    I initially retrieved the supplied raw GitHub URLs, then retrieved the repository files directly through GitHub to obtain complete source and accurate physical line numbering. The web-rendered versions omit some blank lines; the citations below use the actual repository line numbers, not those normalized web line numbers.
    
    For example, the raw web rendering of Janus showed 2,753 lines, while the actual file contains the stated 2,829 lines.
    
    File — Physical lines — Coverage — Functions or identifying content
    
    council2/synthesis.md — 156 — Full — Convergent findings; forced-change dispositions
    1.1/janus.py — 2,829 — Full — run_search(), _share_query(), _tier3_results_get()
    1.1/sentinel.py — 317 — Full — _append_txn(), _scrub_scan(), verify()
    scripts/retention.py — 187 — Full — frag_ref(), heartbeat(), main()
    scripts/compact.py — 133 — Full — http(), report_hash(), main()
    scripts/rotation.py — 194 — Full — _rounds_for(), build_schedule()
    scripts/sentinel_audit.py — 290 — Full — audit_url(), audit_db()
    scripts/backup.py — 200 — Full — sha256_file(), config_paths()
    scripts/restore.py — 148 — Full — sha256_file(), refuse()
    scripts/checkpoint.py — 127 — Full — _audit_key(), heartbeat()
    scripts/frigate_bridge.py — 204 — Full — extract(), forward()
    scripts/provision.py — 130 — Full — save(), issue_key()
    scripts/alert_check.py — 97 — Full — notify(), main()
    COMPACT.md — 137 — Full — Suspension; audit rotation
    TRACK-11-REPORT.md — 342 — Partial — Build claims; interpretations and limitations
    tests/run_tests.py — 1,214 — Partial — suite_compact(), suite_retention(), suite_keyloss()
    
    Markdown documents do not contain executable functions, so I have identified their relevant sections instead.
    
    Source fingerprints:
    
    Janus blob SHA: 0dfe843d6880966ebfbef890f8b55780c54a59a9
    Sentinel blob SHA: 51c508d0f044ea2e9e7fefd196f21f6234886599
    Test suite blob SHA: ecd4488e3c6839056c27fc65f43a3454bac303a3
    
    Primary sources: Round 2 synthesis, Janus, Sentinel, maintenance scripts, test suite.
    
    Runtime qualification: I did not execute the NOCTUA service or its test suite. I independently inspected the source. Findings described as code-confirmed are deductions from the implementation; findings dependent on scheduling, concurrency, filesystem behavior or deployment configuration require runtime tests.
    
    I also examined the enacted text of Arkansas Act 668 of 2025, rather than relying exclusively on secondary summaries.
    
    Standards applied
    
    Throughout this review:
    
    CLAIM: Failure against NOCTUA's own documented commitments.
    LAW: Apparent conflict with statutory requirements, subject to the City Attorney's interpretation.
    ENGINEERING: A correctness, availability, security or operational defect.
    POLICY: An institutional decision that software cannot independently settle.
    
    I accept the honest-claims limitation concerning actions mediated by Janus. I am not treating an administrator's ability to access a database directly as an automatic falsification of that claim. An action performed through Janus that changes data without leaving its promised audit record, however, is squarely within scope.
    
    A. Verification of Round 2 findings
    A1. ChatGPT seat disposition matrix
    
    The synthesis attributes nine convergent finding groups to this seat, plus three seat-specific findings and the forced-change requirement.
    
    Round 2 finding — Disposition
    1. Unbounded Tier 2 and unrestricted fragments — FIXED
    2. Unlogged data paths — FIXED-BUT-WRONG
    3. Missing query references and result counts — FIXED-BUT-WRONG
    4. Suppression and supervisor exception — FIXED-BUT-WRONG
    6. Chain integrity and external anchoring — FIXED-BUT-WRONG
    7. Misleading health reporting — FIXED-BUT-WRONG
    8. Statutory reporting — FIXED-BUT-WRONG
    11. Ingest trust — FIXED-BUT-WRONG
    12. Documentation and implementation drift — FIXED-BUT-WRONG
    Config staleness — FIXED-BUT-WRONG
    Verification-time hot-list currency — NOT FIXED
    Prosecutor authentication — NOT FIXED
    Fail-closed boundary and independent certification — NOT SATISFIED
    
    These dispositions evaluate the complete finding groups. Individual repairs within a group are sometimes correct.
    
    A2. Tier 2 temporal wall — FIXED
    
    janus.py:555–566, 585–617, 2637–2655, 2674–2684, 2711–2719
    
    The local /search endpoint now accepts only Tier 2. Empty, short and wildcard-bearing fragments are rejected. The contemporaneous restriction is implemented in SQL for both reads and hits.
    
    This is a substantive repair, not merely another workflow warning.
    
    Qualification: the window is based on server receipt time, not necessarily the time the vehicle was photographed. Delayed camera events are assigned new receipt timestamps at ingest (janus.py:985–998). If contemporaneous means contemporaneous physical movement, the current implementation does not establish that.
    
    Separate policy and engineering issues with configurable limits and non-search endpoints remain below.
    
    A3. Unlogged paths — FIXED-BUT-WRONG
    
    janus.py:920–931, 2451–2506, 2550–2621, 974–1065
    
    The original /hits and /hotlist exposures are repaired: roles are checked and successful responses are logged.
    
    However:
    
    Mediated operation — Remaining problem
    /tier3/pending — Returns request information without logging the view
    /tier3/pending-reviews — Returns review information without logging the view
    /compact/partners — Returns partner details without logging the view
    /compact/checkpoint — Returns checkpoint without logging the view
    Normal /reads ingest — Commits routine reads without an individual ingest record
    Failed authentication — Missing usernames are not logged; logging exceptions are swallowed
    
    Routine ingest might reasonably be audited in aggregates rather than individually. Public operational health checks might reasonably be exempted. But those exceptions must be expressly defined, not inferred after discovering unlogged routes.
    
    Standard: CLAIM.
    
    Required correction: establish an explicit endpoint-level audit contract that specifies successful accesses, denials, mutations and deliberately exempt operational requests. Enforce that contract centrally.
    
    A4. Query audit content — FIXED-BUT-WRONG
    
    janus.py:2656–2719, 222–228, 2249–2287
    
    Tier 2 query entries now carry a fragment HMAC, case number, user, result count and window.
    
    That fixes the original missing-field finding.
    
    But the required justification is validated and then discarded. The Tier 2 justification variable is not stored in a durable query record or attached to the audit entry. The Compact's why has the same problem.
    
    An auditor can establish that someone supplied nonempty text, but cannot subsequently examine that justification.
    
    This also conflicts with COMPACT.md:49–56, 60–62, which describes recording the justification.
    
    Furthermore, a fragment HMAC is a correlation token, not an independently intelligible description of what was searched. An auditor needs an appropriately restricted way to compare the reference with the underlying authorized search.
    
    Standard: CLAIM, ENGINEERING.
    
    Correction: retain a structured query authorization record under an approved retention schedule, link it to the chain using an immutable ID and hash, and preserve sufficient information for meaningful audit sampling.
    
    A5. Suppression — FIXED-BUT-WRONG
    
    janus.py:214–234, 576–617, 979–998, 1102–1115, 1272–1332, 1764–1825, 2721–2752
    
    The ordinary search no longer deliberately returns suppression stubs or grants supervisors unrestricted access to suppressed search results.
    
    Unfortunately, suppression remains inconsistent across storage and disclosure paths.
    
    Defect 1 — inconsistent plate normalization. Suppression placement normalizes plate formatting; ingest uppercases without performing the same normalization. plate_ref() also does not normalize formatting itself. Near-match warnings do not enforce suppression.
    
    Defect 2 — cached Tier 3 results. Retrieval returns previously stored results without reapplying current suppression rules.
    
    Defect 3 — evidence exports. Evidence assembly selects raw reads without a current suppression check and without restricting the read query to the hit's state.
    
    Defect 4 — suppression existence disclosure. Hot-list additions explicitly disclose that a plate is protected by a suppression. The original claim of indistinguishable absence is therefore narrower than the practical system behavior.
    
    Defect 5 — suppression after result limits. run_search() limits the SQL result set before filtering suppressed records. This can change observable counts and displace otherwise eligible results.
    
    Standard: CLAIM and potential LAW, particularly §12-12-1808(b).
    
    That statutory provision restricts disclosure of captured plate data for qualifying protection orders, with an exception involving qualifying matches. It does not expressly establish a general supervisor exception.
    
    Correction: use one canonical plate representation and one current disclosure filter for every raw-data output, including cached results and evidence assembly. Have counsel define the exact permissible match exception.
    
    A6. Chain integrity — FIXED-BUT-WRONG
    
    sentinel.py:228–258, 298–317
    
    The original cross-process append race is structurally repaired. BEGIN IMMEDIATE surrounds the root read and insert.
    
    I withdraw the original objection to database-chain append atomicity. Concurrent correctness should still be stress-tested, but this is the right transaction structure.
    
    The following remain defective:
    
    External sink delivery is not transactionally ordered across processes.
    The spool is not a reliable durable delivery queue.
    The startup anchor trusts a locally available checkpoint file that restore replaces.
    Sequence verification does not require the first sequence number to be one.
    Checkpoint generation itself has a potential inconsistent-snapshot race.
    
    Detailed findings appear in Section B.
    
    A7. Health reporting — FIXED-BUT-WRONG
    
    janus.py:620–650, 664–679, 1066–1087, 2351–2397
    
    Explicit failed heartbeats now degrade health. The ingest/jobs role split is real. Sink failures and anchor mismatches are included in degradation.
    
    However, chain.verify()["ok"] is reported as chain_ok without being included in the calculation of degraded or overall ok.
    
    A deployment can therefore report both:
    
    chain_ok: false
    ok: true
    
    alert_check.py:65–93 relies on overall ok and can consequently miss the chain integrity failure.
    
    Additional defects:
    
    Cameras that have never submitted reads are not represented in the camera-health calculation.
    Retention health inspects only the oldest primary read.
    Overdue holds are counted but do not themselves degrade health.
    Configuration health is based on cached reload status rather than a fresh health-check reload.
    
    Standard: CLAIM, ENGINEERING.
    
    A8. Statutory reports — FIXED-BUT-WRONG
    
    janus.py:731–828, 999–1006, 1161–1175, 1180–1205, 1396–1416
    
    Substantive improvements include durable outcomes, per-list figures, zero-match list provenance, combined arrest-and-prosecution counts, snapshots and emergency-share calculations.
    
    Remaining problems:
    
    Unresolved alerts disappear. Outcomes are created at verification, not alert creation. An unreviewed hit that expires can vanish without a durable unresolved classification.
    
    Per-list prosecution figures remain ambiguous. Overall prosecution reporting distinguishes no reports from zero prosecutions. Individual list entries return numeric zero alongside coverage information, permitting misleading presentation.
    
    One plate/state, one list. The hot-list primary key is (plate,state) and additions replace existing rows (janus.py:308–312, 1118–1123). A vehicle appearing on multiple legitimate lists cannot retain independent list membership through this representation.
    
    List names are not actually controlled identifiers. _sanitize_list_name() removes one particular case-number pattern, not arbitrary sensitive content.
    
    K8 denominator is questionable. tier3_stats() counts all request rows, including pending and denied requests, rather than only searches actually executed. If K8 measures emergency use as a share of actual Tier 3 actions, the denominator is wrong.
    
    Date boundaries are inconsistent. Counters use day strings while outcomes use complete timestamps. An inclusive calendar end date can count scans for that day while omitting its timestamped outcomes.
    
    Standard: CLAIM, ENGINEERING and potential LAW under §12-12-1805.
    
    The amended statute continues to require six-month compilations, eighteen-month preservation and specified per-list statistics.
    
    A9. Ingest trust — FIXED-BUT-WRONG
    
    janus.py:214–219, 974–998; frigate_bridge.py:126–138, 179–194
    
    State-specific plate references are fixed. The remaining original objections largely survive.
    
    Janus still:
    
    Accepts arbitrary camera identifiers.
    Defaults unknown state to Arkansas.
    Defaults missing confidence to 0.95.
    Provides no persistent event-level idempotency.
    
    The bridge provides limited in-memory deduplication, but its event ID is not forwarded to Janus. Restarting the bridge, losing a response or concurrent delivery can therefore produce duplicate reads.
    
    A confidence value representing an actual OCR measurement must not be invented by infrastructure code.
    
    Standard: CLAIM, ENGINEERING.
    
    A10. Documentation drift — FIXED-BUT-WRONG
    
    janus.py:139–160; retention.py:51–62; frigate_bridge.py:43–53
    
    The default bind address is now localhost. Retention environment variables are actually read.
    
    Using identical environment variable names does not establish identical configuration values across separately launched processes. Nor does either process enforce a maximum permitted policy value.
    
    The 1.0 network bandwidth contradiction was not independently re-evaluated in this round because the updated network deployment documents were outside my inspected files. I cannot certify that portion as fixed.
    
    Integration decisions involving K8, hot-list currency and prosecution reporting remain only partly satisfied, as detailed above and below.
    
    A11. Configuration staleness — FIXED-BUT-WRONG
    
    janus.py:254–297, 509–550, 1495–1499, 1555–1559, 1651–1655, 2680–2684
    
    The original silent, indefinite retention of last-good configuration is improved: failed reloads are recorded and certain searches close after 24 hours.
    
    But the implementation measures failed reload age, not configuration freshness.
    
    A syntactically valid case file whose scheduled upstream export has stopped can remain unchanged indefinitely without becoming stale. The same distinction matters for account revocations.
    
    Further:
    
    The staleness clock is in process memory.
    A restart resets that clock.
    The fail-closed condition is not centralized at all authorization boundaries.
    Tier 3 retrieval does not revalidate current case authorization.
    Configuration recovery is tied to file modification changes, not an authoritative freshness attestation.
    
    Standard: CLAIM, ENGINEERING.
    
    Correction: validate authoritative generation timestamps, schema, maximum age and identity revocation state through one shared authorization gate.
    
    A12. Verification-time hot-list currency — NOT FIXED
    
    janus.py:1130–1179
    
    This is a direct recurrence of my seat-specific Round 2 finding.
    
    The endpoint checks role, case membership and pending hit status. It does not establish that the underlying hot-list record remains valid, current and applicable at verification time.
    
    The ingest-time expiry check is not a substitute for verification-time currency.
    
    Correction: bind hits to a versioned source-list entry and require confirmation of current source status, or an explicitly documented historical-evidence exception.
    
    A13. Prosecutor authentication — NOT FIXED
    
    janus.py:1884–1924
    
    The implementation requires a supervisor, a nonempty prosecutor name and a nonempty date.
    
    It does not authenticate the prosecutor or verify that the sign-off exists.
    
    The application cannot distinguish an actual prosecutor authorization from a supervisor-entered assertion.
    
    The new no-charges disposition workflow at 1962–2040 improves separation of duties, but also permits a charges_concluded disposition to authorize release without the prosecutor authentication originally at issue.
    
    Standard: CLAIM, ENGINEERING; the legally sufficient authorization process is POLICY.
    
    A prosecutor does not necessarily need a Janus account. A separately verified authorization document or controlled institutional attestation could satisfy the intended requirement.
    
    The current code does not establish either.
    
    B. Attack on the new controls
    B1. CRITICAL — Tier 3 results defeat retention
    
    Sources: janus.py:345–352, 1560–1568, 1673–1684, 2721–2752; retention.py:124–160; sentinel_audit.py:200–224.
    
    This is the strongest new finding in the entire review.
    
    Tier 3 approval and emergency execution serialize complete search results into tier3_requests.results.
    
    Those results include plate text, camera identifiers, timestamps and hit information.
    
    The retention script removes old primary reads and replaces old Tier 3 search fragments with HMAC references. It does not expire, redact or delete the serialized result bodies.
    
    The retrieval handler then returns those bodies without checking their age.
    
    The retention defect follows directly from the Tier 3 storage and retrieval design.
    
    The result is an effectively indefinite archive of selected vehicle movements, created through normal authorized operations.
    
    It also defeats subsequent suppression placement and case closure because retrieval does not reapply those controls.
    
    Why 184 passing checks do not catch this: tests/run_tests.py:1134–1138 creates an old Tier 3 request without populating its results field. Lines 1151–1162 check the original reads, case-search ledger and fragment, not retained result contents.
    
    The test establishes fragment scrubbing. It does not establish destruction of search results.
    
    Smallest fix: stop persistently materializing raw result bodies in the workflow table. Store short-lived references, resolve them through the current authorization and suppression boundary, and expire their underlying data according to original capture age. Preserve only plate-free workflow metadata indefinitely.
    
    Existing databases must also be migrated to remove historical result bodies.
    
    Regression test: retain a populated Tier 3 result across a retention run, then demonstrate that expired captured data cannot be recovered through Janus, SQL storage or supported backup/restore procedures.
    
    Standard: CLAIM, LAW, ENGINEERING.
    
    Severity: Deployment-blocking.
    
    B2. CRITICAL — Compact's latest audit failure does not invalidate earlier success
    
    janus.py:2110–2132, 2237–2248
    
    The gate searches for the existence of any successful audit inside the 26-hour interval.
    
    It does not determine the latest audit result.
    
    Consequently, a newly recorded audit failure does not automatically invalidate an earlier success inside the same window. Sharing can remain authorized despite the most recent audit being unsuccessful.
    
    The manual suspension mechanism works (2133–2149), but requiring a supervisor to notice the failure and suspend the partner is different from automated reciprocal verification.
    
    Smallest fix: use the newest authenticated audit outcome and require that outcome to be successful, recent and bound to the currently registered partner identity.
    
    Regression test: record success, then failure, and confirm that sharing immediately closes without manual suspension.
    
    Standard: CLAIM.
    
    Severity: Deployment-blocking for the Compact.
    
    B3. CRITICAL — Checkpoint receipts attest existence, not verification
    
    janus.py:2068–2109, 2244–2248; compact.py:93–119
    
    A receipt is accepted when a partner account identifies a root and entry count appearing in the local checkpoint file.
    
    The implementation does not require:
    
    The checkpoint to be the latest checkpoint.
    Its publication to be recent.
    Verification of the checkpoint signature supplied with the receipt.
    A cryptographically authenticated audit report.
    Independent verification of the referenced chain.
    
    The freshness clock is receipt arrival time, rather than the checkpoint's verified publication time.
    
    The Compact therefore cannot distinguish fresh audit evidence from a recently submitted attestation about an old checkpoint.
    
    Similarly, the registered partner key fingerprint is stored but is not used in receipt validation or share authorization (janus.py:2053–2065).
    
    Correction: use authenticated, replay-resistant receipts bound to agency identity, checkpoint hash, sequence, publication time and independently verifiable audit evidence. Reject stale checkpoints and invalidate receipts when the partner identity or key changes.
    
    Standard: CLAIM, ENGINEERING.
    
    Severity: Deployment-blocking for the Compact.
    
    B4. CRITICAL — Compact provides attestation-based sharing, not independently verified sharing
    
    compact.py:93–108, 123–126; janus.py:2110–2132
    
    The Compact runner asks the audited agency whether its own chain passes verification. It compares the audited agency's reported checkpoint to an entry returned by that same agency.
    
    The purported independent audit does not independently reconstruct the chain or establish the checkpoint against an external witness.
    
    The resulting report_hash is a hash of a small detail object. Janus accepts the caller's Boolean ok and report hash without authenticating or inspecting a corresponding full report.
    
    This may be useful as an administrative attestation process. It is not proof against a dishonest participating agency.
    
    That distinction matters because COMPACT.md:19–20, 30–47, 132–135 makes verification the principal assurance.
    
    Correction: independently reconstruct the relevant chain from authenticated entries and a previously trusted external anchor. Sign the audit report with a distinct auditor key, and verify the report at the receiving service.
    
    If the intended architecture remains trust-based attestation, rewrite the claims accordingly.
    
    Standard: CLAIM.
    
    B5. CRITICAL — Compact sharing eligibility is not statutory sharing eligibility
    
    janus.py:2249–2287; COMPACT.md:49–56
    
    The Compact gate checks reciprocal audit status, agency status, a justification string, fragment validity and tier number.
    
    It does not require an independently established connection between the requested data and evidence of an offense.
    
    The partner's case reference can be empty. Tier 3 sharing invokes the full historical search without the local two-key authorization workflow.
    
    Reciprocal auditing does not itself make every captured plate record lawfully shareable.
    
    Arkansas §12-12-1804(d)(2) authorizes interagency sharing of qualifying captured data indicating evidence of an offense. That provision survives Act 668.
    
    I am not concluding that every conceivable historical query would violate the statute. I am concluding that the present implementation does not establish the statutory predicate before disclosure.
    
    Correction: keep Compact sharing disabled until counsel approves a disclosure model. The code must then enforce that approved model at the responding agency.
    
    At minimum, a partner's audit compliance must be separated from the legal authorization for a particular disclosure.
    
    Standard: LAW, CLAIM.
    
    Severity: Deployment-blocking for live interagency sharing.
    
    B6. Rotation — mathematically sound core, defective enforcement
    
    rotation.py:53–113; janus.py:2164–2209, 2754–2821; COMPACT.md:88–125
    
    The circle-method scheduler is correct in its intended combinatorial behavior for valid, unique member lists.
    
    For three or more distinct agencies, the base and mirrored rounds produce each directed pairing once, with no same-round reciprocal pair. Odd-member schedules assign a witness.
    
    I would retain that algorithm.
    
    The problems surround its inputs, publication and enforcement.
    
    Cycle duration — Full rotation cycle at the default 90-day audit period
    3 members — 1.48 years
    4 members — 1.48 years
    5 members — 2.46 years
    6 members — 2.46 years
    7 members — 3.45 years
    8 members — 3.45 years
    9 members — 4.44 years
    10 members — 4.44 years
    20 members — 9.36 years
    
    Derived from the base-round plus mirrored-round construction in rotation.py:94–107.
    
    B6.1. The seed is descriptive, not a source of scheduling entropy
    
    rotation.py:53–55, 78–107
    
    The schedule is generated from the sorted member list. The seed is computed and included but does not influence the slot ordering.
    
    This does not make the algorithm incorrect. It does mean that predictable assignment order and member-list selection remain governance concerns.
    
    Determinism is not the same thing as resistance to manipulation of inputs.
    
    B6.2. Published cycles are not immutable
    
    janus.py:2169–2207, 2759–2762
    
    Publication inserts another schedule row. Status uses the most recently inserted row.
    
    There is no enforcement that a current cycle cannot be replaced, that members correspond to an authoritative roster, or that a new schedule starts only after the existing cycle ends.
    
    This directly contradicts the documented prohibition on mid-cycle reshuffling.
    
    B6.3. Audit-period completion is not measured within the period
    
    janus.py:2778–2792
    
    The filed-status calculation counts successful audits without a timestamp restriction.
    
    An old daily cross-audit can satisfy an ostensibly new periodic deep-audit assignment.
    
    The code also uses locally recorded audit results for both incoming and outgoing assignments. These are not interchangeable evidence of which agency audited which.
    
    B6.4. Delinquency condition is incompatible with the schedule
    
    janus.py:2793–2812
    
    Delinquency requires a particular agency to owe the local agency an audit in each of the last two completed rounds.
    
    But in a valid rotation cycle, that directed pairing occurs exactly once.
    
    The intended two-consecutive-duty delinquency mechanism therefore cannot operate as written within an ordinary valid cycle.
    
    It should compare an agency's last two assigned obligations, not the last two chronological rounds.
    
    B6.5. Witness duties are not verified
    
    rotation.py:100–113; janus.py:2813–2821
    
    The witness is named in the schedule. There is no corresponding witness completion ledger or validation mechanism in the inspected implementation.
    
    Naming the duty is fixed. Establishing performance of that duty is not.
    
    B6.6. Schedule signatures are optional in practice
    
    rotation.py:157–173; janus.py:2186–2189
    
    The command-line verifier checks a signature only when a key and signature are both present. Janus excludes the signature from its equality comparison and does not independently validate it.
    
    Recomputation establishes mathematical consistency, not authorized publication.
    
    Required change: introduce authoritative membership, immutable cycle identifiers, validated periods, assignment-specific audit evidence and witness records. Correct delinquency tracking across cycles.
    
    Standard: CLAIM, ENGINEERING.
    
    Severity: Code-critical for rotation credibility, although not independently a reason to reject an otherwise isolated local installation.
    
    B7. Standalone audit tool is not independent in URL mode
    
    sentinel_audit.py:87–160, 163–199, 200–224, 246–286
    
    There are five material defects.
    
    Finding — Consequence
    URL verification calls the target's own /audit/verify — Self-reporting is labeled independent verification
    Checkpoint newer than local chain count — Anchor failure is not explicitly recorded in that branch
    Missing checkpoint file in DB mode — Anchor checks may simply be absent from an otherwise successful report
    Derived-data verification checks only fragments and case searches — Persistent Tier 3 raw results escape detection
    DB mode constructs sentinel.Chain() — The purported read-only audit can modify the supplied database
    
    The last finding follows from sentinel_audit.py:164–170 and sentinel.py:115–136, where construction opens a writable connection, sets pragmas and creates tables.
    
    The audit also accepts an additional 26 hours of retention age while labeling the check compliant (sentinel_audit.py:112–123, 204–209).
    
    A scheduling tolerance may be operationally reasonable, but it should be reported separately from compliance with a hard policy deadline.
    
    Correction: make DB mode genuinely read-only, define mandatory checks, fail on missing required evidence, reconstruct the remote chain independently, inspect every raw-data retention class and distinguish warnings from actual policy compliance.
    
    Standard: CLAIM, ENGINEERING.
    
    B8. Sentinel scrubber is a narrow pattern detector, not an enforced data contract
    
    sentinel.py:70–106, 260–276; janus.py:920–928, 1125–1128, 1238–1242, 2283–2285
    
    The scrubber recognizes a limited set of uppercase plate formats. It does not establish that arbitrary permitted strings are free of captured plate data.
    
    The implementation explicitly acknowledges this narrowness in _scrub_scan().
    
    The problem is that Janus continues to pass caller-controlled fields into the permanent chain, including user identifiers, categories, case references and hold references.
    
    Those values are not all validated against fixed schemas or authoritative enumerations.
    
    I therefore reject the unconditional claim in sentinel.py:8–17 that plate text never enters the chain.
    
    Correction: define a strict typed schema for each audit event kind. Restrict identifiers and enumerated values at their authoritative creation boundaries. Keep arbitrary user text outside the permanent chain.
    
    The scrubber can remain as secondary defense, but it cannot be the primary guarantee.
    
    Standard: CLAIM; potential LAW depending on the treatment of retained captured data.
    
    B9. Log-before-data is implemented; mutation atomicity is not
    
    janus.py:953–965, 1118–1129, 1157–1179, 1302–1315, 1562–1583, 1915–1924, 2100–2132
    
    The application now genuinely delays many sensitive response bodies until their audit append succeeds.
    
    I credit that repair.
    
    However, database mutations routinely commit before the corresponding chain append. If the append fails, the API reports an error even though the mutation has already taken effect.
    
    This affects hot-list changes, verification, suppression placement, Tier 3 materialization, evidence release and Compact authorization records.
    
    A 500 response is not a rollback.
    
    Because these are actions mediated by Janus, this is directly within the system's honest-claims boundary.
    
    Correction: use a single transactional boundary for database mutation and its audit event, or an atomic durable outbox that establishes the event before committing the mutation and withholds externally visible effects until completion.
    
    Needs runtime test: inject audit-write failures at each transaction boundary and verify that no successful state change remains unaccounted for.
    
    Standard: CLAIM, ENGINEERING.
    
    Severity: Code-critical.
    
    B10. External sink ordering and delivery are not reliable
    
    sentinel.py:137–144, 176–212, 228–276
    
    The SQLite chain transaction is now serialized across processes. External sink delivery occurs after that transaction commits and is protected only by a process-local lock.
    
    Separate Janus and retention processes can therefore commit entries in sequence order but deliver them externally in a different order.
    
    Other problems:
    
    A partially completed sink write can lead to duplicate delivery during retry.
    Spool failure is explicitly swallowed.
    The spool is stored adjacent to the sink, potentially sharing its failure domain.
    A crash between database commit and streaming leaves an entry with no durable delivery obligation.
    Successful later delivery can reset sink health without establishing that all earlier entries arrived.
    
    These are consequences of the current delivery design, not objections to the hash-chain algorithm.
    
    Needs runtime test: concurrent writers, partial sink failure, full disk, process termination during delivery and recovery after each fault.
    
    Correction: use the durable database chain itself as the delivery queue, with a persistent acknowledged sequence cursor and independently verified sink continuity.
    
    Standard: CLAIM, ENGINEERING.
    
    B11. Startup anchor fails under the supported restore lifecycle
    
    janus.py:471–505, 1418–1446; restore.py:112–124
    
    Janus compares its chain with the last checkpoint in the local file.
    
    If the checkpoint is missing or unreadable, the startup check returns without establishing an anchor.
    
    The startup check does not validate the checkpoint HMAC.
    
    More importantly, the supported restore procedure replaces both the database and its checkpoint file with copies from the same backup set.
    
    A restored older database can therefore agree with its restored older checkpoint. The current independently published checkpoint is not consulted.
    
    The restore can erase the local evidence needed to detect the restore.
    
    This is precisely the rollback concern raised in Round 2, relocated into the maintenance workflow.
    
    Anchor acceptance also clears the mismatch flag without establishing a new externally witnessed recovery baseline.
    
    Correction: obtain the authoritative checkpoint from independently controlled custody. Never replace that authoritative anchor during ordinary recovery. Record explicit recovery transitions and require reconciliation before sensitive service resumes.
    
    Standard: CLAIM, ENGINEERING.
    
    Severity: Code-critical.
    
    B12. Missing-key lockout works for missing keys, not wrong keys
    
    janus.py:175–228; checkpoint.py:50–75
    
    The missing-key test is a legitimate improvement. A populated audit chain with no available key now causes Janus to enter its locked state.
    
    However, the presence of any environment key or existing key file is sufficient to avoid lockout.
    
    The implementation does not verify that the loaded key is the correct key for the existing installation.
    
    A wrong, empty or improperly restored key can invalidate every existing plate reference and suppression relationship without activating the intended missing-key protection.
    
    Changing the key also has consequences for audit-reference comparability.
    
    Correction: bind the installation to a verified key identity and fail closed on missing, invalid or mismatched key material. Use separate keys for plate pseudonymization, checkpoint signing and auditor attestations.
    
    Standard: CLAIM, ENGINEERING.
    
    Severity: Deployment-blocking where suppression reliability depends upon stable HMAC references.
    
    C. Maintenance scripts
    C1. Retention — FAIL
    
    Source: retention.py
    
    This script is the implementation behind the system's central public promise. It is not merely housekeeping.
    
    Its deletion behavior must be evaluated against all data containing captured plate information.
    
    Retention class — Actual behavior
    Primary reads — Deleted after configurable receipt-age threshold
    Hits — Generally retained for 30 days, subject to exceptions
    Case-search fragments — Deleted on a day-based 14-day schedule
    Tier 3 fragments — Replaced with HMAC references
    Tier 3 result bodies — Not purged
    Evidence bundles — Not automatically destroyed here
    Suppression records — Not purged here
    Inactive hot-list records — Not purged here
    Backups — Governed by separate script and clock
    
    Sources: retention.py:102–154; janus.py:308–359; backup.py:181–196.
    
    Some classes, such as active hot-list information and protection-order records, may serve purposes distinct from captured movement history. They need separate lawful retention policies rather than automatic treatment as ordinary reads.
    
    C1.1. Retention clock begins at receipt, not capture
    
    janus.py:985–998; retention.py:102–105
    
    The deletion clock uses Janus receipt time. Backfilled events can therefore remain available well beyond fourteen days after the original physical observation.
    
    If the city's promise concerns capture age, this is a direct mismatch.
    
    C1.2. Fourteen days is not a hard maximum
    
    retention.py:54–56, 102–105; janus.py:153–155, 2372–2373
    
    The configured threshold is fourteen days, but the job is designed to run nightly and health allows a further 26 hours.
    
    Normal operation can consequently retain data beyond fourteen elapsed days.
    
    A strict maximum requires enforcing the deadline at both disclosure and deletion, not simply scheduling a nightly purge.
    
    C1.3. Holds protect hits but not the underlying reads
    
    retention.py:104–122
    
    Primary reads are deleted unconditionally by age before legal-hold conditions are evaluated for hits.
    
    This can remove relevant source data from an active investigation unless the evidence has already been separately preserved.
    
    The city needs a defined process ensuring that a legal hold preserves all necessary evidence before routine deletion occurs.
    
    The current implementation makes no such guarantee in the retention script.
    
    C1.4. Missing key produces successful retention health
    
    retention.py:62–73, 139–154, 183
    
    If the audit key is unavailable, fragment scrubbing is skipped. The job nevertheless reaches a successful heartbeat.
    
    It also differs from Janus's key-resolution behavior: Janus can use the installation key file, while retention reads the environment variable.
    
    C1.5. Fragment references are incompatible
    
    retention.py:65–73; janus.py:222–228
    
    Janus uppercases fragment input and truncates the HMAC to 24 hexadecimal characters.
    
    Retention does not truncate its HMAC.
    
    The resulting scrubbed value is not the same reference used in the chain, contrary to the retention script's documented claim.
    
    Use a shared implementation, not duplicated cryptographic routines.
    
    C1.6. Purge audit failure reports success
    
    retention.py:173–183
    
    A failed RETENTION_PURGE append is printed, but the script still posts a successful heartbeat.
    
    Thus the system may report a successful job even though the promised audit evidence of its operation was not recorded.
    
    C1.7. SQLite physical deletion assurance is incomplete
    
    retention.py:93–96, 156–161
    
    Retention uses VACUUM and a truncate checkpoint, which are useful.
    
    But the script does not inspect the WAL checkpoint result to establish successful truncation. Nor does this establish deletion from filesystem snapshots, backup media or other copies.
    
    Needs runtime test: run retention while competing database readers are active, inspect WAL checkpoint results, and verify that the health response distinguishes actual destruction from a merely attempted maintenance operation.
    
    Overall retention verdict: deployment-blocking. Fixing the primary reads table alone cannot establish the fourteen-day promise.
    
    C2. Backup — FAIL
    
    Source: backup.py
    
    C2.1. Backup expiration is based on backup age, not data age
    
    backup.py:100–110, 181–196
    
    A backup containing a nearly fourteen-day-old read can remain for another fourteen days.
    
    A nightly backup strategy that prunes only by backup creation date can preserve some captured data for approximately twenty-eight days, potentially longer if pruning is delayed.
    
    The backup description recognizes the need to follow the restricted data class's retention schedule, but its implementation does not track that class's original expiration deadlines.
    
    C2.2. Evidence files are excluded
    
    backup.py:100–149; janus.py:1834–1875
    
    The backup includes the database, configuration, key and checkpoints. It does not include the evidence bundle directories referenced by the database.
    
    A successful restore can therefore recover evidence metadata without recovering the corresponding evidence.
    
    Evidence may deliberately require a separate backup system. If so, that system must be explicitly required, monitored and tested. The inspected backup is not a complete evidence recovery mechanism.
    
    C2.3. Manifest authentication is not independent custody
    
    backup.py:124–149
    
    The backup can contain the very audit key used to authenticate its manifest.
    
    This provides useful corruption detection but cannot provide independent authenticity against a party controlling the backup set.
    
    The script acknowledges secret-custody limitations; I do not treat those acknowledged limitations alone as a concealed defect.
    
    C2.4. Health success precedes pruning
    
    backup.py:157–196
    
    The successful backup heartbeat is sent before old backup sets are pruned.
    
    Pruning can fail after the system records success.
    
    Correction: track backup creation, expiry compliance, evidence recovery coverage and off-host custody separately. Report success only after all required work is complete.
    
    C3. Restore — FAIL
    
    Source: restore.py
    
    C3.1. Restore can silently resurrect expired data
    
    restore.py:106–144
    
    The restored database is installed without first applying current retention rules.
    
    It may also restore older user authorization files, case files, suppression state and partner-sharing state.
    
    A restored authorization record is not necessarily still valid.
    
    Correction: reconcile current authorization sources, retention deadlines, protection orders and external audit state before starting live service.
    
    C3.2. Chain verification occurs after replacing production files
    
    restore.py:112–141
    
    The restored chain is verified only after installation.
    
    A structurally defective database may already have displaced the live database by the time verification fails.
    
    Validate the staged recovery set first.
    
    C3.3. Pre-restore copies create unbounded secondary storage
    
    restore.py:108–115, 144
    
    The script deliberately keeps previous live files under .pre-restore-* names.
    
    No cleanup mechanism for those copies was identified in the inspected restore or backup scripts.
    
    That creates another retained data class outside normal purge logic.
    
    C3.4. Recovery does not establish one consistent system snapshot
    
    backup.py:100–137; restore.py:112–135
    
    The database, configuration and checkpoints are captured separately.
    
    The checkpoint file can describe a chain state newer than the database backup. Configuration may likewise represent a different point in time.
    
    Needs runtime test: take a backup under concurrent ingest and audit activity, restore it, and demonstrate a consistent recoverable state.
    
    C4. Checkpoint generation — FAIL pending concurrency repair
    
    Source: checkpoint.py
    
    checkpoint.py:104–123
    
    The root hash and entry count are obtained using separate SQL statements without an explicit shared snapshot transaction.
    
    A concurrent append between those reads can create a checkpoint whose root and entry count describe different chain states.
    
    This can generate a false anchor mismatch without any malicious activity.
    
    The heartbeat also establishes that a local checkpoint was written, not that an independently controlled witness received and preserved it.
    
    I did not inspect publish_witness.sh, so I cannot establish the behavior of the external publication process.
    
    Correction: obtain root and terminal sequence from one consistent database snapshot. Separate checkpoint creation from confirmed external publication.
    
    Needs runtime test: sustained concurrent appends while generating and externally publishing checkpoints.
    
    C5. Frigate bridge — FAIL for operational ingest assurance
    
    Source: frigate_bridge.py
    
    frigate_bridge.py:80–138, 153–196
    
    The bridge accepts event payloads without authenticating the event source at its HTTP endpoint. Its default localhost binding reduces exposure, but local binding is not source authentication.
    
    Other defects:
    
    Unknown confidence is fabricated as 0.95.
    Unknown state is represented as Arkansas.
    A mutable OCR result can produce multiple forwarded events.
    An event ID is not included in the Janus ingest payload.
    Deduplication is volatile and not synchronized across request threads.
    /health always returns ok:true, including after forwarding failures.
    Request size and socket handling lack Janus's corresponding protections.
    
    The bridge explicitly labels its assumed Frigate payload format and state limitation in its documentation. I credit that honesty.
    
    The remaining integration work must verify the actual pinned Frigate version, source authentication, replay semantics, capture timestamps and delivery guarantees.
    
    Needs runtime test: real Frigate event traffic, camera outages, delayed delivery, repeated event updates and bridge restarts.
    
    C6. Provisioning — material operational weaknesses
    
    Source: provision.py
    
    provision.py:45–72, 87–126
    
    Cryptographically random keys and hashed credential storage are correct design choices.
    
    Remaining problems:
    
    User modifications are not written to Sentinel.
    The provisioning record is ordinary console output.
    Concurrent provisioning operations can overwrite one another's changes.
    Temporary file permissions are applied after creation.
    Key issuance is printed before persistence is completed.
    No independently enforced role-assignment approval exists.
    
    Because provisioning is deliberately outside Janus, its absence from Sentinel does not automatically violate the narrow mediated-action claim.
    
    Nevertheless, account and role changes are foundational to two-key authorization. A city cannot establish independent approvals solely by observing two distinct usernames if credential issuance and custody are uncontrolled.
    
    Correction: serialize provisioning updates, create temporary files securely, establish durable credential issuance/revocation records and require appropriate approval for privileged roles.
    
    C7. Alert checking — incomplete
    
    Source: alert_check.py
    
    alert_check.py:51–93; janus.py:2374–2397
    
    The dead-man checker now correctly responds to Janus's overall health flag.
    
    Unfortunately, it inherits Janus's omissions.
    
    It does not independently alert on a failed chain verification when overall health remains affirmative. Nor does it detect the persistent Tier 3 result store, unpruned backup data or missing witness publication.
    
    The correct solution is not to duplicate every validation rule in the alert script. It is to make the authoritative health state comprehensive and test its external alerting path.
    
    D. Convergence and deployment verdict
    D1. Does a deployment-blocking or code-critical finding remain?
    
    Yes. Several remain.
    
    The following are the minimum closure items I would submit to the orchestrator.
    
    Priority — Finding — Smallest acceptable correction
    1 — Persistent Tier 3 raw results — Expire raw results and reapply current disclosure rules
    2 — Inconsistent suppression — Centralize canonicalization and disclosure enforcement
    3 — Retention bypass through backups and recovery — Enforce original data expiry across every managed copy
    4 — Mutations survive audit failure — Atomic mutation-and-audit transaction or durable outbox
    5 — Restore defeats startup anchor — Independently controlled recovery anchor
    6 — Wrong key defeats suppression continuity — Verify installation key identity
    7 — Evidence lifecycle leaks and authorization gaps — Correct bundle custody, destruction and release handling
    8 — Compact accepts obsolete or insufficient audit evidence — Validate latest authenticated audit state
    9 — Compact sharing lacks statutory disclosure predicate — Implement counsel-approved authorization gate
    10 — Rotation completion and delinquency are incorrect — Assignment-bound, period-bound audit records
    11 — Health can be green despite failed chain verification — Include all critical invariants in health
    
    There is an additional evidence lifecycle issue worth explicitly recording.
    
    janus.py:1836–1875 creates timestamped bundle directories but maintains only one bundle pointer per hit. A later export replaces that pointer. janus.py:1950–1959 destroys only the currently referenced bundle.
    
    Earlier export directories may become orphaned. Re-export also does not reset existing release or disposition-confirmation state.
    
    The evidence lifecycle therefore remains defective even after adding a destroy endpoint.
    
    Furthermore, retention.py:115–122 can preserve hits through an unconfirmed evidence disposition row even when no actual evidence bundle exists. Bundle existence and evidence authorization are not equivalent conditions.
    
    These are code defects rather than unresolved philosophical questions.
    
    D2. What does Act 668 actually change?
    
    I examined the legislature's published enacted text, including the actual underlined additions and stricken language.
    
    Arkansas Act 668 of 2025 — official enacted document
    
    The act was approved April 16, 2025. Relevant verified provisions are:
    
    Provision — Effect
    §1804(a) — Establishes 60-day limits for qualifying private users and 150-day limits for other eligible entities, subject to subsection (b)
    §1804(b) — Retains the investigation and criminal-action exceptions and destruction obligations
    §1804(c) — Retains the applicable 24-hour update requirement
    §1804(d) — Retains restrictions on governmental exchange and the offense-evidence sharing exception
    §1805(a) — Retains six-month public statistical compilation and eighteen-month preservation
    §1807(c) — Adds Attorney General enforcement under the Deceptive Trade Practices Act
    
    An important distinction: fourteen days is NOCTUA's stricter proposed policy, not the general municipal statutory maximum of 150 days.
    
    But indefinite retention of ordinary captured plate data raises statutory concerns as well as violating the proposed policy.
    
    The Act does not eliminate the need to examine §1808 privacy restrictions, nor does the Compact's reciprocity mechanism independently supply lawful disclosure authority.
    
    D3. What remains that is not inherently a code defect?
    
    The following belong to the City Attorney, Citizens Commission, City Council, records custodian or independent certifying auditor:
    
    Whether and under what conditions general historical plate searches are permitted.
    The permissible scope of interagency sharing under §12-12-1804(d).
    Whether particular keyed plate references constitute captured or derived data requiring destruction.
    The exact handling of protection orders, match exceptions and conflicts between agencies.
    The institutional authority for prosecutor sign-off and investigation closure.
    Independent custody of audit keys, signing keys and externally published anchors.
    Whether the fourteen-day policy is a hard elapsed-time maximum or permits a documented maintenance interval.
    Formal designation of approved cameras, accounts, agencies and data sources.
    The publication and preservation procedures for statutory statistical reports.
    Independent security certification of the exact production release.
    Explicit acceptance of the limitations involving fully privileged administrators and data copied by authorized recipients.
    
    No application can independently determine whether every officer's stated investigative purpose is truthful. That is a genuine institutional limitation.
    
    But software can preserve the stated purpose, bind it to an authorization decision, enforce expiration and make the event available for audit.
    
    NOCTUA should not confuse the former limitation with a reason to omit the latter controls.
    
    D4. What the reported 184/184 checks actually establish
    
    The strongest evidence against interpreting the count as certification appears in the tests themselves.
    
    Test source — What is demonstrated — What remains unestablished
    946–1013 — Sharing opens with two recorded legs and closes on suspension — Latest failure, stale receipts, independently verified audit evidence
    1015–1047 — Audit tool produces expected reports — Completeness and truthfulness of independent verification
    1049–1067 — Compact runner successfully records an audit — Resistance to dishonest or obsolete audit evidence
    1070–1099 — Missing key triggers lockout — Wrong-key and empty-key handling
    1102–1174 — Old primary reads and fragments are purged — Complete destruction of cached results and other managed copies
    
    I do not dispute that all 184 checks may have passed.
    
    I dispute the evidentiary scope of that result.
    
    The next test suite needs invariant-based negative testing, not simply additional endpoint happy-path assertions.
    
    Specifically:
    
    Retention invariant: expired captured data cannot be recovered from any ordinary managed storage class.
    Disclosure invariant: current authorization and suppression rules apply at every raw-data output.
    Audit invariant: no mediated sensitive mutation becomes effective without durable audit evidence.
    Recovery invariant: restoration cannot silently roll back external trust state or resurrect expired access.
    Compact invariant: a failed, obsolete or unverified audit cannot authorize disclosure.
    Health invariant: a failed critical control cannot coexist with an affirmative overall health state.
    
    Each invariant must be tested under ordinary use, process restarts, partial failures and concurrent activity.
    
    E. One forced change
    Require a single, enforceable captured-data lifecycle invariant before another live deployment candidate is declared.
    
    I would make the following a mandatory acceptance criterion for NOCTUA 1.2:
    
    No captured plate data, or recoverable copy of captured plate data, may remain accessible or be disclosed after its authorized expiration, current suppression, or revocation of the authorization under which it was obtained, except through a separately documented and lawfully authorized evidence-preservation workflow.
    
    This must cover primary reads, hits, Tier 3 results, evidence exports, backups, restore copies, bridge data and interagency responses.
    
    The implementation does not necessarily need separate database files for every class. It does need an explicit inventory of every location where captured data exists, an enforced expiration mechanism for each location, and a shared authorization boundary for disclosure.
    
    This is the forced change because the fourteen-day promise is central to NOCTUA's justification as an alternative to third-party surveillance infrastructure.
    
    If the city cannot demonstrate where its captured data exists and when every ordinary recoverable copy expires, it cannot credibly claim to control retention.
    
    Final council position
    
    Component — Verdict
    Janus local search architecture — Retain
    Sentinel transactional chain — Retain
    Suppression implementation — Repair
    Retention implementation — Reject pending repair
    Evidence lifecycle — Repair
    Backup and restore lifecycle — Reject pending repair
    Compact reciprocity concept — Retain
    Compact verification implementation — Reject pending repair
    Rotation algorithm — Retain
    Rotation enforcement — Repair
    Synthetic-data development — Continue
    Operational deployment using live captured plate data — Do not authorize
    
    Round 3 has not converged.
    
    Version 1.0's principal failure was that its controls could be bypassed through alternative application paths. Version 1.1 closes several of those paths but introduces persistent secondary data stores, insufficiently authenticated trust records and maintenance procedures that undermine its own protections.
    
    The architecture remains worth developing. Its security and privacy claims remain ahead of its implementation.
    
    My vote: proceed to NOCTUA 1.2, with live deployment withheld until the remaining critical invariants are independently demonstrated.
    
    ---
    Chat: https://chatgpt.com/c/6b0549b7-4bcc-83ea-880b-b07b401119d3 — titled "Review Noctua Fixes". Response marked "Response complete" in the UI.
    
    Model setup note: The model picker listed GPT-6.2 (already checked/selected), GPT-6, and GPT-5.6 Sol. No model named "Fable" and no Ultra-class tier were listed, and no step-down was needed — GPT-6.2 was the best available included model. The thinking-effort slider showed "High, 3 of 3", i.e. the maximum effort, at the far-right position. Usage shown in the sidebar was 5-hour usage 100% left, weekly usage 85% left.