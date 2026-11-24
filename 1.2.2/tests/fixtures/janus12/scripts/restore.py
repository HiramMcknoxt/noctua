#!/usr/bin/env python3
"""NOCTUA restore — verify first, restore second, refuse on mismatch.

    python3 restore.py BACKUP_DIR [--db PATH] [--config-dir DIR]

Verifies EVERY file in the backup set against manifest.json
(SHA-256 and size) and the manifest's own signature. When a signing
or audit key is configured, a manifest with NEITHER an Ed25519
signature NOR an HMAC is refused outright (S6): an unsigned manifest
proves nothing, and 1.1 restored one happily. Any missing file, size
change, or hash mismatch → prints REFUSING and exits 2 having
restored NOTHING. Config tarballs are extracted with
tarfile filter="data" (S6) — a tar member that tries to escape the
config directory refuses the whole restore.

On success it:
  * moves the current live files aside TOGETHER to
    <name>.pre-restore-<stamp> — database, -wal, -shm, audit key,
    signing keys (nothing is destroyed by a restore; retention
    prunes the copies on the reads schedule),
  * installs the backup DB and keys,
  * installs the backup's checkpoints file as EVIDENCE beside the
    live one (<db>.checkpoints.jsonl.from-backup-<stamp>) — NEVER
    over it (S6). The live checkpoints file is the anchor the
    running chain is judged against; a backup's older checkpoints
    would roll the anchor back and bless a truncated chain. Janus
    compares the restored chain against the LIVE anchor at boot and
    raises STARTUP_ANCHOR_MISMATCH if they disagree — that
    disagreement is the operator's decision to accept (two-key),
    not this tool's to hide.
  * unpacks config.tar.gz into --config-dir (default /config) and
    evidence.tar.gz into the evidence directory,
  * chmods the restored database 0600,
  * leaves a restore marker (<db>.restore_marker) that Janus chains
    as RESTORE at next boot,
  * verifies the restored chain READ-ONLY (sentinel.verify_detached
    — no Chain instantiation, no writes) and prints the entry count
    and root. A restore whose chain does not verify is FAILED.

Pre-restore copies older than RETENTION_DAYS are pruned at the end
of a successful restore (S1: they carry the reads class).

Stop Janus before restoring and start it after; this tool does not
signal the service (the install guide owns service management).

AUDIT KEY RECOVERY: if the audit key is lost, Janus starts LOCKED
and refuses to mint a replacement over an existing chain. The
supported recovery is THIS tool: a backup set carries the original
audit_key file, and restoring it (with its DB) is how a lost key
comes back. There is no other path, by design.
"""
import hashlib
import hmac
import json
import os
import shutil
import sys
import tarfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sentinel  # noqa: E402


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def refuse(msg):
    print(f"REFUSING TO RESTORE: {msg}")
    sys.exit(2)


def _find_audit_key(bdir, db_path):
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    for cand in (os.path.join(bdir, "audit_key"), db_path + ".audit_key"):
        if os.path.exists(cand):
            return open(cand).read().strip()
    return None


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
    evidence_dir = os.environ.get(
        "NOCTUA_EVIDENCE_DIR",
        os.path.join(os.path.dirname(os.path.abspath(db_path)),
                     "evidence"))
    retention_days = int(os.environ.get("RETENTION_DAYS", "14"))

    mpath = os.path.join(bdir, "manifest.json")
    if not os.path.exists(mpath):
        refuse(f"no manifest.json in {bdir}")
    manifest = json.load(open(mpath))

    # ---- signature gate (S6) -------------------------------------
    # A key configured anywhere (env, the set itself, the live
    # install) means unsigned manifests are refused. The Ed25519
    # signature verifies against the set's OWN signing_pub.pem —
    # the key the set itself carries, fingerprintable against the
    # registered fingerprint out-of-band.
    key = _find_audit_key(bdir, db_path)
    set_pub = os.path.join(bdir, "signing_pub.pem")
    have_sig = bool(manifest.get("manifest_sig")) \
        and os.path.exists(set_pub)
    have_hmac = bool(manifest.get("manifest_hmac")) and bool(key)
    if (key or os.path.exists(set_pub)) and not (have_sig or have_hmac):
        refuse("a signing/audit key is configured but the manifest "
               "carries no verifiable signature — unsigned manifests "
               "are not restored (S6)")
    body = {k: v for k, v in manifest.items()
            if k not in ("manifest_hmac", "manifest_sig", "sig_alg")}
    canonical = sentinel.canonical_bytes(body)
    if have_sig:
        pub_pem = open(set_pub).read()
        if not sentinel.verify_bytes(pub_pem, canonical,
                                     manifest["manifest_sig"]):
            refuse("manifest Ed25519 signature does not verify "
                   "against the set's signing_pub.pem")
    if manifest.get("manifest_hmac"):
        if not key:
            refuse("manifest is HMAC-signed but no audit key is "
                   "available to verify it")
        expect = hmac.new(key.encode(), canonical,
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

    # Move the live set aside TOGETHER (S6): db + wal + shm + keys.
    # A -wal left beside a restored db would replay the OLD chain's
    # tail over the restored file.
    for suffix in ("", "-wal", "-shm", ".audit_key",
                   ".signing_key.pem", ".signing_pub.pem"):
        aside(db_path + suffix)
    shutil.copyfile(os.path.join(bdir, "noctua.db"), db_path)
    os.chmod(db_path, 0o600)
    if "audit_key" in manifest["files"]:
        shutil.copyfile(os.path.join(bdir, "audit_key"),
                        db_path + ".audit_key")
        os.chmod(db_path + ".audit_key", 0o600)
    priv_name, pub_name = "signing_key.pem", "signing_pub.pem"
    if priv_name in manifest["files"]:
        shutil.copyfile(os.path.join(bdir, priv_name),
                        db_path + ".signing_key.pem")
        os.chmod(db_path + ".signing_key.pem", 0o600)
    if pub_name in manifest["files"]:
        shutil.copyfile(os.path.join(bdir, pub_name),
                        db_path + ".signing_pub.pem")
    # Checkpoints: the backup's file is EVIDENCE, never state (S6).
    if "checkpoints.jsonl" in manifest["files"]:
        evidence_copy = db_path + ".checkpoints.jsonl.from-backup-" \
            + stamp
        shutil.copyfile(os.path.join(bdir, "checkpoints.jsonl"),
                        evidence_copy)
        print(f"backup checkpoints kept as evidence: {evidence_copy} "
              f"(the live checkpoints file was NOT overwritten)")

    # Config — extracted with the data filter: absolute paths, ../
    # escapes, and device members refuse the restore (S6).
    tar_path = os.path.join(bdir, "config.tar.gz")
    if "config.tar.gz" in manifest["files"] and os.path.exists(tar_path):
        os.makedirs(config_dir, exist_ok=True)
        try:
            with tarfile.open(tar_path) as tar:
                names = tar.getnames()
                for n in names:
                    aside(os.path.join(config_dir, n))
                tar.extractall(config_dir, filter="data")
        except (tarfile.TarError, ValueError) as exc:
            refuse(f"config tarball refused by the data filter: {exc}")
        print(f"config restored into {config_dir}: {', '.join(names)}")

    # Evidence bundles ride along (S17).
    ev_tar = os.path.join(bdir, "evidence.tar.gz")
    if "evidence.tar.gz" in manifest["files"] \
            and os.path.exists(ev_tar):
        os.makedirs(evidence_dir, mode=0o700, exist_ok=True)
        try:
            with tarfile.open(ev_tar) as tar:
                tar.extractall(evidence_dir, filter="data")
        except (tarfile.TarError, ValueError) as exc:
            refuse(f"evidence tarball refused by the data filter: "
                   f"{exc}")
        for dp, _dn, fn in os.walk(evidence_dir):
            os.chmod(dp, 0o700)
            for name in fn:
                os.chmod(os.path.join(dp, name), 0o600)
        print(f"evidence bundles restored into {evidence_dir}")

    # The marker Janus chains as RESTORE at boot (S6).
    with open(db_path + ".restore_marker", "w") as f:
        json.dump({"from_backup": os.path.basename(
            os.path.abspath(bdir)), "ts": datetime.now(
                timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, f)

    # Prune pre-restore copies past the reads class (S1/S6).
    db_dir = os.path.dirname(os.path.abspath(db_path)) or "."
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for name in os.listdir(db_dir):
        if ".pre-restore-" not in name:
            continue
        p = os.path.join(db_dir, name)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(p),
                                           timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            print(f"pruned pre-restore copy {name} "
                  f"(> {retention_days} days)")

    # The restored chain must verify, read-only, or the restore is
    # not a restore (S16's rule applied to ourselves).
    result = sentinel.verify_detached(db_path)
    if not result.get("ok"):
        print(f"FAILED: restored chain does not verify: {result}")
        sys.exit(3)
    print(f"restored OK: chain verifies, {result['entries']} entries, "
          f"root {result['root'][:16]}…")
    print(f"previous live files kept as *.pre-restore-{stamp}")


if __name__ == "__main__":
    main()
