# Project NOCTUA — Pilot Simulation

A working simulation of the Cabot Open-Source ALPR Pilot spec (Nov. 23, 2026),
built to test whether the design holds together at Cabot's **real** scan and
hit frequencies before anyone asks the Council for anything.

**Everything here is synthetic.** Plates, people, cases, and the hot list are
generated. No real data, no camera access, no hot-list access.

## The rates are Cabot's, not invented

Source: CPD figures in the Oct. 19, 2026 council packet History File
(audited Nov. 2026) — Jan. 1–Jun. 30, 2026, 9 cameras:

- 8,040,000 plates scanned · 688 matches · 7 stolen vehicles recovered · 19 arrests
- 4,935.5 scans / camera / day
- **Match frequency: 8.56 per 100,000 reads (1 per 11,686)** — used unscaled

Volume is scaled to **¼** (3 pilot cameras × 90 days ≈ 333k reads) so a run
finishes quickly and stays watchable. Frequency is never scaled.

Labelled simulation assumptions (not Cabot facts): OCR accuracy 94.5% weighted
(96% day / 91% night), hot list of 220 entries, wrong-state lookalikes at 0.18
per true hit pass, Tier 2 demand ≈ 6/day, Tier 3 applications ≈ 0.7/day with
an 85% grant rate, emergency Tier 3 ≈ 0.09/day, verified-hit records held
30 days, everything else deleted at 14 days.

## Two builds, same engine

1. **`noctua_sim.py`** — the auditable core (Python 3, stdlib only).
   `python3 noctua_sim.py` runs the full 90-day pilot in ~0.2 s and writes
   `simulation_report.json`. Implements: synthetic plate generator, OCR layer
   with confusable-character errors (0/O, 8/B, 1/I, 5/S, 2/Z, 6/G), hot-list
   matching on the *read* plate, verify-before-action (characters **and**
   state), the **Janus** front door (named accounts only, case numbers
   validated against open cases, Tier 3 locked without judicial
   authorization, emergency path logged), the **Sentinel** hash-chained
   append-only audit log with weekly root-hash publication to an outside
   witness and full re-verification, and the 14-day retention job.

2. **`index.html`** — the watchable version. Open it in any browser (no
   server needed). Same rates, same rules, plus: live camera panels, a
   **Verify It** game (you confirm/reject alerts — wrong-state and misread
   cards are mixed in; confirming one is scored as a bad stop), a
   **try-to-get-past-Janus** panel, a real SHA-256 Sentinel chain with a
   Verify Chain button, the retention window aging out day by day, and a
   day-90 report. The verification-card mix is deliberately enriched for
   practice; the background alert rate stays at Cabot's frequency.

## Audited Python run (seed 20261123, Nov. 23, 2026)

| Measure | Result |
|---|---|
| Simulated reads (¼ scale) | 333,033 (full-scale equivalent 1,332,132) |
| OCR accuracy observed | 94.52% |
| True hot-list passes | 28 (28.5 expected at Cabot's rate) |
| Observed match frequency | **8.41 per 100k** vs CPD's 8.56 |
| Alerts raised | 32 |
| Verified hits | 27 |
| Rejected at verification (right number, wrong state) | 5 |
| Hits lost to an OCR misread | 1 |
| Reads deleted by the 14-day retention job | 282,193 |
| Janus — Tier 2 OK / Tier 3 granted / denied / emergency | 541 / 56 / 8 / 6 |
| Janus — blocked: invalid case / no authorization / shared account | 41 / 15 / 5 |
| Sentinel log | 809 entries · 12 witness publications · **chain verified ✓** |

## What the simulation demonstrates

- **The quiet is the finding.** At Cabot's real frequency, a 3-camera pilot
  produces about one alert a day and long stretches of nothing. The system's
  real workload is deletion, logging, and saying no — not hits.
- **Verification is load-bearing.** Wrong-state lookalikes outnumber the
  OCR-miss losses; a number-only match would have sent officers after
  innocent drivers. State + characters, every time.
- **The controls get exercised even when nothing happens.** In 90 days Janus
  blocked 61 improper attempts and every one is in the chain; the retention
  job deleted 85% of everything the cameras ever saw.
- **Nothing here proves field accuracy.** OCR and demand rates are labelled
  assumptions. The pilot spec's hand-checked accuracy protocol (Appendix C)
  is how the real numbers get earned.
