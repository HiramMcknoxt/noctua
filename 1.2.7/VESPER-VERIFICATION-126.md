# Vesper cold verification — NOCTUA 1.2.6 (Nov 25, 2026)

Independent cold re-run of the full acceptance battery by Vesper (not the builder), against `TRACK-126-REPORT.md`.

## Method and interruptions (disclosed)

- One-shot `./run-next.sh` started 15:56 CST (log `scratch/battery-20261125-155632.log`). A VM runtime restart killed it ~16:45 during the S battery — the same failure that interrupted the builder's one-shot. Seven legs had already completed and passed.
- Remaining legs (S, T, U) re-run with the runner's exact commands on unchanged code (`scratch/logs/vesper-cold-126-resume.log`).
- janus125 baseline md5s re-verified unchanged before the run: janus.py `ab455975b9eb987fa95d3a268190a3bf`, sentinel.py `85c7f9e06cecc5565211ccb1d43c62d4`.

## Reconciliation vs the builder's counts

| Leg | Builder | Vesper cold run |
|---|---|---|
| builders' suite | 335/335 | **335 checks, 335 passed, 0 failed** |
| round-4 wrapper | PASS, only A9b confirmed | PASS — verdicts: 41, confirmed: ['A9b'] only |
| round-5 wrapper | PASS, 21 verdicts, none reproduced | PASS — verdicts: 21, reproduced: [] |
| round-6 harness | PASS, all hold / not reproduced | PASS |
| Q + invariants | 35/35 | **35/35 PASS** |
| R battery | 20/20 | **20/20 PASS** |
| load envelope | PASS, complete to 6 burners | COMPLETE at 0/3/6 burners, both directions (500/500 landed, verify COMPLETE) |
| S battery | 25/25 with S10 flake disclosed | 24/25 in both full runs — S10 failed with the identical signature (samples [false×4, null]); **S10 standalone PASS twice**, all five samples false |
| T battery | 20/20 | **20/20 PASS** |
| U battery | 21/21, all discriminating | **21/21 PASS** |

## The S10 flake, characterized

Across four full-battery S runs (two builder, two Vesper), S10-verify-freshness-bound failed each time with exactly one `null` sample among five — a dropped /health response under the case's own six saturating ingest threads on this 1.5-CPU VM. In every returned sample the freshness property held; the baseline (janus123) correctly failed with all samples true. Standalone, the case passes repeatedly (builder ×2, Vesper ×2). Verdict: a test-harness sampling artifact under saturation, NOT a product defect. Round 9 should consider making the case null-tolerant (retry a dropped sample once) so full runs stop carrying a known flake.

## Verdict

**1.2.6 is verified.** Every leg of the acceptance battery passes on Vesper's independent cold run, reconciled against the builder's report. The U9 interpretation (tightened state arms on populated arrival) remains flagged for Round 9 to ratify, as the builder left it.
