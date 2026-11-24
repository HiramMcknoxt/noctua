"""Sentinel — append-only, hash-chained audit log (SQLite). NOCTUA 1.1.

Shared by the Janus service, the retention job, and the Compact tools so
every component writes to the same chain. Each entry's hash covers the
previous entry's hash plus the canonical JSON payload, so editing any
historical entry breaks every hash after it.

Chain entries NEVER contain plate text. Callers pass keyed HMAC plate
references (see janus.plate_ref) wherever a plate would otherwise appear:
under Ark. Code SS 12-12-1802 the plate number itself is captured data,
and an append-only log of plate text would outlive every retention limit
in the system. 1.1 adds a defense-in-depth scrubber inside append():
a string value that looks like a raw plate (and is not a pref: token)
refuses the write and records CHAIN_SCRUB_BLOCKED instead. Callers must
chain only plate_ref values, counts, and coded fields — free text
(justifications, warrant text, review notes) belongs in the database
tables, never in the permanent chain.

1.1 changes vs 1.0 (AI council round 2):
  * ATOMIC APPENDS. 1.0 read the root, computed the hash, and inserted
    as three separate steps: two writers (Janus's threads, or Janus and
    the retention job in another process) could read the same root and
    fork the chain. append() now holds an in-process lock AND wraps
    root-read + insert in a BEGIN IMMEDIATE transaction with busy-retry,
    so the read-modify-write is atomic across processes too.
  * SINK SPOOL. 1.0 dropped sink entries on a write error and latched
    sink_ok=False forever. Now a failed sink write spools the entry to
    <sink>.spool (chain entries contain no plate text, so the spool is
    safe to keep); the next append retries the sink and drains the spool
    IN ORDER before writing its own entry; sink_ok returns to True after
    a successful drain. Sink state (error count, last error) persists in
    the sink_state table, so a restart does not reset the evidence that
    the sink had trouble.
  * verify() checks SEQUENCE CONTINUITY as well as hashes: a silently
    deleted middle entry shows up as a gap even if the remaining
    hashes are internally consistent.

Two mechanisms move the chain's evidence OUTSIDE this box:
  * Streaming sink: if NOCTUA_SENTINEL_SINK is set, every entry is also
    appended as a JSON line to that file (flush + fsync per entry).
    Point it at a path the Clerk/auditor side controls and an insider
    rewriting the local chain can no longer rewrite the streamed copy.
  * Daily signed checkpoints: scripts/checkpoint.py HMAC-signs
    {date, root, entries} and scripts/publish_witness.sh publishes the
    checkpoint outside the system daily. Janus 1.1 additionally anchors
    itself to the newest checkpoint at startup (see janus.py).
"""
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(txt):
    return hashlib.sha256(txt.encode()).hexdigest()


class ChainScrubError(ValueError):
    """A chain payload carried what looks like raw plate text."""


# A raw plate, normalized (spaces/hyphens removed, uppercased): the
# common US shapes — 2-3 letters + 3-4 digits, 3 digits + 3 letters,
# letter + 3 digits + 2 letters. Deliberately narrow: timestamps, case
# numbers (all digits after normalization), camera names (CAM-01 ->
# CAM01, only 2 digits), user names (dots/lowercase), and 64-char
# hashes do NOT match. pref: tokens are exempt by construction.
_PLATE_RE = re.compile(
    r"(?:[A-Z]{2,3}[0-9]{3,4}|[0-9]{3}[A-Z]{3}|[A-Z][0-9]{3}[A-Z]{2})")


def _scrub_scan(value, field=""):
    """Return the dotted field path of the first plate-like raw string
    in a payload value, or None. Only strings that ARE plate-shaped
    after normalization trip this — prose with spaces and lowercase
    does not (prose still does not belong in the chain; the scrubber is
    the last line of defense, not the style guide)."""
    if isinstance(value, str):
        if value.startswith("pref:"):
            return None
        stripped = value.replace(" ", "").replace("-", "")
        norm = stripped.upper()
        if norm == stripped and _PLATE_RE.fullmatch(norm) \
                and any(c.isalpha() for c in norm) \
                and any(c.isdigit() for c in norm):
            return field or "<root>"
        return None
    if isinstance(value, dict):
        for k, v in value.items():
            hit = _scrub_scan(v, f"{field}.{k}" if field else str(k))
            if hit:
                return hit
    if isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            hit = _scrub_scan(v, f"{field}[{i}]")
            if hit:
                return hit
    return None


class Chain:
    def __init__(self, db_path):
        # check_same_thread=False: the Janus HTTP server is threaded.
        # isolation_level=None (autocommit): append() drives its own
        # BEGIN IMMEDIATE / COMMIT so the transaction boundaries are
        # exactly where the code says they are.
        self.db = sqlite3.connect(db_path, check_same_thread=False,
                                  isolation_level=None)
        self.db.execute("PRAGMA busy_timeout = 5000")
        # secure_delete: overwritten content is zeroed, not left
        # recoverable in free pages. The retention promise has to be
        # true at the file layer, not just the SQL layer.
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
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
        self._lock = threading.Lock()
        # Streaming sink (see module docstring). Failures are counted
        # and persisted, never raised: a dead sink must not take the
        # front door down, but it must be visible — Janus reports this
        # at /health, and undelivered entries wait in the spool file.
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
            # Rewrite the spool with everything not yet delivered.
            # The spool lives beside the sink; if THAT write fails too
            # (the directory itself is gone), the error is recorded
            # and the append still succeeds — the chain in the DB is
            # the system of record, the sink is a copy, and /health
            # reports the sink as failed until it recovers.
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

    def _append_txn(self, kind, fields):
        """root-read + insert as ONE immediate transaction, retried on
        lock contention. This is the atomicity the 1.0 chain lacked."""
        ts = now_iso()
        payload = json.dumps({"ts": ts, "kind": kind, **fields},
                             sort_keys=True, separators=(",", ":"))
        last_exc = None
        for attempt in range(12):
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                prev = row[0] if row else "GENESIS"
                h = sha(prev + "|" + payload)
                cur = self.db.execute(
                    "INSERT INTO audit(ts,kind,payload,prev,hash) "
                    "VALUES(?,?,?,?,?)", (ts, kind, payload, prev, h))
                self.db.execute("COMMIT")
                return {"seq": cur.lastrowid, "ts": ts, "kind": kind,
                        "fields": fields, "prev": prev, "hash": h}
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

    def append(self, kind, fields):
        """Append one entry. Raises ChainScrubError (after recording
        CHAIN_SCRUB_BLOCKED) if a payload value looks like raw plate
        text — the chain is permanent, so the write must not happen."""
        bad_field = _scrub_scan(fields)
        if bad_field is not None:
            with self._lock:
                entry = self._append_txn("CHAIN_SCRUB_BLOCKED", {
                    "blocked_kind": kind, "field": bad_field})
                self._stream(entry)
            raise ChainScrubError(
                f"chain payload for {kind} carried plate-like text at "
                f"{bad_field}; blocked and logged at seq {entry['seq']}")
        with self._lock:
            entry = self._append_txn(kind, fields)
            self._stream(entry)
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

    def verify(self):
        """Hash linkage AND sequence continuity. A chain with a deleted
        middle entry fails here even if every remaining hash is
        internally consistent."""
        prev = "GENESIS"
        prev_seq = None
        rows = self.db.execute(
            "SELECT seq,payload,prev,hash FROM audit ORDER BY seq"
        ).fetchall()
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
