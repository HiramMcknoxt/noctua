# Round 10 — ChatGPT seat review (as returned)

- Chat: https://chatgpt.com/c/6b085559-b9e4-83e8-a2c4-2b33e706d99c ("Code Gate Review")
- Model/effort, operator-observed in the UI: GPT-6.2; Thinking effort: High (strongest model offered; Thinking selector "High", 3 of 3). The seat's own text says the UI setting was not independently visible to it — the operator's UI observation governs.
- Method: static anchored code review; no execution. Vote: NOT CONVERGED, expressly "subject to executing-seat reproduction" for its two blocking findings (R10-C01, R10-C02).

---

# NOCTUA Council Round 10 — ChatGPT Seat

Build: NOCTUA 1.2.7 (janus127/)
Model: GPT-6.2
Interface-reported model and effort: Not independently visible to this seat; I cannot transcribe the UI setting verbatim.
Method: Independent, anchored static code review.
Scope: Attached 1.2.7 materials exclusively.

## 1. Executive findings

# NOT CONVERGED

Static seat verdict — subject to executing-seat reproduction

Convergence criteria passed: 1 / 4
Deployment-blocking findings: 2
Orchestrator's V battery: 19 / 19
Previous-build discrimination: 0 / 19

Principal objections

- R10-C01: The ceremony fence leaves historical plate-data disclosure in a safety-write response.
- R10-C02: The anchor fence does not promote an existing file-state mismatch to a subsequently discovered checkpoint disagreement.

The two principal findings are adjacent-shape defects of precisely the kind Round 9 instructed this seat to test for.

I accept the orchestrator's cold verification record. I do not dispute the reported battery results.

## 2. Deployment-blocking findings

### R10-C01 — The ceremony fence protects routes, not all disclosure within those routes

DEPLOYMENT-BLOCKING V4 — REOPENED

The redesigned ceremony state correctly closes the ordinary human data endpoints. However, the permitted safety-write path can still return information derived from the historical plate record.

Code evidence:

| Source anchor | Established behavior |
|---|---|
| janus.py:3384–3407 | The ceremony fence enumerates routes. Suppression placement and hold placement are not included. |
| janus.py:3493–3497 | Authentication permits key-only humans before provisioning. |
| janus.py:4553–4570 | The POST dispatcher applies the enumerated ceremony fence. |
| janus.py:5561–5567 | Suppression placement requires a supervisor, but adds no independent second-factor condition. |
| janus.py:5615–5627 | Suppression placement queries historical reads.plate_raw and returns matching historical variants in warning_near_matches. |
| janus.py:5453–5462 | Hit-hold placement distinguishes nonexistent hits from existing hits and can disclose the existing hit's status. |

Why this matters:

A safety write is permitted during the ceremony because it protects people or preserves evidence. The suppression-placement handler crosses that boundary. Its response contains information obtained from the historical plate record before any new suppression exists. The hold handler independently demonstrates the same architectural distinction: a permitted write can return information about an existing hit.

Required invariant:

During CEREMONY, permitted safety writes may change protective state and return an acknowledgment, but they must not disclose historical read-derived information or existing-hit identity.

Executing-seat acceptance checks:

Using synthetic records, verify that suppression placement still succeeds during CEREMONY but returns no warning_near_matches, and that hold placement still succeeds without disclosing whether the target hit exists.

Disposition:

This reopens V4 on static evidence. Under §3.4, the U9 adjudication itself reopens if an executing seat confirms the disclosure in a live response.

### R10-C02 — V5's reason gate does not account for changing mismatch reasons

DEPLOYMENT-BLOCKING V5 — REOPENED

The V5 fix correctly makes a recorded checkpoint_disagreement sticky. The problem is that the recorded reason need not represent the most serious mismatch subsequently discovered.

Code evidence:

| Source anchor | Established behavior |
|---|---|
| janus.py:2204–2206 | File-state mismatch reasons are eligible for automatic clearance. |
| janus.py:2244–2263 | Automatic clearance is governed by the previously recorded reason and its recorded bad_ids. |
| janus.py:2283–2293 | A newly evaluated mismatch is persisted only when no mismatch is already recorded. |
| janus.py:2302–2308 | Live evaluation invokes _anchor_apply, but the dispatch decision ultimately uses the persisted mismatch flag. |
| janus.py:2460–2481 | The evaluator identifies genuine checkpoint disagreements and their checkpoint identities. |

There is no corresponding transition that promotes an already-recorded file-state mismatch to checkpoint_disagreement when later evaluation establishes a genuine historical disagreement.

Consequently, the reason controlling automatic clearance can remain a stale file-state reason even after a checkpoint disagreement is established.

The commissioned V5 case establishes the behavior when checkpoint_disagreement is the original recorded reason. It does not establish the behavior when a disagreement arises during an existing file-state fence.

Required invariant:

Once an unaccepted historical checkpoint disagreement has been observed, a later clean file evaluation must not clear the fence.

Executing-seat acceptance check:

Exercise successive synthetic evaluations covering file-state damage, historical disagreement and a clean file state, and confirm that the anchor fence remains in place until the disagreement is accepted.

Disposition:

The direct Round 9 repair holds. The adjacent reason-transition defect reopens V5.

## 3. Primary assignment — anchored verification

### V5 — Fence reason gate and append-before-mutate

REOPENED — partial confirmation.

The following commissioned mechanisms are implemented:

- The eligible file-state reasons are explicitly enumerated at janus.py:2204–2206.
- The historical disagreement branch checks recorded bad_ids against accepted identities at janus.py:2253–2261.
- The clear entry is appended before deleting the metadata flag at janus.py:2264–2275.
- The initial set entry is appended before writing mismatch metadata at janus.py:2283–2293.

The prior unlogged-clear defect is addressed by the new ordering.

However, three qualifications remain:

1. Reason promotion is missing. R10-C02 above.
2. The identity set is truncated. janus.py:2476 retains only the first 50 disagreeing checkpoint identities. That is not literally the complete set of disagreeing checkpoints.
3. Append-before-mutate is not strictly transactional atomicity. At janus.py:2285–2293, an append failure prevents recording the mismatch. At janus.py:2308, the fence decision nevertheless depends on the recorded flag. The chair should verify the fail-closed behavior of the append path.

The third qualification is independently important: preventing an unlogged security transition must not depend on the same append that records it.

Recommended repair:

Implement a monotonic anchor-fence state machine, preserving unresolved disagreement identities and refusing automatic clearance while any unaccepted checkpoint disagreement remains recorded.

### V6 — Restore tri-state

CONFIRMED FIXED — commissioned failure shape.

| Anchor | Verification |
|---|---|
| scripts/restore.py:435–452 | Clean absence is distinguished from an exception; exceptions produce "unknown". |
| scripts/restore.py:442–450 | The outgoing database is opened using a normal connection, allowing SQLite recovery rather than deliberately failing on a corrupt header. |
| scripts/restore.py:555–562 | The outgoing state is serialized into the restore marker. |
| janus.py:2534–2541 | Legacy booleans and tri-state strings are mapped; anything else becomes unknown. |
| janus.py:2586–2608 | Provisioned or unknown outgoing state triggers re-enrollment and materialization of missing human entries. |
| janus.py:2609–2612 | Provisioning state is marked in the restored database. |

The original V6 fallback is closed.

Two additional restore-hardening observations belong in the register: valid-JSON non-object restore markers fail at .get(), and failures inside the re-enrollment block are swallowed before marker removal (janus.py:2519–2534, 2613–2618). These are distinct from the commissioned tri-state repair.

### V9 — Anchor-fence safety set

CONFIRMED FIXED.

The actual set at janus.py:2173–2182 is:

```python
ANCHOR_FENCE_SAFETY_POST = {
    "/reads", "/suppressions", "/holds"
}
```

Neither /holds/release nor /suppressions/release appears in the safety set or the recovery exemption set (janus.py:2166–2172).

The dispatch consequence is established at janus.py:4571–4587: a non-exempt POST must either qualify as a safety write or receive 503 during an anchor mismatch.

Both releases therefore wait behind the fence.

I distinguish this from the subsequent stale-configuration checks at janus.py:4588–4605, which are addressed under G5(iii).

### V10 — Keyed hit references in BLOCKED entries

CONFIRMED FIXED.

hit_ref() at janus.py:751–768 produces a domain-separated, keyed HMAC reference using SHA-256, truncated to 16 hexadecimal characters.

I inspected the BLOCKED call sites throughout the supplied janus.py, including an AST-assisted inventory of those containing hit-related arguments. (12 sites enumerated in the original: verify case refusal, verify hit not pending, verify suppressed queue, evidence export case refusal, evidence export nonexistent hit, evidence export suppression, evidence export unverified hit, evidence export case mismatch, evidence export expansion refusal, evidence release, evidence destruction, disposition confirmation — all keyed references.)

No raw hit identifier survives in the inspected BLOCKED payloads.

The commissioned extension is implemented. Raw identifiers in successful custody entries remain deliberately out of scope.

This is not a claim that keyed references eliminate every possible correlation across an audit record.

### V13 — Uniform evidence refusals

CONFIRMED FIXED.

For non-supervisors, the following three conditions now produce the same status and response body:

| Condition | Source anchor |
|---|---|
| Nonexistent hit | janus.py:6588–6596 |
| Suppressed hit | janus.py:6606–6615 |
| Unverified hit | janus.py:6618–6625 |

All three return HTTP 409: {"error":"hit not found or already decided"}

The distinct reasons remain inside the chained BLOCKED records, using V10's keyed references.

The supervisor distinction is preserved by uniform = not role_is(rec, "supervisor") at janus.py:6582, the separate nonexistent-hit response at line 6597, and the status-specific response at lines 6626–6628.

Qualification: This verifies response-code and body uniformity, not constant-time execution. I find no basis to claim a timing side channel is closed.

### V15 — Small fixes

PARTIAL CONFIRMATION — one code sub-item reopened.

| Sub-item | Ruling | Source evidence |
|---|---|---|
| Collision-resistant sink archives | CONFIRMED FIXED | sentinel.py:1963–1976, 1999–2006, 2079 |
| Bounded stranded-sequence summaries | CONFIRMED FIXED | sentinel.py:1255–1273, 1803–1808, 2444–2447; janus.py:4770–4773 |
| Thirty-day pending expiry | REOPENED in part | janus.py:3410–3437, 5154, 5303, 8875 |
| Expired approval refusal | CONFIRMED FIXED | janus.py:5301–5315 |
| Paired escrow pruning | CONFIRMED FIXED for ordinary paired sets | scripts/backup.py:337–387 |
| Non-object checkpoint tail | CONFIRMED FIXED | scripts/checkpoint.py:107–137 |
| COMPACT version correction | CONFIRMED FIXED | COMPACT.md:5–6 |
| Audit tool version | CONFIRMED FIXED | scripts/sentinel_audit.py:487 |
| Migration stamp field | CONFIRMED FIXED | janus.py:1553, 1874, 1902 |
| Enrollment CANT-DO | CONFIRMED FIXED | docs/CANT-DO.md:26 |
| Signing-disabled comment | Present; not fully adjudicated | janus.py:2117, surrounding signing initialization |
| Historical .orig-124 header | Not independently verified | Original historical file not included as a standalone source in the pack |

Pending-expiry qualification: _expire_pending_submissions() is called on submission, decision and queue-read paths. The supplied code does not establish an unconditional timer or a queue-independent sweeper. An untouched pending queue can therefore retain an over-age submission until one of those paths runs.

Escrow qualification: The ordinary paired-set case holds. The pruned_stamps alternative at scripts/backup.py:382–384 deserves a companion test where an exact-name set is pruned while a separately retained, suffixed set remains.

Neither V15 residual independently determines my vote under the final-gate scope discipline.

## 4. Remaining V-item rulings

| Item | Ruling | Anchored evidence |
|---|---|---|
| V1 — Pickup lockout | CONFIRMED FIXED | Verified-key guard inside the counter at janus.py:3196–3221; uniform refusal and no wrong-key count at 5844–5863. |
| V2 — Live-row collision | CONFIRMED FIXED | Conflict update constrained by WHERE hotlist_members.pending=1 at janus.py:5266–5276; uniform response at 5277–5284. |
| V3 — Sink tail truncation | CONFIRMED FIXED | Classification at sentinel.py:1924–1961; mid-file-damage refusal and tail re-derivation at 2174–2198. |
| V4 — Ceremony state | REOPENED | Ordinary dispatcher fencing is present, but permitted safety-write responses retain disclosure at janus.py:5453–5462, 5615–5627. |
| V7 — Pre-restore registry | CONFIRMED FIXED | Unified <db>*.pre-restore-* pattern at sentinel.py:483–493. |
| V8 — Failure accounting | CONFIRMED FIXED | Unknown-name buckets at janus.py:2982–2997; stale-marker removal at 3016–3024. |
| V11 — Pickup expiry and counting | CONFIRMED FIXED | Secret-bearing entry deleted at janus.py:5892–5905; counting rules at 3316–3347. |
| V12 — Unique temp paths | CONFIRMED FIXED | Unique PID/random suffix and replacement at janus.py:5954–5967, scripts/provision.py:73–81. |
| V14 — Legacy probe | CONFIRMED FIXED | Replacement ceremony predicate at janus.py:3350–3371; previous provisioning gate removed from authentication at 3481–3497. |
| V16 — Unreadable sink | CONFIRMED FIXED for nonempty committed chains | All committed sequences selected at sentinel.py:2041–2055, divergence result at 2056–2059. |
| V17 — Out-of-lock persistence | CONFIRMED FIXED | _auth_locked() performs only the in-memory removal at janus.py:3175–3193. |
| V18 — Compact TOTP separation | CONFIRMED FIXED | Separate defaults at scripts/compact.py:95–98, conditional header at 102–115, machine receipt without TOTP at 395, auditor secret at 410–414. |

V2's confirmation is specifically about protecting the existing live row from a non-supervisor submission. It does not establish the inactive-row submission semantics examined under G1.

V8 likewise closes the unbounded arbitrary-username spray mechanism. It does not establish that counting is immune to every possible adversarial interaction with the database.

## 5. Queued Gemini findings

### G1 — Submission collision with an inactive row

VERIFIED — medium severity.

janus.py:5266–5276 permits conflict updates only where the existing row has pending=1. An inactive, nonpending row does not satisfy that predicate. Nevertheless, janus.py:5277–5284 records the submission event and returns the same 202 acknowledgment. The queue decision path selects pending=1 at janus.py:5309–5315. The live-row protection is correct, but the inactive-row submission remains silently unqueued.

Register: Separate the acknowledgment's privacy requirement from durable submission semantics.

### G2 — Pending retention and expiration semantics

VERIFIED — surviving in a changed shape.

- janus.py:5267–5269 creates pending submissions with active=1.
- scripts/retention.py:225–229 purges inactive rows.
- scripts/hotlist_sync.py:86–109 selects expired active memberships without excluding pending entries, and chains HOTLIST_EXPIRED.

V15 introduces an additional age-based cleanup path at janus.py:3413–3437, but that path is demand-driven. Consequently, the new mechanism partially mitigates pending retention without fully separating pending membership from expiry and retention handling.

Severity: Medium. Post-convergence register.

### G3 — Pickup configuration reload

VERIFIED — medium severity.

Ordinary authentication explicitly invokes _reload_config() at janus.py:3459. Pickup is routed directly to its self-authenticating handler before ordinary authentication at janus.py:4540–4544. The handler consults the in-memory USERS record at janus.py:5833–5854. Later, the file rewrite updates the matching entry's key hash at 5924–5932, without repeating the original authentication decision against that file entry. The V12 unique-temp repair does not address freshness of the authorization decision.

Required repair: Make the pickup authorization and users-file mutation operate on a consistent, current account record.

### G4 — Rotation verification version trap

VERIFIED as a latent defect; REFUTED as a current 1.2.7 publication incompatibility.

The accepted prefix list remains exactly ("1.2.2", "1.2.3", "1.2.4", "1.2.5") at scripts/rotation.py:228 and :277. Documents outside that list follow legacy verification branches at 229–239 and 277–282. However, the shipped producer still emits schedule version "1.2.5" at janus.py:8206–8211; the standalone builder likewise uses "1.2.5" at scripts/rotation.py:127. Therefore NOCTUA 1.2.7 does not currently publish an incompatible schedule merely because the service reports version 1.2.7. The defect is a future compatibility trap caused by brittle prefix-based schema discrimination.

Severity: Low currently. Do not mechanically change the emitted schedule version without updating verification to accept it.

### G5 — Five-part register

| Item | Ruling | Evidence and disposition |
|---|---|---|
| (i) Reverse escrow nesting | STILL OPEN — medium | scripts/backup.py:169–180 refuses escrow inside backup, but does not refuse backup inside escrow. Custody-root separation is incomplete. |
| (ii) Disabled enrollment parity | STILL OPEN — medium | scripts/provision.py:383–398 validates existence and human role but does not reject a disabled target. Active-enrollment confirmation at 429–445 also warrants disabled-account parity checking. |
| (iii) Stale configuration blocks anchor-exempt recovery | STILL OPEN — medium | janus.py:2166–2172 identifies recovery exemptions, but 4595–4605 independently exempts only heartbeat and anchor acceptance from the general stale-config check. |
| (iv) Restore fallback | CLOSED BY V6 | scripts/restore.py:435–452, janus.py:2534–2541. Unknown no longer means never provisioned. |
| (v) Unpruned flushed markers | CLOSED BY V8 | janus.py:3023–3024 explicitly discards sufficiently old bucket markers. |

G5(iii) should receive a cause-aware recovery rule. A stale case feed and an untrustworthy users file should not receive identical recovery treatment.

## 6. Ceremony-state adjudication

What held: ceremony is derived from provisioning state rather than arrival history (janus.py:3350–3371); POST, GET and DELETE dispatchers independently enforce ceremony fencing (4553–4570, 8704–8715, 8556–8569); provisioned installs ordinarily require a valid second factor (3493–3513); LAB startup is rejected on provisioned installations (9527–9556); LAB does not itself disable _totp_required() — the separate DEMO waiver does (2883–2893); the installation checklist explicitly requires active enrollment before cameras connect.

What broke: R10-C01 — the route allowlist does not enforce the full intended disclosure boundary. The issue is not that suppression placement remains available (it must); it is the information returned in its response. The hold-placement response is another instance of the same distinction.

LAB lifecycle: no evidence that provisioning during LAB automatically waives second-factor authentication (anchors janus.py:3369–3371, 2883–2893, 3493–3513). The absence of a runtime LAB flag transition remains an operational concern, not classified deployment-blocking on the evidence supplied.

Diagnostic surface: /stats remains open to eligible key-only humans in CEREMONY, returning aggregate counts (janus.py:4263–4282 via 8911–8916). Aggregate counts are materially different from historical plate strings; not classified deployment-blocking.

Ceremony ruling: REOPENED, pending executing-seat confirmation of R10-C01.

## 7. Builder judgment calls

| No. | Ruling | Reason |
|---|---|---|
| 1 | OBJECT IN PART | The extended fence is appropriate, but the safety-write responses are not uniformly nondisclosing. janus.py:3384–3407, 5453–5462, 5615–5627. |
| 2 | RATIFY | Declared LAB fixtures may remain operational without being mistaken for production. Boot refusal on provisioned installations at janus.py:9527–9556. |
| 3 | RATIFY | The S10 retry is conditional on the full-battery context. tests/run_s124_cases.py:1411–1436. |
| 4 | RATIFY | Saturation availability is properly distinguished from the integrity and delivery gate. |
| 5 | RATIFY | V10's extension removes additional refusal identifiers consistently. Custody identifiers remain outside the commissioned V10 scope. |
| 6 | RATIFY | Supervisor-specific evidence refusals are preserved deliberately at janus.py:6582–6628. |
| 7 | RATIFY | Bounded permanent records and a full operator-facing divergence response are defensibly distinct. sentinel.py:1258–1273; janus.py:4770–4788. |
| 8 | RATIFY WITH LIMITATION | Source verification establishes unique temporary paths; it does not establish the absence of all concurrent-pickup failure modes. janus.py:5958–5967. |
| 9 | RATIFY | Seeding stale markers is a legitimate way to exercise the production cleanup predicate. tests/run_v127_cases.py:664–684; janus.py:3023–3024. |
| 10 | RATIFY | Missing outgoing state must mean unknown, not never provisioned. janus.py:2534–2541. |
| 11 | RATIFY | The legacy fallback is a reasonable compatibility measure, provided explicit per-side secrets are present. scripts/compact.py:95–98, 216–225. |

Judgment calls: Ten ratified, some with limitations; one objection in part.

## 8. Post-convergence register (seat's R10-R01..R11)

| ID | Severity | Residual | Evidence |
|---|---|---|---|
| R10-R01 | Medium | Inactive-row submissions silently unqueued | janus.py:5266–5284 |
| R10-R02 | Medium | Pending membership retention and expiry classification | janus.py:3413–3437; scripts/hotlist_sync.py:86–109 |
| R10-R03 | Medium | Pickup authorization freshness | janus.py:5833–5854, 5924–5932 |
| R10-R04 | Low | Rotation schema-version compatibility trap | scripts/rotation.py:228, 277 |
| R10-R05 | Medium | Reverse escrow-root nesting | scripts/backup.py:169–180 |
| R10-R06 | Medium | Disabled-account shell-enrollment parity | scripts/provision.py:383–398 |
| R10-R07 | Medium | Recovery POSTs blocked by independent configuration fence | janus.py:4595–4605 |
| R10-R08 | Medium | Restore marker non-object handling and failure consumption | janus.py:2519–2534, 2613–2618 |
| R10-R09 | Medium | Pending expiry depends on queue activity | janus.py:3413–3437, 5154, 5303, 8875 |
| R10-R10 | Low–medium | Suffixed escrow pairing edge | scripts/backup.py:379–384 |
| R10-R11 | Medium | Recorded checkpoint identity list limited to 50 | janus.py:2476 |

The chair should not interpret this register as a commission for another general hardening round. It records only targeted residual risk.

## 9. Four convergence criteria

Criterion 1 — FAIL: R10-C01 and R10-C02 establish unresolved code-level security invariants, pending execution by the chair's executing seat.
Criterion 2 — FAIL: V4 and V5 are implemented in their direct commissioned shapes but remain incomplete at their adjacent boundary conditions.
Criterion 3 — FAIL: The principal remaining objections concern enforceable software behavior, not accepted CANT-DO limitations or unresolved City Attorney questions.
Criterion 4 — PASS: Accepted. The supplied cold one-shot verification reports exit 0, full battery success and 19/19 V cases.

Score: 1/4. No additional convergence criterion is imposed. Outstanding City Attorney answers are deployment and legal dependencies, not code-convergence failures.

## 10. Single forced change

Make the CEREMONY boundary a nondisclosure invariant, rather than merely an endpoint allowlist. The implementation must preserve the ability to place protection orders and holds while preventing known historical plate strings or existing-hit details from appearing in any ceremony response. The acceptance battery must include response-content assertions for permitted safety writes, not merely route-availability assertions. This is the single change whose verified completion would most materially alter my vote. It would not by itself close R10-C02.

## 11. Coverage and handoff

Static inspection and AST-assisted call-site enumeration. Did not independently execute the service or rerun the acceptance battery. Historical .orig-124 header not independently verified. Line numbers are original source-file line numbers.

Seat's attached HANDOFF.md (verbatim in the browser report): static vote NOT CONVERGED, chair reproduction pending; next step — executing seat should validate that ceremony safety-write responses disclose no historical read-derived strings or case data, and that an anchor disagreement observed during an existing file-state fence cannot be automatically cleared; synthetic fixtures only.

## 12. Final vote

Vote: NOT CONVERGED. Convergence score: 1/4. Model: GPT-6.2 (UI-observed by operator with Thinking effort High; the seat's own text records the UI setting as not independently observable to it).
