"""NOCTUA council round 5 — attack harness (Claude cloud seat).

Reuses the builders' own helpers (Instance, req, sign, post_audit_result,
post_receipt, run_checkpoint) from the tree under test, unmodified, so
every attack runs against exactly the shipped 1.2.1 code. Each attack
prints one line per finding:

    REPRODUCED R5-xx <title> :: <evidence>       the defect is real
    NOT REPRODUCED R5-xx <title> :: <evidence>   it is not

Env: NOCTUA121_TREE = path to the 1.2.1 directory under test
     NOCTUA11_TREE  = path to the 1.1 directory (for upgrade attacks)
Ports used: 19201-19299 on loopback. All state lives in a temp dir.
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

TREE = os.path.abspath(os.environ.get("NOCTUA121_TREE", "1.2.1"))
TREE11 = os.path.abspath(os.environ.get("NOCTUA11_TREE",
                                        os.path.join(TREE, "..", "1.1")))
sys.path.insert(0, os.path.join(TREE, "tests"))
import run_tests as T  # noqa: E402  (builders' helpers, unmodified)

SCRIPTS = os.path.join(TREE, "scripts")
JANUS = os.path.join(TREE, "janus.py")
JANUS11 = os.path.join(TREE11, "janus.py")
DET, PAT, SUP, SUP2, AUD, CA, ING, JOB = (T.DET, T.PAT, T.SUP, T.SUP2,
                                          T.AUD, T.CA, T.ING, T.JOB)
KEYS = T.KEYS
req = T.req
sentinel = T.sentinel_mod
rotation = T.rotation_mod
RESULTS = []


def finding(fid, title, reproduced, evidence=""):
    RESULTS.append((fid, title, reproduced))
    tag = "REPRODUCED " if reproduced else "NOT REPRODUCED "
    print(tag + fid + " " + title
          + ((" :: " + json.dumps(evidence, default=str)[:900])
             if evidence != "" else ""))
    sys.stdout.flush()


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ago(**kw):
    return iso(datetime.now(timezone.utc) - timedelta(**kw))


def instance(name, port, **kw):
    return T.Instance(name, port, **kw)


def db(inst):
    return sqlite3.connect(inst.db)


def heartbeat_all(port):
    for job in T.JOBS:
        s, b = req(port, "POST", "/heartbeat", JOB,
                   {"job": job, "ok": True, "detail": "r5"})
        assert s == 200, b


def run_script(name, env, args=(), timeout=180):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, name),
                           *args], env=env, capture_output=True,
                          text=True, timeout=timeout)


def script_env(inst, **extra):
    env = dict(inst.env)
    env.update({"NOCTUA_JANUS_URL": inst.url, "NOCTUA_JOBS_USER": JOB,
                "NOCTUA_JOBS_KEY": KEYS[JOB]})
    env.update(extra)
    return env


def open_gate(B, A, agency="agency-a"):
    """Open B's share gate for partner `agency` exactly as the builders'
    suite does: register A's pubkey, B's auditor files a signed passing
    audit of A, B publishes a checkpoint, A posts a signed receipt."""
    s, b = req(B.port, "POST", "/compact/partners", SUP,
               {"agency": agency, "endpoint": A.url,
                "pubkey_pem": T.pub_pem(A.db), "agreement_ref": "MOU"})
    assert s == 201, b
    s, b = T.post_audit_result(B.port, B.db, agency, True)
    assert s == 201, b
    cp = T.run_checkpoint(B.db, B.url)
    s, b = T.post_receipt(B.port, A.db, agency, cp)
    assert s == 201, b
    return cp


def bridge(janus_url, port, secret="s3cret"):
    env = dict(os.environ, FRIGATE_BRIDGE_PORT=str(port),
               FRIGATE_BRIDGE_SECRET=secret, NOCTUA_JANUS_URL=janus_url,
               NOCTUA_INGEST_USER=ING, NOCTUA_INGEST_KEY=KEYS[ING])
    proc = subprocess.Popen([sys.executable,
                             os.path.join(SCRIPTS, "frigate_bridge.py")],
                            env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/health" % port,
                                   timeout=1)
            break
        except Exception:
            time.sleep(0.25)

    def event(body):
        r = urllib.request.Request(
            "http://127.0.0.1:%d/event" % port, method="POST",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "X-Bridge-Secret": secret})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read())
    return proc, event


def boot_script(script, env, port, d, probe_user=SUP):
    """Boot any Janus version on `port`; any HTTP answer means up
    (1.1 has no /ping)."""
    proc = subprocess.Popen([sys.executable, script], env=env,
                            stdout=open(os.path.join(d, "boot-%d.log"
                                                     % port), "a"),
                            stderr=subprocess.STDOUT)
    for _ in range(80):
        if proc.poll() is not None:
            break
        try:
            req(port, "GET", "/health", probe_user)
            return proc
        except Exception:
            pass
        time.sleep(0.25)
    try:
        proc.terminate()
    except Exception:
        pass
    raise RuntimeError("boot failed for %s (see %s)" % (
        script, os.path.join(d, "boot-%d.log" % port)))


def summary():
    n = len(RESULTS)
    r = sum(1 for _i, _t, rep in RESULTS if rep)
    print("\n==== %d findings checked, %d reproduced ====" % (n, r))
