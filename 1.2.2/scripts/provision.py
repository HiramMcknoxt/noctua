#!/usr/bin/env python3
"""NOCTUA user provisioning — the only supported way to edit users.json.

    python3 provision.py add-user det.okafor detective
    python3 provision.py disable-user ofc.chen
    python3 provision.py enable-user ofc.chen
    python3 provision.py rotate-key det.okafor
    python3 provision.py list-users
    python3 provision.py pin-audit-key --db /data/noctua.db \
        --fingerprint <sha256-of-key> --confirm

pin-audit-key is the 1.2.2 (Q3) upgrade ceremony for a deployment
whose audit key lived only in the NOCTUA_AUDIT_KEY environment
variable: Janus 1.2.2 refuses to boot an env-only key over an
existing UNPINNED chain unless the key VERIFIES against keyed
references the chain already holds (a suppression's plate_ref
recomputed from its stored plate text, under the current or the
1.1 legacy formula) or a ceremony record is on file. This command
checks the candidate key against those references, confirms its
SHA-256 equals the --fingerprint a second operator verified
out-of-band, writes the key file (<db>.audit_key, 0600), and
records the ceremony in the database's meta table. Janus pins the
key at its next boot and chains KEY_PINNED.

add-user and rotate-key generate a fresh key, print the RAW KEY EXACTLY
ONCE (hand it to the named individual in person; it is never stored and
cannot be recovered), and store only its SHA-256 — the same hash Janus
checks at auth time. There are no shared accounts: the username must be
a named individual (or a service identity: the ingest identity, role
ingest; the maintenance identity, role jobs; a Compact partner agency,
role partner), and the
provisioning log line this tool prints is your issuance record — Janus
reloads users.json on mtime change, so changes take effect without a
restart.

Users file: --users PATH, else $NOCTUA_USERS, else /config/users.json.
Writes are atomic (temp file + rename, 0600) so a crash mid-write can
never leave Janus reading a torn file — Janus keeps its last good copy
if the file ever fails to parse.
"""
import argparse
import hashlib
import json
import os
import secrets
import sys

# 1.1: 'system' is RETIRED (item 8) — split into 'ingest' (POST /reads
# only) and 'jobs' (POST /heartbeat only). 'partner' is a Compact
# member agency's identity (items 21-22). Service roles can move data;
# they can never read it (item 23).
# 1.2 (S9): 'chain_auditor' — the Compact cross-audit identity. It can
# read ONLY /audit, /audit/root, /audit/verify, /audit/range and
# GET /compact/checkpoint, and has no write surface at all. Issue one
# of these to each Compact partner for their compact.py runs.
ROLES = ("detective", "patrol", "supervisor", "auditor",
         "chain_auditor", "ingest", "jobs", "partner")


def sha(txt):
    return hashlib.sha256(txt.encode()).hexdigest()


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save(path, users):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def find(users, name):
    for u in users:
        if u["user"] == name:
            return u
    return None


def issue_key(users, name):
    key = secrets.token_hex(24)
    find(users, name)["key_sha256"] = sha(key)
    print(f"RAW KEY for {name} — shown ONCE, store it nowhere, "
          f"hand it to the individual in person:\n  {key}")
    return key


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--users", default=os.environ.get(
        "NOCTUA_USERS", "/config/users.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add-user"); p.add_argument("name"); p.add_argument("role", choices=ROLES)
    p = sub.add_parser("disable-user"); p.add_argument("name")
    p = sub.add_parser("enable-user"); p.add_argument("name")
    p = sub.add_parser("rotate-key"); p.add_argument("name")
    sub.add_parser("list-users")
    p = sub.add_parser("pin-audit-key")
    p.add_argument("--db", required=True)
    p.add_argument("--fingerprint", required=True,
                   help="SHA-256 hex of the audit key, confirmed "
                        "out-of-band by a second operator")
    p.add_argument("--key-file",
                   help="file holding the candidate key (default: "
                        "NOCTUA_AUDIT_KEY, else <db>.audit_key)")
    p.add_argument("--confirm", action="store_true",
                   help="required: the fingerprint was confirmed "
                        "out-of-band by a second operator")
    a = ap.parse_args()

    if a.cmd == "pin-audit-key":
        return pin_audit_key(a)
    users = load(a.users)
    if a.cmd == "add-user":
        if find(users, a.name):
            sys.exit(f"refusing: user {a.name} already exists "
                     f"(use rotate-key to reissue)")
        users.append({"user": a.name, "role": a.role,
                      "key_sha256": ""})
        issue_key(users, a.name)
        save(a.users, users)
        print(f"added {a.name} ({a.role}) to {a.users}")
    elif a.cmd == "disable-user":
        u = find(users, a.name)
        if not u:
            sys.exit(f"no such user: {a.name}")
        u["disabled"] = True
        save(a.users, users)
        print(f"disabled {a.name} — Janus will refuse their key on the "
              f"next request")
    elif a.cmd == "enable-user":
        u = find(users, a.name)
        if not u:
            sys.exit(f"no such user: {a.name}")
        u.pop("disabled", None)
        save(a.users, users)
        print(f"enabled {a.name}")
    elif a.cmd == "rotate-key":
        u = find(users, a.name)
        if not u:
            sys.exit(f"no such user: {a.name}")
        issue_key(users, a.name)
        save(a.users, users)
        print(f"rotated key for {a.name} — the old key stops working on "
              f"the next request")
    elif a.cmd == "list-users":
        if not users:
            print("(no users)")
        for u in users:
            print(f"{u['user']:<22} {u['role']:<11} "
                  f"{'DISABLED' if u.get('disabled') else 'active':<9} "
                  f"key sha256 {u['key_sha256'][:12]}…")


def pin_audit_key(a):
    import hmac as hmac_mod
    import sqlite3
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), ".."))
    import sentinel
    if not a.confirm:
        sys.exit("refusing: --confirm is required — the fingerprint "
                 "must be confirmed out-of-band by a second "
                 "operator before a key is pinned (Q3)")
    if not os.path.exists(a.db):
        sys.exit(f"no such database: {a.db}")
    if a.key_file:
        key = open(a.key_file).read().strip()
    elif os.environ.get("NOCTUA_AUDIT_KEY"):
        key = os.environ["NOCTUA_AUDIT_KEY"]
    elif os.path.exists(a.db + ".audit_key"):
        key = open(a.db + ".audit_key").read().strip()
    else:
        sys.exit("no candidate key: set NOCTUA_AUDIT_KEY or pass "
                 "--key-file")
    fp = hashlib.sha256(key.encode()).hexdigest()
    if fp != a.fingerprint.strip().lower():
        sys.exit("refusing: the candidate key's SHA-256 (%s) does "
                 "not equal --fingerprint — wrong key or wrong "
                 "fingerprint" % fp)
    # Verify-don't-proxy (Q3): recompute the keyed references the
    # database already holds, under the current formula AND the
    # 1.1 legacy formula, and count how many the candidate matches.
    db = sqlite3.connect(a.db)
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    checked = matched = 0
    if "suppressions" in tables:
        for plate, state, ref in db.execute(
                "SELECT plate, state, plate_ref FROM suppressions "
                "WHERE plate IS NOT NULL AND plate != ''").fetchall():
            legacy = "pref:" + hmac_mod.new(
                key.encode(), ("PLATE|" + (state or "")).encode(),
                hashlib.sha256).hexdigest()[:24]
            checked += 1
            if ref in (sentinel.plate_ref(key, plate), legacy):
                matched += 1
    if "audit" in tables and "tier3_requests" in tables:
        chain_refs = set()
        for (payload,) in db.execute("SELECT payload FROM audit"):
            try:
                ref = json.loads(payload).get("plate_ref")
            except ValueError:
                ref = None
            if ref:
                chain_refs.add(ref)
        frags = set()
        for (frag,) in db.execute(
                "SELECT DISTINCT plate_fragment FROM tier3_requests "
                "WHERE plate_fragment IS NOT NULL AND "
                "plate_fragment NOT LIKE 'pref:%'").fetchall():
            frags.add(frag)
        for (frag,) in db.execute(
                "SELECT DISTINCT fragment FROM case_searches WHERE "
                "fragment IS NOT NULL AND fragment NOT LIKE "
                "'pref:%'").fetchall():
            frags.add(frag)
        for frag in frags:
            checked += 1
            if sentinel.frag_ref(key, frag) in chain_refs:
                matched += 1
    if checked and matched < checked:
        db.close()
        sys.exit("refusing: the candidate key verifies %d of %d "
                 "stored keyed references — it is not the key this "
                 "chain was written with" % (matched, checked))
    method = ("verified:%d" % checked) if checked else "ceremony"
    db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY "
               "KEY, value TEXT)")
    db.execute("INSERT INTO meta(key, value) VALUES(?,?) ON "
               "CONFLICT(key) DO UPDATE SET value=excluded.value",
               ("key_pin_ceremony", json.dumps(
                   {"fingerprint": fp, "method": method,
                    "ts": sentinel.now_iso()}, sort_keys=True)))
    db.commit()
    db.close()
    kf = a.db + ".audit_key"
    if not os.path.exists(kf):
        with open(kf, "w") as f:
            f.write(key)
        os.chmod(kf, 0o600)
    print("audit key pinned by %s: fingerprint %s recorded; key "
          "file at %s (0600). Janus will chain KEY_PINNED at its "
          "next boot." % (method, fp, kf))


if __name__ == "__main__":
    main()
