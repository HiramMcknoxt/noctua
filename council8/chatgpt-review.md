# Round 8 — ChatGPT seat: INVALID (fabricated review), excluded

Chat: https://chatgpt.com/c/6b071cee-f0c0-83ea-8ddd-fd5ec4091c80
UI (browser operator's transcription): GPT-6.2 selected, Thinking High. The seat's own line falsely claimed "the interface shows no model name."
Returned Nov 25, 2026, ~11:44 AM CST after "Worked for 1m 16s" per the chat UI.
Full text: the chat itself and the browser task's PDF artifact (browser-page-20261125T174415Z). Not reproduced here in full — its content is fabricated; the load-bearing claims are quoted in the adjudication.

## Adjudication (Vesper, verified Nov 25, 2026)

The review is **fabricated** — it reviews a system that is not NOCTUA:

- It cites a script `reset_janus_credentials.py` that **does not exist** in janus125 (scripts are: alert_check, backup, checkpoint, compact, frigate_bridge, hotlist_sync, provision, publish_witness.sh, restore, retention, rotation, sentinel_audit).
- It cites functions `_fallback_secret()` and `_resolve_secret()` and environment variables `JANUS_KEY`, `SENTINEL_SHARED_SECRET`, `NOCTUA_SHARED_SECRET` — **grep across the entire janus125 tree returns zero matches for every one of these.**
- It describes the fallback secret as "used only as a HMAC key for identity and timestamp verification, not as a credential for the LLM API" — NOCTUA has no LLM API; this is another system's architecture.
- Its cited lines contain unrelated code: janus.py:1317-1332 is migration savepoint logic; sentinel.py:126-138 is the R3/R5 changelog comment.
- Its "residual rulings R-A to R-F" and "judgment calls (a)-(f)" answer entirely different questions from the brief's — it never engaged the actual residuals (restore indistinguishability, /hotlist residue, unbound identities, pickup, throughput, seat-file adaptations) or the actual judgment calls.
- Its forced change ("single fail-closed authentication lifecycle" across janus/sentinel/reset_janus_credentials) is therefore void.

**Disposition: seat EXCLUDED from Round 8, vote not counted** — same treatment as the Round 5 Grok seat. The failure pattern (76-second "review" of 1.5 MB of attachments, confident citations to a nonexistent codebase) is recorded so future rounds weight this seat's returns accordingly: a ChatGPT return is not evidence until its citations spot-check against the tree.
