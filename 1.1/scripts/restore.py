#!/usr/bin/env python3
"""NOCTUA restore — verify first, restore second, refuse on mismatch.

    python3 restore.py BACKUP_DIR [--db PATH] [--config-dir DIR]

Verifies EVERY file in the backup set against manifest.json (SHA-256
and size), and the manifest's own HMAC when an audit key is available
(env NOCTUA_AUDIT_KEY, the set's own audit_key file, or the live DB's
.audit_key file). Any missing file, size change, or hash mismatch →
prints REFUSING and exits 2 having restored NOTHING.

On success it:
  * moves the current live files aside to <name>.pre-restore-<stamp>
    (nothing is destroyed by a restore),
  * installs the backup DB (and audit_key / checkpoints alongside it),
  * unpacks config.tar.gz into --config-dir (default /config),
  * opens the restored DB and verifies the Sentinel chain end to end,
    printing the entry count and root — a restore that cannot verify
    its own audit chain is reported as FAILED even though bytes moved.

Stop Janus before restoring and start it after; this tool does not
signal the service (the install guide owns service management).

AUDIT KEY RECOVERY (1.1, item 30): if the audit key is lost, Janus
starts LOCKED (/health reports key_missing, data endpoints 503) and
refuses to mint a replacement over an existing chain — a new key
would silently unmatch every suppression and orphan every plate_ref.
The supported recovery is THIS tool: a backup set carries the
original audit_key file, and restoring it (with its DB and
checkpoints) is how a lost key comes back. There is no other path,
by design.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import tarfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sentinel import Chain  # noqa: E402


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def refuse(msg):
    print(f"REFUSING TO RESTORE: {msg}")
    sys.exit(2)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__.splitlines()[2].strip())
    bdir = args[0]
    db_path = os.environ.get("NOCTUA_DB", "/data/noctua.db")
    if "--db" in sys.argv:
        db_path = sys.argv[sys.argv.index("--db") + 1]
    config_dir = "/config"
    if "--config-dir" in sys.argv:
        config_dir = sys.argv[sys.argv.index("--config-dir") + 1]

    mpath = os.path.join(bdir, "manifest.json")
    if not os.path.exists(mpath):
        refuse(f"no manifest.json in {bdir}")
    manifest = json.load(open(mpath))

    # Manifest HMAC, when the manifest carries one and we can find a key.
    if manifest.get("manifest_hmac"):
        key = os.environ.get("NOCTUA_AUDIT_KEY")
        if not key and os.path.exists(os.path.join(bdir, "audit_key")):
            key = open(os.path.join(bdir, "audit_key")).read().strip()
        if not key and os.path.exists(db_path + ".audit_key"):
            key = open(db_path + ".audit_key").read().strip()
        if not key:
            refuse("manifest is HMAC-signed but no audit key is "
                   "available to verify it")
        body = {k: v for k, v in manifest.items() if k != "manifest_hmac"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        expect = hmac.new(key.encode(), canonical.encode(),
                          hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, manifest["manifest_hmac"]):
            refuse("manifest HMAC mismatch — the manifest itself was "
                   "altered, or the wrong audit key was supplied")

    # Every listed file must exist with the recorded hash and size.
    for name, meta in manifest["files"].items():
        p = os.path.join(bdir, name)
        if not os.path.exists(p):
            refuse(f"missing file: {name}")
        if os.path.getsize(p) != meta["size"]:
            refuse(f"size mismatch: {name}")
        if sha256_file(p) != meta["sha256"]:
            refuse(f"SHA-256 mismatch: {name}")
    print(f"manifest verified: {len(manifest['files'])} files, "
          f"created {manifest['created']}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def aside(path):
        if os.path.exists(path):
            os.replace(path, path + ".pre-restore-" + stamp)

    # Install DB + sidecars.
    aside(db_path)
    aside(db_path + ".audit_key")
    aside(db_path + ".checkpoints.jsonl")
    import shutil
    shutil.copyfile(os.path.join(bdir, "noctua.db"), db_path)
    if "audit_key" in manifest["files"]:
        shutil.copyfile(os.path.join(bdir, "audit_key"),
                        db_path + ".audit_key")
        os.chmod(db_path + ".audit_key", 0o600)
    if "checkpoints.jsonl" in manifest["files"]:
        shutil.copyfile(os.path.join(bdir, "checkpoints.jsonl"),
                        db_path + ".checkpoints.jsonl")

    # Install config.
    tar_path = os.path.join(bdir, "config.tar.gz")
    if "config.tar.gz" in manifest["files"] and os.path.exists(tar_path):
        os.makedirs(config_dir, exist_ok=True)
        with tarfile.open(tar_path) as tar:
            names = tar.getnames()
            for n in names:
                aside(os.path.join(config_dir, n))
            tar.extractall(config_dir)
        print(f"config restored into {config_dir}: {', '.join(names)}")

    # The restored chain must verify, or the restore is not a restore.
    result = Chain(db_path).verify()
    if not result.get("ok"):
        print(f"FAILED: restored chain does not verify: {result}")
        sys.exit(3)
    print(f"restored OK: chain verifies, {result['entries']} entries, "
          f"root {result['root'][:16]}…")
    print(f"previous live files kept as *.pre-restore-{stamp}")


if __name__ == "__main__":
    main()
