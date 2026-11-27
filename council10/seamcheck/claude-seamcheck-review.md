# Seam-check seat review — Claude (Opus 5.5, Medium per the interface)

Seat: Claude, seated Nov 26, 2026 by Corey's direction ("you're free to use
claude"). Chat: https://claude.ai/chat/1ca45bd5-be10-4922-a131-ddbf61a82c5a
Runtime: 23:17–23:37 CST (browser-measured). Model/effort as shown in the
UI: **Opus 5.5, Medium** (verified in the model menu and the finished
chat's bottom bar). The seat's own report line says "low effort setting" —
that self-report is wrong against the interface and is preserved below for
the record; the operator-observed values govern, per standing rule.
Seat's probe bundle: noctua128-seamcheck.zip (REPORT.md, HANDOFF.md,
run-next.sh, probes/) produced in the chat.

---

NOCTUA 1.2.8: bounded seam-check report (Claude executing seat)

I ran every probe against the live 1.2.8 server: two seam defects (C2 and
P2), one ambiguous result for the chair (P1), and the other eleven hold.

Model and effort: Claude Opus 5.5 (claude-opus-5-5), low effort setting.
[Chair note: effort self-report contradicted by the interface — Medium.]

Setup:

Code: the server ran from the unmodified 02-janus128.py and
03-sentinel128.py.
Harness: the pack doesn't include run_t125_cases.py, checkpoint.py,
hotlist_sync.py or a janus127 tree, so I built a small replacement harness.
Checkpoints are signed with sentinel's own signing helper: the install's
key for good checkpoints, a foreign key for disagreements.
Expired listings go inactive through the server's own deactivation on
first sighting.
Ceremony state uses the W-battery pattern: seed with lab mode on, then
reboot the same folder with lab mode off.
C4 uses real provisioning: active TOTP enrollments and live codes on every
request.
No baseline: there was no janus127 to diff against, so "same as 1.2.7"
means compared with the shapes in the chair's C01 record.

Promotion seams

P1 — AMBIGUOUS. After promotion records disagreement X, a different
disagreement Y (with X removed) leaves the record byte-identical: same
bad_ids, same detected, and no chain entry names Y.

Fence: cleaning the file leaves the fence standing (503), so nothing
unaccepted ever auto-cleared.
Accept (P1b): a two-key accept done while the file holds only Y gave
X_accepted: false, Y_accepted: true. When X came back it fenced again.
The brief's two questions: the record does not track the latest
disagreement. Clearing does not require the new ids to be covered:
auto-clear checks only the old ids, and the accept takes whatever is in
the file at that moment.
Gap: the two keys can permanently accept a checkpoint (Y) that neither the
record nor /health ever showed them. The fence invariant holds; the chair
decides whether "the record tracks the live disagreement" is also an
invariant.

P2 — SEAM DEFECT (fails closed, low severity). With the stored fence
record made unparseable:

A real disagreement gets no record and no chain entry.
/health returns 500 (Unterminated string…).
Both accept keys get 409 "mismatch is unknown … must be repaired, not
accepted".
Repairing the file still gives 503, and so does a restart.

The fence is permanently stuck with no working way out. The only remedy the
system names (repair) does nothing, and the health page you'd diagnose it
from is down. This state is only reachable through database corruption or
tampering.

P3 — HOLDS, but not in the shape the brief expected. A disagreement already
accepted by two keys is filtered out before the record is touched. So no
promotion is chained, and the fence auto-clears under the file-state
reason. That's not laundering, because the acceptance is already in the
chain. In the mixed case (accepted X plus unaccepted Y), only Y is
promoted, and the fence stays up after Y is removed.

P4 — HOLDS. 16 more seconds of evaluations plus a restart left exactly one
promotion entry in the chain, the record unchanged, and the chain
verifying.

P5 — HOLDS (the key seam). After promotion, each of these left the fence at
503 with reason checkpoint_disagreement and unchanged bad_ids:

a torn line with X still present
a torn line with X gone
the checkpoints file deleted
the file replaced by a directory (unreadable)
the file repaired to clean
a restart on the clean file

The record never falls back to a file-state reason.

P6 — HOLDS.

A record created at boot is promoted by the first live evaluation.
A record created live is promoted by the boot evaluation itself.

Ceremony seams

C1 — HOLDS. These all returned the identical 201
{"result": "suppression placed"}, each adding one chain entry:

a plate with three historical variants
a plate with no reads
a plate with only an exact-match read
raw input written as a variant (cab-123)
re-placing an existing order

C2 — SEAM DEFECT. Hit-scope hold responses are byte-identical across every
leg I tried. But in ceremony the same key-only supervisor can place a
case-scope hold, and that response returns hold_id from the shared counter.
Placing one after each hit-scope attempt shows what actually happened:

hit-scope attempt | gap to next case-scope hold_id | /audit/root entries change
real hit, its own case | 2 | +1
nonexistent id | 1 | 0
real hit, wrong case | 1 | 0
real unverified hit | 2 | +1

Either channel tells the supervisor whether a hit exists and which case a
verified hit stands on. That brings back both disclosures fix 3 removed,
including the case-number leak.
Severity limit, which I also ran: in ceremony this same supervisor can
already read the audit chain. Its alert entries and case-reference
comparisons expose those facts anyway. So the oracle adds no new fact, but
it does break the uniformity fix 3 claims.
Reproduce with python3 probes/c_ceremony.py c2.

C3 — HOLDS. I tried both release endpoints with every path and method
variant I could think of:

Refused (503): query string, fragment, ;x, a doubled leading slash, and an
absolute URL.
No route (404): trailing slash, /./, upper case, %2F, DELETE and GET.
Unsupported method (501): PUT, PATCH, HEAD and OPTIONS.
Other callers: the second supervisor's confirm got 503; the jobs and ingest
roles got 403.

No request succeeded, and both protections stayed in place.

C4 — HOLDS. After real provisioning (provisioned, /hits 200):

Suppression: the near-match warning list is back.
Holds: a real hit gives 201 with hold_id, a missing hit gives 404, and a
wrong case gives 400 naming the hit's case.
Releases: the hold release and the two-key suppression release both succeed.
Fence: no ceremony refusals were chained, so nothing sticky is left over.

G1 seams

G1a — HOLDS. Resubmitting while pending chains new, then pending_updated
twice. There's one row, one queue entry, and the same 202 every time. The
swept-but-pending shape (set up directly in the database) also gives
pending_updated.

G1b — HOLDS. A supervisor re-adding an inactive row gets 201 added. The
row goes live and the chained entry has no effect field. The next sighting
raises an alert.

G1c — HOLDS. On reactivation, the resubmission's category, submitter and
expiry win, and the chain's reactivated / felony_warrant matches the row.
A sighting while pending creates no hit. A protected plate is reactivated
to pending, then its approval is refused and the row removed.

One difference from 1.2.7, not an invariant break: reactivation overwrites
the original listing's submitter and category in the row (the chain keeps
the history), and a reject then deletes the row where 1.2.7 left it for
retention.

G1d — HOLDS. A different case number, or a different state, creates a
fresh pending row with effect new. The inactive row is untouched.

Out of scope, noted
In ceremony, a key-only supervisor can read /audit, whose alert hit ids and
case-reference comparisons expose hit existence and hit-to-case links
whatever the hold endpoint answers.

Bottom line

Seam defects: C2, P2 (P1 ambiguous, for the chair).

To re-run everything, unzip next to the 1.2.8 tree/ folder and run
./run-next.sh (about 12 minutes). The handoff file is current.

Files are in noctua128-seamcheck.zip: REPORT.md, HANDOFF.md, run-next.sh,
probes/ (harness, probe scripts, raw results, run logs)
