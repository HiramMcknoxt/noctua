#!/usr/bin/env python3
# VESPER · the evening watch
"""NOCTUA backup — nightly, signed-manifest, self-pruning.

    python3 backup.py [--out DIR] [--no-prune]

Produces one backup set per run in DIR (default $NOCTUA_BACKUP_DIR
or <db dir>/backups):

    backup-YYYYmmddTHHMMSSZ/
      noctua.db            SQLite ONLINE backup (safe against a live
                           Janus; uses the sqlite3 backup API)
      config.tar.gz        users.json, cases.json, cameras.json,
                           .env — whichever exist
      evidence.tar.gz      the evidence bundle directory, when
                           non-empty (S17: bundles are IN backups —
                           a restore that loses the evidence loses
                           the case), every file 0600
      checkpoints.jsonl    the local checkpoints file, if present
      manifest.json        SHA-256 + size of every file above, plus
                           an Ed25519 signature over the manifest
                           (S7) and the legacy HMAC when an audit
                           key is available

KEY ESCROW (1.2.5, T8): the audit key and the Ed25519 keypair are
NOT in the set. They are written to a separate key escrow —
$NOCTUA_KEY_ESCROW_DIR/key-escrow-<stamp>/ (default: a sibling of
the backup root), files 0600, with its own signed hash manifest —
and the set's manifest records only their SHA-256 hashes. Split
custody: a backup set alone can no longer become the system, and
the escrow alone holds no data. Escrows prune on the same
schedule as sets. (Sets written by 1.2.4 and earlier DO carry the
keys inside; restore.py handles both shapes.)

restore.py verifies the manifest before restoring a single byte and
refuses on any mismatch — and, when a key is configured, refuses an
UNSIGNED manifest outright (S6). The set itself is NOT encrypted
by this script — store it on encrypted, access-controlled storage,
like evidence.

SECRETS: a backup set contains user key hashes and camera
credentials (.env). The key escrow contains the audit key and the
signing key. Store both encrypted and access-controlled, in
separate custody.

NOT IN BACKUP SETS (1.2.4, S11): the TOTP secret store
(<db>.totp.json) is deliberately EXCLUDED — the set above is an
explicit allowlist and the store is not on it. A restore therefore
forces every enrolled account to re-enroll (Janus flips all
enrollments to must_reenroll when it chains the RESTORE): second
factors do not ride along with database backups (2FA-SCOPE).

RETENTION OF BACKUPS: a backup set is only as long-lived as the
most restricted data class it contains. The DB backup contains
plate reads, so backup sets follow the READS schedule: pruning is
ON BY DEFAULT (S1 — the registry classes backups as reads) and
deletes sets older than BACKUP_RETENTION_DAYS (default: the reads
retention, RETENTION_DAYS or 14). --no-prune exists for a one-off
archival set, and using it should be a decision someone signs.

'backup' is a monitored job: this script heartbeats as the jobs
role, ok:false + nonzero exit on ANY failure.

Env: NOCTUA_DB, NOCTUA_USERS, NOCTUA_CASES, NOCTUA_CAMERAS,
     NOCTUA_EVIDENCE_DIR, NOCTUA_ENV_FILE, NOCTUA_CHECKPOINTS,
     NOCTUA_AUDIT_KEY, NOCTUA_BACKUP_DIR, NOCTUA_KEY_ESCROW_DIR,
     BACKUP_RETENTION_DAYS,
     NOCTUA_JANUS_URL, NOCTUA_JOBS_USER, NOCTUA_JOBS_KEY.
"""
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
DB_DIR = os.path.dirname(os.path.abspath(DB))
OUT_ROOT = os.environ.get("NOCTUA_BACKUP_DIR",
                          os.path.join(DB_DIR, "backups"))
PRUNE_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS",
                                os.environ.get("RETENTION_DAYS", "14")))
EVIDENCE_DIR = os.environ.get("NOCTUA_EVIDENCE_DIR",
                              os.path.join(DB_DIR, "evidence"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _audit_key():
    return sentinel.resolve_audit_key(DB)


def config_paths():
    cands = [
        ("users.json", os.environ.get("NOCTUA_USERS", "/config/users.json")),
        ("cases.json", os.environ.get("NOCTUA_CASES", "/config/cases.json")),
        ("cameras.json", os.environ.get("NOCTUA_CAMERAS",
                                        "/config/cameras.json")),
        (".env", os.environ.get("NOCTUA_ENV_FILE", "/srv/noctua/.env")),
    ]
    return [(a, p) for a, p in cands if os.path.exists(p)]


def heartbeat(ok, detail):
    janus = os.environ.get("NOCTUA_JANUS_URL") or os.environ.get(
        "NOCTUA_JANUS")
    jkey = os.environ.get("NOCTUA_JOBS_KEY") or os.environ.get(
        "NOCTUA_SYSTEM_KEY")
    if not janus or not jkey:
        print("backup heartbeat skipped: NOCTUA_JANUS_URL / "
              "NOCTUA_JOBS_KEY not set")
        return
    req = urllib.request.Request(
        janus.rstrip("/") + "/heartbeat",
        data=json.dumps({"job": "backup", "ok": ok,
                         "detail": detail}).encode(),
        headers={"Content-Type": "application/json",
                 "X-Noctua-User": os.environ.get("NOCTUA_JOBS_USER",
                                                 "jobs.local"),
                 "X-Noctua-Key": jkey})
    try:
        urllib.request.urlopen(req, timeout=10).read()
        print("backup heartbeat sent (ok=%s)" % ok)
    except Exception as e:
        print(f"backup heartbeat FAILED ({e})")


def main():
    try:
        return run()
    except Exception as exc:
        print("backup FAILED: %s" % exc)
        heartbeat(False, "backup failed: %s" % exc)
        return 1


def run():
    prune = "--no-prune" not in sys.argv
    out_root = OUT_ROOT
    if "--out" in sys.argv:
        out_root = sys.argv[sys.argv.index("--out") + 1]
    # 1.2.6 (U10): the escrow location is decided — and REFUSED,
    # if wrong — before anything is written. 1.2.5's default put
    # the escrow as a sibling of the backup root, and an operator
    # could point NOCTUA_KEY_ESCROW_DIR INSIDE the backup tree,
    # reuniting the set and its keys under one directory — the
    # T8 split made nominal (round 8, Claude C8-10). Now: the
    # default stays a sibling of the backup root (outside the
    # tree), and an escrow path inside the backup tree is refused
    # loudly, up front, with nothing written.
    escrow_root = os.environ.get(
        "NOCTUA_KEY_ESCROW_DIR",
        os.path.join(os.path.dirname(os.path.abspath(out_root)),
                     "key-escrow"))
    _root_real = os.path.realpath(out_root)
    _esc_real = os.path.realpath(escrow_root)
    if _esc_real == _root_real or _esc_real.startswith(
            _root_real + os.sep):
        print("backup REFUSED: the key escrow directory (%s) is "
              "INSIDE the backup tree (%s) — the T8 custody split "
              "requires the escrow outside it. Set "
              "NOCTUA_KEY_ESCROW_DIR to a directory outside the "
              "backup root." % (escrow_root, out_root))
        heartbeat(False, "key escrow inside the backup tree; "
                         "backup refused")
        return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(out_root, "backup-" + stamp)
    os.makedirs(dest, mode=0o700)

    # 1) Online DB backup — consistent snapshot of a live database.
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    dst_path = os.path.join(dest, "noctua.db")
    dst = sqlite3.connect(dst_path)
    src.backup(dst)
    dst.close()
    src.close()
    os.chmod(dst_path, 0o600)
    # 1.2.2 (Q25): a backup of a BROKEN chain is not signed — the
    # set is verified before anything else is written into it
    # (round 5, ChatGPT F1: 1.2.1's backup signed a corrupted chain
    # happily and restore discovered it only after the swap).
    vres = sentinel.verify_detached(dst_path)
    if not vres.get("ok"):
        shutil.rmtree(dest, ignore_errors=True)
        print("backup FAILED: the source chain does not verify "
              "(%s) — refusing to sign a backup of it" % vres)
        heartbeat(False, "source chain does not verify; backup "
                         "refused")
        return 1
    files = {"noctua.db": {"sha256": sha256_file(dst_path),
                           "size": os.path.getsize(dst_path)}}

    # 2) Config tarball.
    cfg = config_paths()
    if cfg:
        tar_path = os.path.join(dest, "config.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            for arc, p in cfg:
                tar.add(p, arcname=arc)
        os.chmod(tar_path, 0o600)
        files["config.tar.gz"] = {"sha256": sha256_file(tar_path),
                                  "size": os.path.getsize(tar_path),
                                  "contains": [a for a, _p in cfg]}

    # 3) Evidence bundles (S17): included, 0600, when any exist.
    if os.path.isdir(EVIDENCE_DIR) and os.listdir(EVIDENCE_DIR):
        tar_path = os.path.join(dest, "evidence.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            for name in sorted(os.listdir(EVIDENCE_DIR)):
                tar.add(os.path.join(EVIDENCE_DIR, name), arcname=name)
        os.chmod(tar_path, 0o600)
        files["evidence.tar.gz"] = {
            "sha256": sha256_file(tar_path),
            "size": os.path.getsize(tar_path),
            "note": "evidence bundles — handle as evidence"}

    # 4) Checkpoints go in the set; KEY MATERIAL DOES NOT
    # (1.2.5, T8). 1.2.4 put the audit key and the Ed25519 private
    # key inside every set while the docs called the set
    # "encrypted" — it never was (security round 1, ChatGPT F7 /
    # Claude F10). Custody is now SPLIT: keys are escrowed to a
    # separate directory ($NOCTUA_KEY_ESCROW_DIR, default a
    # sibling of the backup root) with its own hash manifest,
    # signed by the signing key it carries; the set's manifest
    # records only the escrow files' HASHES. A backup set alone
    # can no longer become the system; a restore uses the HOST's
    # keys (restore.py's standing posture) or the escrow,
    # deliberately fetched.
    cp = os.environ.get("NOCTUA_CHECKPOINTS", DB + ".checkpoints.jsonl")
    if os.path.exists(cp):
        p = os.path.join(dest, "checkpoints.jsonl")
        shutil.copyfile(cp, p)
        os.chmod(p, 0o600)
        files["checkpoints.jsonl"] = {"sha256": sha256_file(p),
                                      "size": os.path.getsize(p)}
    priv, pub = sentinel.signing_paths(DB)
    # escrow_root was resolved (and the inside-tree refusal
    # applied) at the top of run() — 1.2.6, U10.
    escrow_dest = os.path.join(escrow_root, "key-escrow-" + stamp)
    escrow_files = {}

    def _escrow(name, data_bytes):
        os.makedirs(escrow_dest, mode=0o700, exist_ok=True)
        p = os.path.join(escrow_dest, name)
        with open(p, "wb") as f:
            f.write(data_bytes)
        os.chmod(p, 0o600)
        escrow_files[name] = {"sha256": sha256_file(p),
                              "size": os.path.getsize(p)}

    kf = DB + ".audit_key"
    if os.path.exists(kf):
        with open(kf, "rb") as f:
            _escrow("audit_key", f.read())
    elif os.environ.get("NOCTUA_AUDIT_KEY"):
        # 1.2.2: an env-key deployment's key is escrowed too —
        # without it the escrow could never unlock a restored
        # chain (round 5, Qwen F10).
        _escrow("audit_key",
                os.environ["NOCTUA_AUDIT_KEY"].encode())
        print("note: NOCTUA_AUDIT_KEY written to the KEY ESCROW "
              "from the environment — the escrow is a key carrier; "
              "store it like one")
    for src_p, name in ((priv, "signing_key.pem"),
                        (pub, "signing_pub.pem")):
        if os.path.exists(src_p):
            with open(src_p, "rb") as f:
                _escrow(name, f.read())
    if escrow_files:
        escrow_manifest = {"created": stamp, "files": escrow_files}
        if os.path.exists(priv):
            escrow_manifest["manifest_sig"] = sentinel.sign_bytes(
                priv, sentinel.canonical_bytes(escrow_manifest))
            escrow_manifest["sig_alg"] = "ed25519"
        with open(os.path.join(escrow_dest, "escrow-manifest.json"),
                  "w") as f:
            json.dump(escrow_manifest, f, indent=1, sort_keys=True)
        print("key escrow written: %s (%d key files, NOT in the "
              "backup set)" % (escrow_dest, len(escrow_files)))

    # 5) Manifest: Ed25519 signature (S7) over the canonical manifest
    # body when the signing key is available; the HMAC is kept for
    # continuity with 1.x sets. restore.py requires at least one of
    # them whenever a key is configured (S6).
    manifest = {"created": stamp, "noctua": "1.2.6", "source_db": DB,
                "files": files,
                # T8: the set carries the escrow's HASHES only —
                # proof of which keys belong with this set, without
                # the keys. Restore verifies a set against the
                # HOST's keys; the escrow is fetched deliberately,
                # from its own custody, when a host has none.
                "key_escrow": {
                    "files": {n: v["sha256"]
                              for n, v in escrow_files.items()},
                    "note": "key material is NOT in this set "
                            "(1.2.5, T8) — it is escrowed "
                            "separately by backup.py"}}
    body = sentinel.canonical_bytes(manifest)
    if os.path.exists(priv):
        manifest["manifest_sig"] = sentinel.sign_bytes(priv, body)
        manifest["sig_alg"] = "ed25519"
    key = _audit_key()
    if key:
        manifest["manifest_hmac"] = hmac.new(
            key.encode(), body, hashlib.sha256).hexdigest()
    else:
        manifest["manifest_hmac"] = None
    with open(os.path.join(dest, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print(f"backup written: {dest} ({len(files)} files, "
          f"ed25519={'yes' if 'manifest_sig' in manifest else 'NO'}, "
          f"hmac={'yes' if key else 'NO — no audit key found'})")
    print("WARNING: this backup set contains secrets (user key "
          "hashes, camera credentials in .env). It does NOT "
          "contain the audit or signing keys — those are in the "
          "key escrow. Store BOTH on encrypted, access-controlled "
          "storage, in separate custody.")
    heartbeat(True, "backup set %s (%d files)" % (stamp, len(files)))

    # 6) Prune by default (S1: backups carry the reads class).
    if prune:
        cutoff = datetime.now(timezone.utc) - timedelta(days=PRUNE_DAYS)
        for name in sorted(os.listdir(out_root)):
            if not name.startswith("backup-"):
                continue
            try:
                when = datetime.strptime(
                    name[len("backup-"):], "%Y%m%dT%H%M%SZ").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                continue
            if when < cutoff:
                shutil.rmtree(os.path.join(out_root, name))
                print(f"pruned old backup set {name} "
                      f"(> {PRUNE_DAYS} days — the reads schedule)")
        # T8: escrows prune on the same schedule as their sets.
        if os.path.isdir(escrow_root):
            for name in sorted(os.listdir(escrow_root)):
                if not name.startswith("key-escrow-"):
                    continue
                try:
                    when = datetime.strptime(
                        name[len("key-escrow-"):],
                        "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if when < cutoff:
                    shutil.rmtree(os.path.join(escrow_root, name))
                    print(f"pruned old key escrow {name} "
                          f"(> {PRUNE_DAYS} days — the reads "
                          f"schedule)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
