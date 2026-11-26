# Round 10 — DeepSeek seat review (as returned)

- Chat: https://chat.deepseek.com/a/chat/s/7359f4ce-57ae-47d9-a8a4-363db064f851
- Model/mode, operator-observed: the DeepSeek UI shows no model name or variant picker; mode "DeepThink" (enabled). The seat's own line agrees: "the interface shows no model name."
- Sign-in note: the saved username/password login was REJECTED by DeepSeek ("password incorrect or account doesn't exist"); the user signed in via Google in the task window, after which the seat proceeded. [Publication note: the personal email address named in this line in the original record is omitted from the published copy.]
- **Coverage: SEVERELY LIMITED, disclosed by the seat.** All 8 pack files were attached, but DeepSeek's reader displayed "Length limit reached. DeepSeek can only read the first 8%" — the seat received file 01 in full and file 02 only through the module top, truncated inside `_anchor_apply` at the fragment "…(1.2.6, U2; 1.2.7, V5). 1.2." Files 03–08 were never delivered to its reader. (Same structural failure as Round 9; the seat's register item R-3 asks for reader-resumable chunked packs in future rounds — adopted as a process note in the synthesis.)
- **Vote: NO VOTE CAST — the seat formally declined both CONVERGED and NOT CONVERGED on coverage grounds**, with reasoning preserved below. Per the seat's own instruction, its unruled items are recorded in the synthesis as ABSENT, not affirmative.

---

## What the seat ruled on the code it actually read

- V9 — CONFIRMED FIXED (set-level): `ANCHOR_FENCE_SAFETY_POST = {"/reads", "/suppressions", "/holds"}`; both releases absent, with the V9 rationale in the comment.
- V14 — CONFIRMED FIXED (retirement visible in the received import/schema span; absence-check caveat noted by the seat).
- V5 — PARTIAL: the reason-gate constant read; the atomicity half sits inside `_anchor_apply`, cut off exactly at the verification point — NOT RULED. [Chair note: the seat's gloss on the constant is its own; the V5 edge stands on the Claude A / Claude B / chair executions, which cover the apply logic past this seat's truncation point.]
- V4 — PARTIAL (substrate only): `LAB_MODE` is env-only, which the seat credits with killing Round 9's traveling-marker failure; `_ceremony_state` and the fence set were not received.
- V7 — PARTIAL: the `_audit_key()` fresh-init guard is consistent with the widened pattern; the retention side was not received.
- V10 — PARTIAL: `hit_ref()` helper confirmed (keyed HMAC, "href:" prefix); call sites not received.
- V15 — PARTIAL: three sub-items confirmed in the received span (target_schema_version rename with values unchanged, VERSION = "1.2.7", corrected signing-disabled FENCED comment); the rest not ruled.
- NOT RULED (code not delivered): V1, V2, V3, V6, V8, V11, V12, V13, V16, V17, V18; all of G1–G5.
- Judgment calls: 0 ratifications; 3 reason-based non-objections (JC5, JC8, JC10); 8 cannot-ratify. JC11 (legacy shared-TOTP fallback) flagged to the chair as the call most needing an explicit written decision (register R-2); JC8 noted as a verification-strength item (register R-1: V12's janus half is source-pattern-asserted by the builder's own statement).

## §3.4 ceremony attack (substrate only)

Held in the received code: LAB_MODE env-only (a copied DB no longer carries its own waiver). Named gaps for executing seats (all since covered by the executing seats' work): provision-while-LAB transition timing; restore-onto-LAB ordering vs. the boot refusal; legacy-bootstrap enrollment path; ceremony side-door leak class (error shapes/counts/timing). The seat states its evidence does NOT reopen U9 — and is not a clean pass either, the mechanism body being undelivered.

## §5–§7 — findings, verdict, forced change

New deployment-blocking/critical findings from the received portion: NONE. Register: R-1 (V12 verification strength), R-2 (JC11 written decision), R-3 (chunked packs for this seat in future rounds).

Criteria: 1 cannot certify · 2 cannot certify · 3 cannot assess · 4 cannot assess — each expressly because the record was not delivered, not because any defect was found. The seat's distinction, verbatim in substance: voting NOT CONVERGED would require a named surviving blocker with evidence (§3.5), which it does not have; voting CONVERGED would certify code it never read, "a false certification, and it is the exact failure this gate exists to prevent." Its forced change: deliver the full pack in reader-resumable chunks and re-seat for a bounded handler-surface re-read; failing that, record its rulings as absent. **The chair records them as absent** (see SYNTHESIS.md §1).
