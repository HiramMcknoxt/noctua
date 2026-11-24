# Round 5 — DeepSeek NATIVE seat, CHUNKED retry (chat.deepseek.com, Corey's Chrome)

MODEL/MODE: DeepThink ON for all turns (verified by the browser agent). ⚠️ The review's own MODEL line misidentifies the model as "Claude (Anthropic)" — false; this was DeepSeek chat. Its citations, however, are to real code (verified against janus121 during archiving: _reload_config, _migrate_121's scope, retention.py's flow, _SUPPRESSED_SQL all exist as described) — unlike the Grok seat, the content is grounded; only the identity line is wrong. Chat: https://chat.deepseek.com/a/chat/s/fac5bfed-59af-4ead-911b-a481b8cd346e — ran 10:17–10:31 AM CST, Nov 24, 2026 (harness-measured). Static read, no execution.

## The chunking experiment — MEASURED RESULT: chunking does not fix DeepSeek's cap

Receipts (DeepSeek's own, collected per turn):
- Turn 1, janus.py ALONE (217 KB): "can only read the first **63%**" — cut off inside _evidence_post's /evidence/release branch.
- Turn 2, sentinel.py (54 KB) + docs-combined.txt (34 KB): **both read in full** — the only clean turn.
- Turn 3, scripts-combined.txt alone (123 KB): **99%** — publish_witness.sh truncated mid-line at its final check.
- Turn 4, run_tests.py (116 KB) + attacks-combined.txt (66 KB): **60%** — run_tests.py truncated in the A18 setup; **attacks-combined.txt never received at all** (the budget was consumed by the first file).

Conclusion: the cap behaves like a fixed per-message ingestion budget (~130–140 KB of text), applied across the whole message's attachments in order. janus.py alone exceeds it. Full DeepSeek coverage of this codebase would require splitting janus.py itself into 2–3 sequential parts — possible, but the seat remains static-only, so its ceiling is corroboration, not verification.

**Verdict: NOT CONVERGED** (criteria 1/3 FAIL; 2 FAIL/UNVERIFIED; 4 UNVERIFIED). P-ratings on visible code only: FIXED = P2, P6, P8, P10 (sentinel side), P11 (sentinel side), P14; FIXED-BUT-INCOMPLETE = P4; PARTIAL/UNVERIFIED = P13; UNVERIFIED (in the unread third of janus.py) = P1, P3, P5, P7, P9, P12.

## Findings

- **F3 [CODE-CRITICAL] Legacy hotlist_members.plate / suppressions.plate never canonicalized** — the S14 migration copies plate verbatim from the legacy hotlist table; _migrate_121 normalizes only reads/hits. **Fourth independent seat to find the migration gap** (converges with Qwen F1a/F1b, Claude-1 R5-01, Claude-2 R5-03) — from static reading alone.
- **F1 [CODE-CRITICAL, NEW — verification queue] Malformed config 500s every authenticated request forever.** _reload_config catches only (OSError, ValueError); _apply_config can raise TypeError/KeyError on a wrong-shaped config (list-shaped cameras.json, dict-shaped users.json), and because the mtime is recorded only after a successful apply, every later request re-raises → 500s, including /health, while /ping stays green. Contradicts the documented fail-closed contract. Fix: widen the catch, mark stale.
- **F2 [CODE-CRITICAL, NEW — verification queue] retention.py purge is not atomic with its chain entry.** Purge commits on its own connection, closes, THEN opens a separate Chain connection to append RETENTION_PURGE; a crash in between = unchained deletion in the system's core trust job. (Converges with Claude seat 2's code-read note: retention.py commits at :302, chains at :323-332 on a new connection.) **Forced change: make retention.py single-transaction** (Chain(DB, conn=db) before the purge loop) with a kill-between test.
- F4 [minor] sentinel._insert_locked: caller fields can override the v/ts/kind envelope keys (latent; no current caller does).
- F5 [minor] rotation.py signed_portion omits period_days (alterable without breaking --verify).
- F6 [minor] _anchor_accept records truncation checkpoints as "accepted"; pending acceptance can go stale across restarts.
- F7 [minor] restore.py evidence copy loses 0600 mode; checkpoint/publish_witness double-append if NOCTUA_CHECKPOINTS points at the witness file.
- F8 [design question] chain_auditor credential cannot audit retention in URL mode → routed to Compact policy (is retention part of "auditing the books"?).

Rulings: P1 default acceptable (recommends explicit later); A28 refusal correct, ceremony belongs in the install guide, no override flag; silent verdicts legitimate only with re-aimed refusal assertions per scenario.

[Full verbatim text, including all four receipts, was delivered in the browser-task handoff, Nov 24 10:31 CST.]
