#!/usr/bin/env python3
"""NOCTUA user provisioning — the only supported way to edit users.json.

    python3 provision.py add-user det.okafor detective
    python3 provision.py disable-user ofc.chen
    python3 provision.py enable-user ofc.chen
    python3 provision.py rotate-key det.okafor
    python3 provision.py list-users

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
    a = ap.parse_args()

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


if __name__ == "__main__":
    main()
