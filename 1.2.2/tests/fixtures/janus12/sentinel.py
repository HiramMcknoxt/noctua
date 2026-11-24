"""Sentinel — append-only, hash-chained audit log (SQLite). NOCTUA 1.2.

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

Chain entries NEVER contain plate text. Callers chain keyed HMAC
plate references (plate_ref), hashes of case numbers and free text
(case_hash / why_hash), counts, and coded enum fields only.
"""
import base64
import hashlib
import hmac as hmac_mod
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone


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
REGISTRY_VERSION = "1.2"
PLATE_DATA_STORES = [
    {"store": "reads.plate", "kind": "table", "table": "reads",
     "column": "plate", "ts_col": "ts", "class": "reads",
     "action": "delete_rows"},
    {"store": "reads.plate_raw", "kind": "table", "table": "reads",
     "column": "plate_raw", "ts_col": "ts", "class": "reads",
     "action": "delete_rows"},
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
     "class": "derived", "action": "none",
     "note": "keyed HMAC ref — pseudonymous; the row is the "
             "rate-limit and audit record"},
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
    {"store": "sentinel sink", "kind": "asserted",
     "class": "plate_free", "action": "none"},
    {"store": "sentinel spool", "kind": "asserted",
     "class": "plate_free", "action": "none"},
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


# ---------------- Ed25519 signing (S7) ----------------
# Via the system openssl — the one sanctioned external call. The
# private key lives beside the database at 0600; the public key is
# exportable and is what partners register (by fingerprint).
def signing_paths(db_path):
    return db_path + ".signing_key.pem", db_path + ".signing_pub.pem"


def ensure_signing_key(db_path):
    """Create the Ed25519 keypair if absent; return (priv, pub)."""
    priv, pub = signing_paths(db_path)
    if not os.path.exists(priv):
        subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519",
                        "-out", priv], check=True,
                       capture_output=True, timeout=30)
        os.chmod(priv, 0o600)
    if not os.path.exists(pub):
        subprocess.run(["openssl", "pkey", "-in", priv, "-pubout",
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
    and compare before trusting a public key a checkpoint carries."""
    body = "".join(l for l in pub_pem.splitlines()
                   if not l.startswith("-----"))
    der = base64.b64decode(body)
    return hashlib.sha256(der).hexdigest()


def sign_bytes(priv_path, data):
    """Ed25519-sign data (bytes); return the base64 signature."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        msg = f.name
    sig = msg + ".sig"
    try:
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey",
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
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", pubf,
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


def _sanitize(value, field=""):
    """Return (clean_value, [flagged field paths]). Plate-shaped
    strings are replaced by their SHA-256 — the write proceeds, the
    text does not."""
    if isinstance(value, str):
        leaf = field.rsplit(".", 1)[-1].split("[")[0]
        if leaf in _SCRUB_EXEMPT_FIELDS:
            return value, []
        if _looks_like_plate(value):
            return sha(value), [field or "<root>"]
        return value, []
    if isinstance(value, dict):
        out, flags = {}, []
        for k, v in value.items():
            cv, fl = _sanitize(v, f"{field}.{k}" if field else str(k))
            out[k] = cv
            flags += fl
        return out, flags
    if isinstance(value, (list, tuple)):
        out, flags = [], []
        for i, v in enumerate(value):
            cv, fl = _sanitize(v, f"{field}[{i}]")
            out.append(cv)
            flags += fl
        return out, flags
    return value, []


def _verify_rows(rows):
    prev = "GENESIS"
    prev_seq = None
    for seq, payload, stored_prev, stored_hash in rows:
        if prev_seq is not None and seq != prev_seq + 1:
            return {"ok": False, "broken_at": seq,
                    "reason": "sequence gap — an entry is missing"}
        if stored_prev != prev:
            return {"ok": False, "broken_at": seq}
        if sha(prev + "|" + payload) != stored_hash:
            return {"ok": False, "broken_at": seq}
        prev = stored_hash
        prev_seq = seq
    return {"ok": True, "entries": len(rows), "root": prev}


def verify_detached(db_path):
    """verify() over a fresh READ-ONLY connection (S5/S16): never
    creates tables, never takes the write path, safe to call while
    Janus holds its lock."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT seq,payload,prev,hash FROM audit ORDER BY seq"
        ).fetchall()
    finally:
        db.close()
    return _verify_rows(rows)


class Chain:
    def __init__(self, db_path, conn=None):
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
                         last_error TEXT, last_error_ts TEXT)""")
                self.db.execute(
                    "INSERT OR IGNORE INTO sink_state(id, ok, errors) "
                    "VALUES(1, 1, 0)")
                self.db.execute(
                    """CREATE TABLE IF NOT EXISTS scrub_state(
                         kind TEXT PRIMARY KEY, last_ts REAL)""")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or attempt == 49:
                    raise
                time.sleep(0.1)
        self._lock = threading.Lock()
        # Streaming sink: if NOCTUA_SENTINEL_SINK is set, every entry
        # is also appended as a JSON line to that file (flush + fsync
        # per entry). Failures spool beside it and never raise.
        self.sink_path = os.environ.get("NOCTUA_SENTINEL_SINK") or None
        self.spool_path = (self.sink_path + ".spool") if self.sink_path \
            else None

    # ---------------- sink ----------------
    def _sink_state(self):
        row = self.db.execute(
            "SELECT ok, errors, last_error, last_error_ts FROM "
            "sink_state WHERE id=1").fetchone()
        spooled = 0
        if self.spool_path and os.path.exists(self.spool_path):
            with open(self.spool_path) as f:
                spooled = sum(1 for line in f if line.strip())
        return {"enabled": bool(self.sink_path), "ok": bool(row[0]),
                "errors": row[1], "last_error": row[2],
                "last_error_ts": row[3], "spooled": spooled,
                "path": self.sink_path}

    def sink_status(self):
        with self._lock:
            return self._sink_state()

    def _sink_record_error(self, exc):
        self.db.execute(
            "UPDATE sink_state SET ok=0, errors=errors+1, "
            "last_error=?, last_error_ts=? WHERE id=1",
            (str(exc)[:300], now_iso()))

    def _sink_record_ok(self):
        row = self.db.execute(
            "SELECT ok FROM sink_state WHERE id=1").fetchone()
        if row and not row[0]:
            self.db.execute("UPDATE sink_state SET ok=1 WHERE id=1")

    def _stream(self, entry):
        """Deliver one entry to the sink, draining the spool first so
        the sink's copy is always in chain order. On failure the entry
        (and anything undrained) waits in the spool."""
        if not self.sink_path:
            return
        pending = []
        if os.path.exists(self.spool_path):
            with open(self.spool_path) as f:
                pending = [json.loads(line) for line in f if line.strip()]
        pending.append(entry)
        try:
            with open(self.sink_path, "a") as f:
                for e in pending:
                    f.write(json.dumps(e, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as exc:
            try:
                with open(self.spool_path, "w") as f:
                    for e in pending:
                        f.write(json.dumps(e, sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError:
                pass
            self._sink_record_error(exc)
            return
        if os.path.exists(self.spool_path):
            os.remove(self.spool_path)
        self._sink_record_ok()

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
        S11) or _append_txn wrapped us in BEGIN IMMEDIATE."""
        ts = now_iso()
        payload = json.dumps({"ts": ts, "kind": kind, **fields},
                             sort_keys=True, separators=(",", ":"))
        row = self.db.execute(
            "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev = row[0] if row else "GENESIS"
        h = sha(prev + "|" + payload)
        cur = self.db.execute(
            "INSERT INTO audit(ts,kind,payload,prev,hash) "
            "VALUES(?,?,?,?,?)", (ts, kind, payload, prev, h))
        return {"seq": cur.lastrowid, "ts": ts, "kind": kind,
                "fields": fields, "prev": prev, "hash": h}

    def _append_txn(self, kind, fields):
        if self.db.in_transaction:
            # Participate in the caller's transaction (S11): the
            # handler's data write and this entry commit together.
            return self._insert_locked(kind, fields)
        last_exc = None
        for attempt in range(12):
            try:
                self.db.execute("BEGIN IMMEDIATE")
                entry = self._insert_locked(kind, fields)
                self.db.execute("COMMIT")
                return entry
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
        now = time.time()
        try:
            row = self.db.execute(
                "SELECT last_ts FROM scrub_state WHERE kind=?",
                (kind,)).fetchone()
            if row and now - row[0] < 60:
                return False
            self.db.execute(
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
        clean, flagged = _sanitize(fields)
        with self._lock:
            entry = self._append_txn(kind, clean)
            self._stream(entry)
            if flagged and self._scrub_flag_due(kind):
                flag = self._append_txn("CHAIN_SCRUB_FLAG", {
                    "flagged_kind": kind,
                    "fields": ",".join(sorted(set(flagged)))[:200]})
                self._stream(flag)
            return entry

    def entries(self, limit=200):
        rows = self.db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [{"seq": r[0], "ts": r[1], "kind": r[2],
                 "fields": {k: v for k, v in json.loads(r[3]).items()
                            if k not in ("ts", "kind")},
                 "prev": r[4], "hash": r[5]} for r in rows]

    def entry_at_seq(self, seq):
        row = self.db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit WHERE seq=?",
            (seq,)).fetchone()
        if not row:
            return None
        return {"seq": row[0], "ts": row[1], "kind": row[2],
                "fields": {k: v for k, v in json.loads(row[3]).items()
                           if k not in ("ts", "kind")},
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
        rows = self.db.execute(
            "SELECT seq,payload,prev,hash FROM audit ORDER BY seq"
        ).fetchall()
        return _verify_rows(rows)

    def verify_detached(self):
        return verify_detached(self.db_path)
