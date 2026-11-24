# NOCTUA Council — Round 3 Synthesis (NOCTUA 1.1)

**Seats and models (per Corey's protocol — best included tier, max effort,
no Fable, no credit-gated/Ultra tiers):**
- ChatGPT — GPT-6.2, High. Read all 16 files in full from the repo.
- Gemini — Neon, High (thinking: Extra thorough). Top tier ("Carbon") was
  Ultra-gated at $99.99/mo and was declined per protocol; Neon was the best
  included model. Could not fetch raw URLs this round; reviewed from
  attachments, all 16 files in full.
- Claude (user's browser) — Opus 5.5, Effort Max. Fable 5.2 was shown as
  "Requires usage credits" and was not used. Read all files in full.
- Claude (cloud) — Opus 5.5, Effort Max (Fable 5.2 shown as
  "Requires usage credits," not used). Review delivered as a document
  (49 KB) and archived in full.

**Verdict: NO-GO, unanimous.** Round 3 has not converged. But the character
of the findings changed: the 1.0 failure was controls bypassed through
alternative paths; 1.1 closed most of those, and the seats confirmed the
core repairs (Tier 2 wall, chain atomicity, role splits, QUERY logging,
§1805 counts) as real. What remains is concentrated: **secondary copies of
plate data that retention doesn't know about, trust records that attest
rather than verify, and maintenance scripts that quietly undo the
service's own protections.**

## The convergent core (≥2 seats; load-bearing items verified in code by Vesper)

1. **Tier 3 results are a permanent plate archive.** janus.py stores full
   serialized results in tier3_requests.results; retention.py never
   touches them; retrieval never re-gates. (All 4 seats. Vesper-verified:
   results written at approve/emergency; retention scrubs only
   plate_fragment.) Deployment-blocking.
2. **The Compact gate reads attestations, not audits.** The gate accepts
   ANY ok=1 audit row in 26h (a later failure doesn't close it —
   Vesper-verified in the gate query); receipts accept any historical
   checkpoint and are timestamped on arrival; compact.py trusts the
   auditee's own /audit/verify; partner Tier 3 shares bypass the two-key
   rule. (All 4 seats.) Compact-blocking.
3. **Suppression still leaks on identity mismatch.** plate_ref() doesn't
   normalize (Vesper-verified: uppercases only) and suppression is keyed
   by (plate, state) while the bridge stamps "AR" on nearly every read —
   formatted variants ("VIC 309") and non-AR suppressions silently match
   nothing. /verify and evidence export also bypass the supervisor queue
   for suppressed hits. (Gemini, both Claudes, ChatGPT in part.)
4. **Health still lies at the edges.** chain_ok is computed but NOT in
   degraded — a broken chain reports ok:true (ChatGPT, Gemini, cloud
   Claude). Plus: /health unauthenticated and runs verify() under the
   lock per call; hotlist_sync is monitored but no script ships.
5. **The outside anchor doesn't work as shipped.** publish_witness.sh
   fails on every run (checkpoint.py prints a second line after its JSON;
   the shell script's json.load dies) — after the checkpoint heartbeat
   already said ok. restore.py replaces the live checkpoints file,
   rolling the anchor back invisibly. The startup anchor fails open on a
   missing/malformed checkpoints file and checks only the newest
   checkpoint. (Both Claudes; Gemini on restore.)
6. **One key does two jobs.** Checkpoints, audit reports, and rotation
   schedules are HMAC-signed with the plate-pseudonymization key — a
   partner can't verify a checkpoint without the secret that reverses
   every plate_ref (including the protection-order list), and with it
   can forge checkpoints. Wrong-key boot is also accepted silently (only
   a MISSING key locks). (Gemini, both Claudes.)
7. **Rotation: math right, mechanism hollow.** The pairing algorithm is
   correct (verified by hand by two seats), but the published seed never
   permutes anything (same alphabetical schedule every cycle), duty
   tracking reads the wrong table with no time window, and
   rotation_delinquent is unreachable code. (Gemini, both Claudes.)
8. **Chain content + ordering.** Free text still reaches the permanent
   chain (AUTH_FAIL chains the raw unauthenticated username header;
   case/category/why text in several entry kinds); the scrubber both
   misses real plates (lowercase, prose) and false-fires on legitimate
   IDs (CAM101, CPD-1001) — and because writes commit before chaining, a
   scrubber raise leaves a committed, unlogged action. (Both Claudes,
   Gemini.)
9. **Retention script defects.** frag_ref() in retention.py differs from
   janus.py's (no .upper(), no [:24] — Vesper-verified), so scrubbed
   fragments never match chain refs; the key-file fallback is missing, so
   on default installs the scrub silently skips while the heartbeat says
   ok; secure_delete off in its own connection. (Gemini, both Claudes.)
10. **Scripts never reviewed before earned it.** backup.py: --prune is
    opt-in (plaintext backups accumulate forever by default), evidence
    bundles excluded, no failure heartbeat. restore.py: tar-slip,
    unsigned-manifest acceptance, stale -wal/-shm left behind,
    pre-restore copies never pruned. checkpoint.py: root/count read in
    two statements (self-mismatching checkpoints). frigate_bridge.py:
    unauthenticated /event, no body cap, no camera allowlist.
    (Gemini, both Claudes.)
11. **The test suite's blind spots are structural.** The suite never
    populates Tier 3 results, tests suppression only via the normalized
    full plate, sets the audit key via env (never the shipped key-file
    path), never tests fail-after-ok, replay, witness, or restore — and
    ran 200 appends, not the 1,000-write stress test Gemini's round-2
    forced change required. The suite is written by the build's authors;
    both Claude seats repeat the round-2 acceptance condition: the
    acceptance suite must be adversarial to the builders' assumptions.

## Forced changes — two seats, one demand

ChatGPT and cloud Claude, independently and without coordination, issued
the **same forced change**: an explicit, code-level inventory of every
place captured plate data (or a recoverable copy) can exist, an enforced
expiration for each, and a shared authorization boundary for disclosure —
cloud Claude specified it as a `PLATE_DATA_STORES` registry in janus.py,
with retention.py purging by the registry, sentinel_audit.py auditing by
the registry, and a schema test that fails the build when a plate-bearing
column or folder is unregistered. **ACCEPTED as the spine of 1.2.** It
also retroactively explains every round's worst bug: each was a copy of
plate data that retention's hand-kept list didn't know about.

Gemini's round-2 forced change (1,000-write stress test) remains open and
is carried into 1.2's acceptance tests. ChatGPT's round-2 certification
condition stands as a pre-deployment gate, unchanged.

## Routed out of the loop (not code defects)

- § 12-12-1804(d): whether reciprocal sharing is an "exchange," and
  whether raw-read shares fit "evidence of an offense" — Lane 2 (Ben),
  now with three seats' analysis attached. Shares stay capped at Tier 2
  and the Compact ships OFF by default until counsel answers.
- Key custody (Clerk vs server), witness-repo ownership, hot-list add
  approvals, Frigate's own media retention — Commission/city decisions,
  already in the spec's open list; CANT-DO gains the cloud seat's
  accepted-limitations list (same-box insider with key + sink, colluding
  supervisors, self-reported heartbeats, receipt-time retention clock,
  no stdlib public-key signatures — mitigated in 1.2 by Ed25519 via the
  system openssl for signing, witness publication for verification).

## Disposition

1.2 build commissioned with items S1–S18 (registry spine; Tier 3 result
lifecycle; canonical state-blind suppression identity; ingest honesty +
camera registry; health truth; witness/anchor repair; key separation
with Ed25519 signing; Compact gate semantics + independent recompute;
chain_auditor role; share caps; chain content discipline + same-
transaction logging; rotation correctness; config ceilings; report
residuals; retention correctness; audit-tool truth; evidence residuals;
and a test suite that includes every round-3 attack as a named case,
plus the 1,000-append stress test). Round 4 reviews 1.2 under the same
protocol.
