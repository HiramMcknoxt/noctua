# NOCTUA 1.2.8 — Bounded Seam-Check: Chair's Note and Rulings

Nov 26, 2026. Commissioned by Corey after convergence ("bounded seam-check
on the five fixes"), executed by a Claude seat (Opus 5.5, Medium as shown
in the interface; the seat's self-reported "low effort" line is contradicted
by the interface and disregarded per standing rule), and independently
reproduced by the chair's verifier with its own harness against a
byte-identical scratch copy of janus128. Records:
`claude-seamcheck-review.md` (seat), `CHAIR-VERIFICATION.md` (chair
verification, with re-runnable probes).

## Result in one line

Eleven of fourteen probes HOLD — including P5, the key seam: after a
promotion, the record never regresses to a file-state reason across torn
lines, deletion, an unreadable file, repair, and restart. Three findings
were confirmed by independent reproduction. **Convergence stands**; all
three go on the register as the head of the 1.2.9 pilot-hardening list.

## The findings

**C2 — CONFIRMED seam defect (register, fix in 1.2.9).** Fix 3's uniformity
is scoped to `ceremony and scope == "hit"` (janus.py:5605). In ceremony, a
case-scope hold returns a `hold_id` drawn from the shared counter that
placed hit-holds also consume (INSERT at janus.py:5591), so the gap
between successive case-scope hold_ids — reproduced exactly: 2 / 1 / 1 / 2
across the seat's four legs — tells a key-only supervisor whether the
preceding hit-scope attempt placed a hold, and legs 1 vs 3 leak which case
a verified hit stands on. This breaks the uniformity fix 3 claims. The
seat's severity limit also stands: in ceremony that same supervisor can
already read the same facts in the audit chain, so the oracle discloses
nothing new to anyone — it is a claim-consistency defect, not a new
disclosure channel. Fix direction: ceremony responses carry no hold_id for
any scope (or case-scope placement is ceremony-fenced like the releases).

**P2 — CONFIRMED seam defect (register, fix in 1.2.9).** If the stored
`anchor_mismatch` meta value itself is unparseable, the system has no
working remedy: the promotion branch parses the prior record to {} and
no-ops (janus.py:2305–2330), /health 500s on an unguarded `json.loads`
(janus.py:9537–9538), the accept path refuses with "must be repaired, not
accepted" (janus.py:6207), and neither repairing the checkpoints file nor
restarting clears the fence — the clean-eval path reads the corrupt
record's reason as "", which matches no clearing branch (janus.py:2255–
2270). It fails closed throughout (nothing is ever served past the fence),
and the state is reachable only through database corruption or tampering.
Fix direction: an unreadable fence record becomes a NAMED state — /health
reports it without throwing, and a chained supervisor repair action resets
the record to a fresh evaluation. A system whose core promise is "never
silent" must not have a state it cannot name.

**P1 — CONFIRMED as described; the chair rules it a register defect
(record-fidelity), not a convergence defect.** After promotion records
disagreement X, replacing X with a different foreign checkpoint Y leaves
the record byte-identical — Y appears in neither the record nor /health —
yet a two-key accept performed while only Y is present succeeds and chains
`anchor_accepted_ids = [Y]`: the accept gate reads only the record's
reason (janus.py:6207) while the confirm leg computes the accepted ids
from the live file (janus.py:6258–6259). Why this is not V5 again: nothing
clears silently — the fence stands until a human act, and that act IS
chained with the exact ids accepted, so the record of what happened is
complete after the fact. What is defective is the presentation before the
fact: the acceptors are never shown the live ids they are about to accept
when the disagreement has changed under a standing fence. The mechanism's
purpose is informed acceptance, and a changed disagreement should re-enter
the record (a fresh promotion/update entry when live bad_ids differ from
the recorded ones) and be what the confirm step displays. Fix in 1.2.9,
alongside C2 and P2.

## Disposition

- Convergence at 1.2.8 under criteria 1–4 is unchanged. None of the three
  findings is a silent clear, an unauthorized disclosure to a party who
  could not already read the facts, or a fail-open path.
- The 1.2.9 hardening list now opens with: C2 (ceremony hold_id
  uniformity, all scopes), P2 (named unreadable-record state + working
  repair), P1 (record tracks the live disagreement; confirm displays live
  ids) — ahead of the Round 10 register items (G5(ii)/(iii), G2, Q10-9,
  Q10-1, LAB health-honesty, and the rest of synthesis §5).
- 1.2.9 is pilot-hardening work, built and verified the same way, in the
  pilot phase — it does not gate the UI, the whole-system QA, or the
  documents, and it will be council-checked the same bounded way if Corey
  directs.

— Vesper, chair
