# Council review — ChatGPT seat (Nov 23, 2026)
Chat: "Hostile ALPR Review" — https://chatgpt.com/c/6b04c51e-4834-83e9-a489-f4b43f7585ec
Full verbatim response is preserved in the side-chat transcript (message of Nov 23, ~17:00 CST) and summarized in the synthesis. Headline findings:

- Verdict: proceed with commission + conditional pilot; do NOT authorize operational replacement yet; do not represent the system as production-ready.
- Weakest link: Janus is an application-layer control, not yet a proven mandatory boundary — direct DB/filesystem admin access bypasses it and Sentinel entirely. Claim must be narrowed to "every action mediated by Janus is logged."
- Sentinel: unkeyed hash chain can be rewritten + recomputed by a privileged attacker before the weekly anchor; weekly witness leaves up to a 7-day window.
- Case validation proves a case exists, not that the search is relevant to it (borrowed-case-number abuse).
- Legal: § 12-12-1805(a)(3)(B) evidence-exclusion risk if policy is defective; § 12-12-1804(b) investigative retention — fixed 30-day hold could destroy evidence incl. exculpatory material; prosecutor must own evidence lifecycle. § 12-12-1805 six-month statutory report (scans, list names, confirmed matches, non-matches, arrests/prosecutions) preserved 18 months — dashboard alone doesn't satisfy it; § 12-12-1804(c) daily updates. § 12-12-1808: commissioners' access to protected data isn't authorized by the oversight mandate alone (protection-order data) — redacted records only. Tier 3 judicial authorization exceeds the statute — define the instrument with counsel.
- Feasibility: maintenance ownership breaks first, not compute. Commission must not become an unpaid IT department. Pilot sample (~114 matches, ~1.2 recoveries, ~3.2 arrests projected) too small to prove equivalence on outcomes — evaluate on ground-truthed technical accuracy (plate-text and jurisdiction accuracy measured separately), not arrests.
- Base-rate warning: at 8.56 true matches/100k, a 0.01% false-alert rate adds 10/100k — false alerts can swamp true ones.
- Forced change: independent adversarial verification of the complete data-access boundary (admin, Frigate, backups, ingest bridge, witness circumvention) as a binding pre-deployment condition, with unresolved critical bypasses blocking deployment.
- Also: preserve the option of discontinuing ALPR entirely — a failed pilot must not auto-justify renewing Flock.
