# NOCTUA — Releases index

**Every version listed here is a DEVELOPMENT BUILD — NOT DEPLOYMENT-READY.**
No version in this repository is approved for deployment or for operating a
live ALPR system. Successive hostile-review rounds found real vulnerabilities
in successive versions; those findings are documented in the round syntheses
linked below. Independently of code state, a non-waivable independent
penetration test of the deployed pilot is required before any camera goes
live, alongside the policy, ACIC, Citizens Commission, and Council
authorization gates described in the [README](README.md).

"Verification" means an independent cold re-run of the full acceptance
battery by the orchestrator (Vesper), separate from the builder's own run.

| Version | Date | Battery result | Verification status | Reviewed by |
|---|---|---|---|---|
| [1.0](1.0/) | Nov 24, 2026 | 125/125 | Build verified | [Round 2](council2/) |
| [1.1](1.1/) | Nov 24, 2026 | Round-2 fixes (35 items) + Compact | Build verified | [Round 3](council3/) |
| [1.2](1.2/) | Nov 24, 2026 | 246 checks | Build verified | [Round 4](council4/) |
| [1.2.1](1.2.1/) | Nov 24, 2026 | 312/312 | Build verified | [Round 5](council5/) |
| [1.2.2](1.2.2/) | Nov 24, 2026 | 322/322 | Build verified | Round 6 — NOT CONVERGED |
| [1.2.3](1.2.3/) | Nov 24, 2026 | Builders' suite 332/332; full battery green | **VERIFIED** — independent cold re-run, exit 0 ([TRACK-123 report](1.2.3/TRACK-123-REPORT.md)) | Round 7 — NOT CONVERGED (lifecycle guarantees) |
| [1.2.4](1.2.4/) | Nov 25, 2026 | Builders' suite 332/332; R battery 20/20; full battery green | Verified as a build ([TRACK-124 report](1.2.4/TRACK-124-REPORT.md)) — **then Security Round 1 found a Critical: the new two-factor authentication failed open** | [Security Round 1](security-round/) — NOT CONVERGED |
| [1.2.5](1.2.5/) | Nov 25, 2026 | 335/335; T battery 20/20 (fail-closed 2FA rebuild, T1–T9) | **VERIFIED** — builder battery and independent cold re-run both fully green ([TRACK-125 report](1.2.5/TRACK-125-REPORT.md)) | [Round 8](council8/) — NOT CONVERGED |
| [1.2.6](1.2.6/) | Nov 25, 2026 | 335/335; U battery 21/21 | **VERIFIED** — independent cold re-run ([verification record](1.2.6/VESPER-VERIFICATION-126.md)); S-battery case S10 flake disclosed in the record (harness artifact; property held) | [Round 9](council9/) — NOT CONVERGED, unanimous 7 of 7 (register V1–V18, incl. 3 blockers) |
| [1.2.7](1.2.7/) | Nov 25–26, 2026 | 335/335; V battery 19/19 (all 19 cases fail on 1.2.6, pass on 1.2.7) | **VERIFIED** — independent cold one-shot battery, exit 0 ([verification record](1.2.7/VESPER-VERIFICATION-127.md)) | [Round 10](council10/) — NOT CONVERGED on criterion 2 (one branch: the V5 anchor-fence reason-promotion gap); the loop converged at 1.2.8 by addendum ([synthesis](council10/SYNTHESIS.md)) |
| [1.2.8](1.2.8/) | Nov 26, 2026 | Full battery **SUCCESS** (every leg PASS); W battery 6/6 (all six cases fail on 1.2.7, pass on 1.2.8) | **VERIFIED** — independent cold re-run by the chair ([verification record](1.2.8/VESPER-VERIFICATION-128.md); [build report](1.2.8/TRACK-128-REPORT.md)) | [Round 10](council10/) — **CONVERGED** under criteria 1–4 (convergence addendum to the [synthesis](council10/SYNTHESIS.md)). The code loop's final version. Still a development build — not deployment-ready |

## Draft specifications (not builds)

| Document | Status |
|---|---|
| [Prytaneum credentialing spec v0.1](credentialing/SPEC-v0.1.md) | DRAFT SPEC — NOT BUILT. Charter + technical mechanism for a credentialing foundation: 90-day timed certificates, renewal countersigned with foundation-side two-factor authentication, 3-of-5 threshold revocation, archive never held hostage, foundation-death orphan escape. |
| [ARGUS spec v0.2](argus/SPEC-v0.2.md) | DRAFT SPEC — NOT BUILT. Read-only advisory LLM monitor: holds no Janus credential, its output is never a daemon input, healing by a deterministic non-LLM policy daemon. Supersedes v0.1, which a security round rejected as written. |

## Reading the record

Each round folder holds the round's brief, the individual seat reviews, and
the chair's synthesis (with addenda). Seat-pack folders are not published —
they duplicate the code; the syntheses are the record. Battery logs are not
published; the build reports and verification records carry the results.
