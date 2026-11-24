# Round 5 — Gemini seat review of NOCTUA 1.2.1

MODEL/EFFORT (UI picker, observed by the browser agent): Model "Neon High" (Deeper analysis — Neon, selected), Thinking level "High — Extra thorough". Carbon showed a lock icon (Ultra-gated) and was not selected, per the model protocol. Chat: https://gemini.google.com/app/77cf0c5cffd013c3 — ran 9:07–9:22 AM CST, Nov 24, 2026 (harness-measured). Gemini noted it had NO Python/shell execution sandbox: findings are static code-path traces, not executed runs.

**Verdict: NOT CONVERGED** — all four criteria FAIL per this seat.

P-item table: P1 FIXED · P2 FIXED · P3 FIXED · P4 FIXED-BUT-WRONG · P5 FIXED · P6 FIXED-BUT-WRONG · P7 FIXED · P8 FIXED · P9 FIXED · P10 FIXED-BUT-WRONG · P11 FIXED-BUT-WRONG · P12 FIXED · P13 FIXED-BUT-WRONG · P14 FIXED (cosmetic: backup.py still stamps "noctua": "1.2").

## New findings

- **N1 [DEPLOYMENT-BLOCKING]** — retention.py's unconditional 150-day hits purge deletes a hit whose evidence bundle is still unreleased; afterwards /evidence/release and /evidence/disposition 404 ("no such hit") and /evidence/destroy 409s (no release recorded), while destroy_overdue_bundles never fires because destroy_by is NULL → any prosecution lasting >150 days permanently strands its evidence bundle, invisible to /health and sentinel_audit.
- **N2 [CODE-CRITICAL]** — timestamp parity bugs between sentinel.registry_breaches() and retention.py: (a) case_searches day-string compared against full ISO cutoff → 24h un-clearable breach every day; (b) retention uses floor-days (age_d > days) while the registry uses exact-second cutoffs → hits flagged breached for 24h before purge, and hits can survive to 150d23h59m past the cap.
- **N3 [CODE-CRITICAL]** — janus.py calls chain.flush_deferred() OUTSIDE DBLOCK; flush touches the shared sqlite3.Connection (SELECT hash, UPDATE sink_state, SPOOL_QUARANTINE append with its own COMMIT) → phantom sink entries for rolled-back transactions + shared-connection collisions (P11 regression).
- **N4 [CODE-CRITICAL]** — _migrate_121 normalizes reads.plate and hits.read_plate but NOT suppressions.plate, suppressions.plate_ref, hits.entry_plate, or hotlist_members.plate → pre-upgrade suppressions with formatted plates ('VIC 309') silently stop matching after migration (SQL checks compare s.plate to canonical reads.plate; ref checks use canonical plate_ref against legacy refs). The builders' P4 test used an already-canonical plate, so it missed both modes.
- **N5 [CODE-CRITICAL]** — restore.py on a fresh host (no host key) still falls back to bdir/audit_key inside the untrusted backup set to verify manifest_hmac → forged set with manifest_sig: null installs; simultaneously --pubkey-fingerprint alone is REFUSED on bare-metal (no cross-check against bdir/signing_pub.pem, unlike compact.py / rotation.py --verify).
- **N6 [CODE-CRITICAL/MODERATE]** — config_closed() missing on POST /hotlist, /verify, /holds (all case-gated) and POST /report/compile; /report/compile also allows detective role and returns the full report body, bypassing GET /report's supervisor/auditor fence. Builders' route-enumeration test only inspects _get.
- **N7 [MINOR]** — _post_reads supersede edge cases: lower-confidence different-plate redelivery overwrites a better read and withdraws its pending hit; re-delivery after verification inserts duplicate hit + outcome rows (§ 1805 double-count); withdrawing stale hits doesn't decrement counters.alerts.
- **N8 [MINOR]** — janus build_schedule vs rotation.py --verify diverge: N=2 short-circuit in rotation.py vs Fisher-Yates in janus (~50% of valid 2-member schedules rejected); janus signs members in caller order, rotation.py normalizes sorted(set(...)) → canonical-bytes mismatch on unsorted input.
- **N9 [MINOR]** — sentinel._verify_rows prev_seq starts at None (a chain starting at seq=2 isn't flagged); v1 rows could assert doc ts/kind == column ts/kind; HIT_PROTECTED_SQL GLOB '[0-9]*' matches '1abc' (CAST divergence vs _as_int); rotation uses date.today() local tz vs UTC windows; sentinel_audit URL mode labels the target's self-reported /audit/verify "independent" and downgrades checkpoint errors to warn; checkpoint.py refusal checks only the max-entries checkpoint.

## Judgment-call rulings

- P1 omitted tier → default 2: ACCEPTABLE (strict int check + hardcoded tier2 search make it safe); mild preference for explicit tier in 1.2.2.
- P4/A28 refusal-to-boot: RIGHT default; but ship a one-time pinning ceremony (scripts/pin_audit_key.py --confirm) instead of forcing the secret into a disk file. Not a blocker for greenfield Cabot.
- Silent attacks: SPLIT — A14c, A28, A37 are legitimate passes-by-refusal; A14b, A18, A29, A30, A27 never ran (harness aborted earlier in the same script) and owe re-aimed independent tests printing explicit verdicts; builders' internal tests do not satisfy criterion (4).

## Forced change (1.2.2)

"Harden the 1.2.1 lifecycle and persistence boundaries as one verified contract": fix N1 (evidence endpoints keyed on the evidence row, not hits; § 1804(b) question routed to Ben), N2 (one shared cutoff comparison), N3 (flush_deferred inside DBLOCK or on a detached connection), N4 (complete suppression migration incl. plate_ref re-keying), N5 (no bdir key fallback; fingerprint cross-check; loud --unsafe-unpinned-recovery if an override is needed), N6 (config_closed on POST data/case routes + /report/compile role parity) — each proven by a fail-before-fix builders' test AND a re-aimed independent attack.

## Routed out

Act 668 (Ben); § 12-12-1804(a)–(b) evidence-vs-hit retention boundary (Ben — NEW question raised by N1); § 1804(d) / § 1808(b) / derived-hash status (Ben/ACIC); ACIC hot-list feed + CJIS (Lane 1/3); key custody, witness repo ownership, Frigate media retention, backup custody (Commission/CANT-DO).

[Full verbatim text was delivered in the browser-task handoff, Nov 24 09:22 CST; this file preserves the complete substance — verdict, P-table, all nine findings with traces, rulings, forced change, and routings.]
