# HANDOFF — NOCTUA 1.2.5 builder seat

## Goal
Implement commission items T1–T9 (security-round/SYNTHESIS.md) in the new
tree `janus125/` (copied from janus124/), with a discriminating T battery,
the full prior battery green via one cold `./run-next.sh`, and
TRACK-125-REPORT.md. No git operations, no pushes. Prior trees untouched.

## Done definition
- [x] T1–T9 implemented in janus125/
- [x] tests/run_t125_cases.py discriminates (fails on janus124, passes on janus125) — 20/20
- [~] Full battery green: every leg PASS on final code. A single-process
      ./run-next.sh exit 0 was NOT obtainable in this VM — the runtime reaps
      process trees at ~26–30 min and the battery takes ~50 min. Cold-run log
      scratch/battery-20261125-135439.log records builders/round4/round5/
      round6/Q/R PASS inside the runner before it was reaped during the load
      leg; load/S/T then ran cold with the runner's exact commands on
      unchanged code (scratch/logs/load-raw2.log, s-raw4.log, t-raw3.log).
      See TRACK-125-REPORT §1 and §5.
- [x] TRACK-125-REPORT.md: dispositions, judgment calls, counts + log paths, honest flags
- [x] janus124/ baseline md5s re-verified unchanged

## Current state (evidence)
- TRACK-125-REPORT.md written; battery per-leg results in §1 of the report.
- Builders 335/335; round4 PASS (41 verdicts, A9b only); round5 PASS;
  round6 PASS; Q+invariants 35/35; R 20/20; load PASS (6 burners);
  S 25/25; T 20/20 (all discriminating).
- Judgment calls needing Vesper's reconciliation: TRACK-125 §3 (8 items),
  notably the T1 provisioning-marker design, the restore-flip refinement,
  the T7/R9 strict-outrank reconciliation, the key-only pickup tradeoff,
  the REGISTRY_VERSION bump, and the two assertion-preserving seat-file
  adaptations (round4 attack2 A8 escrow key path; round6 f11 remove guards).

## Next step (exact)
Parent (Vesper) reviews TRACK-125-REPORT.md, reconciles the §3 judgment
calls, and runs the council verification round. If a full single-process
run is required as evidence, run `./run-next.sh` on a host without the
~30-minute process cap (expected ~50 min on this VM's CPU allocation).

## Remaining steps
None for the builder seat. Follow-ups belong to the parent: council
round on 1.2.5, dashboard refresh, any reverts of the §3.8 seat
adaptations if the council prefers the legs red.

## Blockers
None. (Environment note: long background processes are reaped at
~26–30 min in this VM; plan verification runs accordingly.)

## Settled decisions (from the commission + build)
- Provisioned-marker T1 design; restore flip only for provisioned installs
- T7 vs R9 reconciled by the strict-outrank rule; refused plate changes
  are chained, never stored as versions
- chain_auditor stays a TOTP-capable human role (tooling gained TOTP)
- Backup custody = key escrow split; restore pinning seeks escrow material
- REGISTRY_VERSION = "1.2.5" (enforcement semantics changed)

## Model / effort
Muse (builder subagent of Vesper). Task complete; handoff current.
