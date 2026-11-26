#!/usr/bin/env python3
"""Frigate → Janus bridge — the only path from the NVR to the front door.

Frigate (upstream, unrenamed) detects and OCRs plates; this bridge
translates its events into Janus POST /reads calls, authenticating as
the ingest identity — in 1.1 that identity MUST hold the 'ingest'
role (item 8: the retired 'system' role no longer exists, and the
ingest role can POST /reads and nothing else — item 23). Janus stays
the only lasting store and
the only place hot-list matching happens — the bridge keeps nothing but
a bounded in-memory dedupe set and forgets everything on restart.

Run it on the server, bound to localhost:

    FRIGATE_BRIDGE_PORT=8091 python3 frigate_bridge.py

Point Frigate at it with a webhook (Frigate ≥0.13 supports generic
webhooks on review/event alerts) or a small MQTT→HTTP shim that POSTs
the MQTT event JSON verbatim — the bridge accepts the MQTT event shape
unchanged. Endpoints:

  POST /event   one Frigate event (shape below) → maybe one Janus read
  GET  /health  {"ok": true, "forwarded": n, "deduped": n, ...}

PAYLOAD ASSUMPTION (labeled, per INTERFACE.md — verify against the
pinned Frigate version at deploy time, this is the ~1 integration day
the v0.9 README budgets): Frigate's event JSON is
{"before": {...}, "after": {...}, "type": "new"|"update"|"end"}, and
its LPR support exposes the plate on the tracked object as
after.attributes.recognized_license_plate — either "ABC123" or
["ABC123", 0.87] — with after.sub_label as the fallback
("ABC123" or "ABC123, 0.87"). Camera name is after.camera; the event
time is after.start_time (epoch seconds). The bridge ALSO accepts a
plain body {"plate", "state", "camera", "conf", "ts"} so the whole
path is testable without Frigate running (the demo and the test suite
use that shape).

Rules:
  * "end", "update" AND "new" events forward (1.2.4, S9 — this
    paragraph and the code below now agree; 1.2.3's text claimed
    only end/update while the code forwarded "new"). A "new"
    event's plate is an EARLY read: it forwards as one, and Janus
    dedupes persistently on (camera, event_id) and owns the
    supersede decision when the "end" event's final OCR lands —
    the bridge is a pipe, not a judge (Q5). Missing type forwards
    (plain-body test shape). Any other type is ignored.
  * Same event id + same plate forwards once (in-memory dedupe set,
    capped) — and the event id is FORWARDED to Janus (S4), which
    dedupes persistently on (camera, event_id): a bridge restart no
    longer re-ingests the backlog as new reads.
  * State and confidence are forwarded ONLY when Frigate actually
    reported them (S4). 1.1 fabricated "AR" and 0.95 for missing
    values — a guessed state is not a reading, and Janus 1.2 stores
    "" / NULL for what nobody measured.
  * /event requires the shared-secret header X-Bridge-Secret when
    FRIGATE_BRIDGE_SECRET is set — and refuses ALL events (503)
    when it is not set: an unauthenticated plate-injection endpoint
    on the LAN is a hotlist-poisoning endpoint. Bodies are capped
    at 1 MB; stats and the dedupe set are lock-guarded (the server
    is threaded); client sockets time out at 30s.
  * Janus down → the bridge answers 502 and logs; it does NOT queue to
    disk (a disk queue would be a second plate store outside Janus's
    retention rules). Frigate's own event buffer is the outage buffer
    (INTERFACE.md store-and-forward), and events replayed from it land
    here with their original start_time — Janus flags clock skew >5s
    against receipt time, which is how a replayed backlog is visible.

Env: FRIGATE_BRIDGE_PORT=8091, FRIGATE_BRIDGE_BIND=127.0.0.1,
     FRIGATE_BRIDGE_SECRET=<shared secret for /event>,
     NOCTUA_JANUS_URL=http://127.0.0.1:8080,
     NOCTUA_INGEST_USER=ingest.local, NOCTUA_INGEST_KEY=<ingest key>
     (the retired NOCTUA_SYSTEM_* names still work as a fallback).
"""
import hmac
import json
import os
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

JANUS = os.environ.get("NOCTUA_JANUS_URL", "http://127.0.0.1:8080")
SYS_USER = os.environ.get("NOCTUA_INGEST_USER",
                          os.environ.get("NOCTUA_SYSTEM_USER",
                                         "ingest.local"))
SYS_KEY = os.environ.get("NOCTUA_INGEST_KEY",
                         os.environ.get("NOCTUA_SYSTEM_KEY", ""))
PORT = int(os.environ.get("FRIGATE_BRIDGE_PORT", "8091"))
BIND = os.environ.get("FRIGATE_BRIDGE_BIND", "127.0.0.1")
SECRET = os.environ.get("FRIGATE_BRIDGE_SECRET", "")
BODY_CAP = 1_000_000

stats = {"forwarded": 0, "no_plate": 0, "janus_errors": 0}
SEEN_CAP = 10000  # legacy constant, unused since 1.2.2 (Q5)
_lock = threading.Lock()


def _bump(field):
    with _lock:
        stats[field] += 1


def extract(body):
    """Pull (plate, state, camera, conf, ts_iso, event_id) from either
    the Frigate event shape or the plain test shape. Any field may be
    None; the caller decides what is fatal (no plate or no camera is)."""
    after = body.get("after") or body
    plate = conf = None
    attrs = after.get("attributes") or {}
    rlp = attrs.get("recognized_license_plate")
    if isinstance(rlp, (list, tuple)) and rlp:
        plate = str(rlp[0])
        if len(rlp) > 1:
            try:
                conf = float(rlp[1])
            except (TypeError, ValueError):
                pass
    elif isinstance(rlp, str):
        plate = rlp
    if not plate and after.get("sub_label"):
        parts = str(after["sub_label"]).split(",")
        plate = parts[0].strip()
        if conf is None and len(parts) > 1:
            try:
                conf = float(parts[1])
            except ValueError:
                pass
    if not plate and body.get("plate"):
        plate = str(body["plate"])
    camera = after.get("camera") or body.get("camera") or body.get("cam")
    state = after.get("state") or body.get("state")
    if conf is None and body.get("conf") is not None:
        try:
            conf = float(body["conf"])
        except (TypeError, ValueError):
            pass
    ts_iso = body.get("ts")
    if not ts_iso and after.get("start_time"):
        try:
            ts_iso = datetime.fromtimestamp(
                float(after["start_time"]), timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError, OSError):
            ts_iso = None
    return (plate, state, camera, conf, ts_iso,
            after.get("id") or body.get("id"))


def forward(plate, state, camera, conf, ts_iso, event_id,
            event_type=None):
    # S4: absent state/conf stay absent — Janus stores "" / NULL.
    # A bridge that guesses is a bridge that lies on the record.
    # 1.2.2 (Q5): the Frigate event TYPE rides along — Janus ranks
    # an event's "end" delivery above its "update"s when deciding
    # which read is current.
    payload = {"plate": plate.upper(), "cam": camera}
    if event_type:
        payload["event_type"] = str(event_type)
    if state:
        payload["state"] = state.upper()
    if conf is not None:
        payload["conf"] = conf
    if ts_iso:
        payload["ts"] = ts_iso
    if event_id:
        payload["event_id"] = str(event_id)
    req = urllib.request.Request(
        JANUS.rstrip("/") + "/reads",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "X-Noctua-User": SYS_USER, "X-Noctua-Key": SYS_KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read())


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def setup(self):
        super().setup()
        # A stalled client must not freeze the bridge (S4).
        self.connection.settimeout(30)

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            with _lock:
                snap = dict(stats)
            return self.send_json(200, {"ok": True, "service":
                                        "frigate-bridge", **snap})
        return self.send_json(404, {"error": "no such route"})

    def do_POST(self):
        if self.path != "/event":
            return self.send_json(404, {"error": "no such route"})
        # S4: the shared-secret gate, fail-closed. No secret
        # configured = no events accepted, ever — the alternative is
        # an unauthenticated plate-injection endpoint.
        if not SECRET:
            return self.send_json(503, {
                "error": "FRIGATE_BRIDGE_SECRET is not set — the "
                         "bridge refuses events until a shared secret "
                         "is configured"})
        if not hmac.compare_digest(
                self.headers.get("X-Bridge-Secret", ""), SECRET):
            return self.send_json(401, {"error": "bad bridge secret"})
        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            n = 0
        if n < 0:
            # P13: a negative Content-Length is refused outright —
            # read(-1) would block on the socket until EOF.
            return self.send_json(400, {"error":
                                        "negative Content-Length"})
        if n > BODY_CAP:
            return self.send_json(413, {"error": "event body exceeds "
                                               "the 1 MB cap"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self.send_json(400, {"error": "body must be JSON"})
        etype = body.get("type")
        if etype is not None and etype not in ("end", "update", "new"):
            return self.send_json(200, {"forwarded": False,
                                        "reason": f"event type {etype} "
                                                  f"ignored"})
        plate, state, camera, conf, ts_iso, eid = extract(body)
        if not plate:
            _bump("no_plate")
            return self.send_json(200, {"forwarded": False,
                                        "reason": "no plate in event"})
        if not camera:
            return self.send_json(400, {"error": "event has no camera"})
        # 1.2.2 (Q5): NO in-memory dedupe. 1.2.1's (event_id, plate)
        # set dropped exactly the redelivery that carried the
        # corrected plate (round 5, Claude R5-15): Janus dedupes
        # PERSISTENTLY on (camera, event_id) and owns the
        # supersede decision — the bridge is a pipe, not a judge.
        try:
            status, resp = forward(plate, state, camera, conf, ts_iso,
                                   eid, event_type=etype)
        except Exception as e:
            _bump("janus_errors")
            return self.send_json(502, {"forwarded": False,
                                        "error": f"janus unreachable: {e}"})
        _bump("forwarded")
        return self.send_json(200, {"forwarded": True,
                                    "janus_status": status, "janus": resp})


if __name__ == "__main__":
    if not SYS_KEY:
        print("WARNING: NOCTUA_INGEST_KEY is not set — Janus will "
              "refuse every forward with 401")
    if not SECRET:
        print("WARNING: FRIGATE_BRIDGE_SECRET is not set — /event "
              "will refuse all events (503) until it is configured")
    print(f"Frigate bridge listening on {BIND}:{PORT} → {JANUS}/reads")
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
