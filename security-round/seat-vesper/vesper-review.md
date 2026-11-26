# NOCTUA Security Round 1 — Cold Vesper Seat Review of 1.2.4

Seat: Vesper (cold seat — independent security reviewer; not the
builder, not the orchestrator). Model: Muse (Muse Wonder
session, subagent); the interface shows no effort selector for
this seat.
Build under review: `~/workspace/noctua-1.0/janus124/`.
Fail-before tree: `~/workspace/noctua-1.0/janus123/`.
Method: threat-model-first per the round brief. The orchestrator's
battery counts are accepted as given and were NOT re-run for
counts; every finding below is EXECUTED (probe in `probes/`,
output quoted) or cited to file:line. Severity is judged against
NOCTUA's guarantees — confidentiality of reads, integrity and
completeness of the audit chain, availability of alerts — not
generic CVSS.

## 1. Attack surface map (derived from the code)

**Assets.** Plate reads + crops (evidence dir); hot list; hits;
suppression (protection-order) records; Tier 3 search capability;
evidence bundles + their destruction records; the Sentinel chain
itself (completeness is an asset, not just integrity); the audit
HMAC key (`<db>.audit_key` / env); the Ed25519 signing keypair
(`<db>.signing_key.pem`, 0600); per-user API keys (SHA-256 hashes
in users.json); TOTP secrets + recovery-code hashes
(`<db>.totp.json`, 0600); the Compact's partner trust (pinned
pubkeys, cross-audit state, rotation ceremony); backup sets +
restore markers.

**Entry points.**
- HTTP API on loopback (X-Noctua-User / X-Noctua-Key /
  X-Noctua-TOTP headers): /reads (ingest), /hotlist, /verify,
  /hits + suppressed queues, /suppressions(+release), /holds,
  /tier3/{request,approve,deny,emergency,review,results},
  /evidence/{export,release,destroy,disposition,confirm},
  /share/query, /compact/{partners,suspend,reinstate,witness,
  checkpoint-receipt,audit-result,rotation/*}, /audit(+range,
  root, verify, anchor-accept), /report/compile, /heartbeat,
  /auth/2fa/{reenroll,acknowledge}, /health, /ping.
- Operator scripts (cron/CLI, jobs key or local shell):
  retention.py, checkpoint.py, hotlist_sync.py, backup.py,
  restore.py, compact.py, sentinel_audit.py, alert_check.py,
  rotation.py, provision.py, frigate_bridge.py,
  publish_witness.sh.
- Files as input: users.json / cases.json / cameras.json (hot
  reload on every request), partner checkpoint files, hot-list
  feed files, Frigate event stream, backup tarballs, the
  `.restore_marker`, the sink directory (NOCTUA_SENTINEL_SINK).

**Trust boundaries.**
1. Key holder → role fence (auth() + role_is/only_role).
2. Human key holder → second factor (_totp_accept) — NEW in
   1.2.4, hunted hardest (hunt 1).
3. Any writer → the chain (Chain under DBLOCK; scrubber; the
   sink_pending ledger for delivery).
4. The chain → the outside world (signed checkpoints, Clerk
   anchor, sentinel_audit as the independent verifier).
5. Partner → Compact gate (pinned keys, latest-audit rule,
   commit-reveal rotation with ceremony ids).
6. Filesystem → process (config reload, restore, pin ceremony):
   whoever can write the install directory is one boundary away
   from the crown jewels; several findings live here.
7. Edge → ingest (frigate_bridge / hotlist_sync: everything
   arriving is untrusted by charter).

**Attacker models used** (brief numbering): 1 outsider,
2 low-privilege insider, 3 supervisor insider, 4 partner agency,
5 file attacker, 6 edge attacker, 7 supply-chain/operator.

## 2. Findings register

### F1 [HIGH] — The second factor can be brute-forced online in minutes; nothing throttles an attempt
- **Attacker:** anyone holding a stolen/copied human API key —
  the exact threat S11 was commissioned to defeat ("a stolen key
  alone no longer authenticates it," janus.py auth() docstring).
  Also reachable by models 2/3 against a *colleague's* account.
- **Path:** present the stolen key + guessed X-Noctua-TOTP codes
  to any authenticated GET. `_totp_accept` (janus.py:2120)
  accepts any of 3 counters (±1 step) out of 10^6. The only 429
  in the service is the /share/query partner limit (janus.py:
  6580). `_note_auth_fail` (janus.py:2214) throttles only how
  much of the flood gets CHAINED (25/min global cap) — attempts
  themselves are never refused, slowed, or locked out. RFC 6238
  §5.2's required countermeasure ("the verifier MUST limit the
  number of failed attempts") is absent.
- **Evidence (EXECUTED, probe_01_2fa.py check D):** 300 wrong
  codes in 0.4 s — **671 attempts/second**, statuses {401: 300},
  no 429, no lockout. At that rate the expected time to hit one
  of the 3 valid window codes is **~8 minutes** of sustained
  guessing. Past the AUTH_FAIL chain cap, the flood is also
  largely unrecorded as individual events.
- **Guarantee hit:** confidentiality of reads / Tier 3 capability
  — the second factor degrades to a ~minutes-long speed bump for
  precisely the attacker it exists to stop.

### F2 [HIGH] — 2FA fails open on loss of the TOTP store; enrollment coverage is invisible
- **Attackers:** 7 (the restore path is a routine operator
  procedure), 5 (deleting one file achieves the same downgrade
  with zero chain evidence), and the stolen-key holder who
  benefits.
- **Path:** `_totp_required` (janus.py:2169) demands a factor
  only when an entry EXISTS in `<db>.totp.json`
  (`return entry is not None`). Three consequences, all
  executed:
  (a) a human account that was never enrolled authenticates
  key-only, forever, and nothing in /health distinguishes it
  from a machine account — `_totp_status` (janus.py:2182)
  counts only entries present in the file, and the health
  `ok` formula degrades on TOTP state ONLY for unacknowledged
  recovery alerts, never for missing enrollment;
  (b) the store is EXCLUDED from backup sets by design, so a
  restore boots with no store at all: `_consume_restore_marker`
  (janus.py:1973-1992) flips existing entries to
  must_reenroll — with no file there is nothing to flip, so
  EVERY human account silently returns to key-only and no
  TOTP_REENROLL_REQUIRED is chained (the designed
  "restore forces re-enrollment" becomes "restore quietly
  retires the second factor department-wide");
  (c) a file attacker who deletes/renames `<db>.totp.json`
  gets the same department-wide downgrade with no chain entry
  of any kind.
- **Evidence (EXECUTED, probe_01_2fa.py checks A, E, F):** A —
  never-enrolled detective authenticated key-only (HTTP 403 from
  the role fence after successful auth, not 401). E — after a
  restore-shaped boot with no store, the previously ACTIVE
  enrolled supervisor authenticated key-only (HTTP 200 on
  /health); totp counts all zero. F — chain after that boot
  contains RESTORE but NOT TOTP_REENROLL_REQUIRED.
- **Guarantee hit:** the S11 control itself — silently, in the
  exact operational event (restore) the design claimed to have
  handled.

### What held in hunt 1 (executed, probe_01_2fa.py)
- Activation ceremony: pending enrollment activates only on a
  first valid code (B0); key-only is refused once enrolled (B1);
  a fresh code authenticates (B2).
- Sequential replay: a code reused in a NEW request is refused
  (B3) — the last_counter rule works as specified.
- **Concurrent replay does NOT reproduce:** the same fresh code
  fired by 16 simultaneous requests authenticated exactly 1
  (C). The shared-cache in-place mutation serializes the
  counter update in practice. Recorded as tested-and-held, not
  assumed.
- Recovery codes: SHA-256 of the normalized code, single-use,
  use chains RECOVERY_USED + health alert (code-read,
  janus.py:2151-2167; provision.py:341-352 — 160-bit TOTP
  secret, ten 40-bit recovery codes from `secrets`).

### Hunt 2 — command construction: HELD (code-read, complete sweep)
Every subprocess invocation in janus.py, sentinel.py, and all
twelve scripts is an argv list; there is no `shell=True`, no
`os.system`/`os.popen`/`eval`/`exec`/`pickle` anywhere in the
tree. Ed25519 data travels via temp files, never argv:
sentinel.py:1108 (genpkey), :1113 (pubout), :1142 (pkeyutl
-sign), :1170-1172 (pkeyutl -verify — the public key PEM is
written to a tempfile path, so partner-supplied key text never
occupies an argv slot), scripts/rotation.py:328. Paths in argv
derive from operator config (db_path, env), not from request
data. No finding.

### F3 [HIGH] — Chain rollback: invisible inside the checkpoint window, unenforced across it
- **Attacker:** 5 (file attacker with write access to the DB
  directory — stolen server image, rogue admin, ransomware
  staging that restores an older copy), or 3/7 with the same
  access. The rollback target is a valid earlier state of the
  real database (an old backup copy), so every hash in the
  shortened chain verifies.
- **Path, shape A (within the window):** replace the DB with a
  copy taken at the last checkpoint. The anchor compares
  checkpoints against the chain (janus.py:1904-1952): the
  checkpoint agrees with the prefix, so NO STARTUP_ANCHOR_
  MISMATCH is chained. The sink — the one automated comparison
  that could catch it — reads only its own tail line
  (sentinel.py:1632) and ADOPTS a file tail that is ahead of
  the bookkeeping (sentinel.py:1706-1715, `_deliver_locked`);
  divergence surfaces, if at all, as a sink *delivery* error in
  /health (unchained, repairable by sink maintenance), never
  as a security event. The erased entries survive in the sink
  file itself — evidence for a future human audit, silence
  from the running system.
- **Path, shape B (across a checkpoint):** replace the DB with
  a copy taken BEFORE the last checkpoint. The anchor DOES
  detect this (STARTUP_ANCHOR_MISMATCH chains, /health goes
  not-ok) — and nothing else happens. `anchor_mismatch()` is
  consumed only by /health (janus.py:7454) and the
  anchor-accept endpoint; `locked_out()` (janus.py:3246)
  checks only KEY_LOCKED. The service keeps serving reads,
  hits, searches and shares on the truncated history, and
  accepts new entries that chain onto the forged base,
  until a human happens to notice /health and performs the
  two-key acceptance.
- **Evidence (EXECUTED, probe_02_rollback.py):** Phase A —
  checkpoint at 8 entries, chain grown to 12, DB rolled back
  to the checkpoint state: anchor mismatch chained = False;
  sink-vs-chain diverged seqs [9,10,11,12] reported only as
  sink ok=False; /hits HTTP 200. Phase B — DB rolled back
  across the checkpoint: mismatch chained = True, health
  ok=False, and /hits HTTP 200 + POST /reads HTTP 201 with
  the mismatch live.
- **Guarantee hit:** completeness of the audit chain — the
  system's core promise — in both directions: deletion the
  anchor cannot see, and deletion the anchor sees but the
  system does not act on. The header comment's claim that the
  startup anchor "fails CLOSED" (janus.py:57) describes the
  evaluation, not the enforcement; there is no enforcement.
- Custody note (limit, not defect): CHECKPOINTS_PATH defaults
  to beside the DB (janus.py:424) and the sink is wherever
  NOCTUA_SENTINEL_SINK points; if both live in the same
  directory the attacker rewrites, shape A's last outside
  evidence goes too. The design's answer is Clerk-side
  custody of the originals (checkpoint.py's own header says
  as much) — a deployment discipline the code cannot check.

### F4 [MEDIUM] — One ingest identity can fabricate reads at any camera (alert fabrication)
- **Attacker:** 6 (controls one camera/edge feed or the
  bridge's input side).
- **Path:** the bridge forwards Frigate's `after.camera` as
  the read's cam, and Janus's /reads trusts the single ingest
  identity's cam claim — any registered camera id is accepted.
  A compromised edge source therefore mints reads (and, for
  hot plates, ALERTs) attributed to cameras it does not
  control: false alerts at chosen locations, or a cry-wolf
  flood that trains operators to discount real ones — alert
  *integrity* damage, hunt 4's mirror image.
- **Evidence (EXECUTED, probe_03_edges.py check 1):** as the
  ingest identity, POST /reads {plate HOT777, cam CAM-09}
  produced hit id 1 with `"cam": "CAM-09"` in /hits — a hit
  at a camera the sender never touched.
- **Compensating controls:** reads are chained with cam_ts
  skew flagging; the bridge refuses all events when its
  shared secret is unset (frigate_bridge.py, 503) and caps
  bodies at 1 MB. None of these binds a camera identity to a
  credential. The fix direction is per-camera ingest
  identities (or bridge-side per-camera secrets mapped to a
  cam claim Janus can check) — a spec/deployment change, not
  a one-liner, hence Medium.

### F5 [MEDIUM] — /verify is an enumeration oracle for protected hits
- **Attacker:** 2 — and at the LOWEST human tier: /verify
  admits patrol (janus.py:3837).
- **Path:** hit ids are sequential integers. For each id, a
  patrol/detective POST /verify gets three distinguishable
  answers: 200 (live pending hit — and the probe itself
  decides it), 409 "hit not found or already decided"
  (nothing there), or 403 whose message NAMES the reason —
  "that hit is under a protection-order suppression — it
  moves through the supervisor queue only" (janus.py:
  3871-3879). Differencing against /hits (which lists
  unsuppressed hits with plates and times) reconstructs
  which ids are suppressed hits and when protected vehicles
  generated them — the existence-and-timing fact the
  suppression regime exists to conceal.
- **Evidence (EXECUTED, probe_03_edges.py check 2):** patrol
  probing three ids received exactly {suppressed: 403 with
  the suppression message, nonexistent: 409, live: 200}.
- **Compensating control (partial):** every probe chains a
  BLOCKED entry naming the hit and the reason — the
  enumeration is visible in the audit log after the fact.
  The leak is real-time; the accountability is retrospective.
  The 403 needs no distinguishing text: the generic 409
  wording for both cases closes the oracle at no workflow
  cost (supervisors have /suppressed-hits for the truth).

### F6 [LOW] — Any jobs-key holder can forge any job's heartbeat
- **Attacker:** 2/7 with any jobs-class key (every operator
  script shares the role; ARGUS would add another holder).
- **Path:** POST /heartbeat checks only the jobs ROLE
  (janus.py, _post dispatch: role_is(rec, "jobs")), then
  records whatever `job` string the body carries — there is
  no binding between an identity and the job names it may
  report for. A holder of any jobs key can heartbeat
  {job: "checkpoint", ok: true} forever, defeating the
  dead-man switch that makes a silently-dead checkpoint or
  retention job an alarm at /health.
- **Evidence:** code-read (janus.py _post /heartbeat branch;
  heartbeats upsert keyed by the body-supplied job name).
  Recorded at Low for Janus itself — today's holders are the
  operator's own scripts on one host — but it becomes a
  design precondition for ARGUS (see the ruling, Q4).

### What held in hunts 3, 4, 7, 8 (executed unless noted)
- **Hot-list expiry (hunt 4):** hotlist_sync.py is an expiry
  sweep only — it cannot empty or replace the list; every
  deactivation chains HOTLIST_EXPIRED in the same transaction
  (scripts/hotlist_sync.py:84-110), and the ''/NULL no-expiry
  predicate is defended in depth. A hostile feed has no
  delete path here. HELD (code-read).
- **Sink-down backlog (hunt 8):** with the sink path
  unwritable, appends land and /health names it — sink
  ok=false, error counted, health ok=False (probe_03 check
  5). The S1 design alarms instead of degrading silently.
  HELD (executed).
- **Parser shapes (hunt 3):** 1.1 MB body → 413; malformed
  JSON → 400; service alive after both (probe_03 check 4).
  Frigate bridge refuses all events when its secret is unset.
  HELD (executed + code-read).
- **Heartbeat free-text (hunt 7):** a jobs heartbeat whose
  detail carried a plate-shaped string reached the chain
  with NO raw plate text (probe_03 check 3) — the scrubber's
  flag-and-sanitize works on this path. HELD (executed).
- **Camera silence (hunt 4):** CAMERA_SILENCE_S (janus.py:460)
  feeds the health degradation set — a dead camera is a
  named health failure, not a quiet one. HELD (code-read).
- **2FA re-enrollment (hunt 1):** supervisor requests, a
  DIFFERENT auditor confirms, self-confirmation refused,
  24 h staleness window, old secret dies at confirm
  (janus.py:4182-4272). HELD (code-read).
- **Demo waiver (hunt 1):** DEMO_MODE is env-only
  (janus.py:488) and recorded in SYSTEM + /health; no config
  file value reaches it. The round-7 bypass family stays
  closed. HELD (code-read, consistent with the S battery).

## 3. Ruling on ARGUS (hunt 6 — the design at argus/SPEC.md)

**Ruling: ARGUS MAY EXIST — advisory only, and only after the
six constraints below are written into the spec as mechanisms,
not prose.** The spec's skeleton is right: never the alarm,
never a reader of the live DB, never an author of production
code. Every gap I find is the same shape this project has met
in every round — a limit stated as a sentence where it must
exist as a mechanism. Per the spec's own six questions:

1. **Sanitizer bypass — the spec is NOT yet sufficient.** The
   load-bearing claim is "templates have no field that can
   carry plate/case/chain content." But templates constrain
   field *semantics*, and the spec never requires per-field
   *grammars*: a version or error-class string is exactly
   where a crafted value rides, and this codebase's own
   scrubber matches only already-normalized plate shapes
   (sentinel.py:1196-1199) — spaced, hyphenated, lowercase,
   homoglyph, or cross-query-fragmented plates pass it.
   Constraint: every template field gets a machine-checked
   grammar (enum or tight regex) enforced by the PROXY, not
   by ARGUS; free text as a category is abolished, not
   scrubbed.
2. **Injection through the sink — bounded, if two pins are
   added.** Log-borne text cannot touch the deterministic
   layer (ARGUS can neither suppress nor delay a Sentinel
   alert — that limit IS mechanical, and it is the design's
   saving grace). What injection CAN do is work on ARGUS's
   own outputs: suppress its advisory flags, or fabricate a
   digest accusation against a named officer — prose that
   arrives wearing the system's authority. Constraints:
   (a) Tier A triggers must be deterministic fault signals
   (job heartbeat overdue, sink backlog > 0, checkpoint
   missed) — never ARGUS's judgment that something "looks
   like" a fault; (b) every claim in a digest must QUOTE the
   chain entry it rests on, verbatim, beside the claim, so
   fabrication is checkable at a glance.
3. **Injection through research results — the spec's weakest
   point, by its own admission.** Today the quarantine is a
   prompt-level construct with NO mechanical enforcement,
   and the realistic attack is not code — it is a poisoned
   page teaching the operator, via ARGUS's report, that a
   real error is "a known false positive." Constraint:
   research-derived text may appear in reports only as
   fenced quotation with source URL + retrieval hash, and
   ARGUS's report vocabulary contains no dismiss/reassure
   recommendation class for research-derived claims. The
   Tier B path (battery + human approval) already enforces
   mechanically for code; reports need their equivalent.
4. **ARGUS's machine key — acceptable ONLY with a Janus-side
   precondition.** A jobs-class key today can forge any
   job's heartbeat (finding F6) — i.e., it can mask the
   death of the checkpoint job, an alert-suppression
   primitive. Handing that key class to an LLM widens the
   blast radius past what the spec admits. Constraint:
   before ARGUS holds any key, Janus binds job names to
   identities (an identity may heartbeat only its own job
   names), and ARGUS's identity heartbeats only as ARGUS.
5. **Rollback abuse — real, and the spec walks into it.** If
   ARGUS judges post-deploy invariants from sink-visible
   state, an attacker who can perturb that state during the
   window can force a rollback — a veto over security
   patches, repeatable at will. Constraints: the rollback
   decision must be computed deterministically (the
   invariant suites' exit codes, run against the DB/chain
   directly — ARGUS as messenger, never judge), and
   automatic rollback fires AT MOST ONCE per deploy; a
   second failure freezes and calls a human.
6. **Pilot form — acceptable with custody mechanics.** Same-
   host proxy is fine for the pilot ONLY if (a) the sink
   export is delivered INTO a directory ARGUS owns by a
   Janus-side writer (ARGUS gets no read path into Janus's
   directory — F2 of this review is the standing lesson in
   what file custody on a shared host is worth), and (b)
   the proxy runs under its own user with egress only on
   the research VLAN. Production should take the spec's
   separate-appliance option.

If those six constraints land in the spec as mechanisms, the
design is sound and worth building. If they remain
aspirations, ARGUS may not be built — an advisory system
whose limits are prose is a second, softer front door, and
this project has spent seven rounds learning what those cost.

## 4. Verdict against the round's criterion

Criterion: **no surviving Critical or High finding exploitable
by its stated attacker model without a compensating control
already in the code.**

- F1 [HIGH] survives: a stolen human key plus ~8 minutes of
  unthrottled guessing defeats the second factor. No
  compensating control exists in code.
- F2 [HIGH] survives: the second factor fails open — per
  account (never enrolled) and department-wide (store lost
  to restore or deletion) — with no chain record and no
  health signal. No compensating control exists in code.
- F3 [HIGH] survives: rollback is invisible inside the
  checkpoint window and unenforced across it. The sink's
  tail complaint (shape A) and the chained mismatch
  (shape B) are signals without enforcement; neither stops
  the system serving the shortened history.

**Verdict: NOT CONVERGED.** Three High findings stand against
the criterion, all in guarantees the system itself states:
the second factor (twice) and the completeness of the chain.
The battery's green stands too — every battery property I
re-tested held (concurrent replay, scrubber, sink alarm,
parser shapes). The battery measures the properties it was
written to measure; these findings live in the spaces between
them: attempt economics, enrollment coverage, and enforcement
after detection.

## 5. The forced change (the price of my vote)

**Make the second factor fail closed on enrollment state.**
`_totp_required` must demand a factor for every human-role
account — enrolled or not. A human account with no valid
enrollment entry is REFUSED authentication with a chained
2FA_NOT_ENROLLED event (provisioning is how it gets in, the
same way a missing key is refused today); /health must name
every human account lacking an active enrollment; and the
restore path must materialize `must_reenroll` entries for
every human user in users.json when the store is absent, so
"restore forces re-enrollment" becomes true in the case the
design actually ships. One change, three clauses, and F2's
entire family — never-enrolled, store-deleted, post-restore —
closes at once.

Recorded for the synthesis (not the price, but not optional
either): F1's attempt throttle (per-account progressive
refusal on second-factor failures, chained — RFC 6238 §5.2's
requirement) and F3's fence (an anchor-class mismatch,
including sink-tail divergence beyond a bounded crash window,
fences data paths until the two-key acceptance that already
exists is performed). A round that fixes only the price and
leaves those two has not answered this review.

