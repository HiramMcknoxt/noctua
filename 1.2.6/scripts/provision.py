#!/usr/bin/env python3
# VESPER · the evening watch
"""NOCTUA user provisioning — the only supported way to edit users.json.

    python3 provision.py add-user det.okafor detective
    python3 provision.py disable-user ofc.chen
    python3 provision.py enable-user ofc.chen
    python3 provision.py rotate-key det.okafor
    python3 provision.py list-users
    python3 provision.py pin-audit-key --db /data/noctua.db \
        --fingerprint <sha256-of-key> --confirm
    python3 provision.py enroll-2fa det.okafor --db /data/noctua.db

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
    p = sub.add_parser("enroll-2fa")
    p.add_argument("name")
    p.add_argument("--db", required=True)
    p.add_argument("--force", action="store_true",
                   help="overwrite even an ACTIVE enrollment "
                        "(still requires two-key confirmation "
                        "when another ACTIVE enrollment exists; "
                        "prefer Janus's two-key re-enrollment)")
    p.add_argument("--confirm-by",
                   help="1.2.5 (T8): the second operator — a "
                        "DIFFERENT account holding an ACTIVE "
                        "enrollment — confirming this enrollment "
                        "with their own TOTP code")
    p.add_argument("--confirm-code",
                   help="the confirming operator's current TOTP "
                        "code (validated against their enrollment; "
                        "the code is consumed)")
    p = sub.add_parser("unlock")
    p.add_argument("name")
    p.add_argument("--db", required=True,
                   help="the Janus database whose persisted lock "
                        "state is cleared")
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
    if a.cmd == "enroll-2fa":
        return enroll_2fa(a)
    if a.cmd == "unlock":
        return unlock(a)
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


def unlock(a):
    """1.2.6 (U1): the shell-side break-glass for the §10 account
    lockout. POST /auth/unlock needs a supervisor — when EVERY
    supervisor is locked (the C8-01 endgame), the HTTP surface
    has no exit at all. This clears the account's persisted lock
    state directly in meta and records the act in the provision
    marker; Janus honors the pending unlock on its next lock
    check (no restart needed) and chains ACCOUNT_UNLOCKED when it
    consumes the marker. Shell access to the database is the
    credential here — the same custody that can run restore.py —
    and the act is on the chain, not silent."""
    import sqlite3
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), ".."))
    import sentinel
    if not os.path.exists(a.db):
        sys.exit("refusing: no database at %s" % a.db)
    conn = sqlite3.connect(a.db, timeout=30)
    try:
        cur = conn.execute("DELETE FROM meta WHERE key=?",
                           ("auth_lock:" + a.name,))
        conn.commit()
        cleared = cur.rowcount > 0
    finally:
        conn.close()
    marker = a.db + ".provision_marker"
    with open(marker, "a") as f:
        f.write(json.dumps({
            "user": a.name, "by": "provision.py unlock",
            "action": "unlock",
            "ts": sentinel.now_iso()}) + "\n")
    try:
        os.chmod(marker, 0o600)
    except OSError:
        pass
    print("unlock recorded for %s (persisted lock state %s). "
          "A running Janus honors it on the next authentication "
          "attempt; the unlock chains as ACCOUNT_UNLOCKED when "
          "Janus consumes the provision marker."
          % (a.name, "cleared" if cleared else "was not present"))
    return 0


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
    # database already holds and count how many the candidate
    # matches. 1.2.3 (R3): the candidate set is sentinel's ONE
    # implementation (key_ref_candidates — the current formula
    # plus the 1.1 legacy formula over the plate AS STORED and
    # canonicalized). 1.2.2's copy here hashed the literal string
    # "PLATE|<state>" — a formula no version ever wrote with, so
    # the ceremony refused the CORRECT key on every real 1.1
    # database — and read case_searches.fragment, a column that
    # does not exist (the column is `frag`), so it crashed on any
    # database that had ever run a case search (round 6, seat 2
    # F1 / Vesper F2). Janus's boot verifier and this ceremony now
    # share the candidate set, so they can never disagree again.
    db = sqlite3.connect(a.db)
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    checked = matched = 0
    if "suppressions" in tables:
        # 1.2.4 (S6): a genuine 1.0 database's suppressions table
        # has NO plate/state columns (they arrive with the upgrade
        # migration's ALTERs) — 1.2.3's ceremony crashed on exactly
        # that database, the one the ceremony exists to upgrade.
        # Enumerate by the columns the table actually has: no
        # plate text, no checkable pairs.
        scols = {r[1] for r in db.execute(
            "PRAGMA table_info(suppressions)")}
        supp_rows = []
        if {"plate", "state", "plate_ref"} <= scols:
            supp_rows = db.execute(
                "SELECT plate, state, plate_ref FROM suppressions "
                "WHERE plate IS NOT NULL AND plate != ''").fetchall()
        for plate, state, ref in supp_rows:
            checked += 1
            if ref in sentinel.key_ref_candidates(key, plate, state):
                matched += 1
    if "audit" in tables:
        chain_refs = set()
        for (payload,) in db.execute("SELECT payload FROM audit"):
            try:
                ref = json.loads(payload).get("plate_ref")
            except ValueError:
                ref = None
            if ref:
                chain_refs.add(ref)
        frags = set()
        if "tier3_requests" in tables:
            for (frag,) in db.execute(
                    "SELECT DISTINCT plate_fragment FROM "
                    "tier3_requests WHERE plate_fragment IS NOT NULL "
                    "AND plate_fragment NOT LIKE 'pref:%'").fetchall():
                frags.add(frag)
        if "case_searches" in tables:
            for (frag,) in db.execute(
                    "SELECT DISTINCT frag FROM case_searches WHERE "
                    "frag IS NOT NULL AND frag NOT LIKE "
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
    # 1.2.4 (S9): a WRONG pre-existing key file is overwritten,
    # loudly — 1.2.3 wrote the file only if absent, so a stale
    # wrong key silently survived the ceremony and Janus kept
    # refusing the RIGHT key (round 7, Qwen F-I).
    replaced = ""
    if os.path.exists(kf):
        existing = open(kf).read().strip()
        if hashlib.sha256(existing.encode()).hexdigest() != fp:
            replaced = (" NOTE: the pre-existing key file held a "
                        "DIFFERENT key and was REPLACED — the old "
                        "file content is gone.")
    with open(kf, "w") as f:
        f.write(key)
    os.chmod(kf, 0o600)
    print("audit key pinned by %s: fingerprint %s recorded; key "
          "file at %s (0600). Janus will chain KEY_PINNED at its "
          "next boot.%s" % (method, fp, kf, replaced))


def enroll_2fa(a):
    """1.2.4 (S11): enroll a HUMAN account in TOTP two-factor
    auth. The secret is generated here, stored in the 0600 store
    beside the DB (<db>.totp.json — never in users.json, never in
    the chain, never in backup sets), and printed ONCE with ten
    one-time recovery codes (only their SHA-256 hashes are
    stored). The enrollment is PENDING: it activates only when
    the account's first valid code is presented to Janus. An
    ACTIVE enrollment is never overwritten by this command —
    re-enrollment is Janus's two-key supervisor/auditor path, or
    --force here for a bare-metal operator decision.
    1.2.5 (T8): the shell honors two-key too. 1.2.4 let anyone
    with filesystem access enroll or --force-overwrite any
    account unilaterally and chained NOTHING (security round 1,
    ChatGPT F7 / Claude F11). Now: when any OTHER account holds
    an ACTIVE enrollment, that operator must confirm with their
    own TOTP code (--confirm-by/--confirm-code; the code is
    consumed, exactly as Janus would consume it). When NO active
    enrollment exists at all — a fresh install, or a post-restore
    store where every entry is must_reenroll — the enrollment is
    a bootstrap/recovery act: allowed, printed loudly, and
    chained as such. Every enrollment is recorded in the
    provision marker (<db>.provision_marker) that Janus chains as
    PROVISION_2FA at its next flush — the restore-marker pattern."""
    import base64
    import re as re_mod
    users = load(a.users)
    u = find(users, a.name)
    if not u:
        sys.exit(f"no such user: {a.name}")
    human = {"detective", "patrol", "supervisor", "auditor",
             "chain_auditor"}
    roles = set()
    r = u.get("roles")
    if isinstance(r, list):
        roles = {str(x) for x in r}
    if u.get("role"):
        roles.add(u["role"])
    if not (roles & human):
        sys.exit("refusing: %s holds no human role — machine "
                 "identities (ingest, jobs, partner) stay key-only "
                 "by design (2FA-SCOPE)" % a.name)
    path = a.db + ".totp.json"
    data = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except ValueError:
            sys.exit(f"refusing: {path} does not parse — fix or "
                     f"remove it by hand; enrollment state is "
                     f"never guessed at")
    entry = data.get(a.name)
    if entry and entry.get("status") == "active" and not a.force:
        sys.exit("refusing: %s already has an ACTIVE enrollment — "
                 "use Janus's two-key re-enrollment "
                 "(POST /auth/2fa/reenroll) or pass --force"
                 % a.name)
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), ".."))
    import sentinel
    # --- T8 two-key confirmation --------------------------------
    others_active = [name for name, e in data.items()
                     if name != a.name and isinstance(e, dict)
                     and e.get("status") == "active"]
    bootstrap = not any(
        isinstance(e, dict) and e.get("status") == "active"
        for e in data.values())
    confirmed_by = ""
    if others_active:
        if not a.confirm_by or not a.confirm_code:
            sys.exit("refusing: two-key confirmation is required "
                     "— another account (%s) holds an ACTIVE "
                     "enrollment. That operator confirms with "
                     "--confirm-by <their name> --confirm-code "
                     "<their current TOTP code>. (Janus's two-key "
                     "re-enrollment, POST /auth/2fa/reenroll, is "
                     "the other path.)" % ", ".join(
                         sorted(others_active)))
        if a.confirm_by == a.name:
            sys.exit("refusing: the confirmer must be a DIFFERENT "
                     "account than the one being enrolled")
        centry = data.get(a.confirm_by)
        if not (isinstance(centry, dict)
                and centry.get("status") == "active"):
            sys.exit("refusing: confirmer %s holds no ACTIVE "
                     "enrollment" % a.confirm_by)
        code = (a.confirm_code or "").strip()
        matched = None
        if len(code) == 6 and code.isdigit():
            now_c = sentinel.totp_counter_now()
            last = centry.get("last_counter", -1)
            for delta in (-1, 0, 1):
                c = now_c + delta
                if c <= last:
                    continue
                try:
                    if sentinel.totp_code(centry["secret"], c) == code:
                        matched = c
                        break
                except Exception:
                    sys.exit("refusing: the confirmer's stored "
                             "secret does not decode — the store "
                             "is damaged; fix it by hand")
            if matched is None:
                sys.exit("refusing: the confirmer's code did not "
                         "validate (wrong, expired, or already "
                         "used)")
            centry["last_counter"] = matched  # the code is consumed
        else:
            # A confirmer may also confirm with one of their
            # RECOVERY codes (same normalization Janus uses). The
            # code is burned — removed from the stored hashes.
            norm = re_mod.sub(r"[^0-9A-Za-z]", "", code).upper()
            digest = hashlib.sha256(norm.encode()).hexdigest()
            hashes = centry.get("recovery") or []
            if not norm or digest not in hashes:
                sys.exit("refusing: the confirmer's recovery code "
                         "did not validate")
            centry["recovery"] = [h for h in hashes if h != digest]
        confirmed_by = a.confirm_by
    elif bootstrap:
        print("BOOTSTRAP/RECOVERY enrollment: no ACTIVE enrollment "
              "exists to confirm this one (fresh install or "
              "post-restore). This act is chained as a bootstrap "
              "when Janus next runs.")
    else:
        print("RECOVERY enrollment: the only ACTIVE enrollment is "
              "the target's own, so no second key exists to "
              "confirm. This act is chained as a bootstrap when "
              "Janus next runs.")
        bootstrap = True
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    codes, hashes = [], []
    for _ in range(10):
        c = secrets.token_hex(5).upper()
        codes.append("%s-%s" % (c[:5], c[5:]))
        norm = re_mod.sub(r"[^0-9A-Za-z]", "", c).upper()
        hashes.append(hashlib.sha256(norm.encode()).hexdigest())
    data[a.name] = {"secret": secret, "status": "pending",
                    "last_counter": -1, "recovery": hashes,
                    "enrolled_ts": sentinel.now_iso(),
                    "enrolled_by": "provision.py"}
    # 1.2.6 (U11(iv)): unique temp path, like janus._totp_save —
    # the store has two writers and a shared fixed temp let their
    # saves interleave.
    tmp = "%s.tmp.%d.%s" % (path, os.getpid(), secrets.token_hex(4))
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(data, indent=1,
                                sort_keys=True).encode())
    finally:
        os.close(fd)
    os.replace(tmp, path)
    # T8: record the mutation for the chain (Janus consumes the
    # marker at its next locked flush and chains PROVISION_2FA).
    marker = a.db + ".provision_marker"
    with open(marker, "a") as f:
        f.write(json.dumps({
            "user": a.name, "by": "provision.py",
            "confirmed_by": confirmed_by,
            "bootstrap": bool(bootstrap),
            "ts": sentinel.now_iso()}) + "\n")
    try:
        os.chmod(marker, 0o600)
    except OSError:
        pass
    print(f"TOTP enrollment for {a.name} written to {path} (0600), "
          f"status PENDING — it activates on the first valid code.")
    print("This enrollment is recorded in the provision marker; "
          "Janus chains it as PROVISION_2FA at its next flush.")
    print("NOTE: a TOTP change does not rotate the API key here — "
          "for a re-enrollment, also run rotate-key %s and hand "
          "over the new key with the secret." % a.name)
    print(f"TOTP SECRET — shown ONCE, hand it to the individual in "
          f"person:\n  {secret}")
    print(f"Authenticator entry (otpauth):\n  "
          f"otpauth://totp/NOCTUA:{a.name}?secret={secret}"
          f"&issuer=NOCTUA&digits=6&period=30")
    print("RECOVERY CODES — shown ONCE, each usable exactly once:")
    for c in codes:
        print(f"  {c}")


if __name__ == "__main__":
    main()
