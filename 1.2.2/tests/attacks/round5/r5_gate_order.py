"""R5-06: COMPACT.md: 'Any newer failing audit closes the gate
immediately — a pass from yesterday does not survive a failure from
this morning.' share_gate_missing (janus.py:1432-1441) and
/compact/reinstate (janus.py:3285-3288) read the latest row by FILING
ORDER (id DESC). P7 now stores the REPORT's own ts, but nothing orders
by it, nothing refuses a report older than the newest one on file, and
nothing refuses a report_hash already filed. So a pass generated
before a failure — a slow compact.py run whose POST lands late, or the
same signed body filed a second time — reopens a gate the failure
closed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def share(B):
    return req(B.port, "POST", "/share/query", "agency-a",
               {"agency": "agency-a", "tier": 2, "basis_type": "warrant",
                "why": "partner case", "case_ref": "LPD-2027-55",
                "plate_fragment": "ZZZ"})


def file_report(B, report, sig):
    return req(B.port, "POST", "/compact/audit-result", L.AUD,
               {"agency": "agency-a", "report": report, "report_sig": sig})


def signed(B, ok, ts):
    report = {"agency": "agency-a", "ok": ok, "ts": ts, "checks": {}}
    return report, L.T.sign(B.db, report)


def main():
    A = L.instance("r5-ga", 19250)
    B = L.instance("r5-gb", 19251)
    A.start()
    B.start()
    try:
        L.open_gate(B, A)
        s_open = share(B)[0]
        # 09:30 compact.py run passes and is filed.
        p_rep, p_sig = signed(B, True, L.ago(minutes=30))
        s_p1 = file_report(B, p_rep, p_sig)
        # 09:59 run finds agency-a's chain broken; failure filed.
        f_rep, f_sig = signed(B, False, L.ago(minutes=1))
        s_f = file_report(B, f_rep, f_sig)
        after_fail = share(B)
        # The 09:30 pass is posted again (a retry, a replay, anyone
        # holding the auditor credential and that signed body).
        s_p2 = file_report(B, p_rep, p_sig)
        after_refile = share(B)
        # Also: a pass generated 2h ago, never filed, delivered late.
        l_rep, l_sig = signed(B, True, L.ago(hours=2))
        s_f2 = file_report(B, f_rep, f_sig)    # gate closed again
        closed_again = share(B)[0]
        s_late = file_report(B, l_rep, l_sig)
        after_late = share(B)
        c = L.db(B)
        dupes = c.execute("SELECT report_hash, COUNT(*) FROM "
                          "compact_audits GROUP BY report_hash HAVING "
                          "COUNT(*) > 1").fetchall()
        c.close()
        s_list, b_list = req(B.port, "GET", "/compact/partners", L.SUP)
    finally:
        A.stop()
        B.stop()
    finding("R5-06", "after a FAILING audit closes the share gate, an "
            "OLDER passing report — the identical signed body re-posted, "
            "or a 2h-old pass delivered late — is accepted 201 and "
            "reopens the gate: 'latest' is filing order, not audit time, "
            "and duplicate report hashes are accepted",
            s_open == 200 and after_fail[0] == 403
            and s_p2[0] == 201 and after_refile[0] == 200
            and closed_again == 403 and s_late[0] == 201
            and after_late[0] == 200,
            {"share_open": s_open, "pass_filed": s_p1[0],
             "fail_filed": s_f[0], "share_after_fail": after_fail,
             "same_pass_refiled": s_p2, "share_after_refile":
                 after_refile[0], "fail_refiled": s_f2[0],
             "share_closed_again": closed_again,
             "late_2h_pass_filed": s_late[0],
             "share_after_late_pass": after_late[0],
             "duplicate_report_hashes": dupes,
             "partner_list": [
                 {k: x[k] for k in ("agency", "last_audit_ok",
                                    "last_audit_ts", "share_gate_open")}
                 for x in b_list.get("partners", [])]})


if __name__ == "__main__":
    main()
    L.summary()
