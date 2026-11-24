#!/usr/bin/env python3
"""NOCTUA restore — verify first, restore second, refuse on mismatch.

1.2.2 (Q25): failure-atomic, verified BEFORE the swap. The backup
set's own chain is verified read-only before a single live file
moves (1.2.1 verified only after installing, leaving a corrupt DB
live — round 5, ChatGPT F1); the manifest must name noctua.db;
when the host has a signing public key, an Ed25519 signature
against a host-trusted key is required in EVERY path (the
lost-audit-key path included), and --pubkey-fingerprint alone can
pin the SET's public key on a bare-metal host (the fingerprint,
confirmed out-of-band, is the trust root — never the set itself);
the end-of-run prune never touches the copies this run just made
(1.2.1's mtime prune could delete them — round 5, Claude R5-14).

    python3 restore.py BACKUP_DIR [--db PATH] [--config-dir DIR]
                       [--pubkey PEM] [--pubkey-fingerprint HEX]

Verifies EVERY file in the backup set against manifest.json
(SHA-256 and size) and the manifest's own signature. When a signing
or audit key is configured, a manifest with NEITHER an Ed25519
signature NOR an HMAC is refused outright (S6): an unsigned manifest
proves nothing, and 1.1 restored one happily. Any missing file, size
change, or hash mismatch → prints REFUSING and exits 2 having
restored NOTHING. Config tarballs are extracted with
tarfile filter="data" (S6) — a tar member that tries to escape the
config directory refuses the whole restore.

1.2.1 (P6) — the trust root moves to the HOST:
  * The manifest's Ed25519 signature is verified ONLY against the
    LIVE HOST's signing_pub.pem (the one beside the target DB) or a
    key/fingerprint the operator passes explicitly (--pubkey /
    --pubkey-fingerprint). NEVER against a key inside the backup
    set: 1.2 verified against the set's own signing_pub.pem, so an
    attacker-signed set — attacker's users, attacker's keys —
    verified against the attacker's own key and installed cleanly.
    A signature that cannot be checked against a host-side key
    counts for nothing.
  * If the host has an audit key configured (env or the key file
    beside the live DB), a manifest whose manifest_hmac is null or
    missing is refused unless the Ed25519 signature verified
    against a host key: dropping the HMAC is not a downgrade path.
  * The audit-key lookup checks HOST paths (env, live key file)
    before the backup directory's copy.
  * ALL tarballs are fully validated (every member through the data
    filter) BEFORE any live file is moved aside. 1.2 moved the live
    DB and keys aside first and only then discovered a tar-slip —
    a restore that REFUSED had already replaced the live system.

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


def _host_audit_key(db_path):
    """The HOST's audit key: env, else the key file beside the LIVE
    database. This is the 'host has an audit key configured' test —
    a key that exists only inside the backup set does not configure
    the host (P6)."""
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    kf = db_path + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip()
    return None


def _find_audit_key(bdir, db_path):
    """Audit key for HMAC verification, HOST paths first (P6): env,
    the live key file, and only then the backup set's own copy (the
    lost-key recovery path — a backup's key may verify its own
    manifest's HMAC when the host has none, but it never outranks a
    host key)."""
    k = _host_audit_key(db_path)
    if k:
        return k
    cand = os.path.join(bdir, "audit_key")
    if os.path.exists(cand):
        return open(cand).read().strip()
    return None


def _validate_tarball(path, dest):
    """Run EVERY member of a tarball through tarfile's data filter
    WITHOUT extracting (P6). A member the filter would reject at
    extraction time rejects the restore NOW — before a single live
    file has been moved aside."""
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            tarfile.data_filter(member, dest)


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
    pubkey_path = None
    if "--pubkey" in sys.argv:
        pubkey_path = sys.argv[sys.argv.index("--pubkey") + 1]
    pubkey_fp = None
    if "--pubkey-fingerprint" in sys.argv:
        pubkey_fp = sys.argv[sys.argv.index("--pubkey-fingerprint") + 1]
    evidence_dir = os.environ.get(
        "NOCTUA_EVIDENCE_DIR",
        os.path.join(os.path.dirname(os.path.abspath(db_path)),
                     "evidence"))
    retention_days = int(os.environ.get("RETENTION_DAYS", "14"))

    mpath = os.path.join(bdir, "manifest.json")
    if not os.path.exists(mpath):
        refuse(f"no manifest.json in {bdir}")
    manifest = json.load(open(mpath))

    # ---- signature gate (S6 + P6) --------------------------------
    # The trust root is the HOST. trusted_pub comes from, in order:
    # an explicit --pubkey file; the live host's signing_pub.pem
    # beside the target DB (cross-checked against
    # --pubkey-fingerprint when one is passed). The backup set's own
    # signing_pub.pem is NEVER consulted — a key inside the thing
    # being verified vouches for nothing.
    host_key = _host_audit_key(db_path)
    key = _find_audit_key(bdir, db_path)
    trusted_pub = None
    if pubkey_path:
        if not os.path.exists(pubkey_path):
            refuse(f"--pubkey file not found: {pubkey_path}")
        trusted_pub = open(pubkey_path).read()
    else:
        host_pub = db_path + ".signing_pub.pem"
        if os.path.exists(host_pub):
            trusted_pub = open(host_pub).read()
    if pubkey_fp and not trusted_pub:
        # Bare-metal pinning (Q25): the operator's out-of-band
        # fingerprint promotes the SET's public key to a trust
        # root. Without a fingerprint, a key inside the set vouches
        # for nothing and is never consulted (P6).
        set_pub = os.path.join(bdir, "signing_pub.pem")
        if os.path.exists(set_pub):
            cand = open(set_pub).read()
            if sentinel.pubkey_fingerprint(cand) == pubkey_fp:
                trusted_pub = cand
                print("trust root: the backup set's public key, "
                      "pinned by --pubkey-fingerprint")
    if pubkey_fp:
        if not trusted_pub:
            refuse("--pubkey-fingerprint given but no public key "
                   "matches it (no --pubkey, no signing_pub.pem "
                   "beside the live DB, and the set's own key does "
                   "not match the fingerprint)")
        if sentinel.pubkey_fingerprint(trusted_pub) != pubkey_fp:
            refuse("the host public key's fingerprint does not match "
                   "--pubkey-fingerprint")
    if "noctua.db" not in manifest.get("files", {}):
        refuse("the manifest does not name noctua.db — a backup set "
               "without the database is not a backup set (Q25)")
    body = {k: v for k, v in manifest.items()
            if k not in ("manifest_hmac", "manifest_sig", "sig_alg")}
    canonical = sentinel.canonical_bytes(body)
    host_pub_exists = bool(trusted_pub)
    if host_pub_exists and not manifest.get("manifest_sig"):
        # Q25: when the host HAS a signing public key, an Ed25519
        # signature against a host-trusted key is required in
        # every path — the lost-audit-key path included. An
        # HMAC-only set does not install onto a signing host.
        refuse("the host has a signing public key but the manifest "
               "carries no Ed25519 signature — refusing (Q25)")
    sig_ok = False
    if manifest.get("manifest_sig") and trusted_pub:
        sig_ok = sentinel.verify_bytes(trusted_pub, canonical,
                                       manifest["manifest_sig"])
        if not sig_ok:
            refuse("manifest Ed25519 signature does not verify "
                   "against the HOST's public key")
    hmac_ok = False
    if manifest.get("manifest_hmac"):
        if not key:
            refuse("manifest is HMAC-signed but no audit key is "
                   "available to verify it")
        expect = hmac.new(key.encode(), canonical,
                          hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, manifest["manifest_hmac"]):
            refuse("manifest HMAC mismatch — the manifest itself was "
                   "altered, or the wrong audit key was supplied")
        hmac_ok = True
    if host_key:
        # A host with an audit key configured accepts a set only on
        # a host-verified credential: the Ed25519 signature against
        # a host key, or the HMAC under the host's own audit key.
        # manifest_hmac null/missing with no verifiable signature
        # refuses (P6) — and a signature only the SET's key could
        # check is not verifiable.
        if not (sig_ok or (hmac_ok and key == host_key)):
            refuse("the host has an audit key configured but the "
                   "manifest carries no host-verifiable credential "
                   "(manifest_hmac missing, and no Ed25519 signature "
                   "verifiable against a host key) — refusing (P6)")
    elif not (sig_ok or hmac_ok):
        refuse("no verifiable credential: the manifest's signature "
               "cannot be checked against any host key and no audit "
               "key is available for its HMAC (S6/P6)")

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
    # Q25: the SET's chain verifies BEFORE anything live moves.
    bres = sentinel.verify_detached(os.path.join(bdir, "noctua.db"))
    if not bres.get("ok"):
        refuse("the backup set's chain does not verify (%s) — "
               "nothing was restored" % bres)
    print(f"backup chain verified read-only: {bres['entries']} "
          f"entries")

    # ---- tarball pre-validation (P6) -------------------------------
    # EVERY tarball is fully validated BEFORE any live file is
    # moved aside. A restore that refuses from here on has changed
    # NOTHING on disk.
    for tar_name, dest in (("config.tar.gz", config_dir),
                           ("evidence.tar.gz", evidence_dir)):
        tar_path = os.path.join(bdir, tar_name)
        if tar_name in manifest["files"] and os.path.exists(tar_path):
            try:
                _validate_tarball(tar_path, dest)
            except (tarfile.TarError, ValueError) as exc:
                refuse(f"{tar_name} refused by the data filter: {exc}")
    print("tarballs validated: every member passes the data filter")

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
        if stamp in name:
            # Q25/R5-14: never prune the copies THIS run just made
            # — os.replace preserved their old mtimes, and 1.2.1's
            # prune deleted the just-moved-aside live audit key.
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
