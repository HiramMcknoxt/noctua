# NOCTUA Council Round 9 — ChatGPT seat review

Seat: ChatGPT. Model/effort per the browser operator's interface observation: GPT-6.2, Thinking effort High (the response text itself claims no model name is shown — per seat protocol the interface observation governs). Chat: https://chatgpt.com/c/6b0769d6-1fac-83e9-8563-9f8cff60867a. Static code review, no execution. Returned Nov 25, 2026.

---

NOCTUA Council Round 9 — Independent ChatGPT Seat Review
    
    Build: NOCTUA 1.2.6 (janus126/)
    Model: the interface shows no model name
    Effort: not visible from this seat
    Review method: Static source-code review of the eight supplied attachments only.
    
    No external repository, earlier build, or outside source is being substituted for the submitted material. Source citations refer to original source-file line numbers, excluding the attachment headers and combined-file separators.
    
    The builder's and orchestrator's reported test executions are treated as third-party evidence, not as independently executed tests by this seat. The owner's explicit instruction to conduct this round by code-reading takes precedence over the brief's general preference for executable reproductions.
    
    1. Findings register
    
    The first material problem is that the new authentication restrictions are not applied consistently across the authentication entry points.
    
    R9-01 — CODE-CRITICAL — U1 lockout restriction is incomplete
    
    Status: Confirmed by static inspection.
    Classification: Regression-closure failure.
    
    The ordinary authentication path distinguishes incorrect API keys from failures occurring after a valid key has been presented. However, the separate secret-pickup authentication path retains an inconsistent lockout rule.
    
    Evidence:
    
    janus.py:3262–3277 — ordinary authentication records whether the API key verified.
    
    janus.py:5620–5625 — the pickup handler records a lockout failure even when API-key verification fails.
    
    janus.py:3079–3108 — the shared lockout function excludes machine identities but does not independently require successful API-key verification.
    
    janus.py:3007–3008 — the threshold remains five failures, with a 900-second lock period.
    
    Consequence: The claimed U1 property—that an incorrect API key cannot contribute to a human account's lockout—is not true across the complete authentication surface.
    
    This is particularly significant because U1 was a forced change, not an optional improvement.
    
    Required correction: Centralize the lockout eligibility decision so that every authentication entry point applies the same verified-key and human-role requirements. Extend the regression coverage to the secret-pickup path.
    
    R9-02 — CODE-CRITICAL — U6 allows an existing approved hot-list entry to be modified outside the approval queue
    
    Status: Confirmed by static inspection.
    Classification: New defect in the U6 implementation.
    
    The non-supervisor submission path uses the same membership table and conflict key as the supervisor's approved-entry path. Its conflict-update behavior does not preserve the approved entry's attributes.
    
    Evidence:
    
    janus.py:5001–5011 — supervisor additions establish an active, nonpending membership.
    
    janus.py:5041–5050 — non-supervisor submissions use the same conflict key and update category, added_by, added_ts, and expires_ts, without changing the existing pending or active status.
    
    janus.py:4589–4594 — matching consumes active, nonpending membership records.
    
    janus.py:5051–5058 — the chain and HTTP response nevertheless describe the operation as a pending submission.
    
    Consequence: A submission colliding with an existing approved membership can change the effective membership without another supervisor decision. The audit record describes a submission rather than the actual change to an active listing.
    
    U6 therefore implements uniform submission responses without fully implementing the supervisor-approval boundary.
    
    Required correction: Separate proposed changes from approved memberships. A pending proposal must never mutate the currently approved membership until a supervisor explicitly approves it.
    
    R9-03 — CODE-CRITICAL — U9's born-empty marker is permanent rather than a provisioning boundary
    
    Status: Confirmed by static inspection.
    Classification: Architectural defect in the commissioned interpretation.
    
    The distinction between an empty installation ceremony and an installation carrying operational history is legitimate. The implementation, however, distinguishes installations by historical origin rather than their present security state.
    
    Evidence:
    
    janus.py:2854–2866 — the install_born_empty marker is established during initialization.
    
    janus.py:3211–3234 — the continued existence of that marker exempts an unprovisioned installation from the tightened state.
    
    janus.py:3294–3297 — human key-only authentication remains permitted in the ceremony state.
    
    janus.py:4632–4640 — ingest refuses only when _unprovisioned_locked() is true.
    
    tests/run_u126_cases.py:731–758 — the U9 test covers a populated database originating in 1.2.5, which does not carry the newly introduced marker.
    
    Consequence: The born-empty exemption does not itself expire when the installation acquires operational data. The marker is also database metadata rather than a separately established deployment authorization.
    
    The U9 test proves the narrower implemented condition, not the originally commissioned security property.
    
    Required correction: Make production-data service conditional on completed provisioning. Preserve first-boot administration and an explicitly isolated test/demo mode without permitting the normal production data surface to operate indefinitely under the ceremony exemption.
    
    R9-04 — CODE-CRITICAL — Restore's provisioning ratchet does not fail closed on an unknown outgoing state
    
    Status: Confirmed by static inspection; fault behavior not executed.
    Classification: Incomplete U13 closure.
    
    The normal-path repair for R-A is present, but failure handling weakens the provisioning ratchet.
    
    Evidence:
    
    scripts/restore.py:427–443 — an exception when inspecting the outgoing database is converted into outgoing_provisioned = False.
    
    janus.py:2488–2505 — materialization of mandatory re-enrollment depends on the restored state or the outgoing provisioning marker.
    
    janus.py:2514–2520 — exceptions during the re-enrollment/ratchet operation are suppressed, after which the restore marker is removed.
    
    An inability to determine provisioning status is not evidence that the installation was never provisioned. Likewise, unsuccessful re-enrollment-state persistence is not completion of the restore ceremony.
    
    Consequence: The security ratchet is not guaranteed under partial restore failures. Its normal-path regression result does not establish fail-closed behavior when state inspection or persistence fails.
    
    Required correction: Represent outgoing provisioning status as provisioned, never provisioned, or unknown. An unknown state must refuse restoration or conservatively require re-enrollment. Retain the restore marker until the required security state and corresponding audit evidence are successfully persisted.
    
    R9-05 — CODE-CRITICAL — Authentication-failure accounting retains unbounded attacker-controlled state
    
    Status: Confirmed by static inspection.
    Classification: Previously queued small, elevated in severity.
    
    Evidence:
    
    janus.py:2882 — _auth_fail_totals is an ordinary dictionary.
    
    janus.py:2913–2924 — a per-username total is recorded before the global audit-entry cap is applied.
    
    janus.py:3124–3127 — health reporting sorts the entire accumulated dictionary to return only ten entries.
    
    janus.py:4194–4199 — unsuccessful authentication invokes this accounting.
    
    The global chain-write limit does not bound the corresponding memory consumption. Health computation also becomes more expensive as the dictionary grows.
    
    Consequence: Authentication-failure telemetry has an unbounded resource requirement, including on a surface that exists specifically to process unauthenticated requests.
    
    Required correction: Maintain exact bounded counters for configured accounts, aggregate unknown identities into bounded buckets, and retain the global suppressed-failure count.
    
    This belongs in the next code build, not solely in deployment guidance.
    
    R9-06 — CODE-CRITICAL — U2 does not distinguish a repaired checkpoint from the disappearance of a disagreeing checkpoint
    
    Status: Confirmed by static inspection.
    Classification: Security regression introduced by automatic fence clearance.
    
    Evidence:
    
    janus.py:2092–2122 — checkpoint loading establishes the set of checkpoints currently present in the local file.
    
    janus.py:2387–2392 — the anchor evaluation returns clean when no currently loaded, unaccepted checkpoint disagrees.
    
    janus.py:2174–2178 — the implementation explicitly recognizes removal of disagreeing checkpoints as a condition permitting clearance.
    
    janus.py:2183–2202 — the recorded mismatch is deleted and committed before the clearance entry is appended. An exception appending that entry is suppressed.
    
    Two distinct events are being treated as equivalent:
    
    Restoration of a chain that agrees with previously witnessed history.
    
    Disappearance of the checkpoint that established the disagreement.
    
    The second event is not evidence of the first.
    
    Furthermore, the fence-state transition and its audit evidence are not atomic.
    
    Required correction: Persist the identities of disagreeing checkpoints when the fence is established. Automatic clearance should require affirmative reconciliation against those checkpoints. Otherwise, require the existing two-key acceptance ceremony. Commit clearance and its audit entry together.
    
    R9-07 — CODE-CRITICAL — Evidence-export refusal still discloses protection-order status
    
    Status: Confirmed by static inspection.
    Classification: Surviving suppression-confidentiality defect.
    
    Evidence:
    
    janus.py:6297–6303 — detectives are permitted to request evidence exports.
    
    janus.py:6317–6323 — nonexistent hits receive a 404.
    
    janus.py:6330–6341 — suppressed hits receive a distinct 403 explicitly identifying protection-order suppression.
    
    janus.py:6344–6351 — unverified hits receive a separate 409.
    
    Compare this with janus.py:5149–5165, where hit verification intentionally conceals the distinction between suppressed and unavailable hits.
    
    The confidentiality principle applied to verification has not been applied consistently to evidence export.
    
    Required correction: Use a consistent, nonrevealing refusal for unavailable or inaccessible evidence, while retaining appropriately protected internal audit evidence.
    
    R9-08 — CODE-CRITICAL — Hold release remains permitted during an anchor disagreement
    
    Status: Confirmed by static inspection.
    Classification: Round 8 queued finding upheld.
    
    Evidence:
    
    janus.py:2144–2146 — hold release belongs to the anchor-fence safety set.
    
    janus.py:4353–4369 — safety-set operations proceed during an anchor mismatch.
    
    janus.py:5324–5329 — releasing a hold deactivates it.
    
    sentinel.py:724–741 — retention eligibility depends on whether a hit remains protected.
    
    sentinel.py:744–769 — corresponding reads inherit the hit's retention protection.
    
    Placing a hold and releasing a hold have opposite effects on evidence preservation. Their inclusion in the same safety category is incorrect.
    
    Required correction: Remove hold release from the anchor-fence exceptions. Preserve mandatory statutory deletion ceilings independently of the fence.
    
    R9-09 — CODE-CRITICAL — Protected-hit audit entries retain correlatable identifiers
    
    Status: Confirmed by static inspection.
    Classification: Round 8 queued finding upheld.
    
    Evidence:
    
    janus.py:4628–4629 — ALERT entries contain a hit identifier and camera identifier.
    
    janus.py:5160–5163 — BLOCKED verification entries contain the same hit identifier and an explicit suppression reason.
    
    janus.py:6335–6338 — evidence-export refusals retain the same association.
    
    janus.py:8429–8453 and 8463–8481 — authorized chain readers receive the audit entries, including the raw payloads necessary for independent verification.
    
    The protection-order confidentiality boundary is therefore narrower than the application-level suppression boundary.
    
    Required correction: Introduce domain-separated keyed references for sensitive denial records. Review other audit events carrying equivalent identifiers before declaring this correlation closed.
    
    Simply replacing the identifier everywhere with one deterministic pseudonym would not eliminate the correlation.
    
    R9-10 — MAJOR — Sink-divergence acceptance can report successful completion without verified backfill
    
    Status: Confirmed by static inspection; failure condition not executed.
    Classification: New U3 recovery-contract defect.
    
    Evidence:
    
    janus.py:4547–4553 — the acceptance is committed before sink resolution.
    
    sentinel.py:1974–1984 — the existing mirror is archived and its frontier reset.
    
    sentinel.py:1992–1995 — resolution invokes delivery and returns without verifying delivery success.
    
    sentinel.py:2015–2027 — delivery exceptions are caught and recorded rather than propagated.
    
    janus.py:4558–4563 — the endpoint reports that the divergence was resolved and the chain backfilled.
    
    Preserving undelivered obligations is good behavior for ordinary audit writes. It is not sufficient evidence that an explicit recovery ceremony completed.
    
    Required correction: Distinguish acceptance, archival, pending backfill, and verified completion. The API must not claim successful backfill until the corresponding delivery state establishes it.
    
    R9-11 — MAJOR — Sink archival does not guarantee unique archive names
    
    Status: Confirmed by static inspection; collision not executed.
    Classification: New U3 evidence-custody defect.
    
    Evidence: sentinel.py:1968–1974.
    
    The archive name uses a timestamp with one-second resolution and is installed using os.replace. The destination is not checked for prior existence.
    
    That does not establish the promised invariant that a diverged mirror is archived and never deleted: a destination collision can replace an earlier archive.
    
    Required correction: Use collision-resistant archive identifiers and a non-overwriting archival operation.
    
    R9-12 — MAJOR — Secret pickup has an incomplete transactional recovery contract
    
    Status: Confirmed by static inspection.
    Classification: U7 reliability and credential-custody residual.
    
    Evidence:
    
    janus.py:5703–5711 — the replacement API key is persisted.
    
    janus.py:5716–5721 — the in-memory key and TOTP store are then updated.
    
    janus.py:5723–5726 — the audit entries are appended and committed afterward.
    
    janus.py:5727–5733 — the replacement credentials are finally delivered in the HTTP response.
    
    The users file, second-factor store, audit transaction, and credential delivery constitute separate state transitions.
    
    A failure between those transitions can leave the account requiring administrative recovery without establishing the clean completion promised by the pickup operation.
    
    Required correction: Define and test an interrupted-pickup recovery protocol. Distinguish a pending rotation from a completed credential handover and make every intermediate state discoverable.
    
    R9-13 — MINOR — Authentication-flush markers also lack demonstrated lifecycle bounds
    
    Status: Confirmed within the inspected accounting function.
    Classification: Additional resource-accounting residual associated with R9-05.
    
    Evidence:
    
    janus.py:2872–2874 — independent dictionaries and a marker set are initialized.
    
    janus.py:2926–2927 — old failure-count buckets are removed.
    
    janus.py:2935–2937 and 2946–2948 — flush markers accumulate in a separate set.
    
    The pruning applied to failure-count buckets is not applied to these markers in the accounting routine.
    
    Required correction: Give all authentication-accounting structures an explicit lifecycle and enforce bounded storage.
    
    R9-14 — MINOR — Anchor signature memoization introduces a cache-capacity performance cliff
    
    Status: Confirmed by static inspection; large-cache performance not measured.
    Classification: U14 scaling residual.
    
    Evidence:
    
    janus.py:2294–2314 — successful and unsuccessful signature verdicts are memoized.
    
    janus.py:2311–2313 — exceeding the cache threshold clears the entire cache.
    
    janus.py:2339–2358 — each evaluation still iterates through the checkpoint collection.
    
    Memoization is a genuine improvement at the demonstrated 200-checkpoint scale. However, whole-cache eviction creates a discontinuity in performance once the checkpoint history grows beyond the cache's capacity.
    
    Required correction: Define an explicit checkpoint-history scaling policy and test performance around the eviction boundary. This is not independently deployment-blocking for the proposed pilot.
    
    2. Findings summary
    
    Deployment-blocking, non-code: 0
    Code-critical: 9
    Major: 3
    Minor: 2
    Total: 14
    
    The register includes both newly identified defects and surviving findings explicitly referred to this round. The classifications concern the implementation and its stated guarantees, not unresolved Arkansas legal questions.
    
    3. Mandatory named rulings
    
    §3.1 — U9 interpretation
    REJECT
    
    Populated arrival is not the right security boundary.
    
    The relevant question is whether an installation has completed the authorization and credential-enrollment ceremony required to operate on real plate data. Whether its database happened to be empty when Janus first opened it is not an adequate substitute.
    
    janus.py:2854–2866, 3211–3234, 3294–3297, and 4632–4640 establish the difference between the two interpretations.
    
    I would require three explicitly distinct operating states:
    
    Production provisioning: Administration, enrollment, health, narrowly defined safety operations
    Production operational: Normal authorized data operations
    Isolated test/demo: Synthetic fixtures and explicitly isolated test operations
    
    Legacy upgrades must complete provisioning before resuming production operations.
    
    What this breaks: The existing born-empty test fixtures, demonstrations using normal production semantics, and the unrestricted legacy-upgrade workflow. The builder correctly identified that incompatibility.
    
    My disagreement is with the conclusion drawn from it. The test harness should accommodate the security requirement, rather than the production security requirement accommodating the test harness.
    
    The U9 discriminating test at tests/run_u126_cases.py:731–758 is valid evidence for the implemented interpretation. It is not evidence that the interpretation should be ratified.
    
    §3.2 — Queued smalls
    
    (i) Remove hold release from fence safety set — FIX-NOW — R9-08
    (ii) Bound authentication failure totals — FIX-NOW — R9-05, R9-13
    (iii) Keyed references in BLOCKED entries — FIX-NOW — R9-09
    (iv) Fence data during the T1 ceremony — FIX-NOW — R9-03
    (v) 24-hour pickup expiry — FIX-NOW — already implemented — Retain and regression-test
    (vi) Shell-operator honesty gap — CANT-DO — Document the trust boundary
    
    Item (i): Holding evidence preserves the option to investigate an integrity incident. Releasing evidence protection can eliminate that option. The distinction is established at janus.py:2144–2146, 5324–5329, and sentinel.py:724–741.
    
    Item (ii): A global audit-writing cap is insufficient without a corresponding memory bound. See janus.py:2913–2924 and 3124–3127.
    
    Item (iii): Raw hit identifiers permit correlation between ordinary alert events and sensitive refusal events. See janus.py:4628–4629, 5160–5163, and 6335–6338. A suitable correction must preserve independent audit verification without unnecessarily preserving that relationship.
    
    Item (iv): This is substantially the same architectural defect as U9. It should be implemented as one coherent provisioning-state policy, not as another collection of independently maintained endpoint exceptions.
    
    Item (v): The requested 24-hour validity limit already exists in this build.
    
    janus.py:5559–5566 records the enrollment timestamp and token hash.
    
    janus.py:5644–5659 validates the token and applies the 24-hour limit.
    
    janus.py:5718–5721 consumes the token after pickup.
    
    I classify it FIX-NOW because I consider the property mandatory, but its basic implementation is already present. No duplicate implementation is warranted. An explicit expiry regression should establish that the time boundary holds.
    
    Item (vi): The proposed CANT-DO disposition is appropriate.
    
    scripts/provision.py:438–464 establishes that the shell enrollment tool verifies the confirmer's code using the confirmer's stored TOTP secret.
    
    A trusted host administrator with access to those secrets is outside the independence guarantee of that ceremony. The implementation can establish that a valid code was presented; it cannot independently establish which human presented it.
    
    The documentation should say exactly that. Actual independence from the host administrator would require a different credential-custody architecture.
    
    §3.3 — S10 null-tolerance
    ACCEPT WITH CONDITIONS
    
    Accept the single retry as a test-only correction to the freshness-property test. Do not accept it as evidence that the dropped health response is irrelevant to operational availability.
    
    Evidence: tests/run_s124_cases.py:1316–1352.
    
    The test is intended to establish that a stale successful verification result is not returned after the freshness deadline under contention. At lines 1345–1352, it instead combines two properties:
    
    Every health request returns a usable sample.
    
    Every returned verification verdict is false after the tampering event.
    
    Those properties should be evaluated separately.
    
    I would permit one bounded retry of a missing sample, subject to these requirements: retain the original failed observation in the test output, never retry away a returned incorrect chain_ok=True verdict, fail if the retry also returns no usable observation, and report availability separately under the same load envelope.
    
    The reported evidence supports a distinction between freshness and availability. It does not establish the stronger claim that the missing response is definitely a harness artifact rather than an operational availability limitation.
    
    The submitted full-battery result should continue to be described as 24/25 in the full S run, with S10 passing standalone, until the revised test passes under the full-battery conditions.
    
    §3.4 — R-F adaptations and standing process
    RATIFY WITH SCOPE LIMIT
    
    I inspected the complete supplied 08-rf-diffs.txt.
    
    The attachment contains thirteen adapted seat files. The displayed changes fall into three classes:
    
    Detective-to-supervisor hot-list setup — Accept for the existing downstream test properties
    Signing-key lookup relocated to escrow — Accept
    Conditional removal of keys no longer included in backup sets — Accept
    
    Relevant diff evidence, using attachment line numbers:
    
    08-rf-diffs.txt:13–35 — hot-list setup identity changes.
    08-rf-diffs.txt:63–81 — signing-key custody adaptation.
    08-rf-diffs.txt:181–217 — hot-list expiry scenario adaptations.
    08-rf-diffs.txt:281–298 — conditional key removal.
    08-rf-diffs.txt:318–334 — final adapted preauthentication-race scenario.
    
    I found no changed assertion statements in the supplied diff hunks.
    
    There is nevertheless an important distinction between assertion preservation and scenario preservation. Changing the actor from detective to supervisor changes the authorization context even where the assertion remains identical.
    
    For downstream tests that merely need an established active membership, that adaptation is reasonable. It does not establish correctness of the new detective-submission path.
    
    R9-02 illustrates precisely why independent testing of the commissioned replacement path matters.
    
    I ratify the standing practice on these conditions:
    
    Preserve the original seat test.
    Attach the complete diff.
    Identify the commissioned change requiring the adaptation.
    Preserve the original assertion and its intended property.
    Add discriminating coverage for the new behavior where the adaptation changes the authorization context.
    
    Verification limit: I can attest to the supplied diff contents. The attachment pack does not independently establish the completeness or provenance of every preserved original in the builder's filesystem.
    
    §3.5 — U6 validation order
    RATIFY ORDER ONLY
    
    The shipped order is acceptable for the intended immediate HTTP-response confidentiality property:
    
    registry → supervisor suppression refusal → category/expiry → role split
    
    Evidence: janus.py:4964–4997, 5037–5058.
    
    Supervisor / Detective outcomes:
    Unknown list: 400 / 400
    Protected plate with otherwise valid submission: 403 / 202
    Unprotected plate with otherwise valid submission: 201 / 202
    Invalid category or expiry: Validation refusal, unless suppressed first / Validation refusal
    
    For non-supervisors, the list-registry check no longer reveals suppression status. Category and expiry validation are also independent of whether the plate is protected.
    
    For supervisors, the suppression refusal is intentionally informative and lies within their designated authority.
    
    However, this ruling does not ratify U6 as a complete confidentiality or authorization solution:
    
    R9-02 establishes that the submission path can modify existing approved state.
    
    janus.py:5037–5040 establishes that a suppression conflict is recorded conditionally in the audit chain.
    
    R9-09 establishes the broader distinction between application-level confidentiality and audit-payload confidentiality.
    
    The validation ordering itself is acceptable. The membership-state implementation is not.
    
    4. U1–U14 implementation assessment
    
    U1 — Lockout scope: Incomplete. Separate pickup authentication retains incorrect failure accounting.
    U2 — Fence exit: Incomplete. Clearance does not establish reconciliation with previously disagreeing checkpoints.
    U3 — Sink divergence: Partial. Recovery and memoization exist; completion and archive uniqueness need correction.
    U4 — Confidence validation: Confirmed in inspected code. Finite-range validation at janus.py:4716; superseded status and disposition at 4869–4882, 5138–5141, 5167–5174.
    U5 — Demo containment: Normal-path implementation confirmed. Provisioned-install startup refusal at janus.py:9186–9202. Broader production/demo separation depends on U9.
    U6 — Hot-list uniformity: Incomplete. Approved membership can be modified through the pending submission path.
    U7 — Pickup hardening: Partial. Token, age check, and matched-count guard implemented at janus.py:5642–5659, 5677–5702; transactional recovery remains incomplete.
    U8 — Sink-status proof: Reported passing; partially inspected. Dedicated fault-injection test identified. No independent execution.
    U9 — Unprovisioned tightening: Interpretation rejected.
    U10 — Escrow placement: Guard confirmed. Canonical-path comparison in scripts/backup.py:165–178.
    U11 — Smalls: Partially verified. Unique TOTP temporary file confirmed at janus.py:2625–2643; supplied R-F adaptations ratified within stated limits. Other smalls not individually certified.
    U12 — Sink tail reconciliation: Implementation present. Torn-tail handling and divergence distinctions at sentinel.py:2046–2077; exhaustive reconciliation correctness not established by this seat.
    U13 — Restore custody and R-A: Incomplete. Snapshot-key custody is implemented; failure handling does not guarantee the provisioning ratchet.
    U14 — Anchor evaluation cost: Improvement confirmed structurally. Signature cache at janus.py:2291–2314; large-history eviction residual remains.
    
    The strongest evidence in favor of 1.2.6 is that numerous commissioned mechanisms are genuinely present in the source. The defects in this register are not a claim that the builder merely documented fixes without writing them.
    
    They are a claim that several of the implemented mechanisms do not yet enforce their complete intended invariants.
    
    5. Convergence vote
    
    Each convergence criterion is scored as one point, awarded only when satisfied.
    
    1 / 4
    NOT CONVERGED
    
    1. No critical code findings — FAIL
    2. Prior forced changes resolved — PASS
    3. Residuals appropriately documented or routed — FAIL
    4. Orchestrator retests pass — FAIL
    
    Criterion 1 — No surviving deployment-blocking or critical code finding
    FAIL — 0/1.
    R9-01 through R9-09 establish surviving critical code concerns affecting authentication availability, approval authority, provisioning, restore integrity, anchor integrity, confidentiality, and evidence preservation.
    Even if every major and minor finding were waived, this criterion would fail.
    
    Criterion 2 — Every forced change implemented or answered in writing
    PASS — 1/1, procedural interpretation.
    The submitted build report addresses the commissioned changes and explicitly discloses the U9 interpretation.
    The criterion permits a written answer as an alternative to implementation. I therefore award the procedural point without treating an answered item as necessarily resolved.
    Rejection of an implementation or interpretation remains grounds for failure under Criterion 1.
    
    Criterion 3 — Remaining issues are documented CANT-DO limits or appropriately routed legal questions
    FAIL — 0/1.
    Several remaining issues are correctable implementation defects. They are not inherent limitations of municipal ALPR systems, unavoidable consequences of the declared threat model, or questions requiring legal interpretation.
    I accept the brief's account of the ACIC responses and outstanding administrative and legal tracks for purposes of this review. None is the basis of my negative vote.
    
    Criterion 4 — Orchestrator's own retests pass
    FAIL — 0/1, strict full-battery interpretation.
    The verification report discloses that the orchestrator's full S runs returned 24/25, with standalone S10 reruns passing.
    That is substantially stronger evidence than an unexplained intermittent failure, and the evidence favors the underlying freshness property. Nevertheless, the unchanged full-battery test has not passed in the reported saturated execution.
    I would award this point once the separately recorded freshness and availability observations satisfy the ratified test contract.
    This is a test-accounting disagreement, not an allegation that the orchestrator concealed a failure.
    
    6. Single forced change
    
    Replace the born-empty provisioning exemption with an explicit, fail-closed production authorization state.
    
    The price of this seat's vote is a production operating boundary that does not depend on whether the database existed when Janus first imported it.
    
    The acceptance contract must establish that:
    
    An unprovisioned production installation cannot ingest or disclose operational plate data.
    First-boot enrollment and necessary administrative operations remain reachable.
    Restarts, restores, database relocation, and legacy upgrades do not silently relax that boundary.
    Unknown provisioning state fails closed.
    Test and demonstration fixtures operate within an explicitly isolated test/demo environment.
    
    The central evidence requiring this change is janus.py:2854–2866, 3211–3234, 3294–3297, and 4632–4640.
    
    This is the single change that would most alter my vote because it addresses the architectural relationship between U9, T1, U5, and the U13 provisioning ratchet.
    
    Its completion is necessary, not sufficient, for convergence. Other surviving critical findings must still be resolved.
    
    7. Coverage and evidence limitations
    
    01 — Council brief: Read in full
    02 — Janus: Targeted source inspection across authentication, provisioning, anchor evaluation, hot-list submission, pickup, restore consumption, suppression, evidence, and dispatch
    03 — Sentinel: Targeted inspection of sink reconciliation, archival, delivery, retention eligibility, and audit-related behavior
    04 — Operational scripts: Targeted inspection, particularly restore, backup, and enrollment
    05 — Documentation: Sampled; not comprehensively reconciled
    06 — Test suites: Targeted inspection of U-series coverage and S10
    07 — Build and verification reports: Relevant dispositions, judgment calls, and verification sections inspected
    08 — R-F diffs: Read in full
    
    I did not perform a comprehensive line-by-line audit of every source file. Compact rotation, Tier 3 execution, the complete retention registry, the bridge, and all historical attack scenarios were not independently re-audited in full.
    
    No service was started, no attack was executed, and no external repository was accessed. All findings are static conclusions from the attached build. Fault-dependent consequences have been identified as such.
    
    The handoff required by the brief is available here:
    
    HANDOFF.md — Round 9 ChatGPT seat
    
    Final council disposition
    
    NOCTUA 1.2.6: NOT CONVERGED
    
    Convergence score: 1/4.
    
    U9 interpretation: REJECT.
    
    R-F process: RATIFY, with scope limitations.
    
    U6 validation order: RATIFY; implementation remains defective.
    
    S10 harness correction: ACCEPT WITH CONDITIONS.
    
    Single forced change: Explicit fail-closed production provisioning boundary.
    
    NOCTUA 1.2.6 demonstrates meaningful progress. Its remaining problem is that individual mechanisms have been hardened without always enforcing their intended guarantees across every entry point and state transition.
    
    Convergence requires those guarantees to be properties of the system, not merely properties of the scenarios that passed its battery.
