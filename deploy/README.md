# NOCTUA — Deployment Package (in-hand build)

The deployable foundation for the Cabot city-owned ALPR pilot
(spec: `cabot-open-source-alpr-pilot-spec.md`, Nov. 23, 2026).
Everything here runs on commodity hardware with open-source software.
**The only site-specific work left is configuration**: camera IPs and
credentials in `config/cameras.yaml` + `.env`, user keys in
`config/users.json`, and the open-case list in `config/cases.json`.

## The gates come first (do not skip)

Software being ready does not authorize turning it on. In order:

1. **Ordinance** — the Citizens Commission ordinance passes; the Commission
   convenes (first week of Feb 2027) and reports (June 2027).
2. **ACIC decision in writing** — hot-list access path confirmed
   (Path A: matching stays on the dispatch/ACIC side — this package is
   built for Path A; Path B makes the server a CJIS system and must be
   separately approved and priced; Path C: pilot stops).
3. **Separate Council authorization** — public hearing + vote for the
   pilot itself, with the automatic sunset.
4. **Camera inventory confirmed** — the locations in `cameras.yaml` are
   community-mapped points, *not* an official inventory. Confirm with
   CPD / FOIA, including the Home Depot Dr / Going Dr ownership question,
   before mounting anything.

## What runs where

| Piece | What it is | Why |
|---|---|---|
| **Janus** (`janus/`) | The only front door: auth, case validation, tier rules, hot list, verification, search | One door = one place to enforce every rule and log every act |
| **Sentinel** (`janus/sentinel.py`) | Hash-chained append-only audit log inside Janus's database | Tamper-evidence; entries stream to an outside sink as written, and a signed checkpoint is published outside daily (`scripts/publish_witness.sh`) |
| **Frigate** (container) | Open-source NVR with LPR: watches camera streams, OCRs plates, forwards reads to Janus | The city owns the cameras, the server, and the data — no vendor cloud |
| **Retention job** (`scripts/retention.py`) | Nightly deletion past 14 days (hits: 30-day hold), honoring legal holds, logged into the chain | The shredder is itself audited; if it stops, the gap shows |
| **Console** (`../noctua-sim/cpd-console.html`) | The operator UI the demo runs on | In production it talks to Janus's API instead of its built-in simulation |

## Bring-up (Stage 0 — one camera, city lot, test plates only)

```bash
git clone <city repo> noctua && cd noctua/deploy
cp .env.example .env                     # fill in CAM01 creds + audit key
cp config/users.example.json config/users.json
#   set each user's key:  KEY=$(openssl rand -hex 24); echo $KEY
#   hash into users.json:  printf %s "$KEY" | sha256sum
cp config/cases.example.json config/cases.json
#   edit config/cameras.yaml: CAM-01 -> the lot camera's IP, enabled: true
docker compose up -d janus frigate
curl localhost:8080/health               # {"ok": true, ...}
# drive a test car with a test plate past the lot camera;
# add the plate on the hot list (detective key, valid case) and watch
# /hits?status=PENDING fill, then verify it from the console workflow.
docker compose run --rm retention        # prove the shredder runs + logs
./scripts/publish_witness.sh             # prove the witness path works
```

## Go-live checklist (Stage 1 — 3 cameras, 90 days)

- [ ] Gates 1–3 above complete and minuted
- [ ] Camera inventory confirmed in writing; `cameras.yaml` matches it
- [ ] All 3 pilot cameras `enabled: true`, credentials in `.env` only
- [ ] Named user keys issued in person; **no shared accounts exist**
- [ ] Case list wired to the records-system export (not hand-maintained)
- [ ] Retention timer installed (host cron, nightly 03:00)
- [ ] Witness cron installed (daily 09:00); Clerk received test checkpoint
- [ ] Sentinel sink path mounted from Clerk/auditor-controlled storage,
      and /health shows `sentinel_sink.ok: true`
- [ ] Auditor account issued to the named outside auditor (read-only)
- [ ] Accuracy protocol ready (spec Appendix C — hand-checked sample)
- [ ] Day-90 public report template ready; sunset date on the calendar

## Janus API (complete list)

Auth on everything except `/health`, `/audit/verify`, `/audit/root`:
headers `X-Noctua-User` + `X-Noctua-Key`, named individual accounts only.

| Endpoint | Who | What |
|---|---|---|
| `GET /health` | open | Service status, chain root, Sentinel sink status |
| `POST /reads` | system | Ingest a plate read; hot-list match opens a PENDING hit |
| `GET /search?plate=&case=&why=&tier=&judicial=&emergency=` | detective, patrol, supervisor | Read search. `why` (justification) is **required**; catch-all case patterns are banned; suppressed plates return a stub to non-supervisors |
| `GET /hotlist` · `POST /hotlist` · `DELETE /hotlist/<plate>` | read: any role · write: detective, supervisor | The local hot list |
| `POST /verify` | detective, patrol, supervisor | Confirm/reject a hit against a validated case; writes the plate-free outcome record |
| `POST /outcomes` | detective, supervisor | Set arrest / prosecution flags on a verified hit (prosecutor-feedback placeholder) |
| `GET /report?from=&to=` | any role, incl. auditor | § 12-12-1805 aggregates: plates scanned, per-list confirmed matches, non-corresponding matches, arrests, prosecutions |
| `POST /holds` · `POST /holds/release` | place: detective, supervisor · release: supervisor | Legal holds (case or hit) that stop the retention job |
| `POST /suppressions` · `POST /suppressions/release` | supervisor | Protection-order plate suppression |
| `GET /hits?status=` | any role | Hit queue |
| `GET /audit` · `GET /audit/verify` · `GET /audit/root` | audit: detective, supervisor, auditor, patrol | The Sentinel chain, its verification, its current root |
| `GET /stats` | any role | Counts |

## Hardening added Nov. 23, 2026 (council round)

The AI council review (ChatGPT / Claude ×2 / Gemini, synthesized in the
project record) attacked the first build; these are the fixes that held
up, implemented and live-tested the same day:

1. **No plate text in the chain** (earlier fix, same day): chain entries
   carry keyed HMAC plate references, never plate strings — an
   append-only log of plate text would itself become captured plate
   data retained past every limit.
2. **Real deletion**: `secure_delete` on + VACUUM after retention runs,
   so deleted rows are not recoverable from the database file.
3. **Legal holds** (`POST /holds`): a case or hit under an active hold
   is skipped by the retention job and counted (`held_skipped`) in its
   output and chain entry. Holds attach at the hit/evidence layer —
   where § 12-12-1804(b)'s destruction-at-conclusion rule bites. Reads
   carry no case link and still delete by age.
4. **Sentinel streaming + daily signed checkpoints**: every chain entry
   is also appended (flush + fsync) to a sink file when
   `NOCTUA_SENTINEL_SINK` is set — point it at Clerk/auditor-controlled
   storage. `scripts/checkpoint.py` HMAC-signs `{date, root, entries}`
   daily and `publish_witness.sh` publishes it outside and emails the
   Clerk. Sink health is exposed at `/health`; a dead sink is counted,
   never silent.
   **Key custody, stated plainly:** a checkpoint signature means the
   most when the audit key is held by the Clerk/auditor side, so the
   people verifying are not the people being verified. The shipping
   default keeps the key on the server: that detects tampering by
   outsiders and by anyone who doesn't hold the key, but it does **not**
   stop a fully privileged insider who holds both the chain and the
   key. Moving the key to the Clerk/auditor side is a deployment
   decision the Commission should make explicitly, not discover later.
5. **Statutory report generator** (`GET /report`): § 12-12-1805's
   categories — plates scanned, confirmed matches per list, matches
   determined not to correspond, arrests, prosecutions — fed by a
   plate-free `outcomes` table that retention **never** deletes
   (18-month preservation). `POST /outcomes` is where arrest/prosecution
   outcomes land; it is the placeholder for the prosecutor feedback
   loop the statute's "prosecution" number requires. Note:
   `plates_scanned` counts reads currently in the store, so the
   six-month compilation must be snapshotted at period close, before
   the 14-day horizon passes.
6. **Case-gate hardening**: searches require a justification (`why`),
   which is written into the QUERY chain entry; catch-all case numbers
   (default patterns PATROL, TEST, ADMIN, DUTY) are rejected and
   logged; and when one case is used to search more than 8 distinct
   plate fragments in a day, a `CASE_FLAG` chain entry fires once for
   the auditor — flag, not block.
7. **Protection-order suppression** (`POST /suppressions`): a
   suppressed plate (stored as a keyed reference only) returns a bare
   `{"suppressed": true}` stub — no plate, time, or camera — to
   non-supervisor searchers; supervisors see the record with a
   `SUPPRESSED — protection order` marker. Built *before* any
   owner-disclosure feature, per the council's catch about abusers
   co-owning a victim's car.
8. **Frigate lockdown**: all Frigate ports bound to 127.0.0.1 in
   compose; Frigate's own record/snapshot retention set to 14 days in
   its config; the write-only-sensor rule (no human accounts on
   Frigate, Janus the only lasting store, ingest on the system key)
   written into both files.

## Known gaps (honest list for the Commission)

1. **Frigate config is a template.** The lockdown configuration
   (localhost binding, 14-day media retention, write-only-sensor rule)
   is now written into the config and compose files, but the LPR model
   path and the event→Janus bridging (a small poller of Frigate's
   events API) must still be pinned against the exact Frigate version
   deployed; the config file says so where it matters, including the
   retention keys. Budget a day of integration, not a rewrite.
2. **Console → Janus wiring.** The demo console simulates its backend.
   The production console is the same UI with its data calls pointed at
   Janus's REST API (endpoints already match the screens: /search, /hits,
   /verify, /hotlist, /audit).
3. **CJIS Path B is not in this package.** If ACIC requires the server to
   be a CJIS system, that's the separate, priced build in spec §4 —
   hosting, fingerprinting, FIPS modules, audit areas. Nothing here
   pretends otherwise.
4. **Backups.** Nightly encrypted backup of `noctua-data` to city storage,
   with the witness roots making backup-tampering detectable. Add the
   cron line at deploy time; restore is `docker compose down`, restore
   volume, `up`.
5. **Two-key Tier 3.** The spec's two-key rule for historical searches is
   a console+Janus workflow addition (second supervisor approval token);
   Janus already logs the authorization basis for every Tier 3 query.

## Security model in one paragraph

Named accounts only; every search needs a validated case *and* a stated
justification; catch-all cases are banned; historical searches need a
judge; legal holds stop the shredder when a case is live; the auditor
can look but never touch; every action — allowed or blocked — is
hash-chained, streamed to an outside sink as it happens, and anchored
by a signed checkpoint that leaves the building daily; protected plates
are suppressed even from search results; and the data deletes itself
at 14 days. There is no vendor to subpoena, breach, or trust.
