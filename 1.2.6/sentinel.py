#  ___
# (o o)   VESPER · the evening watch
# (   )   Vesper, for Corey Spangler — Cabot, Arkansas
#  ^^^
"""Sentinel — append-only, hash-chained audit log (SQLite). NOCTUA 1.2.6.

Shared by the Janus service, the retention job, and the Compact tools
so every component writes to the same chain. Each entry's hash covers
the previous entry's hash plus the canonical JSON payload, so editing
any historical entry breaks every hash after it.

1.2 changes (council round 3, items S1/S7/S11/S15 of the 1.2 brief):

  * ONE HOME FOR PLATE REFERENCES (S15). plate_ref() and frag_ref()
    live HERE and nowhere else — janus.py and every script import
    them. (Round 3 found retention.py's private reimplementation of
    frag_ref differed from Janus's — no .upper(), no truncation — so
    scrubbed fragments never matched the chain's refs. Two copies of
    a security primitive is a bug waiting for a diff.)
  * CANONICAL, STATE-BLIND PLATE IDENTITY (S3). plate_ref() hashes
    normalize_plate(plate) — spaces/hyphens stripped, uppercased —
    and nothing else. The state a camera bridge GUESSED is not part
    of a vehicle's identity; a protection order follows the vehicle.
  * PLATE_DATA_STORES (S1) — the registry of every place plate text
    (or plate-derived time+place) can exist, each with a retention
    class. janus.py re-exports it as janus.PLATE_DATA_STORES;
    retention.py purges BY it; sentinel_audit.py audits BY it; the
    schema test fails the build when a plate-bearing column or folder
    is missing from it.
  * KEY SEPARATION (S7). The audit key (NOCTUA_AUDIT_KEY) is the
    plate-HMAC secret and never leaves the box. SIGNING — checkpoints,
    audit reports, rotation schedules, Compact receipts — uses a
    separate Ed25519 keypair, generated and used through the system
    openssl (stdlib-only Python is preserved; openssl is the one
    sanctioned external call). Anyone holding a member's PUBLIC key
    can verify its checkpoints; nobody needs the HMAC secret to do it.
  * SCRUBBER FLAGS, NEVER RAISES (S11). 1.1's scrubber raised on
    plate-shaped strings — and because 1.1 committed data BEFORE
    chaining, a raise left a committed, unlogged action. It also
    false-fired on legitimate IDs. In 1.2 the scrubber SANITIZES:
    a plate-shaped string in a chain payload is replaced by its
    SHA-256 before the write, the write proceeds (logged), and a
    throttled CHAIN_SCRUB_FLAG entry records that it happened.
    Structural fields whose values are configuration, not data
    (cam, agency), keyed refs (pref:), hashes, and anything not in
    normalized plate shape are exempt.
  * ATOMIC APPENDS (kept from 1.1): in-process lock + BEGIN IMMEDIATE
    root-read+insert with busy-retry; when the caller already holds a
    transaction on the shared connection (Janus's write handlers),
    the append PARTICIPATES in it — data and its chain entry commit
    together or not at all (S11).
  * verify() checks sequence continuity as well as hashes, and
    verify_detached() runs the same check over a fresh READ-ONLY
    connection so /health never computes it while holding the write
    lock (S5) and restore/audit tools never mutate the DB they check
    (S16).

1.2.1 changes (council round 4, items P10/P11 of the 1.2.1 brief):

  * ONE VERIFICATION CONTRACT. Every chain/signature verification in
    the tree flows through THIS module: entry_hash() / verify rows
    here; janus, sentinel_audit, compact and restore import them and
    keep no local reimplementation. (Round 4 found the copies had
    already drifted — the audit tool missed a history rewrite Janus
    itself caught.)
  * CHAIN HASH v2. A v1 entry's hash is sha(prev | payload) — the
    audit table's kind and ts COLUMNS sat outside it, so rewriting
    them verified clean. A v2 entry's payload carries "v": 2 and its
    hash is sha(prev | ts | kind | payload): the columns are bound.
    verify() accepts v1 (legacy) and v2 entries in one chain; every
    NEW append is v2.
  * SPOOL QUARANTINE + DEFERRED FLUSH. A torn/corrupt spool line is
    quarantined to <spool>.bad with a SPOOL_QUARANTINE chain entry —
    a chained write NEVER fails because of the spool. Spool/sink
    appends take an fcntl.flock. Transactional appends (Janus's
    shared-connection writes) stream to the sink only AFTER commit:
    append() queues them, and the caller runs flush_deferred() once
    the transaction lands; queued entries whose rows never committed
    are dropped by a presence check, never streamed.
  * REGISTRY PARITY. registry_breaches() is the ONE breach check,
    consumed by Janus's /health and by sentinel_audit.py, mirroring
    retention.py's purge semantics exactly (see its docstring). The
    registry itself gains holds.reason and witness_attestations.detail,
    the SQLite -wal/-shm/-journal file-stores, and NON_PLATE_COLUMNS —
    the explicit allowlist manifest the schema test checks EVERY
    column of EVERY table against.
  * case_ref(): case numbers are chained as a KEYED HMAC, not a bare
    SHA-256 — the case-number space is ~10^5 and a bare hash is a
    lookup table (round 4, A36).

1.2.2 changes (council round 5, items Q6/Q8/Q17/Q19/Q20/Q23):

  * V1 RELABELING DETECTED (Q17). _verify_rows cross-checks a v1
    entry's payload kind/ts against its COLUMNS (1.2.1 bound only v2
    entries, so a relabeled v1 entry on an upgraded chain verified
    clean), requires the chain to start at seq 1, and streams rows
    instead of materializing the whole chain in memory.
  * TOKEN-AWARE SCRUBBER (Q19). A plate-shaped TOKEN anywhere in a
    string ('VIC 309', 'VIC-309', 'plate VIC 309 at the gate') marks
    the string plate-bearing; the replacement is the KEYED plate_ref
    when the Chain carries the install's audit key (a bare SHA of a
    plate is a lookup table). The cam / agency / members exemptions
    are VALUE-verified through a checker Janus installs — an
    unregistered camera name or unknown agency id is data.
  * ENVELOPE WINS (Q20). _insert_locked strips caller-supplied v/ts/
    kind keys from the fields; the envelope is never caller data.
  * ONE RETENTION DECISION (Q6). ts_cutoff() / day_cutoff() /
    hit_deletable() live here and are used VERBATIM by retention.py
    and registry_breaches() — the purge deletes exactly what the
    check flags, on the same clock (1.2.1's floor-day purge vs
    exact-second check let protected hits live to 150d23h and flagged
    healthy rows as breaches).
  * REGISTRY COMPLETENESS (Q8). share_queries.plate_ref and
    share_queries.case_ref are registered as class keyed_ref —
    pseudonymous HMAC records, retained as the audit trail, never a
    breach (1.2.1 classed the plate_ref as expiring derived data and
    flagged every ordinary share forever). The evidence check also
    flags a bundle STRANDED by its hit's purge (unreleased, its hit
    row gone), and hit protection checks the bundle EXISTS on disk —
    a deleted bundle protects nothing.
  * ONE SCHEDULE BUILDER (Q23). rotation_schedule() lives here;
    janus.py and rotation.py import it. The seed for a Janus-
    published cycle is commit-reveal (see janus.py): no single
    party's inputs determine it.

1.2.3 changes (council round 6, items R3/R5/R8/R15):

  * ONE KEY-VERIFICATION CANDIDATE SET (R3). key_ref_candidates()
    enumerates every historical plate_ref formula (current
    canonical, the 1.1 (plate|state) formula over the stored text
    AND over the canonical plate) — janus.py's boot check and
    provision.py's pin ceremony both consume it, so the two can
    never again disagree about whether a key is the chain's key.
  * STREAMED-ENTRY LEDGER (R5). A Chain remembers every (seq, hash)
    it has actually streamed to the sink; flush_deferred() never
    re-streams one. Round 6 (Vesper seat F4) showed the presence
    check alone cannot tell a committed entry from its rolled-back
    twin — after a rollback the AUTOINCREMENT sequence is reused,
    and an identical re-append inside the same second reproduces
    the same (seq, hash), so the twin streamed twice.
  * SINK BOOKKEEPING OFF THE DATA CONNECTION (R5). sink_state is
    read and written on a dedicated autocommit connection owned by
    the Chain. 1.2.2 updated it on Janus's shared connection after
    the handler's commit, leaving a write transaction open across
    requests — the WAL writer lock stayed held, cron writers
    starved on database-is-locked, and _note_quarantine's
    in_transaction check read the leaked transaction instead of
    the caller's state (round 6, Gemini F5).
  * ONE RANGE VERIFIER (R8). verify_chain_rows() verifies a
    fetched RANGE of entries (the Compact recompute shape) with
    the same checks _verify_rows applies to a whole chain —
    including the v1 kind/ts cross-check. compact.py and
    sentinel_audit.py call it; neither keeps a private hash loop
    (round 6, Gemini F7: both reimplementations had drifted past
    the v1 cross-check, so a partner serving a relabeled v1 chain
    passed both "independent" recomputes).
  * DISPOSITION-NOTE CLOCK CAPPED (R15). disp_note_days() =
    min(HOLD_DAYS + 30, 150): an unconfirmed disposition note can
    never outlive the statutory cap (round 6, Gemini M12).
    registry_breaches() and retention.py share the helper, so the
    checker and the purger still cannot disagree (Q6).
  * ROTATION NONCES BOUND (R6). rotation_signed_portion() for a
    1.2.3 document also covers a SHA-256 of the revealed nonces:
    stripping the nonces from a published schedule now breaks its
    signature instead of silently un-proving the seed. 1.2.2
    documents (whose signatures predate the field) are verified
    under the portion they were signed with.

1.2.4 changes (council round 7, items S1/S10 of the round-7
synthesis — round 7 voted NOT CONVERGED unanimously on 1.2.3):

  * DURABLE SINK DELIVERY (S1). The delivery obligation is DERIVED
    FROM THE COMMITTED AUDIT TABLE, never from a volatile queue or
    a scalar watermark. _insert_locked writes a sink_pending row in
    the SAME transaction as the audit row (a rollback takes the
    obligation with it — zero uncommitted delivered, structurally);
    _deliver_pending() is the ONE delivery path: under the spool
    flock it re-reads the sink's actual tail line, the pending
    ledger, the legacy spool, and every audit row past the tail,
    and delivers the union in chain order. A verification or
    connection failure PRESERVES the obligation (the pending row
    stays), records the error, and sink_status() reports the
    backlog — Janus's /health is not green over an unresolved gap.
    1.2.3's flush_deferred dropped queued entries it could not
    verify (a read-only connection failure discarded COMMITTED
    entries — ChatGPT R7-01) and its single global watermark let
    one process's delivery strand another's earlier entry forever
    (Claude seat p1b: 7 of 55 RETENTION_PURGE entries never
    arrived). The watermark survives only as a reporting column;
    per-entry state is the ledger.
  * CHAIN CONTRACT (S10). _append_txn returns the participation
    decision CAPTURED AT INSERT (participated: the caller held a
    transaction) alongside the entry; append() acts on that
    captured decision instead of re-reading conn.in_transaction
    after the fact (Qwen F-G / cold-seat S2: on a shared connection
    the re-read could name ANOTHER request's transaction). The
    scrub-flag bookkeeping (scrub_state) lives on the Chain's
    dedicated autocommit connection, so a flag insert can no longer
    leak an open transaction onto a shared connection. EXTERNAL
    SERIALIZATION PRECONDITION, stated plainly: Chain serializes
    appends WITHIN one process (its RLock) and relies on SQLite
    locking + busy-retry ACROSS processes; it does NOT provide a
    cross-process append mutex — Janus serializes its writers with
    DBLOCK and the scripts are single-writer by job design, and a
    deployment that runs two uncoordinated writer processes must
    expect busy-retry latency, not corruption (verify() is the
    arbiter).

Chain entries NEVER contain plate text. Callers chain keyed HMAC
plate references (plate_ref), hashes of case numbers and free text
(case_hash / why_hash), counts, and coded enum fields only.
"""
import base64
import fcntl
import hashlib
import hmac as hmac_mod
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unicodedata
import threading
import time
from datetime import datetime, timedelta, timezone


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(txt):
    return hashlib.sha256(txt.encode()).hexdigest()


# ---------------- plate identity (S3, S15) ----------------
def normalize_plate(plate):
    """The canonical plate form: spaces/hyphens stripped, uppercased.
    Ingest stores this form; suppressions and the hot list key on it;
    a camera that read 'VIC 309' and a suppression entered as 'VIC309'
    are the same vehicle."""
    return re.sub(r"[\s\-]", "", (plate or "")).upper()


def resolve_audit_key(db_path):
    """The plate-HMAC key for scripts: NOCTUA_AUDIT_KEY env, else the
    per-install key file beside the database. Never mints — minting
    is Janus's first-boot act, and a script that cannot find the key
    must say so rather than invent one (S15)."""
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    kf = db_path + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip()
    return None


def plate_ref(key, plate):
    """Keyed HMAC reference for a full plate, over its CANONICAL form
    (state-blind, S3). The same vehicle has the same ref no matter
    which state a bridge guessed or how the camera spaced the text."""
    return "pref:" + hmac_mod.new(
        key.encode(), normalize_plate(plate).encode(),
        hashlib.sha256).hexdigest()[:24]


def legacy_plate_ref(key, plate, state=""):
    """The 1.1 formula (janus11/janus.py): HMAC over
    "{PLATE}|{STATE}" with both sides uppercased and the plate
    taken AS SUBMITTED — 1.1 never canonicalized before hashing,
    so a suppression placed as 'VIC 309' was keyed over the text
    'VIC 309|AR'. Kept ONLY so key verification and the pin
    ceremony can recognize references written by 1.1 installs."""
    msg = "%s|%s" % ((plate or "").upper(), (state or "").upper())
    return "pref:" + hmac_mod.new(
        key.encode(), msg.encode(), hashlib.sha256).hexdigest()[:24]


def key_ref_candidates(key, plate, state=""):
    """EVERY reference `key` could have written for this plate
    (1.2.3, R3): the current canonical formula, and the 1.1 legacy
    formula over the plate text as stored and over its canonical
    form. Key verification (janus boot) and the pin ceremony
    (provision.py) both ask "is the stored ref IN this set?" —
    one implementation, so the ceremony can never again refuse
    the key Janus would accept, or accept one it would refuse
    (round 6: provision.py carried a literal "PLATE|" formula
    that matched nothing any build ever wrote, and Janus's own
    check missed the as-stored-text legacy form, so a 1.1
    suppression stored as 'VIC 309' locked the install out with
    its own original key — seat 2 F1 / Gemini F3)."""
    if plate is None:
        return set()
    return {plate_ref(key, plate),
            legacy_plate_ref(key, plate, state),
            legacy_plate_ref(key, normalize_plate(plate), state)}


def frag_ref(key, frag):
    """Keyed HMAC reference for a search FRAGMENT — a different HMAC
    domain ('FRAG|'), so a fragment ref can never collide with a
    plate ref."""
    return "pref:" + hmac_mod.new(
        key.encode(), ("FRAG|" + (frag or "").upper()).encode(),
        hashlib.sha256).hexdigest()[:24]


def text_hash(txt):
    """SHA-256 of free text (a case number, a justification) for chain
    payloads: the chain proves WHAT was referenced without storing
    the text itself (S11)."""
    return sha(txt or "")


def case_ref(key, case_no):
    """Keyed HMAC reference for a CASE NUMBER (1.2.1, P11/A36). 1.2
    chained case_hash = bare SHA-256(case_no); the case-number space
    is small and structured (YYYY-NNNN, ~10^5), so anyone holding
    the chain — a partner's chain_auditor, by design — could reverse
    every case number in seconds. The keyed form proves WHAT was
    referenced to key holders and nothing to anyone else."""
    return "cref:" + hmac_mod.new(
        key.encode(), ("CASE|" + (case_no or "")).encode(),
        hashlib.sha256).hexdigest()[:24]


def text_ref(key, txt):
    """Keyed HMAC reference for free text (a justification) — the
    same reasoning as case_ref, a different HMAC domain."""
    return "tref:" + hmac_mod.new(
        key.encode(), ("TEXT|" + (txt or "")).encode(),
        hashlib.sha256).hexdigest()[:24]


def canonical_bytes(obj):
    """The one canonical signing form: JSON with sorted keys and
    tight separators, UTF-8. Checkpoints, audit reports, rotation
    schedules, and Compact receipts all sign THESE bytes — two
    implementations that canonicalize differently sign different
    documents, so there is exactly one function (S7/S8)."""
    return json.dumps(obj, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def checkpoint_signed_bytes(cp):
    """The bytes a checkpoint's Ed25519 signature covers: agency,
    date, entries, root, ts — the anchor facts. The signature and
    public key fields themselves are, obviously, not signed."""
    return canonical_bytes({k: cp.get(k) for k in
                            ("agency", "date", "entries", "root", "ts")})


# ---------------- the plate-data registry (S1) ----------------
# Every table.column and folder that can hold plate text or
# plate-derived time+place, with its retention class. retention.py
# purges by this list; sentinel_audit.py checks the oldest item in
# every registered store against its class; the schema test fails the
# build if a plate-ish column or a data folder is not listed here.
#
# class meanings (days resolved by the consumer from env):
#   reads          RETENTION_DAYS from receipt
#   hits           HOLD_DAYS unless held or exported-unreleased
#   derived        RETENTION_DAYS (fragments, free text, share text)
#   tier3_results  RETENTION_DAYS (matched read/hit ids, legacy bodies)
#   hotlist        entry lifetime; expired entries deactivate, dead
#                  rows purge at RETENTION_DAYS
#   suppression    order lifetime; plate TEXT nulled 30 days after
#                  release (the keyed ref stays with the order record)
#   evidence       until release (either SS 1804(b) exit) + 30 days,
#                  then the bundle is destroyed
#   evidence_text  free text in the evidence row; nulled 30 days
#                  after the bundle is destroyed
#   plate_free     asserted plate-free by construction (sink, spool)
#   external       outside Janus's control (Frigate media) —
#                  documented, not enforced
REGISTRY_VERSION = "1.2.6"
PLATE_DATA_STORES = [
    {"store": "reads.plate", "kind": "table", "table": "reads",
     "column": "plate", "ts_col": "ts", "class": "reads",
     "action": "delete_rows_read_guarded"},
    {"store": "reads.plate_raw", "kind": "table", "table": "reads",
     "column": "plate_raw", "ts_col": "ts", "class": "reads",
     "action": "delete_rows_read_guarded"},
    {"store": "hits.read_plate", "kind": "table", "table": "hits",
     "column": "read_plate", "ts_col": "ts", "class": "hits",
     "action": "delete_rows_guarded"},
    {"store": "hits.entry_plate", "kind": "table", "table": "hits",
     "column": "entry_plate", "ts_col": "ts", "class": "hits",
     "action": "delete_rows_guarded"},
    {"store": "hotlist_members.plate", "kind": "table",
     "table": "hotlist_members", "column": "plate",
     "ts_col": "added_ts", "class": "hotlist",
     "action": "purge_inactive"},
    {"store": "suppressions.plate", "kind": "table",
     "table": "suppressions", "column": "plate", "ts_col": "ts",
     "class": "suppression", "action": "null_after_release"},
    {"store": "suppressions.plate_ref", "kind": "table",
     "table": "suppressions", "column": "plate_ref", "ts_col": "ts",
     "class": "suppression", "action": "none",
     "note": "keyed HMAC ref — pseudonymous, retained with the "
             "order record so releases stay auditable"},
    {"store": "tier3_requests.plate_fragment", "kind": "table",
     "table": "tier3_requests", "column": "plate_fragment",
     "ts_col": "created_ts", "class": "derived",
     "action": "scrub_fragment"},
    {"store": "tier3_requests.results", "kind": "table",
     "table": "tier3_requests", "column": "results",
     "ts_col": "created_ts", "class": "tier3_results",
     "action": "null_columns",
     "note": "LEGACY 1.0/1.1 serialized result bodies; 1.2 stores "
             "ids only. Retention nulls legacy bodies at class age."},
    {"store": "tier3_requests.results_read_ids", "kind": "table",
     "table": "tier3_requests", "column": "results_read_ids",
     "ts_col": "created_ts", "class": "tier3_results",
     "action": "null_columns"},
    {"store": "tier3_requests.results_hit_ids", "kind": "table",
     "table": "tier3_requests", "column": "results_hit_ids",
     "ts_col": "created_ts", "class": "tier3_results",
     "action": "null_columns"},
    {"store": "tier3_requests.why", "kind": "table",
     "table": "tier3_requests", "column": "why",
     "ts_col": "created_ts", "class": "derived",
     "action": "null_columns",
     "note": "free text — a justification can name a plate"},
    {"store": "tier3_requests.auth_basis", "kind": "table",
     "table": "tier3_requests", "column": "auth_basis",
     "ts_col": "created_ts", "class": "derived",
     "action": "null_columns",
     "note": "free text — a warrant names its plate"},
    {"store": "tier3_requests.review_note", "kind": "table",
     "table": "tier3_requests", "column": "review_note",
     "ts_col": "created_ts", "class": "derived",
     "action": "null_columns"},
    {"store": "holds.reason", "kind": "table", "table": "holds",
     "column": "reason", "ts_col": "placed_ts", "class": "derived",
     "action": "null_columns",
     "note": "free text — a hold's reason can name a plate (1.2.1, "
             "P10: round 4 found this store unregistered)"},
    {"store": "witness_attestations.detail", "kind": "table",
     "table": "witness_attestations", "column": "detail",
     "ts_col": "ts", "class": "derived", "action": "null_columns",
     "note": "free text filed by a witness — recorded as theirs, "
             "purged like ours (1.2.1, P10)"},
    {"store": "case_searches.frag", "kind": "table",
     "table": "case_searches", "column": "frag", "ts_col": None,
     "day_col": "day", "class": "derived", "action": "delete_rows"},
    {"store": "share_queries.why", "kind": "table",
     "table": "share_queries", "column": "why", "ts_col": "ts",
     "class": "derived", "action": "null_columns",
     "note": "a partner's free text — recorded as theirs, purged "
             "like ours"},
    {"store": "share_queries.plate_ref", "kind": "table",
     "table": "share_queries", "column": "plate_ref", "ts_col": "ts",
     "class": "keyed_ref", "action": "none",
     "note": "keyed HMAC ref — pseudonymous; the row is the "
             "rate-limit and audit record (1.2.2, Q8: classed "
             "keyed_ref — 1.2.1's 'derived' class made the breach "
             "check flag every ordinary share forever)"},
    {"store": "share_queries.case_ref", "kind": "table",
     "table": "share_queries", "column": "case_ref", "ts_col": "ts",
     "class": "keyed_ref", "action": "none",
     "note": "the partner's case reference, stored KEYED (case_ref) "
             "since 1.2.2 (Q7) — 1.2.1 stored partner-supplied raw "
             "text here, an unbounded free-text plate store "
             "controlled by the partner (round 5, ChatGPT F5C)"},
    {"store": "evidence bundles", "kind": "folder", "folder": "evidence",
     "class": "evidence", "action": "destroy_after_release"},
    {"store": "evidence.expand_reason", "kind": "table",
     "table": "evidence", "column": "expand_reason",
     "ts_col": "export_ts", "class": "evidence_text",
     "action": "null_after_destroy"},
    {"store": "evidence.disp_note", "kind": "table",
     "table": "evidence", "column": "disp_note",
     "ts_col": "export_ts", "class": "evidence_text",
     "action": "null_after_destroy"},
    {"store": "backups", "kind": "folder", "folder": "backups",
     "class": "reads", "action": "prune_sets",
     "note": "a backup set contains a full DB copy — it inherits "
             "the reads class and prunes by default"},
    {"store": "pre-restore copies", "kind": "glob",
     "pattern": "<db>.pre-restore-*", "class": "reads",
     "action": "prune_copies"},
    {"store": "sqlite wal", "kind": "file", "pattern": "<db>-wal",
     "class": "db", "action": "none",
     "note": "the database's write-ahead log — it holds whatever "
             "the database holds, for exactly as long as the "
             "database does (1.2.1, P10: declared, class follows "
             "the DB)"},
    {"store": "sqlite shm", "kind": "file", "pattern": "<db>-shm",
     "class": "db", "action": "none",
     "note": "the WAL's shared-memory index — follows the DB"},
    {"store": "sqlite journal", "kind": "file",
     "pattern": "<db>-journal", "class": "db", "action": "none",
     "note": "rollback journal — follows the DB"},
    {"store": "sentinel sink", "kind": "asserted",
     "class": "plate_free", "action": "none"},
    {"store": "sentinel spool", "kind": "asserted",
     "class": "plate_free", "action": "none"},
    {"store": "totp secrets", "kind": "file",
     "pattern": "<db>.totp.json", "class": "plate_free",
     "action": "none",
     "note": "1.2.4 (S11): per-account TOTP secrets + recovery-code "
             "hashes, mode 0600, beside the DB — a credential store, "
             "never plate data; excluded from backup sets, so a "
             "restore forces re-enrollment"},
    {"store": "frigate media", "kind": "asserted",
     "class": "external", "action": "none",
     "note": "Frigate's own event media lives outside Janus; its "
             "retention is a deployment setting (see docs/NETWORK "
             "and the Commission's open questions), not enforced here"},
]


def class_days(entry, retention_days, hold_days):
    """The age limit (days) for a registry entry, or None when the
    class is not a simple age (evidence, suppression, asserted)."""
    cls = entry["class"]
    if cls in ("reads", "derived", "tier3_results"):
        return retention_days
    if cls == "hits":
        return hold_days
    if cls == "hotlist":
        return retention_days
    return None


# ---------------- the non-plate allowlist (1.2.1, P10) ----------------
# EVERY column of EVERY table is either in PLATE_DATA_STORES (above)
# or named here. The schema test is a FULL-COLUMN ALLOWLIST built
# from these two manifests: a new column that lands in neither fails
# the build, whatever its name — round 4's A16 slipped plate data
# past 1.2's name-regex test in a column called vehicle_tag and a
# table called ocr_cache. Columns are listed per table with the
# reason they are not plate stores; case numbers appear here (not in
# the registry) because the registry governs plate text and
# plate-derived time+place — a case number is an identifier whose
# chain exposure is separately controlled (case_ref, keyed).
NON_PLATE_COLUMNS = {
    "audit": {"seq", "ts", "kind", "payload", "prev", "hash"},
    "sink_state": {"id", "ok", "errors", "last_error", "last_error_ts",
                   "last_streamed_seq", "tail_seq", "tail_hash"},
    "sink_pending": {"seq", "hash", "queued_ts"},
    "scrub_state": {"kind", "last_ts"},
    "reads": {"id", "ts", "cam", "state", "conf", "cam_ts", "skew_s",
              "event_id", "supersedes", "phase"},
    "hotlist_members": {"state", "list_source", "case_no", "category",
                        "added_by", "added_ts", "expires_ts", "active",
                        # 1.2.6 (U6): 1 while the entry awaits the
                        # supervisor queue's decision — a workflow
                        # flag, not plate data.
                        "pending"},
    "hits": {"id", "ts", "cam", "state", "list_name", "category",
             "status", "decided_by", "case_no", "decided_ts",
             "suppressed", "read_id",
             # 1.2.6 (U4): the id of the hit that superseded this
             # one — an internal identifier, not plate data.
             "superseded_by"},
    "holds": {"id", "scope", "ref", "placed_by", "placed_ts",
              "released_by", "released_ts", "active", "review_by",
              "case_no"},
    "outcomes": {"hit_id", "list_name", "category", "confirmed",
                 "arrest", "prosecution", "reviewed", "status",
                 "updated_by", "updated_ts", "hit_ts"},
    "case_searches": {"case_no", "day"},
    "case_flags": {"case_no", "day"},
    "suppressions": {"id", "state", "order_ref", "placed_by",
                     "case_no", "ts", "active", "release_requested_by",
                     "release_order_ref", "released_ts"},
    "counters": {"day", "camera_id", "reads", "alerts"},
    "lists_checked": {"day", "list_name"},
    "list_registry": {"list_name", "created_by", "ts"},
    "heartbeats": {"job", "ts", "ok", "detail"},
    "tier3_requests": {"id", "requester", "case_no", "basis_type",
                       "status", "created_ts", "decided_by",
                       "decided_ts", "emergency", "needs_review",
                       "review_finding", "reviewed_by", "reviewed_ts",
                       "results_count", "auditor_review_finding",
                       "auditor_reviewed_by", "auditor_reviewed_ts"},
    "evidence": {"hit_id", "export_ts", "export_by", "manifest_hash",
                 "bundle", "scope", "prosecutor_name",
                 "prosecutor_date", "released_by", "released_ts",
                 "destroyed_ts", "destroyed_by", "destroy_by",
                 "disp_outcome", "disp_by", "disp_date",
                 "disp_posted_by", "disp_confirmed_by",
                 "disp_confirmed_ts", "disp_ts"},
    "report_snapshots": {"id", "from_ts", "to_ts", "compiled_by",
                         "compiled_ts", "body"},
    "partners": {"agency", "endpoint", "audit_key_fingerprint",
                 "pubkey_pem", "agreement_ref", "status", "added_by",
                 "added_ts"},
    "compact_receipts": {"id", "agency", "root", "entries", "sig",
                         "checkpoint_ts", "verified", "received_ts"},
    "compact_audits": {"id", "agency", "ok", "detail", "report_hash",
                       "ts"},
    "share_queries": {"id", "agency", "basis_type", "tier",
                      "result_count", "outcome", "ts"},
    "rotation_schedules": {"id", "cycle_start", "period_days",
                           "members_count", "schedule_hash", "schedule",
                           "published_by", "published_ts"},
    "witness_attestations": {"id", "agency", "cycle_start", "round_no",
                             "ok", "ts"},
    "rotation_contributions": {"cycle_start", "agency", "nonce_hash",
                               "nonce", "committed_ts", "revealed_ts",
                               "ceremony_id"},
    "meta": {"key", "value"},
}


def schema_unregistered(db):
    """[(table, column)] for every column in the database that is in
    NEITHER PLATE_DATA_STORES nor NON_PLATE_COLUMNS — the full-column
    allowlist check (P10). An unknown TABLE fails wholesale: none of
    its columns are in either manifest."""
    registered = {(e.get("table"), e.get("column"))
                  for e in PLATE_DATA_STORES if e["kind"] == "table"}
    out = []
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")]
    for t in tables:
        allowed = NON_PLATE_COLUMNS.get(t, set())
        for row in db.execute("PRAGMA table_info(%s)" % t):
            col = row[1]
            if (t, col) not in registered and col not in allowed:
                out.append((t, col))
    return out


# ---------------- the ONE registry breach check (1.2.1, P10) ----------------
# The hit-protection predicate, shared verbatim by retention.py's
# purge and by registry_breaches below: a hit is protected while a
# VALID hold covers it or an UNRELEASED evidence bundle covers it.
# A hold is valid only while its review date is live — not overdue,
# and not beyond 150 days from placement (P13: paperwork alone never
# extends a hit past the statutory cap). An evidence row protects
# only when a bundle actually exists and neither SS 1804(b) exit
# (prosecutor release, confirmed disposition) has occurred — a
# disposition note with no export protects nothing.
HOLD_PROTECTED_SQL = (
    "EXISTS (SELECT 1 FROM holds WHERE active=1 AND "
    "((scope='hit' AND ref = CAST(hits.id AS TEXT)) OR "
    "(scope='case' AND ref = hits.case_no)) AND "
    "review_by IS NOT NULL AND date(review_by) >= date('now') AND "
    "date(review_by) <= date(placed_ts, '+150 days'))")

# Kept for import compatibility; the holds leg only since 1.2.2 —
# the evidence leg needs the filesystem (see hit_protected).
HIT_PROTECTED_SQL = HOLD_PROTECTED_SQL

HITS_CAP_DAYS = 150


def _evidence_dir_default(db_path=None):
    env = os.environ.get("NOCTUA_EVIDENCE_DIR")
    if env:
        return env
    if db_path:
        return os.path.join(os.path.dirname(os.path.abspath(db_path)),
                            "evidence")
    return None


def hit_protected(db, hit_id, evidence_dir=None, db_path=None):
    """True when hit `hit_id` is protected: a VALID hold covers it
    (HOLD_PROTECTED_SQL — 1.2.2: strict ref equality; 1.2.1's
    GLOB '[0-9]*' + CAST made the malformed ref '1garbage' silently
    protect hit 1, round 5 ChatGPT F6), or an UNRELEASED evidence
    bundle covers it AND THE BUNDLE EXISTS ON DISK (1.2.2, Q7: a
    bundle deleted from disk protected its hit forever in 1.2.1 —
    the SQL never looked, round 5 ChatGPT F5A)."""
    row = db.execute(
        "SELECT 1 FROM hits WHERE hits.id=? AND (%s)"
        % HOLD_PROTECTED_SQL, (hit_id,)).fetchone()
    if row is not None:
        return True
    if evidence_dir is None:
        evidence_dir = _evidence_dir_default(db_path)
    for (bundle,) in db.execute(
            "SELECT bundle FROM evidence WHERE hit_id=? AND "
            "bundle IS NOT NULL AND destroyed_ts IS NULL AND "
            "released_ts IS NULL AND disp_confirmed_ts IS NULL",
            (hit_id,)):
        if evidence_dir and os.path.isdir(
                os.path.join(evidence_dir, bundle)):
            return True
    return False


def _cutoff_iso(days, now_dt):
    return (now_dt - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_cutoff(days, now_dt):
    """THE timestamp cutoff (1.2.2, Q6): an item timestamped before
    this instant is past a `days`-day class. retention.py and
    registry_breaches both call this — one clock, so the purge
    deletes exactly what the check flags."""
    return _cutoff_iso(days, now_dt)


def day_cutoff(days, now_dt):
    """THE day-string cutoff (1.2.2, Q6): a day-column row (YYYY-MM-DD)
    is past its class when its day is before this date. 1.2.1's check
    compared day strings against a full timestamp while the purge
    compared against a date — a boundary-day row was flagged as a
    breach the purge would never clear (round 5, Gemini N2)."""
    return (now_dt - timedelta(days=days)).strftime("%Y-%m-%d")


def disp_note_days(hold_days):
    """The unconfirmed-disposition-note clock (1.2.3, R15):
    HOLD_DAYS + 30, CAPPED at the 150-day statutory ceiling. With
    HOLD_DAYS above 120 the uncapped sum outlived the cap — a note
    could park a plate past the day its hit had to purge (round 6,
    Gemini M12). registry_breaches() and retention.py both call
    this, so the checker and the purger still share one clock
    (Q6)."""
    return min(hold_days + 30, HITS_CAP_DAYS)


def hit_deletable(db, hit_id, hit_ts, retention_days, hold_days,
                  now_dt, evidence_dir=None, db_path=None):
    """THE hit-retention decision (1.2.2, Q6): True when the hit may
    be purged NOW — past the 150-day statutory cap regardless of
    protection, or past its class (the LATER of the retention and
    hold classes, exactly as 1.2.1's two clocks were documented to
    combine) with no valid hold and no on-disk unreleased bundle.
    Exact timestamps everywhere; 1.2.1's purge used whole-day floor
    arithmetic while its check used exact seconds, so the two
    disagreed by up to a day in both directions (round 5, Gemini N2 /
    Claude R5-04/R5-05)."""
    if hit_ts < ts_cutoff(HITS_CAP_DAYS, now_dt):
        return True
    eff = max(hold_days, retention_days)
    if hit_ts >= ts_cutoff(eff, now_dt):
        return False
    return not hit_protected(db, hit_id, evidence_dir=evidence_dir,
                             db_path=db_path)


def read_deletable(db, read_id, read_ts, retention_days, hold_days,
                   now_dt, evidence_dir=None, db_path=None):
    """THE reads-retention decision (1.2.3, R16 — the Q6 one-decision
    principle extended to the reads class; late Round 6 finding,
    DeepSeek F3): a read past the reads class may be purged UNLESS a
    hit that references it (hits.read_id) is not itself deletable —
    the read inherits that hit's protection. 1.2.2 purged reads with
    a plain delete_rows on the reads clock while hit_deletable
    guarded only the hit row, so a held hit survived day 14 but its
    reads did not: a later evidence export (or re-export) produced
    a bundle whose reads.json was empty — releasable but hollow.
    Past the 150-day cap the read purges regardless, exactly as its
    hit does. retention.py's purge and registry_breaches both call
    this — one decision, as with hits."""
    if read_ts < ts_cutoff(HITS_CAP_DAYS, now_dt):
        return True
    if read_ts >= ts_cutoff(retention_days, now_dt):
        return False
    for hid, hts in db.execute(
            "SELECT id, ts FROM hits WHERE read_id=?",
            (read_id,)).fetchall():
        if not hit_deletable(db, hid, hts, retention_days, hold_days,
                             now_dt, evidence_dir=evidence_dir,
                             db_path=db_path):
            return False
    return True


def parse_expiry(value):
    """Parse an operator-supplied hot-list expiry into the canonical
    UTC instant form, or None when it is not an ISO-8601 date /
    datetime (1.2.2, Q4). A bare date means the entry is good
    THROUGH that day (end of day UTC) — the operator's intent when
    they write the day a listing expires. 1.2.1 stored the text as
    given and compared it as a string, so '06/30/2027' and epoch
    '1780000000' sorted BEFORE every ISO timestamp and the entry was
    treated as expired at its first sighting — a live stolen-vehicle
    listing that never alerted (round 5, Claude R5-02)."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            dt = datetime.strptime(v, "%Y-%m-%d").replace(
                tzinfo=timezone.utc) + timedelta(
                hours=23, minutes=59, seconds=59)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rotation_schedule(members, seed):
    """THE Compact rotation schedule builder (1.2.2, Q23) — one
    implementation, imported by janus.py (which publishes) and
    rotation.py (which verifies); 1.2.1 kept two copies and they had
    already diverged at n=2 (round 5, Qwen F4 / Gemini N8). Shape:
    n<2 inactive; n=2 static (two rounds, each audits the other, in
    sorted order — deterministic, no seed involved); n>=3 the seed's
    Fisher-Yates permutation is the auditor ORDER — round r's auditor
    audits the next member cyclically, so in n rounds every member
    audits exactly once and is audited exactly once."""
    ms = sorted(set(members))
    n = len(ms)
    if n < 2:
        return {"mode": "inactive", "rounds": []}
    if n == 2:
        a, b = ms
        return {"mode": "static",
                "rounds": [{"round": 1, "auditor": a, "audited": b},
                           {"round": 2, "auditor": b, "audited": a}]}
    # The permutation is the algorithm both 1.2.1 implementations
    # already shared: Fisher-Yates driven by the seed's SHA-256
    # byte stream (two bytes at a time, big-endian uint16,
    # j = value % (i+1), i from n-1 down to 1) — kept byte-exact
    # so schedules published by earlier builds still verify.
    order = ms[:]
    stream = bytearray(hashlib.sha256(seed.encode()).digest())
    pos = 0

    def next16():
        nonlocal pos
        while pos + 2 > len(stream):
            stream.extend(hashlib.sha256(bytes(stream)).digest())
        v = (stream[pos] << 8) | stream[pos + 1]
        pos += 2
        return v

    for i in range(n - 1, 0, -1):
        j = next16() % (i + 1)
        order[i], order[j] = order[j], order[i]
    rounds = [{"round": r + 1, "auditor": order[r],
               "audited": order[(r + 1) % n]} for r in range(n)]
    return {"mode": "rotation", "rounds": rounds}


def rotation_signed_portion(schedule):
    """The dict the rotation signature covers (1.2.2, Q23):
    members, seed, rounds, cycle_start AND period_days. 1.2.1's
    portion covered only members/seed/rounds, so period_days could
    be altered (30 -> 120) under a still-valid signature (round 5,
    DeepSeek F5). One implementation, shared by janus.py (which
    signs) and rotation.py (which verifies).

    1.2.3 (R6): a 1.2.3 document's portion ALSO covers
    "nonces_sha256" — a hash of the revealed nonces — whenever the
    document carries nonces. 1.2.2's portion left the nonces
    outside the signature, so they could be stripped from a
    published schedule without breaking it, silently un-proving
    the seed (round 6, Gemini M4). The version gate keeps 1.2.2
    documents verifiable under the portion they were actually
    signed with."""
    portion = {"members": schedule["members"],
               "seed": schedule["seed"],
               "rounds": schedule["rounds"],
               "cycle_start": schedule["cycle_start"],
               "period_days": schedule["period_days"]}
    nonces = schedule.get("nonces")
    if nonces and str(schedule.get("version", "")) != "1.2.2":
        portion["nonces_sha256"] = hashlib.sha256(
            canonical_bytes(nonces)).hexdigest()
    return portion


def registry_breaches(db, retention_days, hold_days, db_path=None,
                      backup_dir=None, evidence_dir=None):
    """{store: detail} for every registered store currently past its
    class — the ONE implementation Janus /health and sentinel_audit
    both consume (P10), mirroring retention.py's purge semantics
    exactly: what this function calls a breach is what the next
    retention run would purge, and what it excuses (a scrubbed
    pref: fragment, a destroyed bundle checked ON DISK, a hit under
    a valid hold of EITHER scope or under unreleased evidence) the
    purge excuses too. `db` is any sqlite3 connection (read-only is
    fine). Filesystem stores resolve against db_path's directory,
    NOCTUA_BACKUP_DIR / NOCTUA_EVIDENCE_DIR, or the explicit args."""
    import glob as glob_mod
    now_dt = datetime.now(timezone.utc)
    now = now_iso()
    breaches = {}
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    db_dir = os.path.dirname(os.path.abspath(db_path)) if db_path \
        else None
    if evidence_dir is None:
        evidence_dir = os.environ.get("NOCTUA_EVIDENCE_DIR") or (
            os.path.join(db_dir, "evidence") if db_dir else None)
    if backup_dir is None:
        backup_dir = os.environ.get("NOCTUA_BACKUP_DIR") or (
            os.path.join(db_dir, "backups") if db_dir else None)

    def flag(store, detail):
        breaches.setdefault(store, detail)

    for e in PLATE_DATA_STORES:
        store, action = e["store"], e["action"]
        days = class_days(e, retention_days, hold_days)
        if e["kind"] == "table":
            table, col = e["table"], e["column"]
            if table not in tables:
                flag(store, "registered table %s is MISSING" % table)
                continue
            ts_col = e.get("ts_col") or e.get("day_col")
            if action == "delete_rows_guarded":
                # 1.2.2 (Q6): decided by hit_deletable() row by row —
                # the SAME function retention.py's purge calls, with
                # the evidence leg checked ON DISK. 1.2.1's SQL here
                # and the purge's floor-day arithmetic disagreed in
                # both directions.
                bad = 0
                for hid, hts in db.execute(
                        "SELECT id, ts FROM hits").fetchall():
                    if hit_deletable(db, hid, hts, retention_days,
                                     hold_days, now_dt,
                                     evidence_dir=evidence_dir,
                                     db_path=db_path):
                        bad += 1
                        break
                if bad:
                    flag(store, "hit(s) past the hits class (%d days) "
                                "with no valid hold or unreleased "
                                "evidence — or past the 150-day cap"
                         % days)
                continue
            if action == "delete_rows_read_guarded":
                # 1.2.3 (R16): decided by read_deletable() row by
                # row — the SAME function retention.py's purge
                # calls. A read past its class whose hit is not
                # deletable is NOT a breach: it is protection
                # working (DeepSeek F3's hollow bundle came from
                # the purge ignoring this, not from the check).
                bad = 0
                for rid, rts in db.execute(
                        "SELECT id, ts FROM reads").fetchall():
                    if read_deletable(db, rid, rts, retention_days,
                                      hold_days, now_dt,
                                      evidence_dir=evidence_dir,
                                      db_path=db_path):
                        bad += 1
                        break
                if bad:
                    flag(store, "read(s) past the reads class "
                                "(%d days) not referenced by any "
                                "protected hit — or past the 150-day "
                                "cap" % days)
                continue
            if action == "purge_inactive":
                row = db.execute(
                    f"SELECT MIN({ts_col}) FROM {table} WHERE active=0"
                ).fetchone()
                if row and row[0] and str(row[0]) < _cutoff_iso(
                        days, now_dt):
                    flag(store, "inactive row older than its class "
                                "(%d days)" % days)
                continue
            if action == "null_after_release":
                cut30 = _cutoff_iso(30, now_dt)
                n = db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE active=0 AND "
                    f"released_ts IS NOT NULL AND released_ts < ? AND "
                    f"{col} IS NOT NULL LIMIT 1", (cut30,)).fetchone()[0]
                if n:
                    flag(store, "plate text still present 30+ days "
                                "after the order's release")
                continue
            if action == "null_after_destroy":
                cut30 = _cutoff_iso(30, now_dt)
                n = db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE "
                    f"destroyed_ts IS NOT NULL AND destroyed_ts < ? "
                    f"AND {col} IS NOT NULL LIMIT 1",
                    (cut30,)).fetchone()[0]
                if not n and table == "evidence" \
                        and col == "disp_note":
                    # 1.2.2 (Q7): a disposition note's clock does not
                    # wait for a bundle that may never exist — it
                    # also runs from the CONFIRMED disposition, and a
                    # disposition left unconfirmed past its hit's own
                    # horizon loses the free text (never the outcome
                    # fields). Mirrors retention.py exactly.
                    stale = _cutoff_iso(disp_note_days(hold_days),
                                        now_dt)
                    n = db.execute(
                        "SELECT COUNT(*) FROM evidence WHERE "
                        "disp_note IS NOT NULL AND ("
                        "(disp_confirmed_ts IS NOT NULL AND "
                        "disp_confirmed_ts < ?) OR "
                        "(disp_confirmed_ts IS NULL AND "
                        "destroyed_ts IS NULL AND disp_ts IS NOT "
                        "NULL AND disp_ts < ?)) LIMIT 1",
                        (cut30, stale)).fetchone()[0]
                if n:
                    flag(store, "free text still present past its "
                                "destruction clock (30 days after "
                                "destruction or confirmed disposition; "
                                "an unconfirmed disposition's note "
                                "expires with its hit's horizon)")
                continue
            if days is None or not ts_col:
                continue  # lifetime-governed / asserted-by-registry
            if action == "null_columns":
                where = f"{col} IS NOT NULL"
            elif action == "scrub_fragment":
                where = f"{col} IS NOT NULL AND {col} NOT LIKE 'pref:%'"
            else:
                where = "1=1"
            row = db.execute(
                f"SELECT MIN({ts_col}) FROM {table} WHERE {where}"
            ).fetchone()
            # 1.2.2 (Q6): day-column stores compare against the DAY
            # cutoff; timestamp stores against the timestamp cutoff.
            cut = day_cutoff(days, now_dt) if e.get("day_col") \
                and not e.get("ts_col") else _cutoff_iso(days, now_dt)
            if row and row[0] and str(row[0]) < cut:
                flag(store, "oldest item past its class (%d days)"
                     % days)
        elif e["kind"] == "folder" and e.get("folder") == "evidence":
            if "evidence" not in tables or not evidence_dir:
                continue
            rows = db.execute(
                "SELECT hit_id, bundle, destroyed_ts, destroy_by, "
                "released_ts, disp_confirmed_ts FROM evidence"
            ).fetchall()
            known = {r[1] for r in rows if r[1]}
            hit_ids = {r[0] for r in db.execute("SELECT id FROM hits")}
            for (hit_id, bundle, destroyed_ts, destroy_by,
                 released_ts, disp_confirmed_ts) in rows:
                if not bundle:
                    continue
                on_disk = os.path.isdir(
                    os.path.join(evidence_dir, bundle))
                if destroyed_ts and on_disk:
                    flag(store, "bundle for hit %s is destroyed on "
                                "paper but still on disk" % hit_id)
                elif not destroyed_ts and destroy_by \
                        and destroy_by < now and on_disk:
                    flag(store, "bundle for hit %s is past destroy_by "
                                "and still on disk" % hit_id)
                elif not destroyed_ts and not released_ts \
                        and not disp_confirmed_ts and on_disk \
                        and hit_id not in hit_ids:
                    # 1.2.2 (Q7): the hit purged out from under an
                    # unreleased bundle — the bundle's lifecycle
                    # endpoints used to key on the hit row, so it
                    # could never be released or destroyed. The
                    # endpoints now key on the evidence record; this
                    # flag keeps the stranded state VISIBLE until
                    # someone works it.
                    flag(store, "bundle for hit %s is STRANDED — "
                                "unreleased, and its hit row has "
                                "purged" % hit_id)
            if os.path.isdir(evidence_dir):
                cut_ts = now_dt.timestamp() - retention_days * 86400
                for name in sorted(os.listdir(evidence_dir)):
                    p = os.path.join(evidence_dir, name)
                    if os.path.isdir(p) and name not in known:
                        try:
                            m = os.path.getmtime(p)
                        except OSError:
                            continue
                        if m < cut_ts:
                            flag(store, "ORPHANED bundle %s on disk "
                                        "(no evidence row) past the "
                                        "reads class" % name)
        elif e["kind"] == "folder" and e.get("folder") == "backups":
            if not backup_dir or not os.path.isdir(backup_dir):
                continue
            cut_ts = now_dt.timestamp() - days * 86400
            for name in sorted(os.listdir(backup_dir)):
                p = os.path.join(backup_dir, name)
                if name.startswith("backup-") and os.path.isdir(p):
                    try:
                        m = os.path.getmtime(p)
                    except OSError:
                        continue
                    if m < cut_ts:
                        flag(store, "backup set %s older than the "
                                    "reads class (%d days)"
                             % (name, days))
                        break
        elif e["kind"] == "glob":
            if not db_path:
                continue
            cut_ts = now_dt.timestamp() - days * 86400
            for p in glob_mod.glob(e["pattern"].replace("<db>", db_path)):
                try:
                    m = os.path.getmtime(p)
                except OSError:
                    continue
                if m < cut_ts:
                    flag(store, "pre-restore copy older than the "
                                "reads class (%d days)" % days)
                    break
    return breaches


# ---------------- TOTP (RFC 6238, shared helper) ----------------
# 1.2.5 (T1/T8): ONE implementation of the code math, used by
# Janus (via janus._totp_code), by provision.py's two-key shell
# confirmation, and available to the standalone auditor tooling —
# so the shell can verify a confirmer's code without Janus
# running, and every implementation agrees by construction.
def totp_code(secret_b32, counter):
    """The 6-digit code for a base32 secret at a 30-second counter.
    1.2.6 (U11): the base32 PADDING TOLERANCE lives here now, not
    only in janus._totp_code's wrapper — the standalone auditor
    tooling calls this function directly, and an unpadded secret
    raised binascii.Error there while Janus accepted the same
    secret (round 8 addendum, Qwen Q-F6 parity item)."""
    secret_b32 = secret_b32 + "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(secret_b32)
    digest = hmac_mod.new(key, counter.to_bytes(8, "big"),
                          hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    return "%06d" % ((int.from_bytes(digest[off:off + 4], "big")
                      & 0x7FFFFFFF) % 1000000)


def totp_counter_now(offset_steps=0):
    import time as _time
    return int(_time.time()) // 30 + offset_steps


# ---------------- Ed25519 signing (S7) ----------------
# Via the system openssl — the one sanctioned external call. The
# private key lives beside the database at 0600; the public key is
# exportable and is what partners register (by fingerprint).
# 1.2.5 (T8): the binary is resolved ONCE — an explicit
# NOCTUA_OPENSSL override, else the PATH lookup captured at import,
# else the bare name. The PATH residual (a hostile PATH at service
# start still steers the lookup) is documented in CANT-DO.md;
# deployments that care set NOCTUA_OPENSSL to an absolute path.
OPENSSL = os.environ.get("NOCTUA_OPENSSL") \
    or shutil.which("openssl") or "openssl"


def signing_paths(db_path):
    return db_path + ".signing_key.pem", db_path + ".signing_pub.pem"


def ensure_signing_key(db_path):
    """Create the Ed25519 keypair if absent; return (priv, pub)."""
    priv, pub = signing_paths(db_path)
    if not os.path.exists(priv):
        subprocess.run([OPENSSL, "genpkey", "-algorithm", "ED25519",
                        "-out", priv], check=True,
                       capture_output=True, timeout=30)
        os.chmod(priv, 0o600)
    if not os.path.exists(pub):
        subprocess.run([OPENSSL, "pkey", "-in", priv, "-pubout",
                        "-out", pub], check=True,
                       capture_output=True, timeout=30)
    return priv, pub


def load_signing_pub(db_path):
    _priv, pub = signing_paths(db_path)
    if os.path.exists(pub):
        return open(pub).read()
    return None


def pubkey_fingerprint(pub_pem):
    """SHA-256 of the key's DER bytes — the value partners register
    and compare before trusting a public key a checkpoint carries.
    1.2.5 (T6): a MALFORMED key (not a string, undecodable body)
    has no fingerprint — None, never an exception. 1.2.4 raised
    binascii.Error / AttributeError out of this function into
    Janus's checkpoint evaluation, so one crafted checkpoints-file
    line crashed the boot (security round 1, DeepSeek F13). A
    checkpoint carrying such a key simply fails verification,
    which is where the failure belongs."""
    if not isinstance(pub_pem, str):
        return None
    body = "".join(l for l in pub_pem.splitlines()
                   if not l.startswith("-----"))
    try:
        der = base64.b64decode(body, validate=True)
    except (ValueError, TypeError):
        return None
    if not der:
        # 1.2.6 (U11(ii)): an EMPTY or body-less PEM (headers only)
        # decodes to zero bytes — it is not a key and has no
        # fingerprint. 1.2.5 returned sha256(b"") here, a real-
        # looking fingerprint for no key at all (round 8, DeepSeek
        # follow-up F1), contradicting this docstring.
        return None
    return hashlib.sha256(der).hexdigest()


def sign_bytes(priv_path, data):
    """Ed25519-sign data (bytes); return the base64 signature."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        msg = f.name
    sig = msg + ".sig"
    try:
        subprocess.run([OPENSSL, "pkeyutl", "-sign", "-inkey",
                        priv_path, "-rawin", "-in", msg, "-out", sig],
                       check=True, capture_output=True, timeout=30)
        return base64.b64encode(open(sig, "rb").read()).decode()
    finally:
        for p in (msg, sig):
            if os.path.exists(p):
                os.remove(p)


def verify_bytes(pub_pem, data, sig_b64):
    """Verify an Ed25519 signature against a PEM public key."""
    if not pub_pem or not sig_b64:
        return False
    try:
        sig_raw = base64.b64decode(sig_b64)
    except (ValueError, TypeError):
        return False
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
        f.write(pub_pem)
        pubf = f.name
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        msg = f.name
    sigf = msg + ".sig"
    try:
        with open(sigf, "wb") as f:
            f.write(sig_raw)
        r = subprocess.run(
            [OPENSSL, "pkeyutl", "-verify", "-pubin", "-inkey", pubf,
             "-rawin", "-in", msg, "-sigfile", sigf],
            capture_output=True, timeout=30)
        return r.returncode == 0
    finally:
        for p in (pubf, msg, sigf):
            if os.path.exists(p):
                os.remove(p)


# ---------------- the scrubber (S11) ----------------
class ChainScrubError(ValueError):
    """Retained for API compatibility. 1.2's scrubber never raises on
    data paths — it sanitizes and flags (see Chain.append)."""


# A raw plate, normalized (spaces/hyphens removed, uppercased): the
# common US shapes — 2-3 letters + 3-4 digits, 3 digits + 3 letters,
# letter + 3 digits + 2 letters. Only strings ALREADY in normalized
# shape (all-uppercase, no spaces or hyphens) can match: prose,
# timestamps, usernames (dots/lowercase), and case numbers (digits +
# hyphen) never do.
_PLATE_RE = re.compile(
    r"(?:[A-Z]{2,3}[0-9]{3,4}|[0-9]{3}[A-Z]{3}|[A-Z][0-9]{3}[A-Z]{2})")
# Structural fields whose values are configuration/identity, not
# captured data: camera ids come from the camera registry (CAM-101 is
# a camera, not a plate), agency ids from the partner registry
# (CPD-1001 is an agency, not a plate).
_SCRUB_EXEMPT_FIELDS = {"cam", "camera", "agency"}


def _looks_like_plate(value):
    if value.startswith("pref:"):
        return False
    stripped = value.replace(" ", "").replace("-", "")
    if stripped != value:
        return False  # not in normalized shape — prose, not a plate
    if len(stripped) > 10:
        return False
    return bool(_PLATE_RE.fullmatch(stripped)) \
        and any(c.isalpha() for c in stripped) \
        and any(c.isdigit() for c in stripped)


def _plate_shaped_token(txt):
    """True when an already-canonical token (no spaces/hyphens,
    uppercase) is plate-shaped."""
    if len(txt) > 10 or len(txt) < 4:
        return False
    return bool(_PLATE_RE.fullmatch(txt)) \
        and any(c.isalpha() for c in txt) \
        and any(c.isdigit() for c in txt)


# 1.2.5 (T9): Unicode confusables. 1.2.4's tokenization was
# ASCII-only ([A-Za-z0-9]+), so a plate typed with Cyrillic
# homoglyphs ('АВС123' — Cyrillic А, В, С) or full-width forms
# never even became a token and sailed through the scrubber into
# the chain (security round 1, DeepSeek F1 + Claude F17).
# Detection now runs on a FOLDED copy: NFKC normalization (folds
# full-width and compatibility forms) plus a Cyrillic/Greek
# look-alike map. Folding is DETECTION-ONLY — the stored value
# and normalize_plate (hence every plate_ref ever written) are
# untouched; a folded match costs a hashed field, same as any
# other scrubber hit.
_CONFUSABLES = {
    # Cyrillic capitals
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
    "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
    "Х": "X", "Ѕ": "S", "Ј": "J", "І": "I",
    # 1.2.6 (U11(v)): Cyrillic З is a DIGIT look-alike (3), not a
    # letter — round 8's cold seat executed 'BYX12З' sailing
    # through the 1.2.5 fold (C8-13).
    "З": "3",
    # Cyrillic lowercase
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "х": "x", "у": "y", "і": "i", "ѕ": "s", "ј": "j",
    "з": "3",
    # Greek capitals
    "Α": "A", "Β": "B", "Ε": "E", "Η": "H", "Ι": "I",
    "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P",
    "Τ": "T", "Χ": "X", "Ζ": "Z",
    # Greek lowercase
    "α": "a", "ο": "o", "ρ": "p", "τ": "t", "χ": "x",
    "ν": "v", "ι": "i", "κ": "k",
}
_CONFUSABLES_TABLE = {ord(k): v for k, v in _CONFUSABLES.items()}


def _fold_confusables(value):
    """NFKC + confusables fold, for DETECTION only (T9).
    1.2.6 (U11(v)): non-ASCII decimal digits fold to their ASCII
    values too — Arabic-Indic (٣), Extended Arabic-Indic (۳) and
    Devanagari (३) digits are Unicode category Nd, and a plate
    written with them tokenized as plate-shaped in 1.2.5 only when
    the digits happened to be ASCII (round 8, cold-seat F-3). The
    claimed detection classes are now: ASCII plates, Cyrillic/
    Greek letter homoglyphs, Cyrillic З for 3, full-width forms
    (NFKC), and Nd digits of any script. Fragmentation of a plate
    across four or more tokens remains a named NON-claim."""
    folded = unicodedata.normalize("NFKC", value) \
        .translate(_CONFUSABLES_TABLE)
    out = []
    for ch in folded:
        if not ch.isascii() and unicodedata.category(ch) == "Nd":
            try:
                out.append(str(unicodedata.digit(ch)))
                continue
            except (ValueError, TypeError):
                pass
        out.append(ch)
    return "".join(out)


def _contains_plate(value):
    """1.2.2 (Q19): plate detection is TOKEN-AWARE. 1.2.1 only caught
    a string that was, whole and entire, already in normalized plate
    shape — so 'VIC 309', 'VIC-309' and 'plate VIC 309 at the gate'
    sailed through the scrubber as prose (round 5, Vesper F8). Now:
    the whole string canonicalized, and every window of 1-3
    consecutive alphanumeric tokens canonicalized, is checked against
    the plate shapes. A false positive costs a hashed field, never a
    failed write; a false negative costs a plate in the chain.
    1.2.5 (T9): the same checks also run over the confusables-folded
    form of the value, so homoglyph plates are detected too."""
    if value.startswith("pref:"):
        return False
    if _plate_shaped_token(normalize_plate(value)):
        return True
    for text in (value, _fold_confusables(value)):
        tokens = re.findall(r"[A-Za-z0-9]+", text)
        for w in (1, 2, 3):
            for i in range(len(tokens) - w + 1):
                if _plate_shaped_token(
                        "".join(tokens[i:i + w]).upper()):
                    return True
    return False


def _sanitize(value, field="", key=None, exempt_check=None):
    """Return (clean_value, [flagged field paths]). Plate-bearing
    strings are replaced by their KEYED plate_ref when the Chain
    carries the install's audit key (a bare SHA-256 of a plate is a
    dictionary — round 5), else by their SHA-256 — the write
    proceeds, the text does not. The cam / camera / agency / members
    exemptions are VALUE-verified when exempt_check is installed:
    exempt_check(field, value) returns True only for a value the
    deployment actually knows (a registered camera, a registered
    partner, this agency) — an unverified value is treated as data
    (1.2.1 exempted by field NAME, so a plate-shaped string in a
    field CALLED agency was chained raw: round 5, ChatGPT F4)."""
    if isinstance(value, str):
        leaf = field.rsplit(".", 1)[-1].split("[")[0]
        if leaf in _SCRUB_EXEMPT_FIELDS or leaf == "members":
            if exempt_check is None or exempt_check(leaf, value):
                return value, []
            # unverified identity value — fall through to the
            # plate check like any other string
        if _contains_plate(value):
            if key:
                return plate_ref(key, value), [field or "<root>"]
            return sha(value), [field or "<root>"]
        return value, []
    if isinstance(value, dict):
        out, flags = {}, []
        for k, v in value.items():
            cv, fl = _sanitize(v, f"{field}.{k}" if field else str(k),
                               key, exempt_check)
            out[k] = cv
            flags += fl
        return out, flags
    if isinstance(value, (list, tuple)):
        out, flags = [], []
        for i, v in enumerate(value):
            cv, fl = _sanitize(v, f"{field}[{i}]", key, exempt_check)
            out.append(cv)
            flags += fl
        return out, flags
    return value, []


def entry_hash(prev, ts, kind, payload):
    """THE chain hash (1.2.1, P11 — the one verification contract).
    v2 payloads (their JSON carries "v": 2) hash as
    sha(prev | ts | kind | payload) — the audit table's ts and kind
    COLUMNS are inside the hash, so rewriting them breaks the chain
    (round 4, A10). v1 payloads keep the legacy sha(prev | payload)
    so pre-1.2.1 chains still verify. Every consumer — Janus,
    sentinel_audit, compact.py's recompute, restore — hashes through
    here; a private copy of this formula is exactly the drift round
    4 was convened to kill."""
    try:
        v2 = json.loads(payload).get("v") == 2
    except (ValueError, AttributeError):
        v2 = False
    if v2:
        return sha(prev + "|" + ts + "|" + kind + "|" + payload)
    return sha(prev + "|" + payload)


def verify_chain_rows(rows, start_seq=0, start_prev="GENESIS"):
    """Verify a RANGE of chain entries (1.2.3, R8): rows are
    (seq, ts, kind, payload, prev, hash) tuples in seq order,
    expected to begin at start_seq + 1 linked to start_prev. The
    checks are EXACTLY _verify_rows' — hash recomputation plus the
    v1 kind/ts cross-check — factored so the Compact recompute
    (compact.py) and the external auditor (sentinel_audit.py) run
    the same verification Janus runs on its own chain, instead of
    private hash loops that drift (round 6, Gemini F7: both
    reimplementations had lost the v1 cross-check, so a partner
    serving a relabeled v1 chain passed both). Returns the same
    verdict dict as _verify_rows; "entries" counts the rows given
    and "root" is the last row's hash."""
    prev = start_prev
    prev_seq = start_seq
    n = 0
    for row in rows:
        if isinstance(row, dict):
            # HTTP callers hand over /audit/range entry dicts.
            row = (row["seq"], row["ts"], row["kind"],
                   row["payload"], row["prev"], row["hash"])
        seq, ts, kind, payload, stored_prev, stored_hash = row
        n += 1
        if seq != prev_seq + 1:
            return {"ok": False, "broken_at": seq,
                    "reason": "sequence gap — an entry is missing"}
        if stored_prev != prev:
            return {"ok": False, "broken_at": seq}
        if entry_hash(prev, ts, kind, payload) != stored_hash:
            return {"ok": False, "broken_at": seq}
        try:
            pj = json.loads(payload)
        except ValueError:
            pj = None
        if isinstance(pj, dict) and pj.get("v") != 2:
            if pj.get("kind") != kind or pj.get("ts") != ts:
                return {"ok": False, "broken_at": seq,
                        "reason": "v1 entry's kind/ts columns "
                                  "disagree with its payload — the "
                                  "entry was relabeled"}
        prev = stored_hash
        prev_seq = seq
    return {"ok": True, "entries": n, "root": prev}


def _verify_rows(rows):
    """rows: an ITERABLE of (seq, ts, kind, payload, prev, hash) in
    seq order (1.2.2: streamed, not materialized — a 600k-entry chain
    no longer costs a full in-memory copy to verify). The checks
    themselves are verify_chain_rows' (1.2.3, R8 — one
    implementation); this wrapper only preserves the distinct
    head-missing verdict: a chain that does not START at seq 1 has
    lost its head (1.2.2, Q17 — the gap check alone only compared
    consecutive rows, so a chain truncated from the front verified
    as a valid shorter chain)."""
    import itertools
    it = iter(rows)
    try:
        first = next(it)
    except StopIteration:
        return {"ok": True, "entries": 0, "root": "GENESIS"}
    if first[0] != 1:
        return {"ok": False, "broken_at": first[0],
                "reason": "sequence does not start at 1 — the "
                          "head of the chain is missing"}
    return verify_chain_rows(itertools.chain([first], it))


def verify_detached(db_path):
    """verify() over a fresh READ-ONLY connection (S5/S16): never
    creates tables, never takes the write path, safe to call while
    Janus holds its lock."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "ORDER BY seq")
        return _verify_rows(cur)
    finally:
        db.close()


class Chain:
    """One chain writer. SERIALIZATION CONTRACT (1.2.4, S10):
    appends are serialized within a process by this object's RLock
    and across processes only by SQLite's own locking (BEGIN
    IMMEDIATE + busy-retry) — Chain provides NO cross-process
    append mutex, and none is needed for correctness (the hash
    chain is built inside the write transaction; verify() is the
    arbiter), but a caller that needs strict append ORDER across
    processes must serialize externally, as Janus does with
    DBLOCK. Sink delivery is serialized across processes by the
    spool flock (see _deliver_pending)."""

    def __init__(self, db_path, conn=None, key=None):
        # key: the install's audit key, when the caller has it — the
        # scrubber then replaces plate-bearing strings with KEYED
        # plate_refs instead of bare SHA-256s (1.2.2, Q19). Janus
        # passes its key; scripts pass resolve_audit_key()'s result.
        self.key = key
        # exempt_check: callable(leaf_field, value) -> bool,
        # installed by Janus once its config loads — value-verifies
        # the scrubber's cam/agency/members exemptions (Q19).
        self.exempt_check = None
        # conn: Janus passes its OWN connection so a handler's data
        # writes and its chain appends share one transaction (S11).
        # Scripts construct Chain(db_path) and get a private one.
        self.db_path = db_path
        self._own_conn = conn is None
        if conn is not None:
            self.db = conn
        else:
            # check_same_thread=False: the Janus HTTP server is
            # threaded. isolation_level=None (autocommit): append()
            # drives its own BEGIN IMMEDIATE / COMMIT.
            self.db = sqlite3.connect(db_path, check_same_thread=False,
                                      isolation_level=None)
            self.db.execute("PRAGMA busy_timeout = 5000")
            # secure_delete: overwritten content is zeroed, not left
            # recoverable in free pages.
            self.db.execute("PRAGMA secure_delete = ON")
            # journal_mode=WAL needs a brief exclusive lock; when two
            # processes open a FRESH database at the same moment (the
            # S18 stress shape), busy_timeout alone does not always
            # cover the file-creation race — retry the pragma and the
            # DDL below until the lock frees.
            for attempt in range(50):
                try:
                    self.db.execute("PRAGMA journal_mode = WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc) or attempt == 49:
                        raise
                    time.sleep(0.1)
        for attempt in range(50):
            try:
                self.db.execute(
                    """CREATE TABLE IF NOT EXISTS audit(
                         seq INTEGER PRIMARY KEY AUTOINCREMENT,
                         ts TEXT NOT NULL, kind TEXT NOT NULL,
                         payload TEXT NOT NULL, prev TEXT NOT NULL,
                         hash TEXT NOT NULL)""")
                self.db.execute(
                    """CREATE TABLE IF NOT EXISTS sink_state(
                         id INTEGER PRIMARY KEY CHECK(id=1),
                         ok INTEGER DEFAULT 1, errors INTEGER DEFAULT 0,
                         last_error TEXT, last_error_ts TEXT,
                         last_streamed_seq INTEGER DEFAULT 0)""")
                # 1.2.3 (R4): the sink_state ROW is no longer
                # inserted here. Chain construction happens on
                # Janus's shared connection BEFORE the audit-key
                # fingerprint check, and an INSERT is DML — on a
                # KEY_LOCKED boot nothing may write. The row is
                # created lazily by _book_conn() on first sink use,
                # which is always post-boot.
                self.db.execute(
                    """CREATE TABLE IF NOT EXISTS scrub_state(
                         kind TEXT PRIMARY KEY, last_ts REAL)""")
                # 1.2.4 (S1): the durable delivery ledger. A row
                # here is written by _insert_locked in the SAME
                # transaction as its audit row and deleted only
                # when the entry is durably in the sink — the
                # obligation survives crashes, failed verifications
                # and sink outages, and is visible to every process
                # that opens this database.
                self.db.execute(
                    """CREATE TABLE IF NOT EXISTS sink_pending(
                         seq INTEGER PRIMARY KEY, hash TEXT NOT NULL,
                         queued_ts TEXT)""")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or attempt == 49:
                    raise
                time.sleep(0.1)
        # RLock, not Lock: append() holds this while _stream runs,
        # and a spool quarantine discovered mid-stream is chained by
        # _note_quarantine RE-ENTERING append() on the same thread —
        # with a plain Lock that self-deadlocks (found by the 1.2.1
        # builders' suite, hanging on exactly that path).
        self._lock = threading.RLock()
        # Streaming sink: if NOCTUA_SENTINEL_SINK is set, every entry
        # is also appended as a JSON line to that file (flush + fsync
        # per entry). Failures spool beside it and never raise.
        self.sink_path = os.environ.get("NOCTUA_SENTINEL_SINK") or None
        self.spool_path = (self.sink_path + ".spool") if self.sink_path \
            else None
        # 1.2.1 (P11): entries appended inside a caller-held
        # transaction wait here until flush_deferred() runs after
        # the commit; quarantined spool lines wait for their chain
        # entry the same way.
        self._deferred = []
        self._quarantined = 0
        # 1.2.3 (R5): sink bookkeeping lives on a DEDICATED
        # autocommit connection (see _book_conn), and every
        # (seq, hash) this Chain has actually streamed is
        # remembered here so flush_deferred() can never stream a
        # rolled-back entry's committed twin a second time.
        self._book = None
        self._streamed = set()
        self._streamed_max = 0
        self._watermark_cache = None
        # 1.2.6 (U3): the verified seq->hash index of the sink file,
        # memoized on (path, size, mtime_ns). A diverged obligation
        # made 1.2.5 re-parse the ENTIRE sink on every delivery
        # pass — per-request cost grew with total sink size forever
        # (round 8, Claude C8-03). The memo is refreshed by stat on
        # each use and updated in place with this process's own
        # writes, so after the first pass the per-pass cost is one
        # stat, not one scan.
        self._sink_map_cache = None
        # 1.2.6 (U3): the seqs a delivery pass found stranded by a
        # divergence, named for the resolution ceremony.
        self._diverged_seqs = []

    # ---------------- sink ----------------
    def _book_conn(self):
        """The Chain's private bookkeeping connection (1.2.3, R5):
        sink_state reads/writes ONLY. Autocommit, so an UPDATE
        lands immediately and never leaves a write transaction
        open on the caller's connection — 1.2.2 recorded sink
        errors on Janus's shared connection after the handler's
        commit, holding the WAL writer lock across requests
        (round 6, Gemini F5). Created lazily: constructing a
        Chain performs no DML at all (R4)."""
        if self._book is None:
            book = sqlite3.connect(self.db_path,
                                   check_same_thread=False,
                                   isolation_level=None)
            book.execute("PRAGMA busy_timeout = 5000")
            book.execute(
                """CREATE TABLE IF NOT EXISTS sink_state(
                     id INTEGER PRIMARY KEY CHECK(id=1),
                     ok INTEGER DEFAULT 1, errors INTEGER DEFAULT 0,
                     last_error TEXT, last_error_ts TEXT,
                     last_streamed_seq INTEGER DEFAULT 0)""")
            book.execute(
                """CREATE TABLE IF NOT EXISTS scrub_state(
                     kind TEXT PRIMARY KEY, last_ts REAL)""")
            book.execute(
                """CREATE TABLE IF NOT EXISTS sink_pending(
                     seq INTEGER PRIMARY KEY, hash TEXT NOT NULL,
                     queued_ts TEXT)""")
            cols = [r[1] for r in book.execute(
                "PRAGMA table_info(sink_state)")]
            if "last_streamed_seq" not in cols:
                book.execute(
                    "ALTER TABLE sink_state ADD COLUMN "
                    "last_streamed_seq INTEGER DEFAULT 0")
            # 1.2.4 (S1): the sink's tail — the (seq, hash) of the
            # last line known written, the frontier per-entry
            # delivery is measured against (the sink FILE remains
            # the ground truth; see _deliver_pending).
            for col, ddl in (("tail_seq", "INTEGER DEFAULT 0"),
                             ("tail_hash", "TEXT")):
                if col not in cols:
                    book.execute(
                        "ALTER TABLE sink_state ADD COLUMN %s %s"
                        % (col, ddl))
            book.execute(
                "INSERT OR IGNORE INTO sink_state(id, ok, errors) "
                "VALUES(1, 1, 0)")
            self._book = book
        return self._book

    def _watermark(self):
        """The sink's delivered frontier (1.2.4, S1): the seq of
        the last line known to be in the sink, from sink_state's
        tail record. REPORTING ONLY since 1.2.4 — delivery
        decisions are per-entry (the sink_pending ledger plus the
        sink file's own tail line), never this scalar: 1.2.3's
        watermark was the delivery mechanism, and one process
        advancing it stranded another process's earlier committed
        entry permanently (round 7, register A2)."""
        if self._watermark_cache is None:
            try:
                row = self._book_conn().execute(
                    "SELECT tail_seq FROM sink_state "
                    "WHERE id=1").fetchone()
                self._watermark_cache = row[0] or 0 if row else 0
            except Exception:
                self._watermark_cache = 0
        return self._watermark_cache

    def _persist_watermark(self):
        # Kept for shape compatibility: the reporting column
        # last_streamed_seq tracks the delivered frontier.
        if self._streamed_max <= (self._watermark_cache or 0):
            return
        try:
            self._book_conn().execute(
                "UPDATE sink_state SET last_streamed_seq=? "
                "WHERE id=1 AND COALESCE(last_streamed_seq, 0)<?",
                (self._streamed_max, self._streamed_max))
            self._watermark_cache = self._streamed_max
        except Exception:
            pass

    def _note_streamed(self, entry):
        """Remember that (seq, hash) reached the sink (1.2.3, R5).
        Bounded: entries far behind the streamed maximum are
        pruned — a deferred entry is always recent, so the window
        only needs to cover in-flight flushes."""
        self._streamed.add((entry["seq"], entry["hash"]))
        if entry["seq"] > self._streamed_max:
            self._streamed_max = entry["seq"]
        if len(self._streamed) > 8192:
            floor = self._streamed_max - 4096
            self._streamed = {sh for sh in self._streamed
                              if sh[0] >= floor}

    def _sink_state(self):
        row = self._book_conn().execute(
            "SELECT ok, errors, last_error, last_error_ts FROM "
            "sink_state WHERE id=1").fetchone()
        spooled = 0
        if self.spool_path and os.path.exists(self.spool_path):
            with open(self.spool_path) as f:
                spooled = sum(1 for line in f if line.strip())
        # 1.2.4 (S1): the unresolved delivery backlog is part of
        # the sink's state — Janus's /health reads it, and health
        # is not green while it is non-empty.
        pending = 0
        oldest_pending = None
        try:
            pending, oldest_pending = self._book_conn().execute(
                "SELECT COUNT(*), MIN(queued_ts) FROM sink_pending"
            ).fetchone()
        except Exception:
            pending, oldest_pending = 0, None
        return {"enabled": bool(self.sink_path), "ok": bool(row[0]),
                "errors": row[1], "last_error": row[2],
                "last_error_ts": row[3], "spooled": spooled,
                "pending": pending or 0,
                "oldest_pending_ts": oldest_pending,
                # 1.2.6 (U3/U12): the seqs a divergence strands,
                # named so the resolution ceremony (and /health's
                # readers) can see exactly what the mirror is
                # missing.
                "diverged_seqs": list(self._diverged_seqs),
                "path": self.sink_path}

    # ---------------- durable delivery (1.2.4, S1) ----------------
    def _sink_seq_hashes(self):
        """{seq: hash} for every line in the sink file (1.2.5, T3).
        Built only when a delivery pass meets a below-tail
        candidate — the rollback signature — so the common path
        never pays for the scan. An unreadable line is skipped:
        its seq is simply absent from the map, which the caller
        treats as divergence (fail-closed).
        1.2.6 (U3): the map is MEMOIZED on the file's (size,
        mtime_ns). 1.2.5 rebuilt it on every pass that met a
        below-tail candidate, and a diverged obligation keeps such
        a candidate in every pass — so one honest restore taxed
        every request with a full sink scan, growing without bound
        (round 8, Claude C8-03). Callers must treat the returned
        dict as READ-ONLY; _deliver_locked updates it in place
        with the entries it writes itself."""
        if not self.sink_path or not os.path.isfile(self.sink_path):
            self._sink_map_cache = None
            return {}
        try:
            st = os.stat(self.sink_path)
            key = (self.sink_path, st.st_size, st.st_mtime_ns)
        except OSError:
            return {}
        if self._sink_map_cache and self._sink_map_cache[0] == key:
            return self._sink_map_cache[1]
        out = {}
        try:
            with open(self.sink_path, "rb") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        e = json.loads(raw.decode("utf-8",
                                                  "replace"))
                        out[int(e["seq"])] = e["hash"]
                    except Exception:
                        continue
        except OSError:
            return out
        try:
            st = os.stat(self.sink_path)
            key = (self.sink_path, st.st_size, st.st_mtime_ns)
        except OSError:
            pass
        self._sink_map_cache = (key, out)
        return out

    def _sink_file_tail(self):
        """The sink file's tail as (seq, hash, state) — 1.2.6
        (U12). state is one of:
          "absent"     no sink file (or no sink configured)
          "empty"      the file exists and is zero-length (or all
                       blank) — the ONLY states that may take the
                       vanished-mirror branch in _deliver_locked
          "ok"         the last line parses; (seq, hash) is it
          "torn"       the file is non-empty, its final line does
                       not parse (a power cut / ENOSPC partial
                       write), but an earlier line does: (seq,
                       hash) is the last VALID line and the caller
                       truncates the torn remainder before
                       appending — a torn line was never a complete
                       entry, so nothing delivered is lost
          "unreadable" the file is non-empty and NO line parses:
                       the mirror's content is unknown, which is a
                       divergence, never a vanished sink
        1.2.5 returned (0, None) on ANY parse failure, so a torn
        final line was indistinguishable from an absent sink and
        the delivery pass re-delivered the whole chain INTO the
        existing file — duplicates throughout the witness mirror,
        ledger cleared, health green (round 8 addendum, Qwen
        Q-F1)."""
        if not self.sink_path or not os.path.isfile(self.sink_path):
            return 0, None, "absent"
        try:
            size = os.path.getsize(self.sink_path)
        except OSError:
            return 0, None, "absent"
        if size == 0:
            return 0, None, "empty"
        step = min(size, 262144)
        while True:
            try:
                with open(self.sink_path, "rb") as f:
                    f.seek(size - step)
                    chunk = f.read()
            except OSError:
                return 0, None, "unreadable"
            lines = chunk.split(b"\n")
            if step < size:
                lines = lines[1:]  # first line is a partial read
            last_valid = None
            torn_after = False
            for raw in lines:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    e = json.loads(raw.decode("utf-8"))
                    last_valid = (int(e["seq"]), e["hash"])
                    torn_after = False
                except Exception:
                    if last_valid is not None:
                        torn_after = True
            if last_valid is not None:
                return last_valid[0], last_valid[1], \
                    ("torn" if torn_after else "ok")
            if step >= size:
                return 0, None, "unreadable"
            step = min(size, step * 4)

    def _sink_truncate_torn(self):
        """Truncate the sink file to just past its last VALID
        line (1.2.6, U12). Called only from _deliver_locked, under
        the spool flock, when _sink_file_tail reported "torn". A
        line counts as valid when it parses as a chain entry; the
        scan is over the whole file because the torn fragment's
        start is not known — this is a rare recovery path, not a
        per-request cost."""
        try:
            cut = 0
            with open(self.sink_path, "rb") as f:
                while True:
                    pos = f.tell()
                    raw = f.readline()
                    if not raw:
                        break
                    if not raw.strip():
                        cut = f.tell()
                        continue
                    try:
                        e = json.loads(raw.decode("utf-8"))
                        int(e["seq"])
                        e["hash"]
                        cut = f.tell()
                    except Exception:
                        break
            with open(self.sink_path, "r+b") as f:
                f.truncate(cut)
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            pass

    def sink_divergence(self):
        """The current sink divergence, or None (1.2.6, U3): the
        seqs where the sink file's record disagrees with — or is
        missing from — the committed chain, computed from the
        file's own content against the audit table. This is the
        read-only half of the resolution ceremony; Janus chains
        the acceptance BEFORE calling resolve_sink_divergence(),
        so the acceptance entry itself backfills into the fresh
        mirror."""
        if not self.sink_path:
            return None
        with self._lock:
            book = self._book_conn()
            row = book.execute(
                "SELECT tail_seq FROM sink_state WHERE id=1"
            ).fetchone()
            tail_seq = (row[0] or 0) if row else 0
            file_seq, _fh, _state = self._sink_file_tail()
            sink_map = self._sink_seq_hashes()
            stranded = []
            for seq, h in book.execute(
                    "SELECT seq, hash FROM audit ORDER BY seq"
                    ).fetchall():
                if seq <= max(tail_seq, file_seq) \
                        and sink_map.get(seq) != h:
                    stranded.append(seq)
            if not stranded and file_seq >= tail_seq:
                return None
            return {"stranded_seqs": stranded,
                    "file_seq": file_seq, "tail_seq": tail_seq}

    def resolve_sink_divergence(self):
        """Resolve a sink divergence by ROTATION (1.2.6, U3): the
        diverged sink file is archived beside the live one (never
        deleted — it is evidence of what the mirror held), the
        recorded tail resets, and the delivery pass backfills the
        whole committed chain into a fresh sink file. Returns
        {"stranded_seqs": [...], "archived_sink": name} or None
        when there is no divergence to resolve. The stranded seqs
        are the entries the OLD mirror held differently or not at
        all — the acceptance Janus chains names them."""
        info = self.sink_divergence()
        if info is None:
            return None
        with self._lock:
            lock_fd = self._spool_lock()
            try:
                archived = None
                if os.path.isfile(self.sink_path):
                    archived = "%s.diverged-%s" % (
                        self.sink_path,
                        datetime.now(timezone.utc).strftime(
                            "%Y%m%dT%H%M%SZ"))
                    os.replace(self.sink_path, archived)
                book = self._book_conn()
                book.execute(
                    "UPDATE sink_state SET tail_seq=0, "
                    "tail_hash=NULL, last_streamed_seq=0 "
                    "WHERE id=1")
                self._watermark_cache = 0
                self._sink_map_cache = None
                self._streamed = set()
                self._streamed_max = 0
                self._diverged_seqs = []
            finally:
                if lock_fd is not None:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                        os.close(lock_fd)
                    except OSError:
                        pass
        self._deliver_pending()
        return {"stranded_seqs": info["stranded_seqs"],
                "archived_sink": os.path.basename(archived)
                if archived else None}

    def _deliver_pending(self):
        """Deliver every outstanding committed entry to the sink,
        in chain order (1.2.4, S1). The obligation set is derived
        fresh, under the spool flock, from committed state only:
        the sink_pending ledger, the legacy spool, and every audit
        row past the sink's tail (the backfill that heals entries
        appended by a process that had no sink configured, and
        pre-1.2.4 history on first run). The sink file's own tail
        line is adopted before deciding — an entry already in the
        sink is never written twice, and an entry whose audit row
        never committed is never written at all (its ledger row
        rolled back with it). On sink failure the undelivered set
        is (re)written to the spool and the ledger rows REMAIN:
        delivery retries on the next append/flush, and
        sink_status() reports the backlog until it clears. NEVER
        raises."""
        if not self.sink_path:
            return
        with self._lock:
            lock_fd = self._spool_lock()
            try:
                self._deliver_locked()
            except Exception:
                # Delivery must never fail the write that triggered
                # it; the ledger keeps the obligation and the error
                # surfaces through sink_state.
                try:
                    self._sink_record_error(Exception(
                        "delivery pass failed"))
                except Exception:
                    pass
            finally:
                if lock_fd is not None:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                        os.close(lock_fd)
                    except OSError:
                        pass

    def _deliver_locked(self):
        book = self._book_conn()
        # Adopt the sink file's real tail when it is AHEAD of the
        # recorded one (crash window, or a 1.2.3-era sink whose
        # frontier lived only in last_streamed_seq).
        row = book.execute(
            "SELECT tail_seq, tail_hash FROM sink_state WHERE id=1"
        ).fetchone()
        tail_seq = (row[0] or 0) if row else 0
        tail_hash = row[1] if row else None
        file_seq, file_hash, tail_state = self._sink_file_tail()
        if tail_state == "torn":
            # 1.2.6 (U12): a torn final line (power cut / ENOSPC
            # partial write) is truncated back to the last valid
            # entry BEFORE anything appends — appending after a
            # partial line would weld the next entry onto the
            # fragment. The torn bytes were never a complete
            # entry, so truncating them loses nothing delivered;
            # the truncation is recorded, never silent.
            self._sink_truncate_torn()
            self._sink_map_cache = None
            self._sink_record_error(Exception(
                "sink tail torn: truncated the partial final line "
                "back to seq %d" % file_seq))
        if file_seq > tail_seq:
            tail_seq, tail_hash = file_seq, file_hash
            book.execute(
                "UPDATE sink_state SET tail_seq=?, tail_hash=? "
                "WHERE id=1", (tail_seq, tail_hash))
        elif tail_state in ("absent", "empty") and tail_seq:
            # The sink file vanished: the mirror is gone, so the
            # obligation is the whole chain again. 1.2.6 (U12):
            # ONLY a genuinely absent/empty file takes this
            # branch — a non-empty file whose tail does not parse
            # is a divergence below, never a vanished sink.
            tail_seq, tail_hash = 0, None
            book.execute(
                "UPDATE sink_state SET tail_seq=0, tail_hash=NULL "
                "WHERE id=1")
        elif tail_state == "unreadable" or 0 < file_seq < tail_seq:
            # 1.2.6 (U12): the mirror is damaged, not gone — a
            # non-empty file with no parseable line, or a file
            # TRUNCATED below the recorded tail. 1.2.5 matched no
            # branch for the truncated case: the missing range was
            # never re-delivered and health stayed green. Now it
            # is a NAMED divergence: obligations are preserved
            # (nothing is written past the damage, nothing is
            # marked delivered), sink_state goes not-ok, and the
            # stranded seqs are named for the U3 resolution
            # ceremony.
            if tail_state == "unreadable":
                stranded = [r[0] for r in book.execute(
                    "SELECT seq FROM audit ORDER BY seq").fetchall()]
                why = ("sink file is non-empty but no line in it "
                       "parses — its content is unknown")
            else:
                stranded = [r[0] for r in book.execute(
                    "SELECT seq FROM audit WHERE seq>? AND seq<=? "
                    "ORDER BY seq", (file_seq, tail_seq)).fetchall()]
                why = ("sink truncated: the file ends at seq %d "
                       "but the recorded tail is seq %d — entries "
                       "%s are missing from the mirror"
                       % (file_seq, tail_seq, stranded))
            self._diverged_seqs = stranded
            self._sink_record_error(Exception(
                "sink divergence: " + why))
            return
        # The candidate set: ledger + audit backfill + spool.
        cand = {}
        for seq, h in book.execute(
                "SELECT seq, hash FROM sink_pending").fetchall():
            cand[seq] = h
        for seq, h in book.execute(
                "SELECT seq, hash FROM audit WHERE seq>?",
                (tail_seq,)).fetchall():
            cand.setdefault(seq, h)
        spool_entries, bad = self._read_spool()
        if bad:
            self._quarantined += len(bad)
        for e in spool_entries:
            if isinstance(e, dict) and "seq" in e and "hash" in e:
                cand.setdefault(e["seq"], e["hash"])
        if not cand:
            return
        delivered, to_write = [], []
        blocked = None
        diverged = []
        sink_map = None
        for seq in sorted(cand):
            h = cand[seq]
            if seq < tail_seq or (seq == tail_seq
                                  and h == tail_hash):
                if seq < tail_seq:
                    # 1.2.5 (T3): a below-tail candidate is
                    # delivered-on-faith NO LONGER. After a chain
                    # rollback, new appends REUSE seqs below the
                    # sink's tail with different hashes; 1.2.4
                    # marked them delivered and deleted the
                    # obligation, so the mirror silently diverged
                    # from the chain it mirrors (security round 1,
                    # Claude F6). The candidate must match the
                    # sink FILE's own record at that seq; anything
                    # else is a named divergence, and the
                    # obligation stands.
                    if sink_map is None:
                        sink_map = self._sink_seq_hashes()
                    if sink_map.get(seq) != h:
                        blocked = ("sink divergence at seq %d: "
                                   "the sink's record there is a "
                                   "different entry than the chain "
                                   "now holds (rollback?)" % seq)
                        diverged.append(seq)
                        continue
                delivered.append(seq)
                continue
            if seq == tail_seq and h != tail_hash:
                # The sink's tail is a DIFFERENT entry at this seq
                # (the chain was rebuilt under an existing sink).
                # Refuse to guess: leave the obligation standing
                # and name it in sink_state.
                blocked = ("sink tail mismatch at seq %d: the sink "
                           "holds a different entry than the chain"
                           % seq)
                diverged.append(seq)
                continue
            arow = book.execute(
                "SELECT seq,ts,kind,payload,prev,hash FROM audit "
                "WHERE seq=?", (seq,)).fetchone()
            if arow is None or arow[5] != h:
                # A phantom obligation: the audit row never
                # committed (its ledger row was written by a
                # foreign path or the row was rolled back before
                # the ledger existed). Dropping it loses nothing —
                # there is no committed entry to deliver.
                delivered.append(seq)
                continue
            fields = {k: v for k, v in json.loads(arow[3]).items()
                      if k not in ("ts", "kind", "v")}
            to_write.append({"seq": arow[0], "ts": arow[1],
                             "kind": arow[2], "fields": fields,
                             "prev": arow[4], "hash": arow[5]})
        err = None
        if to_write:
            try:
                with open(self.sink_path, "a") as f:
                    for e in to_write:
                        f.write(json.dumps(e, sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                tail_seq = to_write[-1]["seq"]
                tail_hash = to_write[-1]["hash"]
                delivered.extend(e["seq"] for e in to_write)
                for e in to_write:
                    self._note_streamed(e)
                if self._sink_map_cache:
                    # 1.2.6 (U3): our own writes extend the
                    # memoized index in place — the next pass pays
                    # a stat, not a re-scan.
                    _key, _map = self._sink_map_cache
                    for e in to_write:
                        _map[e["seq"]] = e["hash"]
                    try:
                        _st = os.stat(self.sink_path)
                        self._sink_map_cache = (
                            (self.sink_path, _st.st_size,
                             _st.st_mtime_ns), _map)
                    except OSError:
                        self._sink_map_cache = None
            except OSError as exc:
                err = exc
                # The spool is the second durable copy (its drain
                # is part of every later pass). A spool failure too
                # still loses nothing: the ledger rows remain.
                try:
                    with open(self.spool_path, "w") as f:
                        for e in to_write:
                            f.write(json.dumps(e, sort_keys=True)
                                    + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                except OSError:
                    pass
        if delivered:
            marks = ",".join("?" * len(delivered))
            book.execute(
                "DELETE FROM sink_pending WHERE seq IN (%s)" % marks,
                delivered)
            book.execute(
                "UPDATE sink_state SET tail_seq=?, tail_hash=?, "
                "last_streamed_seq=MAX(COALESCE(last_streamed_seq,"
                "0), ?) WHERE id=1",
                (tail_seq, tail_hash, max(delivered)))
            self._watermark_cache = tail_seq
        if err is not None:
            self._sink_record_error(err)
        elif blocked is not None:
            self._sink_record_error(Exception(blocked))
            self._diverged_seqs = sorted(set(diverged))
        else:
            self._diverged_seqs = []
            # A clean pass drained the spool into the sink (or
            # found it empty): the file has no further purpose.
            if self.spool_path and os.path.exists(self.spool_path):
                try:
                    os.remove(self.spool_path)
                except OSError:
                    pass
            self._sink_record_ok()

    def _spool_lock(self):
        """An flock'd lockfile guarding sink/spool appends (1.2.1,
        P11): two Chain processes streaming to one sink must not
        interleave lines. Returns the open lock fd or None."""
        if not self.sink_path:
            return None
        try:
            fd = os.open(self.sink_path + ".lock",
                         os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            return fd
        except OSError:
            return None

    def _read_spool(self):
        """(entries, bad_lines). A torn or corrupt spool line is NOT
        an error (1.2.1, P11/A11): it is quarantined to <spool>.bad
        and counted, and the caller chains SPOOL_QUARANTINE. 1.2's
        json.loads raise made every chained write fail behind one
        half-written line — a stolen-plate read was lost to a power
        cut's punctuation."""
        entries, bad = [], []
        if self.spool_path and os.path.exists(self.spool_path):
            with open(self.spool_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entries.append(json.loads(line))
                    except ValueError:
                        bad.append(line.rstrip("\n"))
            if bad:
                with open(self.spool_path + ".bad", "a") as bf:
                    for line in bad:
                        bf.write(line + "\n")
                os.remove(self.spool_path)
        return entries, bad

    def sink_status(self):
        """The sink's state, FAIL-CLOSED (1.2.6, U8). 1.2.5 let an
        exception inside _sink_state (e.g. <sink>.spool replaced
        by a directory → IsADirectoryError on open) propagate to
        the caller; Janus's /health happened to catch it, but the
        status contract itself was 'raises sometimes'. Now an
        undeterminable state IS a state: enabled, not ok, unknown,
        with the error named — and since delivery never treats an
        unknown sink as delivered (the ledger only clears on a
        verified write), unknown means not-delivered everywhere."""
        with self._lock:
            try:
                return self._sink_state()
            except Exception as exc:  # noqa: BLE001 — status must not raise
                return {"enabled": bool(self.sink_path),
                        "ok": False, "unknown": True,
                        "error": "status_unknown: %s: %s"
                                 % (type(exc).__name__, exc),
                        "errors": -1, "last_error": str(exc)[:300],
                        "last_error_ts": None, "spooled": 0,
                        "pending": 0, "oldest_pending_ts": None,
                        "diverged_seqs": list(self._diverged_seqs),
                        "path": self.sink_path}

    def _sink_record_error(self, exc):
        self._book_conn().execute(
            "UPDATE sink_state SET ok=0, errors=errors+1, "
            "last_error=?, last_error_ts=? WHERE id=1",
            (str(exc)[:300], now_iso()))

    def _sink_record_ok(self):
        row = self._book_conn().execute(
            "SELECT ok FROM sink_state WHERE id=1").fetchone()
        if row and not row[0]:
            self._book_conn().execute(
                "UPDATE sink_state SET ok=1 WHERE id=1")

    def _stream(self, entry):
        """Deliver one entry to the sink (1.2.4, S1): a thin
        wrapper over _deliver_pending — the entry's obligation is
        already in the ledger (written with its audit row), and
        the delivery pass drains the whole backlog in chain order,
        this entry included. Kept under its old name for the
        callers that stream a single entry. NEVER raises."""
        if not self.sink_path:
            return
        self._deliver_pending()

    def flush_deferred(self):
        """Run after a caller-held transaction commits (1.2.4, S1):
        deliver everything the commit made durable. 1.2.1–1.2.3
        presence-checked each queued entry here and DROPPED the
        ones it could not verify — round 7 (ChatGPT R7-01) showed
        a read-only connection failure discarding COMMITTED entries
        outright, with health green over the gap. Under the ledger
        the check is structural, not sampled: an entry whose
        transaction rolled back has no ledger row (it rolled back
        too), and an entry that committed is visible to the
        delivery pass's own committed-state reads. A verification
        failure therefore cannot discard an obligation any more —
        there is nothing here to drop. The in-memory queue now only
        tracks WHICH appends waited, for the quarantine chaining
        below."""
        self._deferred = []
        self._deliver_pending()
        self._note_quarantine()

    def _note_quarantine(self):
        if self._quarantined and not self.db.in_transaction:
            n, self._quarantined = self._quarantined, 0
            try:
                self.append("SPOOL_QUARANTINE", {
                    "lines": n,
                    "bad_file": os.path.basename(self.spool_path)
                    + ".bad" if self.spool_path else ""})
            except Exception:
                pass

    # ---------------- chain core ----------------
    def root(self):
        row = self.db.execute(
            "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else "GENESIS"

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]

    def hash_at_seq(self, seq):
        row = self.db.execute("SELECT hash FROM audit WHERE seq=?",
                              (seq,)).fetchone()
        return row[0] if row else None

    def _insert_locked(self, kind, fields):
        """root-read + insert. The caller guarantees atomicity: either
        it holds an open transaction on this connection (participate —
        S11) or _append_txn wrapped us in BEGIN IMMEDIATE. New entries
        are hash v2 (P11): the payload carries "v": 2 and the hash
        binds the ts and kind COLUMNS as well as the payload bytes."""
        ts = now_iso()
        # 1.2.2 (Q20): the envelope keys are never caller data — a
        # field named v/ts/kind would otherwise override the real
        # envelope in the dict merge below (latent in 1.2.1: no
        # caller passed them, but the merge order made it possible).
        fields = {k: v for k, v in fields.items()
                  if k not in ("v", "ts", "kind")}
        payload = json.dumps({"v": 2, "ts": ts, "kind": kind, **fields},
                             sort_keys=True, separators=(",", ":"))
        row = self.db.execute(
            "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev = row[0] if row else "GENESIS"
        h = entry_hash(prev, ts, kind, payload)
        cur = self.db.execute(
            "INSERT INTO audit(ts,kind,payload,prev,hash) "
            "VALUES(?,?,?,?,?)", (ts, kind, payload, prev, h))
        if self.sink_path:
            # 1.2.4 (S1): the delivery obligation is written in the
            # SAME transaction as the audit row — it commits with
            # the entry and rolls back with it, so the sink can
            # never hold an uncommitted entry nor lose a committed
            # one to a volatile queue.
            self.db.execute(
                "INSERT OR IGNORE INTO sink_pending(seq, hash, "
                "queued_ts) VALUES(?,?,?)",
                (cur.lastrowid, h, ts))
        return {"seq": cur.lastrowid, "ts": ts, "kind": kind,
                "fields": fields, "prev": prev, "hash": h}

    def _append_txn(self, kind, fields):
        """Insert one entry, returning (entry, participated) —
        1.2.4 (S10): the participation decision is CAPTURED AT
        INSERT, from the connection state seen here, and returned
        with the entry. append() acts on this captured value; it
        never re-reads conn.in_transaction afterwards (on a shared
        connection the re-read could observe ANOTHER request's
        transaction and misroute the delivery — round 7, Qwen
        F-G). participated=True means the caller held a transaction
        and the entry commits (or rolls back) with it."""
        if self.db.in_transaction:
            # Participate in the caller's transaction (S11): the
            # handler's data write and this entry commit together.
            return self._insert_locked(kind, fields), True
        last_exc = None
        for attempt in range(12):
            try:
                self.db.execute("BEGIN IMMEDIATE")
                entry = self._insert_locked(kind, fields)
                self.db.execute("COMMIT")
                return entry, False
            except sqlite3.OperationalError as exc:
                last_exc = exc
                try:
                    self.db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                if "locked" not in str(exc) and "busy" not in str(exc):
                    raise
                time.sleep(0.05 * (attempt + 1))
        raise last_exc

    def _scrub_flag_due(self, kind):
        """Throttle state for CHAIN_SCRUB_FLAG (1.2.4, S10): read
        and written on the Chain's dedicated autocommit bookkeeping
        connection — NEVER on self.db. 1.2.3 ran this INSERT on the
        shared connection, where (under sqlite3's implicit
        transactions) it opened a transaction nobody committed:
        the next append mistook the leak for caller participation
        and deferred a delivery that then waited on a commit that
        was never coming (round 7, cold-seat S2)."""
        now = time.time()
        try:
            book = self._book_conn()
            row = book.execute(
                "SELECT last_ts FROM scrub_state WHERE kind=?",
                (kind,)).fetchone()
            if row and now - row[0] < 60:
                return False
            book.execute(
                "INSERT INTO scrub_state(kind, last_ts) VALUES(?,?) "
                "ON CONFLICT(kind) DO UPDATE SET last_ts=excluded."
                "last_ts", (kind, now))
            return True
        except sqlite3.Error:
            return False

    def append(self, kind, fields):
        """Append one entry. Plate-shaped strings in the payload are
        replaced by their SHA-256 BEFORE the write (S11): the write
        always proceeds and is always logged; a throttled
        CHAIN_SCRUB_FLAG entry records that sanitizing happened.
        This method never raises over payload content."""
        clean, flagged = _sanitize(fields, key=self.key,
                                   exempt_check=self.exempt_check)
        with self._lock:
            entry, participated = self._append_txn(kind, clean)
            if participated:
                # Participating in the caller's transaction (S11):
                # the sink copy waits for the commit (P11 deferred
                # flush) — streaming now would publish an entry a
                # rollback is about to un-happen.
                self._deferred.append(entry)
            else:
                self._deliver_pending()
                self._note_quarantine()
            if flagged and self._scrub_flag_due(kind):
                flag, flag_participated = self._append_txn(
                    "CHAIN_SCRUB_FLAG", {
                        "flagged_kind": kind,
                        "fields": ",".join(sorted(set(flagged)))[:200]})
                if flag_participated:
                    self._deferred.append(flag)
                else:
                    self._deliver_pending()
                    self._note_quarantine()
            return entry

    def entries(self, limit=200):
        rows = self.db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [{"seq": r[0], "ts": r[1], "kind": r[2],
                 "fields": {k: v for k, v in json.loads(r[3]).items()
                            if k not in ("ts", "kind", "v")},
                 "prev": r[4], "hash": r[5]} for r in rows]

    def entry_at_seq(self, seq):
        row = self.db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit WHERE seq=?",
            (seq,)).fetchone()
        if not row:
            return None
        return {"seq": row[0], "ts": row[1], "kind": row[2],
                "fields": {k: v for k, v in json.loads(row[3]).items()
                           if k not in ("ts", "kind", "v")},
                "prev": row[4], "hash": row[5]}

    def entries_range(self, from_seq, to_seq):
        """Entries with from_seq <= seq <= to_seq, ascending, with the
        RAW payload string — the Compact recompute (S8) rehashes the
        exact bytes, so it must not round-trip through JSON."""
        rows = self.db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "WHERE seq>=? AND seq<=? ORDER BY seq",
            (from_seq, to_seq)).fetchall()
        return [{"seq": r[0], "ts": r[1], "kind": r[2],
                 "payload": r[3], "prev": r[4], "hash": r[5]}
                for r in rows]

    def verify(self):
        cur = self.db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "ORDER BY seq")
        return _verify_rows(cur)

    def verify_detached(self):
        return verify_detached(self.db_path)
