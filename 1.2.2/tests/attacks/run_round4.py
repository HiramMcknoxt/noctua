#!/usr/bin/env python3
"""Wrapper runner for the in-tree round-4 attack suite.

Runs every attack*.py against the tree named by --tree (default:
the janus122 tree this suite ships in) via the suite's own
NOCTUA12_TREE convention, collects every VERDICT line, and fails
loudly if any scenario is silent (a file that prints no verdict
for an expected scenario is a HARNESS FAILURE, not a pass).

Expected on a fixed tree: every scenario NOT REPRODUCED except
A9b, whose CONFIRMED is the contrast control (the defense working:
the tamper was DETECTED). A27 is the negative control and must be
NOT REPRODUCED.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, "round4")
FILES = ["attack1.py", "attack2.py", "attack2b.py", "attack3.py",
         "attack4.py", "attack5.py"]
EXPECTED = ["A1", "A1b", "A2", "A2b", "A3", "A4", "A5", "A6a",
            "A6b", "A7", "A8", "A9", "A9b", "A10", "A11", "A12",
            "A13", "A14a", "A14b", "A14c", "A15", "A16", "A17",
            "A18", "A19", "A19b", "A20", "A21", "A21b", "A23",
            "A24", "A25", "A26", "A27", "A28", "A29", "A30", "A34",
            "A35", "A36", "A37"]
ALLOWED_CONFIRMED = {"A9b"}


def main():
    tree = (sys.argv[1] if len(sys.argv) > 1
            else os.path.abspath(os.path.join(HERE, "..", "..")))
    env = dict(os.environ, NOCTUA12_TREE=tree)
    verdicts = {}
    harness_failures = []
    for fn in FILES:
        p = subprocess.run([sys.executable, os.path.join(SUITE, fn)],
                           env=env, capture_output=True, text=True,
                           timeout=1800)
        found = [(aid, verdict) for verdict, aid in re.findall(
            r"^(CONFIRMED|NOT REPRODUCED)\s+(A[0-9]+[a-z]?)\b",
            p.stdout, re.M)]
        # A file's own exit code reflects its CONFIRMED tally
        # (A9b CONFIRMED is the expected contrast control), so it
        # is not a harness signal. Harness failure = silence or a
        # traceback.
        if "Traceback" in p.stderr:
            harness_failures.append("%s raised a traceback" % fn)
        if not found:
            harness_failures.append("%s printed no verdicts" % fn)
        for aid, verdict in found:
            verdicts[aid] = verdict
        sys.stdout.write(p.stdout)
        if p.stderr:
            sys.stderr.write("[%s stderr]\n%s\n" % (fn, p.stderr))
    missing = [a for a in EXPECTED if a not in verdicts]
    if missing:
        harness_failures.append("silent scenarios: %s"
                                % ", ".join(missing))
    confirmed = sorted(a for a, v in verdicts.items()
                       if v == "CONFIRMED")
    unexpected = [a for a in confirmed if a not in ALLOWED_CONFIRMED]
    print("=" * 60)
    print("ROUND-4 SUITE vs %s" % tree)
    print("verdicts: %d  confirmed: %s" % (len(verdicts), confirmed))
    print("harness failures: %s" % (harness_failures or "none"))
    print("unexpected CONFIRMED: %s" % (unexpected or "none"))
    ok = not harness_failures and not unexpected
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
