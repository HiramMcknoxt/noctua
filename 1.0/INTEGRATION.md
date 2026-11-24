# NOCTUA 1.0 — integration record (Nov 24, 2026)

How the three build tracks were reconciled, what the simulation findings changed,
and what remains genuinely open. Verified by an independent smoke test of the
integrated Janus (fresh DB + demo seed): health honestly reports DEGRADED on a
fresh install (retention/checkpoint never run), unjustified search blocks,
case-backed Tier 2 returns reads, Tier 3 approval is role-gated, chain verifies.

## Decisions

1. **Store-and-forward (Track B flag #1) — resolved by architecture, not new code.**
   The per-site edge component is Frigate itself: it holds events locally through
   an outage, and the Janus bridge deliberately keeps NO disk queue (a queue
   would be a second plate store outside Janus's retention rules). Replayed
   events land against server receipt time, so a backlog is visible in the data
   rather than disguised. Frigate's own retention (≤14 days) bounds the buffer.
2. **Clock skew (Track C finding 2) — fixed in code.** Reads carry `ts` =
   server receipt time (retention keys on it) and `cam_ts` = camera time;
   skew >5s is flagged in the chain. Exports carry both timestamps. Camera-side
   NTP discipline is in NETWORK.md/INSTALL.md.
3. **K8 emergency-normalization (Track C finding 1) — threshold pinned here:**
   emergency uses exceeding **25% of all Tier 3 actions on a 3-month rolling
   share**, computed automatically in the monthly report, trips the kill
   condition. (Simulated: +5%/month creep trips the rolling measure months
   after the true crossing begins — the rolling window is the noise fix, and
   the lag is documented, not hidden.)
4. **Dead-man witness (Track C finding 3) — adopted as doctrine.** On-box
   heartbeats + alert_check exist (Track A), but the binding alarm is
   off-box: the Clerk/auditor expects a signed checkpoint daily, and a MISSED
   checkpoint is itself the alarm. Job heartbeats ride in the checkpoint
   payload from 1.0's checkpoint.py. OPERATIONS.md carries the response.
5. **False-alert rate (Track C finding 5) — added as a first-class pilot
   metric.** Pilot success/kill language must carry a false-alerts-per-100k
   threshold alongside OCR accuracy; the Stage 0 measurement sets the number.
   OCR accuracy alone is not a pass.
6. **Verify-before-stop currency (Track C finding 4) — adopted.** Verification
   re-checks hot-list currency at verify time; alerts older than the labeled
   actionable window are presented as LEADS with read age displayed, not as
   live alerts.
7. **Prosecutor feedback loop (Track C finding 6) — owned.** OPERATIONS.md
   names the role (System Administrator collects; prosecutor's office is the
   source) and a monthly cadence; the §1805 "prosecutions" line reads
   "not yet reported" rather than silently zero when no update has landed.
8. **Volume-weighted spares (Track C finding 7) — adopted** in NETWORK.md /
   OPERATIONS.md: repair priority and the spare-camera pool are weighted by
   site volume; the busiest site's dark week ≈ 4.8 expected matches.

## Track A deviations — accepted with reasons recorded
- `/search?tier=3` no longer executes on a flag; two-key workflow only. (The
  interface's two-key mandate overrides the v0.9 behavior — correct call.)
- Exported hits are undeletable until prosecutor release; never-exported
  verified hits keep the 30-day timer. Matches the §1804(b) lifecycle design.
- The auditor may close post-hoc emergency reviews (judgment record, no data
  access, reviewer ≠ emergency user). Accepted; it is the only staffing model
  that works at this scale, and the exception is narrow and chained.
- Backups prune as whole sets on the most restrictive class schedule.
- Frigate's LPR payload path is a labeled assumption, confirmed during the
  budgeted deploy-time integration day against the pinned Frigate build.

## Still open (honest list)
- Checkpoint key custody: three documented options, Commission decides;
  CANT-DO's insider wording assumes the default (key on server).
- Frigate media question: event media ≤14 days vs "raw video not retained" —
  Commission decision; both positions are written in the policy draft's terms.
- Path A dispatch/CAD real-time ingest: unconfirmed — Lane 1 (ACIC) question.
- Path B (CJIS): out of scope by design; priced separately if ACIC requires it.
- Per-read byte sizes (storage/bandwidth math): labeled assumptions until
  Stage 0 measures them.
