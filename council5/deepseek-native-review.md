# Round 5 — DeepSeek NATIVE seat (chat.deepseek.com, Corey's Chrome) review of NOCTUA 1.2.1

MODEL/MODE: No named model selector in the DeepSeek UI — DeepThink toggle enabled (visual active state; the response itself names no model). Chat: https://chat.deepseek.com/a/chat/s/c5d2272e-da6c-4afe-a354-3d3bdedc56f3 — ran 9:56–10:01 AM CST, Nov 24, 2026 (harness-measured). Corey signed in himself via Google.

**CRITICAL LIMIT: DeepSeek read only the first 19% of the attachments** (its own system note: "Length limit reached"). In practice it had janus.py (partial — the text ends mid-function at _evidence_post) and NOT sentinel.py, the scripts, the docs/synthesis, the test suite, or the attack suite. Many items are honestly marked CANNOT VERIFY. This seat did not execute code.

**Verdict: NOT CONVERGED (on the evidence available)** — criterion 1 NO, 2 cannot fully verify, 3 NO, 4 cannot verify.

P-items checkable from janus.py alone: P1 FIXED (handler outside the read window, unverified in full), P2 PARTIALLY VERIFIED, P3 PARTIALLY FIXED / INCOMPLETE (claim gap — see N2), P4 FIXED, P7 FIXED, P11 FIXED, P13 MOSTLY FIXED; P9/P12 CANNOT VERIFY.

## New findings

- **N1 [code-critical, NEEDS ORCHESTRATOR CODE CHECK] Locked-boot migration skip resurrects the P2 ''-expiry defect.** _migrate_121 early-returns when KEY_LOCKED is true; a locked boot is exactly the state an env-key-only 1.1→1.2.1 upgrade lands in. The DB then keeps hotlist_members.expires_ts='' rows; on the ingest path '' is falsy so the expiry check is skipped (treated as no-expiry), and the hotlist_sync sweep predicate (not in this seat's read window) may still treat '' as expired. Verify in code: janus121 _migrate_121 KEY_LOCKED ordering + hotlist_sync.py sweep predicate + what a locked boot permits (data endpoints are config-closed under lock per P13 — the question is whether the sweep still runs and what it does to '' rows).
- **N2 [claim gap, not a defect]** P3's "all read paths live-suppress" could not be confirmed for /hits, /tier3/results, /share/query — those handlers were outside the 19% read window. ANSWERED by other seats: ChatGPT and the Vesper seat exercised those paths live (Vesper F-probes confirmed query-time suppression on /hits + tier3; the residual defects there are the ones in their findings, not absence of the check).
- N3 [minor] _post_verify SELECTs hits.suppressed but never uses it — dead code echoing the stamp-vs-live confusion P3 ended.
- N4 [minor] _post_holds default review_by sits exactly at the validation boundary; consistent, worth a comment.
- N5 [minor] compact_receipts has no unique constraint on (agency, root, entries); gate reads latest by id — sound in current logic, flagged for the endpoint reviewer.
- N6 [minor] If openssl is missing (SIGNING_PUB_PEM None), every checkpoint fails signature acceptance → anchor fails closed every boot; the boot warning ("disables signing, not the service") understates that. Docs/ops.

## Rulings

P1 default acceptable but must be documented in COMPACT.md + the endpoint docstring (builders' wording is ambiguous). P4/A28 refusal correct; the error message is not actionable — the ceremony/runbook is the missing piece. Silent attacks: NOT a legitimate pass — each refusal must be an asserted test, not a harness crash (converges with ChatGPT/Gemini/Vesper rulings).

**Forced change (P15): make the env-key upgrade ceremony explicit and tested** — boot-time stderr naming the exact remediation (copy NOCTUA_AUDIT_KEY into <DB>.audit_key mode 0600 and restart, or unset the env var); builder-suite assertions for HOLD_DAYS=400 / RETENTION_DAYS=151 / TIER2_WINDOW_H=73 boot refusals, env-key locked-boot /health naming the reason, and client-seed rotation 400; docstring fix stating the missing-tier rule in both places.

Routed to Ben: whether HOLD_DAYS and RETENTION_DAYS are the same clock under § 12-12-1804(a); state-blind suppression identity vs state-specific protection orders; Act 668 unsettled.

## Orchestrator's note

Second DeepSeek data point, opposite failure mode from Merlin's: native DeepSeek with DeepThink reasoned more sharply (found the N1 lock-path interaction nobody else raised) but its attachment ceiling — first 19% of ~600 KB — makes it structurally unable to review a codebase this size in one pass. For future rounds, DeepSeek seats need the code split across multiple messages or a reduced core-file set. N1 goes into the synthesis verification queue.

[Full verbatim text was delivered in the browser-task handoff, Nov 24 10:01 CST.]
