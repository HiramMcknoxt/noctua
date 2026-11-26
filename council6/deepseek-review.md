# Round 6 — DeepSeek (native) seat review of NOCTUA 1.2.2 (archive)

Seat: DeepSeek native, DeepThink ON, delivered in 8 chunked parts
(per-message ingestion cap ~130-140 KB; the Q battery's second file
was never provided — test-internal claims marked UNVERIFIED by the
seat). Code-read only; executed nothing. Chat:
https://chat.deepseek.com/a/chat/s/039ee011-21c4-47dd-b04c-ed55985fa4ee
Review retrieved Nov 24 ~18:37 CST via the user's Gmail sign-in.
Model line anomaly (again): the seat identifies itself as "Claude
(Anthropic)" and declines to invent a version — the identity line is
unreliable; its code citations were verified by the orchestrator
where load-bearing.

## Verdict: NOT CONVERGED (criteria 1 FAIL, 2 PARTIAL FAIL, 3 FAIL, 4 UNVERIFIED)

- **F1 [CODE-CRITICAL]** auth() runs outside DBLOCK on the /health +
  /audit/verify warm path and _reload_config() chains CONFIG_CHANGED
  on the shared connection — a config change can be silently lost to
  another handler's rollback. CONVERGES with Gemini F6 and Claude
  seat 2's F4 (orchestrator-reproduced). Fixed in 1.2.3 by R4.
- **F2 [CODE-CRITICAL]** rotation grindable by a single supervisor:
  _rotation_commit takes all members' hashes in one body and a
  supervisor may commit AND reveal for any member — whoever supplies
  all nonces can grind the seed; the shipped rotation_ceremony helper
  encodes single-party control. Its forced change (partner-identity
  authorship; supervisor transports hashes only) is exactly 1.2.3's
  R6, incl. the helper rewrite (sign_db).
- **F3 [CODE-CRITICAL, adjudicated REAL by the orchestrator]** a held
  hit loses its reads at RETENTION_DAYS: reads purge with plain
  delete_rows on the reads clock; hit protection guards only the hit
  row. An export/re-export after day 14 yields an empty reads.json —
  a releasable but hollow bundle. VERIFIED in janus122 AND in the
  in-progress janus123 (reads stores still action delete_rows, no
  hit-protection join). Sent to the 1.2.3 builder as a late finding
  (fix: reads linked to a non-deletable hit inherit protection + a
  discriminating battery case).
- F4 [MINOR] the warm gate keys on any valid credential, not the
  endpoint role — an ingest account can force a detached scan every
  60s. Addressed in 1.2.3 by R4's role-gated pre-warm.
- F5 [MINOR] _migrate_122's merge drops the duplicate order's
  order_ref/case_no. (1.2.3's R1/R2 rebuild keeps per-order records;
  builder asked to confirm a battery case covers field preservation.)
- F6 [MINOR] duplicate redeliveries insert orphaned reads rows;
  counters undercount superseded versions. (Cf. Gemini M8.)
- Probes: Q16 property accepted on code-read (not the test's
  completeness); Q18 not clean (F1/F4); rotation probe 4 survives
  (F2); migration probe 5: nothing beyond F5, real-DB UNVERIFIED.
- Judgments: (a) both-tree-pass NOT verified wholesale (Q16/Q22
  accepted on code-read; Q02/Q03/Q06/Q17 UNVERIFIED for lack of the
  Q battery file); (b) Q25 trust root ACCEPTABLE on code-read — the
  lone dissent from the round's consensus; the missing test is a gap,
  not a defect, in its view; (c) strip-not-raise accept, DDL accept,
  disp-note clock accept, /health scope accept; courier REJECT (F2).
