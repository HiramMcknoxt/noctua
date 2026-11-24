"""Sentinel — append-only, hash-chained audit log (SQLite). NOCTUA 1.0.

Shared by the Janus service and the retention job so every component writes
to the same chain. Each entry's hash covers the previous entry's hash plus
the canonical JSON payload, so editing any historical entry breaks every
hash after it.

Chain entries NEVER contain plate text. Callers pass keyed HMAC plate
references (see janus.plate_ref) wherever a plate would otherwise appear:
under Ark. Code SS 12-12-1802 the plate number itself is captured data,
and an append-only log of plate text would outlive every retention limit
in the system.

Two mechanisms move the chain's evidence OUTSIDE this box (AI council
round, Nov. 23, 2026 — an unkeyed chain anchored only weekly leaves a
forgery window):

  * Streaming sink: if NOCTUA_SENTINEL_SINK is set, every entry is also
    appended as a JSON line to that file (flush + fsync per entry). Point
    it at a path the Clerk/auditor side controls (a mounted share, a
    shipped log directory) and an insider rewriting the local chain can
    no longer rewrite the streamed copy. A sink write failure never
    crashes the caller — it is counted and reported via sink_status()
    (Janus exposes it at /health) so silence is visible, not silent.
  * Daily signed checkpoints: scripts/checkpoint.py HMAC-signs
    {date, root, entries} and scripts/publish_witness.sh publishes the
    checkpoint outside the system daily.

1.0 change vs v0.9: PRAGMA busy_timeout on the connection, so a chain
append that collides with another writer waits briefly instead of
failing with "database is locked". Nothing else changed — the chain
format is byte-compatible with v0.9, so a v0.9 chain verifies under 1.0.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(txt):
    return hashlib.sha256(txt.encode()).hexdigest()


class Chain:
    def __init__(self, db_path):
        # check_same_thread=False: the Janus HTTP server is threaded.
        # Appends are serialized by the GIL + SQLite's own write lock at
        # this scale; a busier deployment should add an explicit lock.
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout = 5000")
        # secure_delete: overwritten content is zeroed, not left recoverable
        # in free pages. The retention promise has to be true at the file
        # layer, not just the SQL layer (AI council finding, Nov. 23, 2026).
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS audit(
                 seq INTEGER PRIMARY KEY AUTOINCREMENT,
                 ts TEXT NOT NULL, kind TEXT NOT NULL,
                 payload TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL)"""
        )
        self.db.commit()
        # Streaming sink (see module docstring). Failures are counted,
        # never raised: a dead sink must not take the front door down,
        # but it must be visible — Janus reports this at /health.
        self.sink_path = os.environ.get("NOCTUA_SENTINEL_SINK") or None
        self.sink_errors = 0
        self.sink_ok = True

    def sink_status(self):
        return {"enabled": bool(self.sink_path), "ok": self.sink_ok,
                "errors": self.sink_errors, "path": self.sink_path}

    def _stream(self, entry):
        if not self.sink_path:
            return
        try:
            with open(self.sink_path, "a") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            self.sink_errors += 1
            self.sink_ok = False

    def root(self):
        row = self.db.execute(
            "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else "GENESIS"

    def append(self, kind, fields):
        ts = now_iso()
        payload = json.dumps({"ts": ts, "kind": kind, **fields},
                             sort_keys=True, separators=(",", ":"))
        prev = self.root()
        h = sha(prev + "|" + payload)
        cur = self.db.execute(
            "INSERT INTO audit(ts,kind,payload,prev,hash) VALUES(?,?,?,?,?)",
            (ts, kind, payload, prev, h))
        self.db.commit()
        entry = {"seq": cur.lastrowid, "ts": ts, "kind": kind,
                 "fields": fields, "prev": prev, "hash": h}
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

    def verify(self):
        prev = "GENESIS"
        rows = self.db.execute(
            "SELECT seq,payload,prev,hash FROM audit ORDER BY seq").fetchall()
        for seq, payload, stored_prev, stored_hash in rows:
            if stored_prev != prev:
                return {"ok": False, "broken_at": seq}
            if sha(prev + "|" + payload) != stored_hash:
                return {"ok": False, "broken_at": seq}
            prev = stored_hash
        return {"ok": True, "entries": len(rows), "root": prev}
