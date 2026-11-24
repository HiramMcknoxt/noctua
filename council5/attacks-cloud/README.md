# NOCTUA council round 5 — attack suite (Claude cloud seat)

Adversarial checks against NOCTUA 1.2.1, written outside the build.
Every check prints one line: `REPRODUCED <id>` (the defect is real on
the shipped code) or `NOT REPRODUCED <id>`. A script that dies prints
`ERROR` and fails the run — a silent verdict is a harness failure,
never a pass (the round-5 ruling on round 4's eight silent verdicts).

```
NOCTUA121_TREE=/path/to/noctua/1.2.1 \
NOCTUA11_TREE=/path/to/noctua/1.1 bash run_all.sh
```

Reuses the builders' helpers (`tests/run_tests.py`: Instance, req,
sign, post_audit_result, post_receipt, run_checkpoint) unmodified, so
each attack runs against exactly the shipped code. R5-01 and R5-13 boot
the repo's real `1.1/janus.py` first and upgrade its database in place
(the key-file shape the builders bless for P4/A28). Loopback ports
19201-19299; temp dirs only. Python 3.12+, openssl, bash.

| ID | Script | Defect |
| --- | --- | --- |
| R5-01 | r5_legacy_suppression.py | 1.1 protection orders void for every keyed check after the upgrade |
| R5-02 | r5_hotlist_expiry.py | US-format / epoch expiry disables a hot-list entry at first sighting |
| R5-03a/b/c | r5_supersede.py | supersede path deletes stolen-plate alerts |
| R5-04 | r5_evidence_deadend.py | exported bundle undestroyable after its hit's 150-day purge |
| R5-05a/b | r5_parity.py | purge vs check disagree; /health never green; cap enforced late |
| R5-06 | r5_gate_order.py | older pass filed after a failure reopens the Compact gate |
| R5-07 | r5_rotation_grind.py | publisher still chooses who audits whom (A14c re-aimed) |
| R5-08 | r5_gates.py | auditor's emergency review blind and pre-emptable |
| R5-09 | r5_gates.py | holds with no case, by detectives, released by one supervisor |
| R5-10 | r5_gates.py | case list never goes stale by age |
| R5-11 | r5_gates.py | Tier 3 executes on basis_type "other" |
| R5-12 | r5_minor.py | INGEST_REJECTED chains raw caller text, unthrottled |
| R5-13 | r5_minor.py | wrong key in the key file pinned over an unpinned chain |
| R5-14 | r5_minor.py | restore deletes the key copies it moved aside |
| R5-15 | r5_minor.py | hyphenated fragment misses canonical plates |
| R5-16 | r5_minor.py | stale Tier 3 request reaches the approver blank, still executes |
| R5-17 | r5_restore_envkey.py | self-HMAC'd backup restores attacker accounts on env-key hosts |

`results-2026-11-24.log` is the run against commit 80d3715 (1.2.1):
17 of 17 REPRODUCED.
