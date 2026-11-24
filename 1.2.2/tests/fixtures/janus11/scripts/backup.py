#!/usr/bin/env python3
"""NOCTUA backup — nightly, hash-manifested, self-pruning.

    python3 backup.py [--out DIR] [--prune]

Produces one backup set per run in DIR (default $NOCTUA_BACKUP_DIR or
./backups):

    backup-YYYYmmddTHHMMSSZ/
      noctua.db            SQLite ONLINE backup (safe against a live
                           Janus; uses the sqlite3 backup API, not a
                           file copy of a running database)
      config.tar.gz        users.json, cases.json, cameras.yaml, .env —
                           whichever exist at their configured paths
      audit_key            the .audit_key file next to the DB, if used
      checkpoints.jsonl    the local checkpoints file, if present
      manifest.json        SHA-256 + size of every file above, plus an
                           HMAC of the manifest body keyed by the audit
                           key when one is available

restore.py verifies the manifest before restoring a single byte and
refuses on any mismatch.

SECRETS: a backup set contains everything needed to become the system —
user key hashes, camera credentials (.env), and the audit key. Store
backup sets encrypted and access-controlled, like evidence. The manifest
HMAC proves the set was not altered by someone without the audit key;
it does not make the set safe to leave lying around.

RETENTION OF BACKUPS (INTERFACE.md): a backup set is only as
long-lived as the most restricted data class it contains. The DB backup
contains plate reads, so backup sets follow the READS schedule: --prune
deletes sets older than BACKUP_RETENTION_DAYS (default 14). The
plate-free outcomes data that must survive 18 months lives in the live
DB's outcomes table and in the § 12-12-1805 report snapshots, not in
long-kept full backups. A city that keeps full DB backups for 18 months
has quietly repealed its own 14-day retention rule.

Env: NOCTUA_DB, NOCTUA_USERS, NOCTUA_CASES, NOCTUA_CAMERAS,
     NOCTUA_ENV_FILE, NOCTUA_CHECKPOINTS, NOCTUA_AUDIT_KEY,
     NOCTUA_BACKUP_DIR, BACKUP_RETENTION_DAYS=14.
"""
import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import sqlite3
import sys
import tarfile
import urllib.request
from datetime import datetime, timedelta, timezone

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
OUT_ROOT = os.environ.get("NOCTUA_BACKUP_DIR", "./backups")
PRUNE_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _audit_key():
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    kf = DB + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip()
    return None


def config_paths():
    """(arcname, path) for every config file that exists."""
    cands = [
        ("users.json", os.environ.get("NOCTUA_USERS", "/config/users.json")),
        ("cases.json", os.environ.get("NOCTUA_CASES", "/config/cases.json")),
        ("cameras.yaml", os.environ.get("NOCTUA_CAMERAS",
                                        "/config/cameras.yaml")),
        (".env", os.environ.get("NOCTUA_ENV_FILE", "/srv/noctua/.env")),
    ]
    return [(a, p) for a, p in cands if os.path.exists(p)]


def main():
    prune = "--prune" in sys.argv
    out_root = OUT_ROOT
    if "--out" in sys.argv:
        out_root = sys.argv[sys.argv.index("--out") + 1]
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

    # 3) Audit key + checkpoints, when present.
    kf = DB + ".audit_key"
    if not os.environ.get("NOCTUA_AUDIT_KEY") and os.path.exists(kf):
        p = os.path.join(dest, "audit_key")
        shutil.copyfile(kf, p)
        os.chmod(p, 0o600)
        files["audit_key"] = {"sha256": sha256_file(p),
                              "size": os.path.getsize(p)}
    cp = os.environ.get("NOCTUA_CHECKPOINTS", DB + ".checkpoints.jsonl")
    if os.path.exists(cp):
        p = os.path.join(dest, "checkpoints.jsonl")
        shutil.copyfile(cp, p)
        files["checkpoints.jsonl"] = {"sha256": sha256_file(p),
                                      "size": os.path.getsize(p)}

    # 4) Manifest, HMAC-signed with the audit key when available.
    manifest = {"created": stamp, "noctua": "1.1", "source_db": DB,
                "files": files}
    key = _audit_key()
    if key:
        canonical = json.dumps(manifest, sort_keys=True,
                               separators=(",", ":"))
        manifest["manifest_hmac"] = hmac.new(
            key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    else:
        manifest["manifest_hmac"] = None
    with open(os.path.join(dest, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print(f"backup written: {dest} ({len(files)} files, "
          f"manifest_hmac={'yes' if key else 'NO — no audit key found'})")
    print("WARNING: this backup set contains secrets (key hashes, "
          "camera credentials, audit key). Store it encrypted.")

    # 4b) 1.1: 'backup' is a monitored job (item 8) — heartbeat as the
    # jobs role so a silently-dead backup schedule degrades /health.
    janus = os.environ.get("NOCTUA_JANUS_URL") or os.environ.get(
        "NOCTUA_JANUS")
    jkey = os.environ.get("NOCTUA_JOBS_KEY") or os.environ.get(
        "NOCTUA_SYSTEM_KEY")
    if janus and jkey:
        req = urllib.request.Request(
            janus.rstrip("/") + "/heartbeat",
            data=json.dumps({"job": "backup", "ok": True,
                             "detail": f"backup set {stamp}"}).encode(),
            headers={"Content-Type": "application/json",
                     "X-Noctua-User": os.environ.get("NOCTUA_JOBS_USER",
                                              "jobs.local"),
                     "X-Noctua-Key": jkey})
        try:
            urllib.request.urlopen(req, timeout=10).read()
            print("backup heartbeat sent")
        except Exception as e:
            print(f"backup heartbeat FAILED ({e})")
    else:
        print("backup heartbeat skipped: NOCTUA_JANUS_URL / "
              "NOCTUA_JOBS_KEY not set")

    # 5) Prune: backup sets older than the reads retention schedule.
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


if __name__ == "__main__":
    main()
