# Council Round 9 — Synthesis (chair: Vesper)

**Subject:** NOCTUA 1.2.6 (`janus126/`). **Date:** Nov 25, 2026.
**Verdict: NOT CONVERGED** — unanimous across the six seats seated and returned, on code grounds only. The commission for 1.2.7 is §6.

## 1. The seats

| Seat | Model / effort (interface-observed) | Method | Vote | U9 |
|---|---|---|---|---|
| Vesper (cold) | executing subagent | executed (own repros + T/U re-run) | NOT CONVERGED | RATIFY |
| Claude | Opus 5.5 / Medium | executed (6 repros) | NOT CONVERGED | Reject as shipped, ratify principle |
| Claude B (Merlin slot) | Opus 5.5 / Medium | executed (8 repros) | NOT CONVERGED | REJECT |
| ChatGPT | GPT-6.2 / Thinking High | static, cited | NOT CONVERGED (1/4) | REJECT |
| Qwen | Qwen4-Max / Thinking | static, anchored | NOT CONVERGED | RATIFY |
| DeepSeek | interface shows none | static, **coverage-limited** | NOT CONVERGED | RATIFY, conditional |
| Gemini | — | **not returned** (sign-in awaits Corey's phone approval) | — | — |

DeepSeek's reader truncated the pack at ~9% (brief + janus.py through `_consume_restore_marker`); it disclosed this and scoped every claim. Its handler-surface silence is not evidence of anything. Gemini's review, if it lands, arrives as an addendum and cannot change the verdict — six seats, including three executing ones, already establish every blocker below.

## 2. What the round established

Round 8's fixes mostly hold — U3, U4, U5, U7's token flow, U8, U10, U13's custody, and U14 survived every seat, several under execution. What failed is a pattern worth naming: **three of the round's own fixes are incomplete at their edges** — U1 closed on the main auth path but not the pickup path its own round added (U7); U6's queue is uniform on fresh plates but bypassed on collisions; U12's tail repair handles a torn tail but destroys the file when the damage is mid-file. The battery missed all three for the same reason: its cases exercise the commissioned shape, not the adjacent one. The R-F addition adopted in §5 (name the coverage an adaptation removes; add a companion case for the displaced path) is aimed at exactly this.

## 3. Verified findings register (chair-verified: executed by ≥1 seat and/or read in code by the chair)

- **V1 — BLOCKER (U1×U7). Pickup wrong-key attempts count toward lockout.** `_totp_pickup`'s wrong-key branch calls `_auth_lock_note_failure` directly (janus.py:5620–5625), bypassing the verified-key guard. Executed by three seats: the Claude seat locked ALL human accounts including both supervisors (the supervisor unlock path then refuses — no unlocked supervisor exists); Claude B locked both supervisors with ten requests; the Vesper seat locked an enrolled detective. Also: the pickup "account is locked" reply (janus.py:5614–5618) discloses lock state to an unauthenticated caller. *Found by: ChatGPT R9-01, Qwen F2, Vesper R9-V2, Claude C9-01, Claude B F1.*
- **V2 — BLOCKER (U6). A non-supervisor submission mutates a live hot-list entry on key collision.** The submission INSERT's ON CONFLICT updates category/added_by/added_ts/expires_ts without regard to pending (janus.py:5041–5050); against a live (pending=0) row the "submission" rewrites it in place, chains HOTLIST_ADD_PENDING, and never enters the queue. Executed by three seats (delisted a live stolen-vehicle entry via a past expiry; a no-expiry variant makes a 30-day listing permanent). *Found by: ChatGPT R9-02, Qwen F1, Vesper R9-V1, Claude C9-02, Claude B F2.*
- **V3 — BLOCKER (U12). Sink torn-tail recovery truncates at the FIRST unparseable line.** `_sink_truncate_torn` (sentinel.py:1891–1922) scans from the file's start and cuts at the first bad line; a mid-file welded line deletes every valid entry after it, delivery continues from the stale tail position, `sink_status` reports ok, and the recorded message claims the wrong seq. Executed by both Claude seats; mechanism read and confirmed by the chair. Seqs deleted are in neither the live sink nor any archive. *Found by: Claude C9-03, Claude B F3.*
- **V4 — HIGH (U9). The born-empty marker travels with the database and the ceremony never ends.** The marker is a row in the DB's own meta table (janus.py:2854–2866, trusted at 3227–3234). Executed by both Claude seats: a born-empty 1.2.6 DB that ingested real reads while unprovisioned, copied to a fresh host, still serves key-only (ingest 201, search 200); deleting the marker row from the same copy locks it. Separately, a born-empty install serves the full data surface indefinitely — nothing but provisioning ends the state. *Found by: Claude C9-04, Claude B F4; Vesper R9-V5 (host-access caveat).*
- **V5 — HIGH (U2). Fence auto-clear is reason-blind, and the transition is not atomic with its chain entry.** `_anchor_apply` clears any recorded mismatch on a clean evaluation — including a genuine checkpoint_disagreement whose disagreeing lines were simply deleted from the local file (the docstring itself says "or removed"). Executed by both Claude seats (rollback fence lifted within seconds of deleting one line; zero acceptance entries). Independently, the clear/set path commits the meta change BEFORE the chain append and swallows append failure (`except Exception: pass`), so a security transition can land unchained. *Found by: ChatGPT R9-06, DeepSeek F1+F3, Qwen F4+F11, Claude C9-05, Claude B F5.*
- **V6 — MEDIUM (U13). Restore's outgoing-provisioned read fails open.** Any exception reading the outgoing DB yields `outgoing_provisioned = False` (restore.py:427, 443 — default and fallback), the same silent shape as TRACK-126's defect 2. Chair-verified. *Found by: ChatGPT R9-04, Claude B F10.*
- **V7 — MEDIUM (retention/registry). Pre-restore copies escape the registered glob and the schema allowlist.** The registry pattern is `<db>.pre-restore-*` (sentinel.py:483–484); restore also creates `<db>-wal.pre-restore-*`, `<db>-shm.pre-restore-*` (plate-bearing) and `<db>.audit_key.pre-restore-*` key snapshots — none match, none are pruned or flagged, and a restored directory fails the build's own suite_schema allowlist. Executed by Claude B (4 of 5 aged files missed). Chair-verified pattern. *Found by: Qwen F3, Claude B F9.*
- **V8 — MEDIUM (queued small ii). `_auth_fail_totals` (and `_auth_fail_flushed`) grow without bound** from unauthenticated requests; /health sorts the whole dict per call. Growth measured by two seats (~93–120 bytes per sprayed username, linear). *All seats: FIX-NOW.*
- **V9 — MEDIUM (queued small i, extended). Destructive releases ride the anchor-fence safety set.** ANCHOR_FENCE_SAFETY_POST (janus.py:2144–2146) contains `/holds/release` (all seats: remove) and `/suppressions/release` (four seats: remove — lifting a protection order during a suspected rollback is the same class of act). *FIX-NOW, unanimous as extended.*
- **V10 — MEDIUM (queued small iii). BLOCKED chain entries carry the raw hit id**, joinable by any partner chain reader to the ALERT entry's camera + timestamp for a protection-order vehicle. Executed by the Vesper seat and Claude B. Fix direction (Claude B): keyed `href:` HMAC references in BLOCKED payloads; the same treatment for the evidence-refusal chained entry (janus.py:6338). *FIX-NOW carries (5 seats; Vesper seat voted pilot-gate, preserved as dissent).*
- **V11 — LOW-MED (U7 hygiene + lockout accounting).** (a) A pending pickup's SECRET never expires — only its token does (Claude C9-08); on token expiry the pending entry and secret persist indefinitely. (b) `_lockout_counts` also counts store_unavailable / must_reenroll states (Claude B F11): a corrupt store or a post-restore re-enrollment state turns ordinary logins into locks — an operator fault taxing users.
- **V12 — LOW (U11(iv) completion).** users.json writers still use a fixed temp path (janus pickup path; provision.py `save()`), the exact torn-write shape U11(iv) fixed for the TOTP store. *Qwen F5.*
- **V13 — LOW (evidence-export oracle).** Evidence export returns distinct refusals — 404 nonexistent, 403 naming protection-order suppression, 409 unverified (janus.py:6297–6351) — while /verify was deliberately made uniform in T7. *ChatGPT R9-07.* The chair counts this a real inconsistency; no other seat flagged it, none contradicted it.
- **V14 — LOW (U9 legacy boundary).** The legacy-chain probe keys on payload v2 (arrived 1.2.1) rather than the TOTP era (1.2.4) its rationale cites (Qwen F10). Mooted if V4's redesign retires the probe (the commission does); recorded so the reasoning isn't lost.
- **V15 — Nits bundle.** Sink archive names have one-second resolution and os.replace can overwrite an earlier archive (ChatGPT R9-11, Claude B F12); the divergence ceremony chains an unbounded stranded_seqs list into one entry and /health (Claude C9-09); pending hot-list submissions without expiry never age out and approval can reactivate an expired pending row (Claude B F8); escrow pruning can orphan an archival set's escrow (Qwen F11); checkpoint.py treats a valid-JSON non-object final line as a persistent failure rather than a truncatable tail (Qwen F11); the boot comment "disables signing, not the service" misdescribes the fenced reality when SIGNING_PUB_PEM is None (DeepSeek F4); attack2.py.orig-124's header describes only its 1.2.5 change (Qwen, Claude C9-11); COMPACT.md's second line still says "1.2.4 is what the code does" (Qwen F9).

**Adjudicated — the version literals (DeepSeek F2, Qwen F9).** The literals exist: `_migrate_124` stamps MIGRATION / MIGRATION_DEFECT `"to": "1.2.5"` and migration_status `"version": "1.2.5"` (janus.py:1533, 1853, 1877); schedule documents and sentinel_audit.py also carry "1.2.5". The chair rules this **not a U11 violation**: the migration stamps name that migration's *target* schema version (historically accurate — the migration was authored in 1.2.5 and still performs the 1.2.4→1.2.5 step), and the schedule version is a document-format version. DeepSeek's forced change is therefore declined as framed. Two residues are real: TRACK-126's claim that "every user-visible version string reads 1.2.6" is overstated and must not be repeated, and sentinel_audit.py reporting its own version as 1.2.5 on a 1.2.6 tree is an operator-facing wart — both go to the 1.2.7 smalls (rename the migration stamp fields for explicit semantics; the audit tool reports the build it ships with).

**Needs-verification carried forward:** DeepSeek F5 — whether `anchor_fenced()` can invoke `_anchor_apply` outside DBLOCK (the seat couldn't see dispatch). The 1.2.7 builder must check the fence-application call sites for lock discipline and report either way.

## 4. The U9 adjudication

The round split 3–3 on the populated-arrival line, but the evidence breaks the tie, and the chair rules **the shipped mechanism is rejected; the convergent redesign is commissioned (V4 in §6)**:

- The ratifiers' own conditions cannot be met by the shipped design. DeepSeek ratified *contingent on* the marker being durable and not writable by an unprivileged path; Qwen ratified with the marker as a "code-visible line." An in-database meta row is neither host-bound nor copy-resistant — the executed copy attack (two seats) is decisive against the mechanism, whatever one thinks of the line.
- The rejectors converge on one design from three directions: unprovisioned = ceremony state everywhere (open: ingest, safety writes, provisioning, auth admin, health; refused for key-only humans: searches, hits view, Tier 3, shares, reports), with fixtures carried by an explicit lab flag instead of a database marker (Claude B's NOCTUA_LAB=1; Claude's data-presence fencing + host-bound exemption; ChatGPT's three explicit states). The designs differ in trim, not in kind.
- The builder's original objection — the literal reading breaks every fixture — is answered by the lab flag, which is fixture churn in one shared helper, not a product compromise. The objection that a born-empty install must ingest before provisioning is answered by keeping ingest in the open set: the fence binds the *disclosure* surface, which is empty until data exists, so first-boot flow is unchanged in practice.
- Preserved dissent: the Vesper seat and Qwen would have kept populated-arrival with the marker hardened; DeepSeek's ratification stands as recorded. If the redesigned ceremony state produces its own executed blocker in Round 10, this adjudication reopens.

## 5. §3 rulings tally

- **(i) /holds/release out of the safety set:** FIX-NOW, unanimous; extension to /suppressions/release carried (4 seats). → V9.
- **(ii) Bound _auth_fail_totals:** FIX-NOW, unanimous. → V8.
- **(iii) Keyed hit refs in BLOCKED:** FIX-NOW carries (5–1, Vesper seat dissenting for pilot-gate). → V10.
- **(iv) Ceremony-state fencing:** resolved by the V4 design — fencing IS the mechanism (ChatGPT, Claude, Claude B for FIX-NOW; Qwen and the Vesper seat's pilot-gate is answered by the go-live enrollment checklist item riding in V4's docs work).
- **(v) 24h pickup expiry:** implemented by U7 (verified by execution — aged store → 401); residual secret hygiene → V11(a).
- **(vi) Shell-operator honesty gap:** CANT-DO, unanimous — **and the entry does not exist in CANT-DO.md yet** (verified by two seats). The 1.2.7 build writes it.
- **S10 null-tolerance:** ACCEPT as a test-only fix, unanimous with conditions: exactly one retry of a dropped sample, logged in the case output; a wrong returned value still fails; a drop in a standalone run still fails (Claude B); full-battery results keep being reported as 24/25 until the revised case passes under load, and /health availability under saturation becomes its own named load-envelope measurement rather than being absorbed (ChatGPT, Claude B).
- **R-F process:** RATIFIED, unanimous, with the **coverage-companion addition** (ChatGPT, Claude, Claude B): when an adaptation changes the actor, the build names the coverage removed and adds a companion case exercising the original actor's path under the new semantics. Retroactive application: V2's discriminating case is exactly the companion case the DET→SUP sweep displaced.
- **U6 validation order:** RATIFIED (all seats; DeepSeek's registry-probe caveat noted — the non-supervisor path must emit the uniform 202 regardless of registry outcome, which the shipped code does). The defect was the write, not the order.
- **Claude B's R-F query** (f2d/f4 boot "122" — if that label runs janus122 code, the adaptation sits outside the stated rule): the 1.2.7 builder must answer it in its report.

## 6. Commission — NOCTUA 1.2.7 (items V1–V15)

Build in a new tree `janus127/` copied from `janus126/`; janus126 untouched. Every item ships with a discriminating case (fails on 1.2.6, passes on 1.2.7) in a new V battery, and the full prior battery stays green via one cold `./run-next.sh`.

- **V1** Key-verified predicate inside `_auth_lock_note_failure` itself (no caller can count a failure without a verified key); pickup wrong-key → AUTH_FAIL evidence only. The pickup "locked" reply becomes a uniform 401. Case: wrong-key spray at every pre-auth route (pickup included) locks nobody; post-key wrong-token still counts.
- **V2** Non-supervisor hot-list submission never mutates a live row: conflict with pending=0 → DO NOTHING (uniform 202, submission chained). Conflict with a pending row may update the *submission* only. Case: detective submits hostile expiry over a live supervisor listing — row byte-identical, alert still fires, 202 byte-identical to the fresh-plate case. (This is also the R-F companion case owed for the DET→SUP adaptations.)
- **V3** Sink truncation cuts only bytes after the last valid line of the tail; cut bytes archived to `<sink>.torn-<ts>`; a mid-file unparseable line is a named divergence (never truncated away); file_seq re-derived after any truncation; sink ok contingent on tail seq continuity; the truncation message reports the true seq. Case: the two Claude seats' welded-mirror shape — entries after the weld survive or surface as named divergence, never silently vanish.
- **V4** U9 redesign per §4: retire the born-empty marker and legacy probe as gating mechanisms. Unprovisioned = ceremony state (open: ingest, safety writes, provisioning, auth admin, health; disclosure surface refused for key-only humans). NOCTUA_LAB=1 for fixtures: chained at boot, named in /health, refused on a provisioned install. Legacy unprovisioned DBs land in the same ceremony state with the existing bootstrap enrollment path. Cases: copied born-empty DB with data serves no disclosure surface on the new host; born-empty first-boot flow (ingest → enroll → serve) works without the lab flag; fixtures under NOCTUA_LAB=1 serve; NOCTUA_LAB=1 on a provisioned install refuses boot. Docs: INSTALL §8 gains the "every human enrolled ACTIVE before ingest connects" go-live checkbox.
- **V5** Fence auto-clear only for file-state reasons (checkpoints_malformed, checkpoints_unreadable, checkpoints_missing, anchor_check_error after its threshold). checkpoint_disagreement clears only via accepted IDs / the two-key accept. The fence transition and its chain entry become atomic: append first (or same transaction); an append failure aborts the state change. Builder also answers DeepSeek F5 (call-site lock discipline) in the report. Cases: deletion of the disagreeing line no longer clears; malformed-file repair still auto-clears; injected chain-append failure leaves the fence state unchanged.
- **V6** Restore outgoing-provisioned becomes tri-state (provisioned / never / unknown); unknown is treated as provisioned (must_reenroll materializes) — fail closed. Case: outgoing DB unreadable/corrupt at the marker read → incoming install materializes must_reenroll.
- **V7** Registry glob widened to cover every pre-restore artifact restore creates (`<db>*.pre-restore-*` plus the key-copy patterns, or each suffix registered explicitly); suite_schema's allowance mirrored; case: restore, age the copies past the reads class, retention prunes them and the schema check passes on the restored directory.
- **V8** Bound the failure accounting: exact counters for configured accounts, unknown usernames aggregated into bounded buckets, the global suppressed count retained; `_auth_fail_flushed` pruned on bucket rollover. Case: 50k distinct sprayed usernames leave the structures bounded (assert the bound, not just RSS).
- **V9** Remove `/holds/release` and `/suppressions/release` from ANCHOR_FENCE_SAFETY_POST. Statutory deletion ceilings are unaffected (they are time-based, not fence-gated). Case: during a fence, both releases 503 while placements still chain.
- **V10** BLOCKED payloads (verify path and evidence-refusal path) carry a keyed hit reference (`href:` HMAC under the audit key) instead of the raw hit id; internal custody joins remain possible for the key holder. Case: a partner-reader join attempt across BLOCKED↔ALERT yields nothing; the auditor's keyed join still works.
- **V11** (a) On pickup-token expiry, clear the pending entry and its secret and chain PICKUP_EXPIRED. (b) Lockout counting excludes store_unavailable (an availability event, not a credential failure); must_reenroll counts only when a code was actually presented and failed. Cases for both.
- **V12** Unique temp + os.replace for both users.json writers. Case in the U11(iv) shape (concurrent writers cannot tear).
- **V13** Evidence export refuses uniformly (the /verify shape) for nonexistent / suppressed / unverified hits to non-supervisor roles; the distinct reason is chained internally only. Case: the three refusals are byte-identical for a detective.
- **V14** (no code — the probe is retired by V4; recorded here so the item is answered in writing.)
- **V15** Smalls: collision-proof sink archive names (monotonic suffix); stranded_seqs in chain payloads and /health capped (count + first-N + hash of the full list); undecided pending submissions expire after 30 days (chained HOTLIST_PENDING_EXPIRED) and approving an expired pending row refuses; escrow pruned only with its paired set; checkpoint.py treats a valid-JSON non-object final line as a truncatable tail; the signing-disabled boot message corrected to name the fenced consequence; attack2 .orig-124 header completed; COMPACT.md's stale version line corrected; sentinel_audit.py reports the shipping build's version; the migration stamp fields renamed for explicit semantics (values unchanged); the enroll-2fa shell-operator CANT-DO entry written into docs/CANT-DO.md (item vi's owed half).

**Criterion 5 status (unchanged):** ACIC answered in writing Nov 25; the no-vendor MOU follow-up and Ben Hooper's statutory answers are outstanding. Legal track, not a code vote.

## 7. What would change the verdict

A 1.2.7 that closes V1–V15 with discriminating cases, survives Vesper's cold re-run, and passes a Round 10 whose executing seats re-run the Round 9 reproductions against it. The blockers are each a few lines; the round's lesson is that the cases must hunt the adjacent shape, not the commissioned one.

---

## Addendum 1 — Gemini seat (Nov 25, 2026, evening)

The Gemini seat was seated late (sign-in stall; the Chrome was in
fact already signed in) and returned after the synthesis was
written. Full seat record: `council9/gemini-review.md`. Chat:
https://gemini.google.com/app/607255d2abba86e6

- Model/effort (operator-observed; governs): "Neon High" —
  "Deeper analysis 4 Neon", Thinking level: High. The seat's own
  §5 says "the interface shows no model name" (self-identity
  unreliable in all directions, as with both Claude seats and Qwen
  in this round).
- Coverage limits: no execution environment (inspection only,
  reproductions supplied); 02-janus.py.txt truncated at
  _share_query(); 06-tests truncated inside run_t125_cases.py.
- Vote: NOT CONVERGED (code grounds) — the verdict is now
  unanimous across all seven seats. U9: REJECT as shipped.
  §3 rulings match the chair tally on every item ((i)–(v)
  FIX-NOW, (vi) CANT-DO; S10 accept-with-conditions; R-F ratify;
  U6 order ratify).
- Agreements with the register: F1 = V1, F2 = the V4 attack,
  F3 = V2, F8 = V3.

### Chair verification of the seat's three new findings (code read, Nov 25)

- **Gemini F4 → V16 (HIGH, added to the 1.2.7 commission).**
  CONFIRMED at sentinel.py:1921–1950 (janus126): sink_divergence()
  computes stranded only for seq <= max(tail_seq, file_seq); with
  a non-empty unparseable sink (tail_seq 0, file_seq 0) stranded
  is empty and file_seq >= tail_seq, so it returns None — while
  _deliver_locked treats the same "unreadable" state as a
  divergence and halts delivery. POST
  /audit/sink-divergence-accept therefore 409s forever; the
  documented recovery ceremony can never run for this state.
  Distinct from V3 (a different function). Fix direction: when
  the tail state is "unreadable", all audit seqs are stranded
  and the divergence dict is returned.
- **Gemini F5 → V17 (HIGH, added to the 1.2.7 commission).**
  CONFIRMED at janus.py:3068–3076 + 3031–3041 (janus126):
  _auth_locked() calls _auth_lock_persist(user) — DELETE +
  db.commit() on the shared connection — when a shell unlock is
  pending, and _auth_locked runs on auth paths outside DBLOCK.
  Fix direction: remove the persist call from _auth_locked()
  (provision.py unlock already deleted the meta row;
  _consume_provision_marker persists inside DBLOCK).
- **Gemini F6 → V18 (MEDIUM-HIGH, added to the 1.2.7
  commission).** CONFIRMED at scripts/compact.py:76–101
  (janus126): one global NOCTUA_TOTP_SECRET is attached to every
  http() call, while main() authenticates as two different human
  accounts on two different agencies' servers; two provisioned
  agencies cannot share a TOTP secret, so a two-provisioned
  Compact sync cannot authenticate both sides. Fix direction:
  per-side secrets (--partner-totp-secret /
  NOCTUA_PARTNER_TOTP_SECRET, --auditor-totp-secret /
  NOCTUA_AUDITOR_TOTP_SECRET); omit the TOTP header on
  machine-role partner receipt posts.

The builder was still in its fix phase when this addendum
landed; V16–V18 were passed to it the same evening, each to
ship with a discriminating V-battery case (fails on 126,
passes on 127).

### Queued for Round 10 (unverified or register-adjacent)

Gemini F3 extensions (inactive-row submission silently
unapprovable; pending rows evading retention while sync sweeps
them), F7's _reload_config half, F9's rotation.py --verify
prefix-list trap, and the F10 bundle. Round 10 executes these
against 1.2.7; the V2 dedicated-pending-table redesign may moot
the F3 extensions.

---

## Addendum 2 — Corey's decisions (Nov 25, 2026, ~21:24–21:27 CST)

1. **Evans/Hill emails CANCELLED.** Corey: "Cancel the Evans Hill
   email. No need." Nothing was ever sent. The drafts file
   (~/workspace/noctua-1.0/evans-hill-drafts.md) is marked
   cancelled; do not revive without a fresh instruction.
2. **Criterion 5 CLOSED, with scoping.** The proposed fifth
   convergence criterion (loop stays open until Ben's + ACIC's
   written answers are in and folded in) is NOT adopted for the
   code loop. Convergence remains criteria 1–4. Rationale, as
   put to Corey and accepted: ACIC's answers (complete,
   including the Nov 25 vendor follow-up — a no-vendor
   city-operated system can receive the file under MOU, on ACIC
   policy) settled every question that could have changed the
   architecture. Ben's outstanding answers govern what ships
   ENABLED and what the policy says — surfaces the build holds
   as configuration (Tier 3 basis types, retention periods,
   reporting categories) — plus deployment sequencing
   (policy-before-capture, lot test). **Deployment and any
   pilot remain gated on Ben's answers; code convergence is
   not.** If an answer from Ben contradicts a shipped
   legal-sensitive default, the remedy is a configuration
   change plus a verification note — the loop reopens only if
   an answer reveals an actual code defect.

3. **Endgame sequence confirmed by Corey (Nov 25, 2026,
   ~21:31 CST):** (1) get the code right (converge), (2) the
   operator UI against the final build, (3) white papers /
   slide deck (frozen package rebuilt against the finished
   system), (4) the LLM — ARGUS, under the v0.2 constraints
   Security Round 1 imposed (read-only advisory, separate
   hardware, no Janus credential, deterministic non-LLM
   healing only, no automatic rollback of database state).
