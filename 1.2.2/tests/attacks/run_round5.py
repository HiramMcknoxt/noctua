#!/usr/bin/env python3
"""Wrapper runner for the in-tree round-5 (Claude seat 1) attack
suite, including the re-aimed A18 anonymous-scan scenario.

Runs every r5_*.py against the tree named by --tree (default: the
janus122 tree this suite ships in) via NOCTUA121_TREE, with
NOCTUA11_TREE pointed at the in-tree 1.1 fixture. Every expected
scenario id must print a verdict; silence is a HARNESS FAILURE.
Expected on a fixed tree: every scenario NOT REPRODUCED.
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, "round5")
EXPECTED = ["R5-01", "R5-02", "R5-03a", "R5-03b", "R5-03c", "R5-04",
            "R5-05a", "R5-05b", "R5-06", "R5-07", "R5-08", "R5-09",
            "R5-10", "R5-11", "R5-12", "R5-13", "R5-14", "R5-15",
            "R5-16", "R5-17", "A18"]


def main():
    tree = (sys.argv[1] if len(sys.argv) > 1
            else os.path.abspath(os.path.join(HERE, "..", "..")))
    tree11 = os.path.join(tree, "tests", "fixtures", "janus11")
    env = dict(os.environ, NOCTUA121_TREE=tree, NOCTUA11_TREE=tree11)
    verdicts = {}
    harness_failures = []
    for path in sorted(glob.glob(os.path.join(SUITE, "r5_*.py"))):
        fn = os.path.basename(path)
        p = subprocess.run([sys.executable, path], env=env,
                           capture_output=True, text=True,
                           timeout=1800)
        found = re.findall(r"(NOT REPRODUCED|REPRODUCED)\s+(\S+)",
                           p.stdout)
        if p.returncode != 0:
            harness_failures.append(
                "%s exited %d" % (fn, p.returncode))
        if not found:
            harness_failures.append("%s printed no verdicts" % fn)
        for verdict, fid in found:
            verdicts[fid] = verdict
        sys.stdout.write(p.stdout)
        if p.stderr:
            sys.stderr.write("[%s stderr]\n%s\n" % (fn, p.stderr))
    missing = [a for a in EXPECTED if a not in verdicts]
    if missing:
        harness_failures.append("silent scenarios: %s"
                                % ", ".join(missing))
    reproduced = sorted(a for a, v in verdicts.items()
                        if v == "REPRODUCED")
    print("=" * 60)
    print("ROUND-5 SEAT-1 SUITE vs %s" % tree)
    print("verdicts: %d  reproduced: %s" % (len(verdicts), reproduced))
    print("harness failures: %s" % (harness_failures or "none"))
    ok = not harness_failures and not reproduced
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
