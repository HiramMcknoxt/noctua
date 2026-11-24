# AI Council Review Brief — Project NOCTUA (for Gemini / Claude / ChatGPT)

You are reviewing, as one member of a three-AI council, a real municipal
proposal being prepared for a city council and a citizens commission in
Cabot, Arkansas (pop. ~26k). Be hostile and specific. Generic praise is
useless. Your full answer will be synthesized with the other two members'
answers; disagreements will be preserved, not averaged away.

## The situation
Cabot leases 9 Flock ALPR cameras (8 Falcon + 1 Flex; $27,500 invoiced in
2026 on staggered 24-month tranches; hardware stays Flock's). CPD's own
reported figures, Jan 1–Jun 30 2026: 8,040,000 plates scanned, 688 matches
(8.56 per 100k reads), 7 stolen vehicles recovered, 19 arrests. A city
council member proposes replacing the third-party system with a
city-owned, open-source system: commodity LPR cameras, open-source
detection/OCR (Frigate LPR or fast-alpr), all data on a city server, a
Citizens Commission (7 volunteers) that designs the system, and a separate
council vote before anything is implemented. Arkansas law (Ark. Code
§§ 12-12-1801–1808) caps government ALPR retention at 150 days and
requires a public local policy; it does not require a warrant. The
proposal sets 14-day retention anyway.

## What has been built (all tested, all synthetic data)
1. **A pilot spec**: two gated stages (1-camera lot test, then 3 cameras /
   90 days), success metrics, kill conditions, budget ≈ $3–10k hardware
   for 3 cameras, software $0, staff time tracked honestly, CJIS costs
   explicitly unpriced and gated.
2. **"Janus"** — a working front-door service (stdlib Python + SQLite):
   named accounts only (no shared logins exist), every search requires a
   case number validated against an open-case list, Tier 3 historical
   searches require judicial authorization or a supervisor emergency flag,
   the outside-auditor role is read-only, and EVERY allowed and blocked
   action is written to the audit log. Tested live: bad case → blocked and
   logged; auditor search → blocked; role violations → blocked.
3. **"Sentinel"** — the audit log is an append-only SHA-256 hash chain;
   weekly the root hash is published outside the system (City Clerk +
   public git repo). Tested live: an insider-style edit to one logged
   entry made chain verification report the exact broken entry; restoring
   it made verification pass again.
4. **Retention job** — nightly, deletes non-hit reads past 14 days and
   resolved hits past a 30-day hold, and logs its own deletions into the
   chain. Tested live.
5. **Hot-list matching stays on the ACIC/dispatch side** unless ACIC
   approves the city box as a CJIS system (a separate, priced decision —
   "Path B"). If ACIC says approved-vendors-only, the pilot stops
   ("Path C"). Nothing goes live before ACIC answers in writing.
6. **A demo console** (the CPD operations UI) and a public dashboard,
   both running a simulation locked to Cabot's real match frequency,
   with a live tamper-test button for council demonstrations.
7. **A deploy package**: docker-compose (Frigate + Janus), a
   cameras.yaml where the only site work left is IPs + credentials,
   users/cases config, runbook, and an honest "known gaps" list
   (Frigate LPR bridge pinning, console→API wiring, Path B excluded,
   two-key Tier 3 workflow not yet implemented).

## Your assignment — answer all five, briefly and specifically
1. **Security**: Where does this design actually break? Consider insider
   threats, the case-validation dependency, key management, the witness
   mechanism, and the Frigate→Janus ingest path. Name the weakest link.
2. **Legality / policy (Arkansas)**: What in this design is legally
   exposed, over-built, or missing relative to §§ 12-12-1801–1808, public
   records law, and evidence handling?
3. **Feasibility**: A 26k-person city's police department and a volunteer
   commission must run this. What breaks first operationally?
4. **The demo**: The council demo hinges on the tamper test and the
   wrong-state verification story. What will a skeptical council member
   or resident ask that this demo does NOT answer?
5. **One change**: If you could force exactly one change before this goes
   in front of the council, what is it?

Rules: cite the specific component by name when you criticize it. If a
part is sound, say so in one line and move on. Do not invent facts about
Cabot beyond what is above.
