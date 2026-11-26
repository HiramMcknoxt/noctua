#!/usr/bin/env python3
#  ___
# (o o)   VESPER · the evening watch
# (   )   Vesper, for Corey Spangler — Cabot, Arkansas
#  ^^^
"""Janus — the NOCTUA front door. Version 1.2.4.

The ONLY way anything reads or writes NOCTUA data. Stdlib-only Python
service over SQLite, built to the Cabot pilot spec and the NOCTUA
interface spec. 1.2 is the council-round-3 hardening release: round 3
confirmed 1.1's core repairs (Tier 2 wall, chain atomicity, role
splits, QUERY logging, SS 1805 counts) and concentrated on what
remained — secondary copies of plate data retention didn't know
about, trust records that attested rather than verified, and scripts
that quietly undid the service's own protections.

1.2 changes (item numbers are the round-3 brief, S1-S17):
 S1  PLATE_DATA_STORES: a code-level registry (declared in
     sentinel.py, re-exported here) of every table.column and folder
     that can hold plate text or plate-derived time+place, each with
     a retention class. retention.py purges BY the registry;
     sentinel_audit.py audits BY it; a schema test fails the build
     when a plate-bearing column or folder is unregistered.
 S2  Tier 3 results are no longer stored as serialized bodies.
     tier3_requests stores only the matched read ids + hit ids;
     GET /tier3/results/<id> resolves them LIVE through the current
     shaping layer (suppression filter, case revalidation); aged-out
     detail returns the plate-free summary and says so.
 S3  Canonical, state-blind suppression identity: plate_ref() hashes
     the canonical plate only (sentinel.normalize_plate); ingest
     stores plate (canonical) AND plate_raw (as read). Search
     shaping filters suppressed rows IN SQL before the LIMIT.
     /verify and /evidence/export route suppressed hits only via
     the supervisor queue.
 S4  Ingest honesty: a camera REGISTRY (cameras.json) — an
     unregistered camera's reads are refused (INGEST_REJECTED).
     Missing state is stored as "" (unknown), missing confidence as
     NULL; the 0.95/AR fabrication is gone. Frigate event ids are
     forwarded and deduped persistently on (camera, event_id).
 S5  Health truth: degraded includes a broken chain and a retention
     breach, by name. /health requires auth (supervisor/auditor/
     jobs); the unauthenticated probe is GET /ping. Chain
     verification is cached (<=60s) and computed on a detached
     read-only connection, never under the write lock. Camera health
     is computed against the registry — a camera that has never
     reported appears as never_reported. scripts/hotlist_sync.py
     ships, so the monitored hotlist_sync job can actually exist;
     the witness job is monitored too.
 S6  Witness + anchor: checkpoint.py reads (seq, hash) in ONE query
     inside one transaction and keeps stdout to the single JSON
     line; publish_witness.sh posts the witness heartbeat only
     after a successful publish. restore.py never overwrites the
     live checkpoints file, requires a signed manifest when a key
     is configured, uses tarfile filter="data", moves db + -wal +
     -shm aside together, prunes pre-restore copies per the
     registry, and leaves a marker Janus chains as RESTORE at boot.
     The startup anchor fails CLOSED on a missing/malformed
     checkpoints file, verifies checkpoint SIGNATURES, checks the
     max-entries checkpoint, and remembers accepted state.
 S7  Key separation: NOCTUA_AUDIT_KEY stays the plate-HMAC secret.
     Checkpoints, audit reports, rotation schedules, and Compact
     receipts are signed with an Ed25519 keypair (system openssl;
     sentinel.py). Boot stores the audit key's fingerprint in meta
     and locks on a MISMATCH, not just on a missing key.
 S8  Compact gate semantics: the gate reads the LATEST audit row
     per partner — a newer failure closes it immediately. Receipts
     must name our NEWEST checkpoint, carry the partner's Ed25519
     signature over (root, entries, checkpoint_ts, agency), and
     freshness is measured from the checkpoint's own timestamp.
     compact.py independently recomputes the partner's chain over
     GET /audit/range and records a SIGNED report — the endpoint
     verifies the signature, not a bare boolean.
 S9  chain_auditor role: /audit, /audit/root, /audit/verify,
     /audit/range, GET /compact/checkpoint — nothing else.
     /tier3/results readership is requester + supervisors only.
 S10 Shares capped at Tier 2; case_ref and basis_type required;
     partner free text is stored in the DB and NEVER chained raw
     (the chain carries why_hash); the stale-config fail-closed
     rule applies; 60 queries/hour per partner, then 429.
 S11 Chain discipline + atomic logging: Janus's data connection IS
     the chain's connection — a handler's data writes and its chain
     appends commit in ONE transaction. Chain payloads carry
     case_hash / why_hash and enum categories; AUTH_FAIL chains a
     hashed username, throttled, with aggregate counts. The
     scrubber sanitizes and flags (CHAIN_SCRUB_FLAG) instead of
     raising, and legitimate IDs (CAM-101, CPD-1001) work.
 S12 Rotation correctness: build_schedule's seed actually permutes
     the slots (documented algorithm); members are deduplicated
     and validated; publication validates members against the
     partner registry, requires a real date and a 7-120 day
     period, and refuses to replace an active cycle (voiding is
     supervisor+auditor two-key, ROTATION_VOID). Duty tracking
     reads signed receipts (audits of us) and audit rows (audits
     by us) inside each round's window; witness duty is tracked
     via attestations.
 S13 Config ceilings: RETENTION_DAYS > 150 refuses startup; the
     Tier 2 window ceiling is 72h (refused, value in the error).
     The effective config is recorded in the SYSTEM chain entry at
     boot. Stale-config fail-closed applies to ALL data endpoints.
     Config reloads chain CONFIG_CHANGED with a diff hash.
 S14 Report residuals: REPORT_COMPILE chains a HASH of the
     snapshot. List names come from a supervisor-managed list
     registry (POST /lists). K8's denominator is EXECUTED Tier 3
     searches only. Per-list prosecutions get the same
     "not yet reported" treatment as the totals. Outcomes are
     created at ALERT time (status=unresolved) and updated at
     verification — an unreviewed hit that ages out stays counted
     as unresolved forever. A plate may sit on multiple lists:
     hotlist membership is its own table.
 S17 Evidence residuals: re-export deletes the prior bundle in the
     same operation; released bundles carry destroy_by (release +
     30d), surfaced in /health when overdue; custody excerpts
     compare hit ids as ints; HOLD entries carry hit_id; evidence
     bundles are included in backups (0600).

Concurrency: one shared SQLite connection plus one lock serializing
request handling (DBLOCK). Request bodies are read before the lock
and responses are serialized after it, so the lock covers database
work only. At a 9-camera city's volume that is not a bottleneck.
Stated plainly: this is a small-city service, not a horizontal-scale
design.

1.2.1 changes (council round 4, items P1-P13 of the 1.2.1 brief —
round 4 reproduced 39 defects at runtime against 1.2; each item is
the fix for named findings):
 P1  Share tier is strict: /share/query accepts ONLY tier==2 as a
     JSON int. tier=1, tier=true, tier=3 all refuse with
     SHARE_BLOCKED and the refused tier chained as a coded value.
 P2  "" no longer means expiry: hotlist rows store NULL when no
     expiry is given (existing '' rows are migrated at boot), and
     hotlist_sync sweeps in ONE transaction with its chain entries.
 P3  Suppression is a property of the PLATE AT QUERY TIME. /hits,
     Tier 3 result resolution, /verify, /evidence/export and share
     results all evaluate live suppression (canonical plate vs the
     active orders) at read time; hits.suppressed is a cache only.
 P4  In-place upgrades are repaired at first 1.2.1 boot: legacy
     reads.plate / hits.read_plate are normalized to canonical form
     (original kept in plate_raw), chained as MIGRATION with counts.
 P7  Compact records bind: audit-result requires report.agency ==
     the filing agency and report.ts within 26h, and stores the
     report's own ts; the share gate is evaluated AT QUERY TIME by
     one helper (newest checkpoint must exist; the latest receipt
     must match it, be verified, and be <=26h old); reinstate reads
     the latest audit row by id.
 P9  Rotation: the seed is DERIVED (SHA-256 of sorted members,
     cycle_start, current chain root) — a publisher-supplied seed
     is refused; delinquency counts completed rounds only, per
     agency, by direction-correct filings; /compact/witness
     requires a supervisor or the partner's registered-key
     signature and chains WITNESS_ATTEST.
 P11 One verification contract (sentinel.entry_hash, hash v2);
     anchor acceptance records the accepted CHECKPOINT IDS, so a
     later good checkpoint does not re-trigger an accepted
     disagreement; first config load chains CONFIG_CHANGED and the
     SYSTEM entry carries the config hash + hold_days; a key-locked
     boot no longer eats the restore marker; an env audit key is
     never trust-on-first-use pinned over an existing chain.
 P12 /tier3/pending shows a SUPERVISOR approver the fragment, case,
     justification, and auth basis — the second key can judge what
     it approves. Detectives stay plate-free, own requests only.
 P13 Holds: review_by must be a real date in (today, today+HOLD_DAYS];
     HOLD_DAYS itself is capped at 150 at boot; retention is never
     blocked past 150 days by paperwork alone (an unconfirmed
     disposition protects nothing without a bundle). DELETE /hotlist
     DELETES the identified membership (404 when none). /audit limit
     outside 1..1000 is a 400. Negative Content-Length is a 400.
     /audit/verify uses the cached detached verify and never holds
     DBLOCK while verifying. A Frigate redelivery with a corrected
     plate supersedes the stored read (READ_SUPERSEDED) instead of
     dying as a duplicate.

1.2.2 changes (council round 5, items Q1-Q28 of the round-5
synthesis — round 5 reproduced the 1.1->1.2.1 upgrade voiding every
pre-upgrade protection order, and eight valid seats voted NOT
CONVERGED):
 Q1/Q2 Registry-driven upgrade repair: suppressions are RE-KEYED
     under the current formula from their stored plate text,
     hotlist_members / hits.entry_plate are canonicalized, holds
     gain their review_by backfill, plate-less orders are explicitly
     invalidated and chained — never silently void. No data repair
     runs on a key-locked boot; all of it runs, chained, on the
     first unlocked boot.
 Q3  The audit-key pin VERIFIES: an unpinned key over an existing
     chain is pinned only after it reproduces stored keyed refs
     (current or 1.1 legacy formula), or after the two-operator
     provision.py pin-audit-key ceremony. A wrong key in the key
     FILE no longer pins silently.
 Q4  Hot-list expiry is a parsed instant: ISO-8601 validated at the
     door (400 otherwise), stored canonical UTC, compared parsed.
 Q5  Reads are append-only VERSIONS of an event; currency is one
     decision (phase, then confidence, then arrival). A plate change
     of currency WITHDRAWS pending hits — never deletes them; a hit
     id the API returned never 404s; the read behind a verified hit
     is immutable. The bridge no longer dedupes.
 Q6  One retention decision (sentinel.hit_deletable / ts_cutoff /
     day_cutoff), shared by the purge and the breach check;
     retention.py purges and chains in ONE transaction.
 Q7  The evidence lifecycle keys on the evidence record, not the
     hit row: release / disposition / destroy work after the hit
     purges; a stranded bundle is flagged in /health; re-export is
     failure-atomic and resets the release clock; a bundle missing
     on disk protects nothing; partner case_refs are stored keyed.
 Q9  config_closed() is enforced at DISPATCH for every data
     endpoint, POSTs included; POST /report/compile takes GET
     /report's role fence; /search is allow-listed by role.
 Q10 Evidence expand requires an executed Tier 3 request covering
     the same case and plate; the reason is chained.
 Q11 Tier 3 instruments are configuration (NOCTUA_TIER3_BASIS_TYPES,
     default warrant,court_order): 'other' cannot execute.
 Q12 Holds require a validated case and the supervisor role, and
     release only on documented authority (prosecutor sign-off or
     case closure); every id/ref at the API boundary is strictly
     validated ('1garbage' / '1.0' refuse with 400).
 Q13 The outside auditor's emergency review is independent of the
     supervisor's, and the auditor sees what it reviews.
 Q14 The case-list feed itself goes stale: a configured freshness
     window (export stamp or file age) fails closed.
 Q15 AUTH_FAIL throttling no longer crashes on its own markers;
     SHARE_BLOCKED / receipt refusals are chain-throttled.
 Q16 flush_deferred presence-checks on a separate read-only
     connection; Janus flushes inside DBLOCK after commit.
 Q18 /health and /audit/verify authenticate BEFORE any chain scan;
     the cached verify is single-flight.
 Q21 The Compact gate is a function of audit TIME: stale or
     duplicate signed reports are refused at filing.
 Q23 Rotation is commit-reveal: members commit nonce hashes, then
     reveal; the seed derives from the REVEALED nonces; cycle_start
     chains from the previous cycle's end; ONE schedule builder
     (sentinel.rotation_schedule) serves Janus and rotation.py.
 Q24 A supervisor attests only for the home agency; partner
     attestations require the registered signature and schedule
     membership.
 Q26 A malformed config of ANY shape fails closed (stale), never a
     500 loop.
 Q27 Search fragments are canonicalized like plates; an aged-out
     Tier 3 request EXPIRES instead of executing blank; the report
     snapshot parameter is validated; custody excerpts include
     OUTCOME_UPDATE; SHARE_OUT chains tier_defaulted.

1.2.3 changes (council round 6, items R1-R15 of the round-6
synthesis — five seats voted NOT CONVERGED on 1.2.2, and the
orchestrator reproduced the headliners in-tree):
 R1  Protection orders are RECORDS: one row per order under a
     surrogate id, UNIQUE(plate_ref, order_ref). Placing a second
     order never overwrites the first; a release lifts only the
     order it names; query-time suppression is "any live order
     covers the plate". (Round 6: two seats independently found a
     fresh install losing protection when orders overlapped.)
 R2  Migration integrity: every repair unit runs in its own
     SAVEPOINT; a bad row quarantines as a chained MIGRATION_DEFECT
     and a /health migration_status marker — never a silent total
     rollback. Duplicate hot-list spellings merge deterministically
     (union of protections). A plate-less order is RECOVERED by
     matching its stored ref against known plates, and kept ACTIVE
     when no plate matches — counted unverifiable, never silently
     invalidated (the order 1.2.2 deactivated was one 1.2.1 had
     honored). Key verification tries every historical formula
     (sentinel.key_ref_candidates).
 R3  The pin ceremony verifies with the same candidate set Janus
     boots with; provision.py's legacy formula and column name are
     fixed; the boot refusal names the ceremony that works.
 R4  No out-of-lock side effects: _reload_config never chains (the
     CONFIG_CHANGED/STALE entries flush at the start of the next
     locked section, or at boot); the chain verify never computes
     while DBLOCK is held and the pre-warm is limited to roles that
     can consume a verify; no DML runs before the key fingerprint
     check (the receipts dedupe moved into the chained migration;
     the list-registry seed row is planted after the check, on
     unlocked boots only).
 R5  The sink battery is real: flush_deferred also consults the
     Chain's streamed-entry ledger (a rolled-back entry's
     committed twin is never streamed twice), sink bookkeeping
     moved to a dedicated connection, and the Q16 case runs
     against NOCTUA_SENTINEL_SINK with fault injection.
 R6  The rotation ceremony has a phase barrier (commitments freeze
     at the first reveal and are never overwritten), authorship
     (a partner's filing is its own identity or its Ed25519
     signature; a supervisor transports, never authors), a cancel
     path (supervisor alone before any reveal, two-key after),
     void that clears the cycle's contributions, a 16-character
     nonce floor, and published schedules that bind the nonces
     into the signature and carry the publisher's public key.
     Witness attestations bind to the round's designated attester.
 R7  compact.py anchors at the partner's CHECKPOINT (its state
     keeps a checkpoint mark separate from the live mark; two
     consecutive runs against a healthy partner both pass), and a
     future-dated checkpoint now fails the freshness check here
     and in compact.py.
 R8  One verification implementation: compact.py and
     sentinel_audit.py verify fetched ranges through
     sentinel.verify_chain_rows, v1 cross-check included.
 R9  A same-plate supersede re-points the event's PENDING hits at
     the new current read, so a later correction withdraws the hit
     it actually belongs to (round 6, Gemini F8).
 R10 restore.py's trust root is the host, full stop: a backup
     set's own audit key no longer vouches for its manifest.
 R11 Restore-orphaned evidence bundles enter the retention purge:
     an on-disk bundle with no evidence row is deleted at the
     reads class, so the breach flag clears by work, not by hand.
 R12 The stale-feed fence is cause-aware: a stale case FEED
     closes data reads (503 naming the feed and its age) while
     safety writes — ingest and protection-order placement and
     release — proceed with a chained warning. A stale config
     FILE still closes everything.
 R13 Chain-growth attribution: SHARE_BLOCKED and INGEST_REJECTED
     throttles key on the AUTHENTICATED identity, never on
     caller-supplied text, and the entries name the caller.
 R15 Honesty sweep: version stamps; /health carries
     migration_status and the CHAIN_SCRUB_FLAG count; the
     disposition-note clock is capped at the 150-day ceiling.

1.2.4 changes (council round 7, items S1-S12 of the round-7
synthesis — round 7 voted NOT CONVERGED unanimously on 1.2.3):
 S1  Sink delivery is durable: the obligation derives from the
     committed audit table (sentinel's sink_pending ledger), a
     verification failure preserves it, and /health is not green
     over an unresolved delivery backlog.
 S2  Boot repair preserves semantics: hot-list canonicalization
     keeps '' (stateless) instead of rewriting it to NULL, and a
     recovered plate-less order regains its plate AND its current
     plate_ref in one statement — it is fully active on the FIRST
     boot, not the second.
 S3  ONE suppression predicate: every disclosure leg — SQL and
     Python alike — decides by keyed plate_ref (the SQL legs call
     the same plate_ref through a registered SQLite function), and
     a plate-less order whose ref matches a plate under any
     historical formula suppresses that plate everywhere.
 S4  The demo/install boundary is SERVER-SIDE: demo mode is the
     NOCTUA_DEMO_MODE=1 environment opt-in, recorded in the SYSTEM
     entry and /health. The users-file guard runs inside
     _apply_config on boot AND every reload — a violating reload
     is refused and the last-good config kept. Multi-role entries
     under ANY name (and "imperator" in any case) require demo
     mode; the file's own "demo" flag is parsed strictly (JSON
     true only) and licenses nothing by itself.
 S5  Rotation ceremony completeness: bulk commitments are
     signature-gated per entry exactly as single contributions
     are; /commit closes in ALL shapes at the first reveal;
     contributions record a ceremony-instance id and a cancelled
     or voided ceremony's contributions are tombstoned against
     replay; witness designation at n>=4 rotates deterministically
     among the eligible others; witness status splits positive vs
     adverse attestations; n=2 self-attestation is labeled.
 S6  Migration completeness: a janus10 fixture (the real 1.0 tree)
     rides in tests/fixtures; the direct 1.0 -> current upgrade
     completes (the legacy hotlist's `source` column is honored);
     the suppressions rebuild isolates per row; MIGRATION_DEFECT
     and /health carry the exception MESSAGE, not just its type.
 S7  Evidence lifecycle completion: retention remediates
     destroyed-on-paper bundles, and destruction is ordered
     record-first — files are deleted only after the destroy is
     committed and chained, never before.
 S8  Restore honesty: restore.py is "pre-validated; the swap is
     not I/O-failure-atomic", installs via copy-to-temp +
     os.replace, and never prints REFUSING after the live set has
     been replaced; Janus refuses to mint a fresh key/chain over
     a directory holding .pre-restore-* copies with no restore
     marker.
 S9  Boundary hygiene: _strict_id clamps to SQLite's int64 and
     rejects negatives (400, never 500) and routes /tier3/results
     and /audit/range; the boot refusal prints only remedies that
     work (pin ceremony with --confirm, env precedence stated);
     the pin ceremony overwrites a wrong pre-existing key file;
     anchor acceptance clears only checkpoint_disagreement;
     frigate_bridge's doc and code agree on "new" events;
     alert_check no longer calls a case-feed staleness a data
     fail-close; compact recompute fails explicitly on an
     inverted range.
 S10 Chain contract: _append_txn returns the participation
     decision captured at insert; scrub bookkeeping cannot leak a
     transaction on a shared connection; chain verification
     freshness under load is bounded (NOCTUA_VERIFY_MAX_STALE_S,
     default 300) and /health says so when the bound is exceeded.
 S11 Two-factor authentication (2FA-SCOPE.md): TOTP (RFC 6238)
     for every HUMAN role, enrolled via provision.py, secrets in
     a 0600 file beside the DB (never in the chain, never in
     backups — a restore forces re-enrollment), replay-proof
     within its window, failures feeding the AUTH_FAIL throttle,
     one-time recovery codes whose use chains RECOVERY_USED and
     flags /health until a supervisor acknowledges, two-key
     supervisor re-enrollment. Machine identities stay key-only.
     The demo waiver exists only through S4's server-side mode.
 S12 Measurement honesty: the load comparison is re-measured
     per-process with landed-count verification on both trees;
     boot-time migration scan cost is measured on a large DB;
     hits(read_id) gains its index.
"""
import base64
import hashlib
import hmac as hmac_mod
import json
import os
import re
import secrets
import shutil
import sqlite3
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import sentinel
from sentinel import Chain, now_iso, sha

VERSION = "1.2.4"
# S1: the plate-data registry is declared once, in sentinel.py (the
# module every component already shares), and re-exported here so
# janus.PLATE_DATA_STORES is the name the council's forced change
# asked for.
PLATE_DATA_STORES = sentinel.PLATE_DATA_STORES
REGISTRY_VERSION = sentinel.REGISTRY_VERSION

DB_PATH = os.environ.get("NOCTUA_DB", "/data/noctua.db")
USERS_PATH = os.environ.get("NOCTUA_USERS", "/config/users.json")
CASES_PATH = os.environ.get("NOCTUA_CASES", "/config/cases.json")
CAMERAS_PATH = os.environ.get("NOCTUA_CAMERAS", "/config/cameras.json")
BIND = os.environ.get("NOCTUA_BIND", "127.0.0.1")
PORT = int(os.environ.get("NOCTUA_PORT", "8080"))
EVIDENCE_DIR = os.environ.get(
    "NOCTUA_EVIDENCE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "evidence"))
CHECKPOINTS_PATH = os.environ.get("NOCTUA_CHECKPOINTS",
                                  DB_PATH + ".checkpoints.jsonl")
AGENCY = os.environ.get("NOCTUA_AGENCY", "THIS-AGENCY")

# Retention clocks: the same env names retention.py uses.
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD_DAYS = int(os.environ.get("HOLD_DAYS", "30"))
TIER2_WINDOW_H = float(os.environ.get("NOCTUA_TIER2_WINDOW_H", "24"))

# S13: hard ceilings, refused at startup with the value named. The
# 150-day ceiling is Ark. Code SS 12-12-1804(a)'s statutory cap — a
# config above it is not a policy choice, it is an illegality the
# service declines to boot into. The 72h Tier 2 ceiling keeps
# "contemporaneous" from quietly becoming "last quarter".
if RETENTION_DAYS > 150:
    raise SystemExit(
        "REFUSING TO START: RETENTION_DAYS=%d exceeds the 150-day "
        "statutory ceiling (Ark. Code 12-12-1804(a))" % RETENTION_DAYS)
if TIER2_WINDOW_H > 72:
    raise SystemExit(
        "REFUSING TO START: NOCTUA_TIER2_WINDOW_H=%s exceeds the "
        "72-hour ceiling for a 'contemporaneous' Tier 2 window"
        % TIER2_WINDOW_H)
if HOLD_DAYS > 150:
    # P13: the hits class is a retention promise; a hold window
    # above the statutory cap would keep plate data past the
    # 150-day ceiling of Ark. Code 12-12-1804(a) by configuration.
    raise SystemExit(
        "REFUSING TO START: HOLD_DAYS=%d exceeds the 150-day "
        "statutory ceiling (Ark. Code 12-12-1804(a))" % HOLD_DAYS)

# Dead-man thresholds: a required job whose last heartbeat is older
# than this (or missing, or ok:false) makes /health report degraded.
JOB_MAX_AGE_S = {"retention": 26 * 3600, "checkpoint": 26 * 3600,
                 "hotlist_sync": 26 * 3600, "backup": 30 * 3600,
                 "witness": 26 * 3600}
CAMERA_SILENCE_S = 6 * 3600
BODY_CAP = 1_000_000

BASIS_TYPES = ("warrant", "court_order", "other")
# 1.2.2 (Q11): the instruments a Tier 3 search may EXECUTE on are
# configuration, defaulting to judicial instruments only. Round 5
# executed a Tier 3 search on basis_type "other" with the auth basis
# "verbal OK from the lieutenant" (Claude R5-11) — spec SS7 item 3
# requires an entered judicial-authorization number with signed
# authorization. Whether any non-judicial instrument may ever
# qualify is the City Attorney's question; the code defaults closed
# and the accepted set is named in the SYSTEM entry at boot.
TIER3_BASIS_TYPES = tuple(
    t.strip() for t in os.environ.get(
        "NOCTUA_TIER3_BASIS_TYPES", "warrant,court_order").split(",")
    if t.strip()) or ("warrant", "court_order")
# 1.2.2 (Q14): the case list is a FEED, and a feed that stops
# arriving must fail closed like any other stale config (spec SS7
# item 9 — round 5, Claude R5-10: a 30-day-old case list searched
# happily). The window is measured from the export stamp inside
# cases.json ("exported_ts") when present, else the file's mtime.
# 0 disables the feed check (the file's own 24h staleness rule
# still applies).
CASES_MAX_AGE_H = float(os.environ.get("NOCTUA_CASES_MAX_AGE_H", "48"))
# 1.2.4 (S4): DEMO MODE IS A SERVER-SIDE INSTALL DECISION. It is
# set by the operator in the service's environment — never by a
# config file the service reads. Demo mode is what licenses
# multi-role accounts (the demo seed's `imperator` presenter) and
# the S11 TOTP waiver; it is recorded in the SYSTEM chain entry
# and surfaced in /health, so a demo install can never pass for a
# production one in the record.
DEMO_MODE = os.environ.get("NOCTUA_DEMO_MODE") == "1"
# 1.2.4 (S10): the chain-verification freshness bound. Under
# saturating ingest DBLOCK is held almost continuously, so the
# detached verify may be unable to refresh for a while; /health
# serves the cached result marked stale only up to this bound —
# past it, chain_ok reports False ("verify overdue") rather than
# vouching for a chain nobody has checked lately (round 7, Claude
# seat p4). Stated here, in /health's chain_verify.stale detail,
# and in the SYSTEM entry.
VERIFY_MAX_STALE_S = float(os.environ.get(
    "NOCTUA_VERIFY_MAX_STALE_S", "300"))
REVIEW_FINDINGS = ("justified", "unjustified", "needs_followup")
SERVICE_ROLES = ("ingest", "jobs", "partner")
DATA_ROLES = ("detective", "supervisor", "auditor")
# S9: the chain_auditor may touch exactly these GET paths.
CHAIN_AUDITOR_GETS = ("/audit", "/audit/root", "/audit/verify",
                      "/audit/range", "/compact/checkpoint")
AUDIT_READ_ROLES = ("supervisor", "auditor", "chain_auditor")
# S11/S14: hot-list categories chained as an ENUM; unknown maps to
# "other". (The DB keeps the operator's original wording; the
# permanent chain gets the code.)
CATEGORY_ENUM = ("stolen_vehicle", "felony_warrant", "warrant",
                 "missing_person", "amber_alert", "silver_alert",
                 "evidence", "expired", "test", "other")


def category_enum(category):
    norm = re.sub(r"\s+", "_", (category or "").strip().lower())
    return norm if norm in CATEGORY_ENUM else "other"


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def _audit_key():
    """(key, locked). Resolve the plate_ref HMAC key: env, else the
    per-install key file (created with os.open 0o600 — no TOCTOU
    window). If the database already holds audit rows and NO key is
    available, return (None, True): Janus must start LOCKED (round-2
    item 30). Minting a fresh key would silently unmatch every
    suppression and orphan every plate_ref already in the chain."""
    has_rows = False
    if os.path.exists(DB_PATH):
        try:
            probe = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            has_rows = probe.execute(
                "SELECT COUNT(*) FROM audit").fetchone()[0] > 0
            probe.close()
        except sqlite3.Error:
            has_rows = False  # no audit table yet = fresh install
    # 1.2.4 (S8): the FRESH-INIT GUARD, checked before ANY key
    # source is honored. This directory holds .pre-restore-*
    # copies — a restore moved a live system aside here — but the
    # database has no audit rows and no restore marker completes
    # the story. Starting would found a FRESH chain over the
    # installation's own recovery copies (round 7, Qwen F-H: a
    # mid-swap I/O failure leaves exactly this shape, and 1.2.3's
    # next boot disguised the data loss as a fresh install — with
    # the deployment's env key, no less, so key-minting was never
    # the step that needed guarding). Refuse: the operator either
    # completes the restore (its marker exempts the copies, and a
    # restored database has rows) or removes the copies
    # deliberately.
    if not has_rows:
        try:
            base = os.path.basename(DB_PATH)
            db_dir = os.path.dirname(os.path.abspath(DB_PATH))
            copies = [n for n in os.listdir(db_dir)
                      if n.startswith(base) and ".pre-restore-" in n]
        except OSError:
            copies = []
        if copies and not os.path.exists(DB_PATH
                                         + ".restore_marker"):
            _AUDIT_KEY_GUARD["reason"] = "pre_restore_copies"
            return None, True
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k, False
    kf = DB_PATH + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip(), False
    if has_rows:
        return None, True
    k = secrets.token_hex(32)
    fd = os.open(kf, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, k.encode())
    finally:
        os.close(fd)
    return k, False


_AUDIT_KEY_GUARD = {"reason": None}
AUDIT_KEY, KEY_LOCKED = _audit_key()
KEY_LOCK_REASON = ((_AUDIT_KEY_GUARD["reason"] or "missing")
                   if KEY_LOCKED else None)


def plate_ref(plate):
    """This deployment's plate_ref: sentinel.plate_ref over the
    canonical, state-blind plate identity (S3/S15)."""
    if AUDIT_KEY is None:
        return "pref:unavailable"
    return sentinel.plate_ref(AUDIT_KEY, plate)


def frag_ref(frag):
    if AUDIT_KEY is None:
        return "pref:unavailable"
    return sentinel.frag_ref(AUDIT_KEY, frag)


def normalize_plate(plate):
    return sentinel.normalize_plate(plate)


def case_hash(case_no):
    """1.2.1 (P11/A36): case numbers are chained as a KEYED HMAC
    (sentinel.case_ref). 1.2's bare SHA-256 was reversible by brute
    force over the ~10^5 case-number space in seconds — the chain
    is readable by partners' chain_auditors by design, so anything
    chained must be keyed or public."""
    if AUDIT_KEY is None:
        return "cref:unavailable"
    return sentinel.case_ref(AUDIT_KEY, case_no or "")


def why_hash(text):
    if AUDIT_KEY is None:
        return "tref:unavailable"
    return sentinel.text_ref(AUDIT_KEY, text or "")


# --- users / cases / cameras, reloaded on mtime change so
# --- provision.py and the nightly case export take effect without a
# --- restart. A FAILED reload marks the file stale, chains
# --- CONFIG_STALE (throttled), degrades /health, and past 24h of
# --- staleness the data surface fails closed. A SUCCESSFUL reload
# --- whose content changed chains CONFIG_CHANGED with a diff hash
# --- (S13): account and case-list changes are auditable events.
USERS = {}
# 1.2.4 (S4): USERS_DEMO is the SERVER-SIDE demo mode (the
# NOCTUA_DEMO_MODE environment opt-in) and nothing else. 1.2.3
# took it from the users file's own "demo" flag — a file could
# declare itself a demo and license the god account (round 7,
# register C). The file's flag is still parsed (strictly: JSON
# true only) into USERS_FILE_DEMO for /health diagnostics, but it
# licenses nothing.
USERS_DEMO = DEMO_MODE
USERS_FILE_DEMO = False
CASES = set()
CAMERAS = {}
_config = {
    "users": {"path": USERS_PATH, "mtime": None, "stale_since": None,
              "last_chain": 0.0, "hash": None},
    "cases": {"path": CASES_PATH, "mtime": None, "stale_since": None,
              "last_chain": 0.0, "hash": None},
    "cameras": {"path": CAMERAS_PATH, "mtime": None,
                "stale_since": None, "last_chain": 0.0, "hash": None},
}


CASES_EXPORTED_TS = None


class ConfigGuardError(ValueError):
    """A users config the install mode forbids (1.2.4, S4). A
    ValueError so _reload_config's stale machinery treats it like
    any other unusable config — the last-good config is kept and
    the file is marked stale — while the boot sequence can still
    name it as the refusal it is."""


def _users_guard_error(users):
    """The S4 install-mode guard over a candidate users dict, or
    None when the config is admissible. Runs inside _apply_config
    — on the boot load AND on every hot reload — so there is no
    path by which a forbidden account becomes live: 1.2.3 ran its
    guard once at boot, and a hand edit to users.json admitted
    `imperator` into a running production install on the next
    request (round 7, register C / Qwen F-B). The rules:
      * an account named `imperator` (any case) is the demo seed's
        presenter account and exists only in demo mode;
      * an entry carrying MORE THAN ONE role is a god account
        under whatever name it travels — demo mode only.
    Demo mode is the server-side NOCTUA_DEMO_MODE=1 opt-in; the
    users file cannot declare it for itself."""
    if DEMO_MODE:
        return None
    for name, rec in users.items():
        if str(name).lower() == "imperator":
            return ("user 'imperator' is the DEMO-ONLY presenter "
                    "account and this install is not in demo mode "
                    "(NOCTUA_DEMO_MODE=1 is a server-side opt-in; "
                    "a users file cannot declare itself a demo)")
        roles = rec.get("roles") or [rec.get("role")]
        roles = {r for r in roles if r}
        if len(roles) > 1:
            return ("user %r carries multiple roles %s — "
                    "multi-role accounts exist only in demo mode "
                    "(NOCTUA_DEMO_MODE=1, set server-side)"
                    % (name, sorted(roles)))
    return None


def _apply_config(name, data):
    """Apply one parsed config file. 1.2.2 (Q26): the SHAPE is
    validated and a wrong shape raises ValueError — round 5 showed
    _reload_config catching only (OSError, ValueError) while a
    list-shaped cameras.json or dict-shaped users.json raised
    TypeError/KeyError inside the request path, so /ping stayed
    green while every authenticated request 500'd forever (the
    mtime was recorded only on success, so every request retried
    and re-raised). A bad shape is a stale config, not a crash."""
    global USERS, CASES, CAMERAS, CASES_EXPORTED_TS, USERS_FILE_DEMO
    if name == "users":
        # 1.2.3 (demo commission): users.json may also be an object
        # {"demo": true, "users": [...]} — the form demo/seed_demo.py
        # writes. An entry may carry "roles" (a list) instead of
        # the single "role". 1.2.4 (S4): the file's demo flag is
        # parsed STRICTLY — JSON true only; the string "false" was
        # truthy under 1.2.3's bool() and flipped an install into
        # "demo" (round 7, cold-seat I3) — and it licenses NOTHING:
        # demo mode is server-side (DEMO_MODE). The candidate user
        # set is built and guard-checked BEFORE any global moves,
        # so a refused reload leaves the last-good config live.
        file_demo = False
        if isinstance(data, dict):
            file_demo = data.get("demo") is True
            data = data.get("users")
        if not isinstance(data, list) or not all(
                isinstance(u, dict) and "user" in u
                and ("role" in u or "roles" in u)
                and ("key_sha256" in u or "key" in u) for u in data):
            raise ValueError("users.json must be a list of "
                             "{user, key_sha256, role} objects "
                             "(or a {demo, users} object wrapping "
                             "that list)")
        candidate = {u["user"]: u for u in data}
        guard_err = _users_guard_error(candidate)
        if guard_err:
            raise ConfigGuardError(guard_err)
        USERS_FILE_DEMO = file_demo
        USERS = candidate
    elif name == "cases":
        if not isinstance(data, dict) \
                or not isinstance(data.get("open_cases"), list):
            raise ValueError("cases.json must be an object with an "
                             "open_cases list")
        CASES = set(data["open_cases"])
        CASES_EXPORTED_TS = data.get("exported_ts")
    else:  # cameras: a JSON list of ids, or {cameras: [...]} / {id: {...}}
        if isinstance(data, dict) and "cameras" in data:
            data = data["cameras"]
        if isinstance(data, dict):
            CAMERAS = dict(data)
        elif isinstance(data, list):
            CAMERAS = {c: {} for c in data}
        else:
            raise ValueError("cameras.json must be a list or object")


def _reload_config():
    """Reload any config file whose mtime moved. 1.2.3 (R4): this
    function NEVER chains and never writes the database. Round 6
    (seat 2 F4 / Gemini F6) showed auth() calling it OUTSIDE DBLOCK,
    where its chain.append landed on the shared connection inside
    ANOTHER request's open transaction — the other request's
    answered writes then rolled back while their chain entries
    committed. A reload now only updates the in-memory config and
    records PENDING chain entries; _flush_config_chain() lands
    them at the start of the next locked section (or at boot)."""
    for name, st in _config.items():
        try:
            m = os.path.getmtime(st["path"])
            if m != st["mtime"]:
                with open(st["path"], "rb") as f:
                    raw = f.read()
                _apply_config(name, json.loads(raw))
                digest = sha(raw.decode("utf-8", "replace"))[:16]
                # P11/A13: the FIRST load chains too. 1.2 chained
                # only changes against an in-memory hash, so an
                # account added while Janus was stopped was live at
                # boot with no CONFIG_CHANGED anywhere — the audit
                # trail began after the fact it most needed to
                # record. The boot-time load is a chained fact.
                changed = digest != st["hash"]
                st["hash"] = digest
                st["mtime"] = m
                st["stale_since"] = None
                st.pop("guard_error", None)
                if changed:
                    st["pending_changed"] = digest
        except (OSError, ValueError, TypeError, KeyError,
                AttributeError) as exc:
            # Q26: ANY malformed shape is a stale config — see
            # _apply_config. The request path must never see the
            # exception, or one bad nightly export 500s the service.
            # 1.2.4 (S4): an install-mode guard refusal lands here
            # too — the reload is refused, the last-good config
            # stays live, and the refusal is recorded by name for
            # the boot check and /health.
            if isinstance(exc, ConfigGuardError):
                st["guard_error"] = str(exc)
            if st["stale_since"] is None:
                st["stale_since"] = time.time()
            now = time.time()
            if now - st["last_chain"] > 3600:
                st["pending_stale"] = type(exc).__name__


def _flush_config_chain():
    """Land pending CONFIG_CHANGED / CONFIG_STALE entries (R4).
    The caller holds DBLOCK (request dispatch) or is the boot
    sequence; the entries commit as their OWN transaction before
    the handler runs, so they can never ride — or be rolled back
    with — another request's work. If a previous handler somehow
    left a transaction open, the flush defers rather than join
    it. On a KEY_LOCKED boot nothing is chained, ever (Q02)."""
    if KEY_LOCKED:
        return
    if db.in_transaction:
        return
    landed = False
    for name, st in _config.items():
        digest = st.pop("pending_changed", None)
        if digest:
            try:
                chain.append("CONFIG_CHANGED", {
                    "file": name, "diff_hash": digest,
                    "config_hash": digest})
                landed = True
            except Exception:
                st["pending_changed"] = digest
        err = st.pop("pending_stale", None)
        if err:
            try:
                chain.append("CONFIG_STALE", {
                    "file": name, "error": err})
                st["last_chain"] = time.time()
                landed = True
            except Exception:
                st["pending_stale"] = err
    if landed:
        try:
            db.commit()
        except sqlite3.Error:
            pass


def config_hash():
    """The combined hash of the three config files as last loaded —
    carried in the SYSTEM chain entry (P11/A13), so the exact
    account/case/camera set a boot started under is a chain fact,
    not a log line."""
    parts = []
    for name in ("users", "cases", "cameras"):
        parts.append("%s=%s" % (name, _config[name]["hash"] or "none"))
    return sha("|".join(parts))[:32]


def cases_feed_stale():
    """Q14: is the case-list FEED itself stale? The window runs from
    the export stamp inside cases.json when it parses, else from
    the file's mtime — a nightly export that stopped running 30
    days ago leaves a file Janus happily searches against (round 5,
    Claude R5-10). Returns (stale, age_hours or None)."""
    if CASES_MAX_AGE_H <= 0:
        return False, None
    stamp = None
    if CASES_EXPORTED_TS:
        try:
            stamp = parse_ts(CASES_EXPORTED_TS).timestamp()
        except (ValueError, TypeError):
            stamp = None
    if stamp is None:
        try:
            stamp = os.path.getmtime(CASES_PATH)
        except OSError:
            return False, None
    age_h = (time.time() - stamp) / 3600.0
    return age_h > CASES_MAX_AGE_H, round(age_h, 1)


def config_status():
    out, fail_closed = {}, False
    now = time.time()
    stale_files = []
    for name, st in _config.items():
        since = st["stale_since"]
        out[name] = {
            "stale": since is not None,
            "stale_since": (datetime.fromtimestamp(
                since, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if since else None)}
        if since and now - since > 24 * 3600:
            fail_closed = True
            stale_files.append(name)
    feed_stale, feed_age = cases_feed_stale()
    out["cases"]["feed_stale"] = feed_stale
    out["cases"]["feed_age_hours"] = feed_age
    if feed_stale:
        fail_closed = True
    out["fail_closed"] = fail_closed
    # 1.2.3 (R12): the fence is cause-aware — a stale config FILE
    # and a stale case FEED close different surfaces, and the 503
    # names which one fired. `closed_reasons` is the machine form;
    # config_closed() renders the human form.
    out["closed_reasons"] = {
        "files": stale_files,
        "feed_stale": bool(feed_stale),
        "feed_age_hours": feed_age}
    return out


db = sqlite3.connect(DB_PATH, check_same_thread=False)


def _sql_plate_ref(value):
    """The plate_ref primitive as a SQLite function (1.2.4, S3):
    SQL suppression legs call THIS — sentinel.plate_ref over the
    install's key — so the SQL decision and the Python decision
    are the same function, not two implementations that can drift
    (round 7, register B3 / Qwen F-F). NULL in, NULL out: a NULL
    plate matches no order."""
    if value is None or AUDIT_KEY is None:
        return None
    return sentinel.plate_ref(AUDIT_KEY, value)


db.create_function("noctua_plate_ref", 1, _sql_plate_ref)
db.execute("PRAGMA busy_timeout = 5000")
db.execute("PRAGMA secure_delete = ON")
db.execute("PRAGMA journal_mode = WAL")
db.executescript(
    """CREATE TABLE IF NOT EXISTS reads(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         plate TEXT, plate_raw TEXT, state TEXT, conf REAL,
         cam_ts TEXT, skew_s INTEGER, event_id TEXT,
         supersedes INTEGER, phase TEXT);
       CREATE TABLE IF NOT EXISTS hotlist_members(
         plate TEXT, state TEXT, list_source TEXT, case_no TEXT,
         category TEXT, added_by TEXT, added_ts TEXT,
         expires_ts TEXT, active INTEGER DEFAULT 1,
         PRIMARY KEY(plate, state, list_source, case_no));
       CREATE TABLE IF NOT EXISTS hits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         read_plate TEXT, entry_plate TEXT, state TEXT, list_name TEXT,
         category TEXT, status TEXT DEFAULT 'PENDING', decided_by TEXT,
         case_no TEXT, decided_ts TEXT, suppressed INTEGER DEFAULT 0,
         read_id INTEGER);
       CREATE TABLE IF NOT EXISTS holds(
         id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, ref TEXT,
         reason TEXT, placed_by TEXT, placed_ts TEXT,
         released_by TEXT, released_ts TEXT, active INTEGER DEFAULT 1,
         review_by TEXT, case_no TEXT);
       CREATE TABLE IF NOT EXISTS outcomes(
         hit_id INTEGER PRIMARY KEY, list_name TEXT, category TEXT,
         confirmed INTEGER DEFAULT 0, arrest INTEGER DEFAULT 0,
         prosecution INTEGER, reviewed INTEGER DEFAULT 0,
         status TEXT DEFAULT 'unresolved', updated_by TEXT,
         updated_ts TEXT, hit_ts TEXT);
       CREATE TABLE IF NOT EXISTS case_searches(
         case_no TEXT, day TEXT, frag TEXT,
         PRIMARY KEY(case_no, day, frag));
       CREATE TABLE IF NOT EXISTS case_flags(
         case_no TEXT, day TEXT, PRIMARY KEY(case_no, day));
       CREATE TABLE IF NOT EXISTS suppressions(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         plate_ref TEXT, plate TEXT, state TEXT,
         order_ref TEXT, placed_by TEXT, case_no TEXT, ts TEXT,
         active INTEGER DEFAULT 1, release_requested_by TEXT,
         release_order_ref TEXT, released_ts TEXT,
         UNIQUE(plate_ref, order_ref));
       CREATE TABLE IF NOT EXISTS counters(
         day TEXT, camera_id TEXT, reads INTEGER DEFAULT 0,
         alerts INTEGER DEFAULT 0, PRIMARY KEY(day, camera_id));
       CREATE TABLE IF NOT EXISTS lists_checked(
         day TEXT, list_name TEXT, PRIMARY KEY(day, list_name));
       CREATE TABLE IF NOT EXISTS list_registry(
         list_name TEXT PRIMARY KEY, created_by TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS heartbeats(
         job TEXT PRIMARY KEY, ts TEXT, ok INTEGER, detail TEXT);
       CREATE TABLE IF NOT EXISTS tier3_requests(
         id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT,
         case_no TEXT, why TEXT, plate_fragment TEXT, auth_basis TEXT,
         basis_type TEXT, status TEXT DEFAULT 'PENDING', created_ts TEXT,
         decided_by TEXT, decided_ts TEXT, emergency INTEGER DEFAULT 0,
         needs_review INTEGER DEFAULT 0, review_finding TEXT,
         review_note TEXT, reviewed_by TEXT, reviewed_ts TEXT,
         results_count INTEGER, results TEXT, results_read_ids TEXT,
         results_hit_ids TEXT, auditor_review_finding TEXT,
         auditor_reviewed_by TEXT, auditor_reviewed_ts TEXT);
       CREATE TABLE IF NOT EXISTS evidence(
         hit_id INTEGER PRIMARY KEY, export_ts TEXT, export_by TEXT,
         manifest_hash TEXT, bundle TEXT, scope TEXT, expand_reason TEXT,
         prosecutor_name TEXT, prosecutor_date TEXT, released_by TEXT,
         released_ts TEXT, destroyed_ts TEXT, destroyed_by TEXT,
         destroy_by TEXT,
         disp_outcome TEXT, disp_by TEXT, disp_date TEXT, disp_note TEXT,
         disp_posted_by TEXT, disp_confirmed_by TEXT,
         disp_confirmed_ts TEXT, disp_ts TEXT);
       CREATE TABLE IF NOT EXISTS report_snapshots(
         id INTEGER PRIMARY KEY AUTOINCREMENT, from_ts TEXT, to_ts TEXT,
         compiled_by TEXT, compiled_ts TEXT, body TEXT);
       CREATE TABLE IF NOT EXISTS partners(
         agency TEXT PRIMARY KEY, endpoint TEXT,
         audit_key_fingerprint TEXT, pubkey_pem TEXT,
         agreement_ref TEXT, status TEXT DEFAULT 'active',
         added_by TEXT, added_ts TEXT);
       CREATE TABLE IF NOT EXISTS compact_receipts(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT, root TEXT,
         entries INTEGER, sig TEXT, checkpoint_ts TEXT,
         verified INTEGER DEFAULT 0, received_ts TEXT);
       CREATE TABLE IF NOT EXISTS compact_audits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT, ok INTEGER,
         detail TEXT, report_hash TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS share_queries(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT,
         case_ref TEXT, why TEXT, basis_type TEXT, plate_ref TEXT,
         tier INTEGER, result_count INTEGER, outcome TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS rotation_schedules(
         id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_start TEXT,
         period_days INTEGER, members_count INTEGER, schedule_hash TEXT,
         schedule TEXT, published_by TEXT, published_ts TEXT);
       CREATE TABLE IF NOT EXISTS witness_attestations(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT,
         cycle_start TEXT, round_no INTEGER, ok INTEGER, detail TEXT,
         ts TEXT);
       CREATE TABLE IF NOT EXISTS rotation_contributions(
         cycle_start TEXT, agency TEXT, nonce_hash TEXT, nonce TEXT,
         committed_ts TEXT, revealed_ts TEXT,
         PRIMARY KEY(cycle_start, agency));
       CREATE TABLE IF NOT EXISTS meta(
         key TEXT PRIMARY KEY, value TEXT);"""
)
db.commit()

# --- migrations for databases created by 1.0/1.1 -------------------
def _cols(table):
    return [r[1] for r in db.execute(f"PRAGMA table_info({table})")]


for _t, _c, _d in (
        ("reads", "plate_raw", "TEXT"), ("reads", "event_id", "TEXT"),
        ("reads", "cam_ts", "TEXT"), ("reads", "skew_s", "INTEGER"),
        ("reads", "supersedes", "INTEGER"),
        ("reads", "phase", "TEXT"),
        ("hits", "read_id", "INTEGER"),
        ("holds", "case_no", "TEXT"),
        ("evidence", "disp_ts", "TEXT"),
        ("tier3_requests", "auditor_review_finding", "TEXT"),
        ("tier3_requests", "auditor_reviewed_by", "TEXT"),
        ("tier3_requests", "auditor_reviewed_ts", "TEXT"),
        ("hits", "state", "TEXT DEFAULT 'AR'"),
        ("hits", "list_name", "TEXT"),
        ("hits", "suppressed", "INTEGER DEFAULT 0"),
        ("holds", "review_by", "TEXT"),
        ("outcomes", "reviewed", "INTEGER DEFAULT 0"),
        ("outcomes", "status", "TEXT DEFAULT 'unresolved'"),
        ("suppressions", "plate", "TEXT"), ("suppressions", "state", "TEXT"),
        ("suppressions", "order_ref", "TEXT"),
        ("suppressions", "release_requested_by", "TEXT"),
        ("suppressions", "release_order_ref", "TEXT"),
        ("suppressions", "released_ts", "TEXT"),
        ("tier3_requests", "basis_type", "TEXT"),
        ("tier3_requests", "review_note", "TEXT"),
        ("tier3_requests", "results", "TEXT"),
        ("tier3_requests", "results_read_ids", "TEXT"),
        ("tier3_requests", "results_hit_ids", "TEXT"),
        ("evidence", "scope", "TEXT"), ("evidence", "expand_reason", "TEXT"),
        ("evidence", "destroyed_ts", "TEXT"),
        ("evidence", "destroyed_by", "TEXT"),
        ("evidence", "destroy_by", "TEXT"),
        ("evidence", "disp_outcome", "TEXT"), ("evidence", "disp_by", "TEXT"),
        ("evidence", "disp_date", "TEXT"), ("evidence", "disp_note", "TEXT"),
        ("evidence", "disp_posted_by", "TEXT"),
        ("evidence", "disp_confirmed_by", "TEXT"),
        ("evidence", "disp_confirmed_ts", "TEXT"),
        ("partners", "pubkey_pem", "TEXT"),
        ("rotation_contributions", "ceremony_id", "TEXT"),
        ("compact_receipts", "checkpoint_ts", "TEXT"),
        ("compact_receipts", "verified", "INTEGER DEFAULT 0")):
    if _c not in _cols(_t):
        db.execute(f"ALTER TABLE {_t} ADD COLUMN {_c} {_d}")
db.commit()


def _deferred_data_migrations(counts):
    """The pre-1.2 DATA migrations (plate_raw backfill, outcomes
    review state, the 1.1 hotlist -> hotlist_members move incl. the
    DROP TABLE). 1.2.2 (Q2): these used to run inline at schema time
    — on a KEY-LOCKED boot too, rewriting history with no chain
    entry anywhere (round 5, Qwen F10). They now run from
    _migrate_124, on the first UNLOCKED boot only, with their row
    counts folded into the chained MIGRATION entry. Structural DDL
    above (CREATE TABLE / ADD COLUMN) still runs on every boot: it
    is idempotent, carries no plate data, and a locked boot needs
    the tables to answer /health."""
    n = db.execute(
        "UPDATE reads SET plate_raw = plate WHERE plate_raw IS NULL"
    ).rowcount
    if n:
        counts["reads_plate_raw_backfilled"] = n
    n = db.execute(
        "UPDATE outcomes SET reviewed = 1, status = 'reviewed' "
        "WHERE reviewed = 0 AND updated_ts IS NOT NULL").rowcount
    if n:
        counts["outcomes_marked_reviewed"] = n
    if "hotlist" in [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]:
        # S14: the 1.1 single-row hotlist becomes the membership
        # table — a plate may sit on several lists, under cases.
        # 1.2.4 (S6): the list-source column is whichever the
        # legacy table actually carries — 1.1 renamed it list_name,
        # but a genuine 1.0 table calls it `source` (the 1.0 DDL:
        # plate, state, category, source, case_no, ...). 1.2.3
        # SELECTed list_name unconditionally, so a direct 1.0
        # upgrade raised OperationalError on EVERY boot, the
        # migration never completed, and the hot list never moved
        # (round 7, cold-seat F1 — the upgrade path itself was the
        # outage). Individual statements, not executescript: the
        # caller isolates this unit in a SAVEPOINT.
        n_hot = db.execute(
            "SELECT COUNT(*) FROM hotlist").fetchone()[0]
        hcols = _cols("hotlist")
        if "list_name" in hcols:
            src_expr = ("CASE WHEN list_name IS NULL OR "
                        "list_name = '' THEN 'Local agency list' "
                        "ELSE list_name END")
        elif "source" in hcols:
            src_expr = ("CASE WHEN source IS NULL OR source = '' "
                        "THEN 'Local agency list' ELSE source END")
        else:
            src_expr = "'Local agency list'"
        db.execute(
            "INSERT OR IGNORE INTO hotlist_members(plate, state, "
            "list_source, case_no, category, added_by, added_ts, "
            "expires_ts, active) SELECT plate, state, %s, case_no, "
            "category, added_by, added_ts, expires_ts, active "
            "FROM hotlist" % src_expr)
        db.execute("DROP TABLE hotlist")
        if n_hot:
            counts["hotlist_rows_migrated"] = n_hot
    db.commit()

db.executescript(
    """CREATE INDEX IF NOT EXISTS idx_reads_plate ON reads(plate);
       CREATE INDEX IF NOT EXISTS idx_reads_ts ON reads(ts);
       CREATE INDEX IF NOT EXISTS idx_hits_plate ON hits(read_plate);
       CREATE INDEX IF NOT EXISTS idx_hits_read_id ON hits(read_id);""")
# 1.2.2 (Q5): reads are append-only VERSIONS of an event — several
# rows may share (cam, event_id), so 1.2's UNIQUE index on that pair
# is dropped wherever an upgraded database still carries it.
db.execute("DROP INDEX IF EXISTS idx_reads_event")
db.execute("CREATE INDEX IF NOT EXISTS idx_reads_event "
           "ON reads(cam, event_id)")
db.commit()
# 1.2.3 (R4): NO data writes run at import any more. Round 6
# (Vesper F3, Gemini M7) showed 1.2.2's receipts dedupe DELETE, the
# list-registry seed INSERT, and the Chain constructor's own
# bookkeeping writes all landing BEFORE the audit-key fingerprint
# check — a key-locked boot rewrote data with no chain entry
# anywhere. The dedupe now runs inside _migrate_124 (counted in
# the chained MIGRATION entry, first unlocked boot); the seed row
# is planted after the fingerprint check; and the Chain is
# constructed after the check too (its sink bookkeeping lives on
# its own connection now — sentinel 1.2.3). What remains at
# import is structural DDL only: idempotent, plate-free, and a
# locked boot still needs the tables to answer /health.
DBLOCK = threading.Lock()


def _mig_unit(name, fn, counts, defects):
    """One migration repair unit (R2): runs in its own SAVEPOINT,
    so a failure rolls back ONLY that unit and is recorded as a
    defect — 1.2.2 ran every repair inside one try, and a single
    hot-list primary-key collision silently rolled back the whole
    pass (round 6, Gemini F4 / seat 2 F2a)."""
    db.execute("SAVEPOINT mig_unit")
    try:
        fn(counts)
    except sqlite3.Error as exc:
        try:
            db.execute("ROLLBACK TO mig_unit")
            db.execute("RELEASE mig_unit")
        except sqlite3.Error:
            pass
        # 1.2.4 (S6): the defect carries the exception MESSAGE, not
        # just its type — "OperationalError" told the operator
        # nothing about WHICH column the 1.0 schema lacked (round
        # 7, cold-seat F1: the type alone sent the diagnosis to a
        # code read instead of the health page).
        defects.append({"unit": name, "error": type(exc).__name__,
                        "message": str(exc)[:200]})
        return
    try:
        db.execute("RELEASE mig_unit")
    except sqlite3.Error as exc:
        # A unit that committed behind our back (an executescript
        # or a stray commit) destroys its own savepoint; the work
        # landed, but the unit broke the isolation contract — say
        # so as a defect rather than crash the boot.
        defects.append({"unit": name,
                        "error": "savepoint_lost:"
                                 + type(exc).__name__,
                        "message": str(exc)[:200]})


def _migrate_124():
    """1.2.3 boot repairs — REGISTRY-DRIVEN (Q1), per-item failure
    isolation (R2). Every repair is a no-op on a database that does
    not need it; whatever changes is chained ONCE as MIGRATION with
    per-store counts, and every failed unit is chained as
    MIGRATION_DEFECT and surfaced in /health as migration_status —
    a repair that cannot complete is a visible deployment
    condition, never a silent rollback (round 6 forced change).
    On a KEY-LOCKED boot NOTHING here runs (Q2): the repairs wait
    for the first unlocked boot and are chained then.

    Carried from 1.2.1/1.2.2 (P4/P2/Q1): reads.plate /
    hits.read_plate / hits.entry_plate canonicalization; hotlist
    '' expiry -> NULL; expiry text parsed to the canonical
    instant; holds review_by backfill and canonical hit refs;
    hits.read_id backfill; the deferred pre-1.2 data migrations.
    New in 1.2.3 (round 6, R1/R2):
      * suppressions become RECORDS (R1): the table is rebuilt
        with a surrogate id and UNIQUE(plate_ref, order_ref) —
        every legacy row keeps its own identity (its order_ref,
        or a synthesized LEGACY-<rowid>), never merged, never
        deleted.
      * suppression re-keying no longer merges collisions: two
        orders for one vehicle coexist as two records.
      * plate-less orders are RECOVERED by matching their stored
        ref against the plates the system actually knows (under
        the current formula AND the 1.1 legacy formula); a ref
        that matches nothing stays ACTIVE — 1.2.2 invalidated
        such an order outright, including one 1.2.1 had honored
        (seat 2, F2c) — and is counted unverifiable in
        migration_status instead of being silently voided.
      * hot-list canonicalization MERGES duplicate spellings
        deterministically (the row with the latest added_ts is
        kept; active is the union; the expiry is the LATEST
        non-null, open-ended winning) instead of dying on the
        primary key.
      * the compact_receipts dedupe (DeepSeek N5) runs here,
        counted, instead of as an unchained import-time DELETE
        (R4 — it fired on key-locked boots too).
    New in 1.2.4 (round 7, S2/S6):
      * hot-list canonicalization preserves a stateless entry's
        '' state — 1.2.3 rewrote it to NULL, and the match
        predicate (state=? OR state='' OR ?='') can never match
        NULL, so a state-less hot-list entry silently stopped
        alerting (register B1, the round's one true regression).
      * a RECOVERED plate-less order regains plate, state AND
        plate_ref in one statement — 1.2.3 set the plate only, so
        the order was half-active for its whole first boot: its
        hits vanished from both queues while /verify and
        /evidence/export still allowed them (register B2). A
        recovery counts only when the restored ref verifies
        under the current formula.
      * the suppressions rebuild isolates PER ROW: a duplicate
        (plate_ref, order_ref) pair in legacy data splits
        deterministically (the later row's order_ref gains a
        #<rowid> suffix) instead of aborting the whole rebuild
        and bricking the suppression surface (Qwen F-E).
      * the deferred pre-1.2 migrations honor the genuine 1.0
        hotlist shape (its list-source column is `source`, not
        1.1's `list_name`) — see _deferred_data_migrations."""
    if KEY_LOCKED:
        return
    counts = {}
    defects = []

    def _defect_chain():
        for d in defects:
            chain.append("MIGRATION_DEFECT", {
                "unit": d["unit"], "error": d["error"],
                "message": d.get("message", ""),
                "to": "1.2.4"})

    try:
        _deferred_data_migrations(counts)
    except sqlite3.Error as exc:
        # The deferred unit commits internally; a failure is a
        # defect like any other, and the remaining units still run.
        defects.append({"unit": "deferred_data_migrations",
                        "error": type(exc).__name__,
                        "message": str(exc)[:200]})
        try:
            db.rollback()
        except sqlite3.Error:
            pass

    def _receipts(counts):
        n = db.execute(
            "DELETE FROM compact_receipts WHERE id NOT IN "
            "(SELECT MIN(id) FROM compact_receipts "
            "GROUP BY agency, root, entries)").rowcount
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS "
                   "idx_receipts_agency_root ON compact_receipts"
                   "(agency, root, entries)")
        if n:
            counts["receipts_deduped"] = n
    _mig_unit("receipts_dedupe", _receipts, counts, defects)

    def _supp_rebuild(counts):
        if "id" in _cols("suppressions"):
            return
        # Individual statements, NOT executescript: executescript
        # issues an implicit COMMIT first, which would destroy
        # this unit's SAVEPOINT (and silently commit the units
        # before it).
        db.execute(
            """CREATE TABLE suppressions_new(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 plate_ref TEXT, plate TEXT, state TEXT,
                 order_ref TEXT, placed_by TEXT, case_no TEXT,
                 ts TEXT, active INTEGER DEFAULT 1,
                 release_requested_by TEXT,
                 release_order_ref TEXT, released_ts TEXT,
                 UNIQUE(plate_ref, order_ref))""")
        # 1.2.4 (S6 / Qwen F-E): PER-ROW isolation. 1.2.3 copied
        # the table with one INSERT...SELECT — a single duplicate
        # (plate_ref, order_ref) pair in legacy data violated the
        # new UNIQUE constraint, rolled the whole unit back, and
        # left the old schema in place, so every suppression
        # placement 500'd until manual SQL. Now each row lands in
        # its own SAVEPOINT; a row whose (plate_ref, order_ref)
        # pair is already taken keeps its own record under a
        # deterministically suffixed order_ref — two records,
        # never merged, never lost — and is counted, not fatal.
        legacy_rows = db.execute(
            "SELECT rowid, plate_ref, plate, state, order_ref, "
            "placed_by, case_no, ts, active, release_requested_by, "
            "release_order_ref, released_ts FROM suppressions "
            "ORDER BY rowid").fetchall()
        split = 0
        for row in legacy_rows:
            (rid, ref, plate, state, oref, placed_by, case_no, ts,
             active, rrb, ror, rts) = row
            if oref is None or oref == "":
                oref = "LEGACY-%d" % rid
            db.execute("SAVEPOINT supp_row")
            try:
                db.execute(
                    "INSERT INTO suppressions_new(plate_ref, plate, "
                    "state, order_ref, placed_by, case_no, ts, "
                    "active, release_requested_by, "
                    "release_order_ref, released_ts) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (ref, plate, state, oref, placed_by, case_no,
                     ts, active, rrb, ror, rts))
                db.execute("RELEASE supp_row")
            except sqlite3.IntegrityError:
                db.execute("ROLLBACK TO supp_row")
                db.execute("RELEASE supp_row")
                db.execute(
                    "INSERT INTO suppressions_new(plate_ref, plate, "
                    "state, order_ref, placed_by, case_no, ts, "
                    "active, release_requested_by, "
                    "release_order_ref, released_ts) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (ref, plate, state, "%s#%d" % (oref, rid),
                     placed_by, case_no, ts, active, rrb, ror, rts))
                split += 1
        db.execute("DROP TABLE suppressions")
        db.execute("ALTER TABLE suppressions_new RENAME TO "
                   "suppressions")
        n = db.execute(
            "SELECT COUNT(*) FROM suppressions WHERE order_ref "
            "LIKE 'LEGACY-%'").fetchone()[0]
        counts["suppressions_table_rebuilt"] = 1
        if n:
            counts["suppressions_legacy_order_refs"] = n
        if split:
            counts["suppressions_rebuild_duplicates_split"] = split
    _mig_unit("suppressions_rebuild", _supp_rebuild, counts, defects)

    def _plate_norm(counts):
        for table, col, key in (
                ("reads", "plate", "reads_plate_normalized"),
                ("hits", "read_plate", "hits_read_plate_normalized"),
                ("hits", "entry_plate",
                 "hits_entry_plate_normalized")):
            n = 0
            for rid, val in db.execute(
                    f"SELECT rowid, {col} FROM {table} WHERE {col} "
                    "IS NOT NULL").fetchall():
                canon = normalize_plate(val)
                if canon != val:
                    db.execute(
                        f"UPDATE {table} SET {col}=? WHERE rowid=?",
                        (canon, rid))
                    n += 1
            if n:
                counts[key] = n
    _mig_unit("plate_normalization", _plate_norm, counts, defects)

    def _hotlist_canon(counts):
        groups = {}
        for row in db.execute(
                "SELECT rowid, plate, state, list_source, case_no, "
                "added_ts, expires_ts, active FROM hotlist_members "
                "WHERE plate IS NOT NULL").fetchall():
            key = (normalize_plate(row[1] or ""),
                   (row[2] or "").upper(), row[3], row[4])
            groups.setdefault(key, []).append(row)
        merged = norm = 0
        for (canon, cstate, _src, _case), rows in groups.items():
            rows.sort(key=lambda r: (r[5] is None, r[5] or "",
                                     r[0]))
            keep = rows[-1]
            active = max((r[7] or 0) for r in rows)
            exps = [r[6] for r in rows if r[6]]
            expires = None if len(exps) < len(rows) else max(exps)
            if keep[1] != canon or (keep[2] or "") != cstate:
                norm += 1
            # 1.2.4 (S2): cstate is written AS GROUPED — a
            # state-less entry's '' stays ''. 1.2.3 wrote
            # `cstate or None`, rewriting '' to NULL; the match
            # predicate (state=? OR state='' OR ?='') never
            # matches NULL, so every state-less hot-list entry
            # silently stopped alerting at the 1.2.3 upgrade
            # (round 7, register B1).
            db.execute(
                "UPDATE hotlist_members SET plate=?, state=?, "
                "active=?, expires_ts=? WHERE rowid=?",
                (canon, cstate, active, expires, keep[0]))
            for extra in rows[:-1]:
                db.execute(
                    "DELETE FROM hotlist_members WHERE rowid=?",
                    (extra[0],))
                merged += 1
        if norm:
            counts["hotlist_members_plate_normalized"] = norm
        if merged:
            counts["hotlist_members_merged"] = merged
        n = db.execute(
            "UPDATE hotlist_members SET expires_ts=NULL WHERE "
            "expires_ts=''").rowcount
        if n:
            counts["hotlist_empty_expiry_to_null"] = n
    _mig_unit("hotlist_canonicalization", _hotlist_canon, counts,
              defects)

    def _hotlist_expiry(counts):
        n = bad = 0
        for rowid, exp in db.execute(
                "SELECT rowid, expires_ts FROM hotlist_members "
                "WHERE expires_ts IS NOT NULL").fetchall():
            parsed = sentinel.parse_expiry(exp)
            if parsed is None:
                db.execute(
                    "UPDATE hotlist_members SET active=0 WHERE "
                    "rowid=?", (rowid,))
                bad += 1
            elif parsed != exp:
                db.execute(
                    "UPDATE hotlist_members SET expires_ts=? "
                    "WHERE rowid=?", (parsed, rowid))
                n += 1
        if n:
            counts["hotlist_expiry_canonicalized"] = n
        if bad:
            counts["hotlist_expiry_unparseable_deactivated"] = bad
    _mig_unit("hotlist_expiry_parse", _hotlist_expiry, counts,
              defects)

    def _supp_repair(counts):
        rekeyed = recovered = 0
        # The plates this installation actually knows — the
        # recovery pool for plate-less orders (R2).
        known = set()
        for table, col in (("reads", "plate"),
                           ("hits", "read_plate"),
                           ("hits", "entry_plate"),
                           ("hotlist_members", "plate")):
            for (p,) in db.execute(
                    f"SELECT DISTINCT {col} FROM {table} WHERE "
                    f"{col} IS NOT NULL").fetchall():
                if normalize_plate(p):
                    known.add(normalize_plate(p))
        rows = db.execute(
            "SELECT id, plate_ref, plate, state, active FROM "
            "suppressions ORDER BY id").fetchall()
        for sid, ref, plate, state, active in rows:
            db.execute("SAVEPOINT mig_row")
            try:
                if plate and normalize_plate(plate):
                    canon = normalize_plate(plate)
                    new_ref = plate_ref(canon)
                    db.execute(
                        "UPDATE suppressions SET plate=?, state=?, "
                        "plate_ref=? WHERE id=?",
                        (canon, (state or "").upper() or None,
                         new_ref, sid))
                    if new_ref != ref:
                        rekeyed += 1
                elif active:
                    match = None
                    for cand in sorted(known):
                        if ref in sentinel.key_ref_candidates(
                                AUDIT_KEY, cand, state):
                            match = cand
                            break
                    if match:
                        # 1.2.4 (S2): recovery restores the WHOLE
                        # identity in one statement — plate, the
                        # canonical state, and the plate_ref under
                        # the CURRENT formula. 1.2.3 set the plate
                        # only and left the legacy-formula ref in
                        # place, so for the order's whole first
                        # boot the SQL legs suppressed its hits
                        # (by plate text) while the ref-based legs
                        # did not (the stored ref never equaled
                        # the current ref): the hits vanished from
                        # both queues and /verify still allowed
                        # them (round 7, register B2). A recovery
                        # counts only when the restored ref is the
                        # one the live predicate computes.
                        new_ref = plate_ref(match)
                        db.execute(
                            "UPDATE suppressions SET plate=?, "
                            "state=?, plate_ref=? WHERE id=?",
                            (match, (state or "").upper() or None,
                             new_ref, sid))
                        if new_ref == plate_ref(match):
                            recovered += 1
            except sqlite3.Error as exc:
                db.execute("ROLLBACK TO mig_row")
                db.execute("RELEASE mig_row")
                defects.append({
                    "unit": "suppression_row:%d" % sid,
                    "error": type(exc).__name__,
                    "message": str(exc)[:200]})
                continue
            db.execute("RELEASE mig_row")
        if rekeyed:
            counts["suppressions_rekeyed"] = rekeyed
        if recovered:
            counts["suppressions_plate_recovered"] = recovered
    _mig_unit("suppressions_repair", _supp_repair, counts, defects)

    def _holds(counts):
        n = bad = 0
        for hid, ref in db.execute(
                "SELECT id, ref FROM holds WHERE scope='hit'"
                ).fetchall():
            if ref is not None and re.fullmatch(r"[0-9]+",
                                                ref or ""):
                canon = str(int(ref))
                if canon != ref:
                    db.execute("UPDATE holds SET ref=? WHERE id=?",
                               (canon, hid))
                    n += 1
            elif ref is not None:
                db.execute(
                    "UPDATE holds SET active=0 WHERE id=? AND "
                    "active=1", (hid,))
                bad += 1
        if n:
            counts["holds_ref_normalized"] = n
        if bad:
            counts["holds_invalid_ref_deactivated"] = bad
        n = 0
        for hid, placed in db.execute(
                "SELECT id, placed_ts FROM holds WHERE active=1 "
                "AND review_by IS NULL").fetchall():
            try:
                base = parse_ts(placed).date()
            except (ValueError, TypeError):
                base = datetime.now(timezone.utc).date()
            db.execute(
                "UPDATE holds SET review_by=? WHERE id=?",
                ((base + timedelta(days=HOLD_DAYS)).isoformat(),
                 hid))
            n += 1
        if n:
            counts["holds_review_by_backfilled"] = n
    _mig_unit("holds_repair", _holds, counts, defects)

    def _hits_backfill(counts):
        n = db.execute(
            "UPDATE hits SET read_id=(SELECT id FROM reads WHERE "
            "reads.cam=hits.cam AND reads.ts=hits.ts AND "
            "reads.plate=hits.read_plate ORDER BY id LIMIT 1) "
            "WHERE read_id IS NULL AND EXISTS (SELECT 1 FROM reads "
            "WHERE reads.cam=hits.cam AND reads.ts=hits.ts AND "
            "reads.plate=hits.read_plate)").rowcount
        if n:
            counts["hits_read_id_backfilled"] = n
    _mig_unit("hits_read_id_backfill", _hits_backfill, counts,
              defects)

    try:
        _defect_chain()
        if counts or defects:
            chain.append("MIGRATION", {
                "to": "1.2.4", "defects": len(defects), **counts})
        db.commit()
    except sqlite3.Error as exc:
        defects.append({"unit": "migration_chain",
                        "error": type(exc).__name__,
                        "message": str(exc)[:200]})
        try:
            db.rollback()
        except sqlite3.Error:
            pass
    # What could NOT be repaired stays visible in /health until it
    # is zero. Plate-less ACTIVE orders that no known plate could
    # explain are UNVERIFIABLE, not void: they stay in force (R2)
    # and are counted here, by name, on every boot.
    try:
        unrepaired = {
            "suppressions_without_plate_text": db.execute(
                "SELECT COUNT(*) FROM suppressions WHERE active=1 "
                "AND (plate IS NULL OR plate='')").fetchone()[0],
            "holds_without_review_by": db.execute(
                "SELECT COUNT(*) FROM holds WHERE active=1 AND "
                "review_by IS NULL").fetchone()[0],
        }
        status = {
            "version": "1.2.4",
            "state": "incomplete" if defects else "complete",
            "counts": counts,
            "defects": defects,
            "unrepaired": unrepaired,
            "unverifiable":
                unrepaired["suppressions_without_plate_text"],
            "ts": now_iso(),
        }
        _meta_set("migration_status",
                  json.dumps(status, sort_keys=True))
        if any(unrepaired.values()):
            _meta_set("migration_unrepaired",
                      json.dumps(unrepaired, sort_keys=True))
        else:
            db.execute("DELETE FROM meta WHERE "
                       "key='migration_unrepaired'")
            db.commit()
    except sqlite3.Error:
        try:
            db.rollback()
        except sqlite3.Error:
            pass
# Catch-all case numbers ("PATROL-2026", a duty log, a test case) are
# how the case gate gets laundered — any case containing one of these
# patterns is rejected and logged. Comma list, case-insensitive
# substring match.
BANNED_CASE_PATTERNS = [p.strip().upper() for p in os.environ.get(
    "NOCTUA_BANNED_CASE_PATTERNS", "PATROL,TEST,ADMIN,DUTY").split(",")
    if p.strip()]


# ---------------- meta + boot integrity (S6, S7) ----------------
def _meta_get(key):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(key, value):
    db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
    db.commit()


def _verify_key_against_stored_refs(key):
    """Q3: can this candidate key EXPLAIN the keyed refs already in
    the database? Returns (checked, matched). Checkable pairs:
    suppressions (plate text -> plate_ref, under the current formula
    AND the 1.1 legacy HMAC(plate|state) formula), and Tier 3 /
    search fragments (fragment text -> frag_ref) checked against the
    refs carried in the chain itself. This replaces 1.2.1's
    file-vs-env PROXY (round 5, Claude R5-13: a WRONG key written
    into the key file was pinned silently, and then 'verified'
    everything written with it — the check verified the key's
    LOCATION, never the key)."""
    checked = matched = 0
    try:
        for plate, state, ref in db.execute(
                "SELECT plate, state, plate_ref FROM suppressions "
                "WHERE plate IS NOT NULL").fetchall():
            # 1.2.3 (R3): the candidate set is sentinel's ONE
            # implementation — the current formula plus the 1.1
            # legacy formula over the plate AS STORED and over the
            # canonical plate. 1.2.2 tried the legacy formula over
            # the canonical plate only, so a 1.1 order stored as
            # 'VIC 309' (ref over 'VIC 309|AR') never verified and
            # its install locked with the CORRECT key in hand
            # (round 6, Gemini F3 / seat 2 F1).
            checked += 1
            if ref in sentinel.key_ref_candidates(key, plate, state):
                matched += 1
        chain_refs = set()
        for (payload,) in db.execute("SELECT payload FROM audit"):
            try:
                pj = json.loads(payload)
            except ValueError:
                continue
            if isinstance(pj, dict) and pj.get("plate_ref"):
                chain_refs.add(pj["plate_ref"])
        frags = [r[0] for r in db.execute(
            "SELECT DISTINCT plate_fragment FROM tier3_requests "
            "WHERE plate_fragment IS NOT NULL AND plate_fragment "
            "NOT LIKE 'pref:%'")]
        frags += [r[0] for r in db.execute(
            "SELECT DISTINCT frag FROM case_searches")]
        for frag in frags:
            checked += 1
            if sentinel.frag_ref(key, frag) in chain_refs:
                matched += 1
    except sqlite3.Error:
        pass
    return checked, matched


def _key_fingerprint_check():
    """S7 + 1.2.2 (Q3): at first boot Janus stores the audit key's
    fingerprint in meta; every later boot compares. A MISMATCH — or
    a probe error against a chain that already has rows — locks the
    service, exactly as a missing key does. First pin over an
    EXISTING chain no longer trusts the key's SOURCE (1.2.1 pinned
    any key that arrived via the key file): the candidate key must
    VERIFY against stored keyed refs (see
    _verify_key_against_stored_refs), or arrive through the
    two-operator pinning ceremony recorded by provision.py
    pin-audit-key (meta key_pin_ceremony names the fingerprint the
    operator confirmed out-of-band; the candidate must match it).
    Nothing checkable and no ceremony: locked, with the remediation
    named in the refusal (see __main__)."""
    global KEY_LOCKED, KEY_LOCK_REASON
    if KEY_LOCKED:
        return
    try:
        stored = _meta_get("audit_key_fingerprint")
        if stored is None:
            n = 0
            try:
                n = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
            except sqlite3.Error:
                n = 0
            if n == 0:
                # Over an EMPTY chain any key is the install's key
                # by definition.
                _meta_set("audit_key_fingerprint", sha(AUDIT_KEY))
                return
            ceremony = _meta_get("key_pin_ceremony")
            if ceremony:
                try:
                    rec = json.loads(ceremony)
                except ValueError:
                    rec = {}
                if hmac_mod.compare_digest(
                        str(rec.get("fingerprint", "")),
                        sha(AUDIT_KEY)):
                    _meta_set("audit_key_fingerprint", sha(AUDIT_KEY))
                    _meta_set("key_pin_pending_chain", "ceremony")
                    return
            checked, matched = _verify_key_against_stored_refs(
                AUDIT_KEY)
            if checked and matched == checked:
                _meta_set("audit_key_fingerprint", sha(AUDIT_KEY))
                _meta_set("key_pin_pending_chain",
                          "verified:%d" % checked)
            else:
                KEY_LOCKED = True
                KEY_LOCK_REASON = "unpinned_key_over_existing_chain"
        elif not hmac_mod.compare_digest(stored, sha(AUDIT_KEY)):
            KEY_LOCKED = True
            KEY_LOCK_REASON = "mismatch"
    except sqlite3.Error:
        try:
            n = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        except sqlite3.Error:
            n = 0
        if n:
            KEY_LOCKED = True
            KEY_LOCK_REASON = "probe_error"


_key_fingerprint_check()

# S11: the chain SHARES Janus's connection — a handler's data writes
# and its chain appends are one transaction, committed together.
# 1.2.2 (Q19): the chain carries the audit key so the scrubber's
# replacements are KEYED plate_refs, and Janus installs the
# exemption checker — cam / agency / members values are exempt from
# scrubbing only when the deployment actually knows them.
# 1.2.3 (R4): the Chain is constructed HERE, after the fingerprint
# check — 1.2.2 constructed it at schema time, and its constructor
# wrote sink/scrub bookkeeping rows on key-locked boots too.
chain = Chain(DB_PATH, conn=db, key=AUDIT_KEY)


def _scrub_exempt_check(leaf, value):
    if leaf in ("cam", "camera"):
        return value in CAMERAS
    if leaf in ("agency", "members"):
        if value == AGENCY:
            return True
        try:
            return db.execute(
                "SELECT 1 FROM partners WHERE agency=?",
                (value,)).fetchone() is not None
        except sqlite3.Error:
            return False
    return False


chain.exempt_check = _scrub_exempt_check
db.execute("CREATE INDEX IF NOT EXISTS idx_audit_kind ON audit(kind)")
db.commit()
if not KEY_LOCKED:
    # The default local list exists from boot; every other name a
    # report may print must be registered by a supervisor first
    # (S14). Planted after the fingerprint check (R4): on a locked
    # boot even this seed row waits.
    db.execute("INSERT OR IGNORE INTO list_registry(list_name,"
               " created_by, ts) VALUES('Local agency list', "
               "'system', ?)", (now_iso(),))
    db.commit()

# The Ed25519 signing keypair (S7) — created beside the DB if absent.
# Failure here (no openssl) is loud at boot and disables signing, not
# the service: checkpoints will fail elsewhere, by name.
SIGNING_PRIV = None
SIGNING_PUB = None
try:
    SIGNING_PRIV, SIGNING_PUB = sentinel.ensure_signing_key(DB_PATH)
    SIGNING_PUB_PEM = open(SIGNING_PUB).read()
except Exception as exc:  # pragma: no cover - environment failure
    SIGNING_PUB_PEM = None
    print("janus: WARNING — Ed25519 signing key unavailable: %s" % exc,
          file=sys.stderr)


def _load_checkpoints():
    """(list, error). The checkpoints file is the outside anchor's
    local copy; a malformed line is an anchor problem, not a detail
    to skip (S6)."""
    if not os.path.exists(CHECKPOINTS_PATH):
        return [], None
    cps = []
    try:
        with open(CHECKPOINTS_PATH) as f:
            for line in f:
                if line.strip():
                    cps.append(json.loads(line))
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__
    return cps, None


def anchor_mismatch():
    return _meta_get("anchor_mismatch") is not None


def _checkpoint_id(cp):
    """A checkpoint's identity for acceptance purposes: its entry
    count and root. Two checkpoints with the same id ARE the same
    anchor fact; a new checkpoint is a new fact (1.2.1, P11)."""
    return [cp.get("entries"), cp.get("root")]


def _accepted_checkpoint_ids():
    try:
        raw = json.loads(_meta_get("anchor_accepted_ids") or "[]")
        return {tuple(x) for x in raw if isinstance(x, list)}
    except ValueError:
        return set()


def _bad_checkpoints(cps=None):
    """The published checkpoints that DISAGREE with the chain right
    now: bad Ed25519 signature, a root that is not the chain hash at
    the checkpoint's entry count, or an entry count the chain no
    longer has (truncation). Acceptance is not consulted here — this
    is the raw disagreement list _anchor_accept records against."""
    if cps is None:
        cps, err = _load_checkpoints()
        if err or not cps:
            return []
    bad = []
    for cp in cps:
        n = cp.get("entries")
        if cp.get("sig_alg") == "ed25519":
            ok_sig = bool(SIGNING_PUB_PEM) and bool(cp.get("pubkey")) \
                and sentinel.pubkey_fingerprint(cp["pubkey"]) \
                == sentinel.pubkey_fingerprint(SIGNING_PUB_PEM) \
                and sentinel.verify_bytes(
                    SIGNING_PUB_PEM,
                    sentinel.checkpoint_signed_bytes(cp),
                    cp.get("sig", ""))
            if not ok_sig:
                bad.append(cp)
                continue
        if not isinstance(n, int):
            bad.append(cp)
        elif n == 0:
            if cp.get("root") != "GENESIS":
                bad.append(cp)
        elif n > chain.count():
            bad.append(cp)  # the checkpoint claims entries we no
            # longer have — the chain was truncated under it
        elif chain.hash_at_seq(n) != cp.get("root"):
            bad.append(cp)
    return bad


def _anchor_evaluate():
    """(mismatch, detail). Checks EVERY published checkpoint (via
    _bad_checkpoints), minus the specific checkpoints a two-key
    acceptance already recorded. 1.2 pinned acceptance to the
    NEWEST checkpoint's (root, entries), so the next good daily
    checkpoint changed the pin and the same accepted disagreement
    re-triggered at every restart (round 4, A15). 1.2.1 records the
    accepted checkpoint IDS: an accepted checkpoint stays accepted
    forever; a NEW disagreeing checkpoint is a new fact and does
    trigger. A checkpoints file that vanished or went malformed
    while the chain has history fails CLOSED."""
    if KEY_LOCKED:
        return False, {}
    cps, err = _load_checkpoints()
    if err:
        return True, {"reason": "checkpoints_unreadable", "error": err}
    if not cps:
        if chain.count() > 0 and _meta_get("anchor_seen_checkpoint"):
            return True, {"reason": "checkpoints_missing"}
        return False, {}
    _meta_set("anchor_seen_checkpoint", "1")
    accepted = _accepted_checkpoint_ids()
    bad = [cp for cp in _bad_checkpoints(cps)
           if tuple(_checkpoint_id(cp)) not in accepted]
    if not bad:
        return False, {}
    newest = max((c for c in bad if isinstance(c.get("entries"), int)),
                 key=lambda c: c["entries"], default=None)
    detail = {"reason": "checkpoint_disagreement",
              "bad_entries": sorted({str(c.get("entries"))
                                     for c in bad})[:5],
              "checkpoint_entries": newest.get("entries")
              if newest else None,
              "checkpoint_root": newest.get("root") if newest else None,
              "chain_entries": chain.count()}
    return True, detail


def _startup_anchor_check():
    mismatch, detail = _anchor_evaluate()
    if mismatch and not anchor_mismatch():
        detail = dict(detail, detected=now_iso())
        _meta_set("anchor_mismatch", json.dumps(detail))
        chain.append("STARTUP_ANCHOR_MISMATCH", {
            "reason": detail.get("reason", ""),
            "checkpoint_entries": detail.get("checkpoint_entries") or 0,
            "chain_entries": chain.count()})


def _consume_restore_marker():
    """S6: restore.py leaves a marker beside the DB; Janus chains
    the RESTORE at boot (restore itself cannot chain into a service
    that is stopped) and removes the marker."""
    marker = DB_PATH + ".restore_marker"
    if not os.path.exists(marker):
        return
    if KEY_LOCKED:
        # P11/A29: a locked boot must NOT consume the marker — 1.2
        # deleted it unchained, so the restore it recorded vanished
        # from history. The marker waits for the first boot that can
        # actually chain the RESTORE.
        return
    try:
        info = json.load(open(marker))
    except (OSError, ValueError):
        info = {}
    chain.append("RESTORE", {
        "from_backup": str(info.get("from_backup", ""))[:64],
        "restored_ts": str(info.get("ts", ""))[:32]})
    # 1.2.4 (S11): the TOTP secret file is excluded from backup
    # sets, so a restore forces re-enrollment — a secret that
    # survived in a copied directory must not silently keep
    # working against a restored chain.
    try:
        tdata = _totp_load()
        flipped = [u for u, e in tdata.items()
                   if isinstance(e, dict)
                   and e.get("status") != "must_reenroll"]
        if flipped:
            for u in flipped:
                tdata[u]["status"] = "must_reenroll"
            _totp_save(tdata)
            chain.append("TOTP_REENROLL_REQUIRED", {
                "accounts": len(flipped),
                "note": "restore forces re-enrollment — the "
                        "secret file is not in backup sets"})
    except Exception:
        pass
    try:
        os.remove(marker)
    except OSError:
        pass


def _imperator_guard():
    """The demo god account stays in the demo. 1.2.3 checked the
    name once at boot against a file-declared demo flag; round 7
    (register C / Qwen F-B) bypassed it three ways — a hot reload
    after boot, a multi-role entry under any other name, and the
    string "false" parsing as demo. 1.2.4 (S4): the guard itself
    lives in _apply_config (see _users_guard_error) and runs on
    the boot load AND every reload, keyed on the server-side demo
    mode. This boot step remains as the hard refusal: when the
    FIRST load was refused, or the live config somehow violates
    the guard, Janus refuses to start."""
    err = _config["users"].get("guard_error") \
        or _users_guard_error(USERS)
    if err:
        print("REFUSING TO START: %s (users file: %s). Remove the "
              "account, or — for a throwaway demo only — start the "
              "service with NOCTUA_DEMO_MODE=1 in its environment "
              "and the demo seed's config." % (err, USERS_PATH),
              file=sys.stderr)
        sys.exit(3)
    if "imperator" in USERS and not USERS_DEMO:
        print("REFUSING TO START: user 'imperator' exists in %s, "
              "which is not a demo-flagged users file. imperator is "
              "the DEMO-ONLY presenter account (every role at "
              "once); it may exist only in a config written by "
              "demo/seed_demo.py ({\"demo\": true, \"users\": [...]}). "
              "Remove the account, or — for a throwaway demo only — "
              "use the demo seed's config." % USERS_PATH,
              file=sys.stderr)
        sys.exit(3)


_reload_config()
_imperator_guard()
_flush_config_chain()
_migrate_124()
_startup_anchor_check()
# NOTE: _consume_restore_marker() is called AFTER the two-factor
# section below, not here — since 1.2.4 it also flips TOTP
# enrollments to must_reenroll, and those helpers are defined
# there. (Calling it here chained the RESTORE but silently
# skipped the flip on a NameError the flip's own guard swallowed
# — caught by the S11 battery case.)
# Q3: a pin established by verification or ceremony at this boot is
# itself a chain fact, recorded once the chain is writable.
_pin_how = _meta_get("key_pin_pending_chain")
if _pin_how and not KEY_LOCKED:
    try:
        chain.append("KEY_PINNED", {"method": _pin_how.split(":")[0],
                                    "detail": _pin_how[:64]})
        db.execute("DELETE FROM meta WHERE key='key_pin_pending_chain'")
        db.commit()
    except Exception:
        pass


# ---------------- two-factor authentication (1.2.4, S11) ----------------
# Per 2FA-SCOPE.md: TOTP (RFC 6238, HMAC-SHA1, 30-second step) is
# the second factor for every HUMAN role. Machine identities
# (ingest, jobs, partner) stay key-only — they have no human to
# hold a phone, and their fences are re-verified by the S battery.
# Secrets live in a 0600 file beside the DB — never in the chain,
# never in users.json, and excluded from backup sets, so a
# restore forces re-enrollment (see _consume_restore_marker).
# Enrollment is by provision.py (the secret is shown once, and the
# enrollment stays PENDING until the first valid code activates
# it); re-enrollment is the two-key endpoint below.
TOTP_PATH = DB_PATH + ".totp.json"
TOTP_HUMAN_ROLES = {"detective", "patrol", "supervisor", "auditor",
                    "chain_auditor"}
_totp_cache = {"mtime": None, "data": {}}


def _totp_load():
    try:
        m = os.path.getmtime(TOTP_PATH)
    except OSError:
        return {}
    if _totp_cache["mtime"] != m:
        try:
            with open(TOTP_PATH) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        _totp_cache["mtime"] = m
        _totp_cache["data"] = data
    return _totp_cache["data"]


def _totp_save(data):
    tmp = TOTP_PATH + ".tmp"
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(data, indent=1,
                                sort_keys=True).encode())
    finally:
        os.close(fd)
    os.replace(tmp, TOTP_PATH)
    _totp_cache["mtime"] = None
    _totp_cache["data"] = data


def _totp_code(secret_b32, counter):
    """One RFC 6238 TOTP value: HMAC-SHA1 over the 30-second
    counter, dynamic truncation, six digits."""
    pad = "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(secret_b32 + pad)
    digest = hmac_mod.new(key, counter.to_bytes(8, "big"),
                          hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    val = (((digest[off] & 0x7F) << 24) | (digest[off + 1] << 16)
           | (digest[off + 2] << 8) | digest[off + 3]) % 1000000
    return "%06d" % val


def _recovery_hash(code):
    norm = re.sub(r"[^0-9A-Za-z]", "", code or "").upper()
    return hashlib.sha256(norm.encode()).hexdigest(), norm


def _totp_accept(user, code):
    """Validate a presented second factor for an ENROLLED account.
    Returns True only for: a TOTP value in the ±1-step drift
    window whose counter is NEWER than the last accepted counter
    (an accepted code is never replayable, even inside its own
    window), or an unused recovery code. A pending enrollment
    ACTIVATES on its first valid code — it cannot activate any
    other way. A recovery code's use chains RECOVERY_USED and
    flags the account in /health until a supervisor acknowledges
    it. Failures return False and the caller's 401 feeds the
    existing AUTH_FAIL throttle (see need_auth)."""
    data = _totp_load()
    entry = data.get(user)
    if not entry or entry.get("status") == "must_reenroll":
        return False
    code = (code or "").strip()
    if re.fullmatch(r"[0-9]{6}", code):
        now_counter = int(time.time()) // 30
        last = entry.get("last_counter", -1)
        for delta in (-1, 0, 1):
            counter = now_counter + delta
            if counter <= last:
                continue
            if hmac_mod.compare_digest(
                    _totp_code(entry["secret"], counter), code):
                entry["last_counter"] = counter
                if entry.get("status") == "pending":
                    entry["status"] = "active"
                    entry["activated_ts"] = now_iso()
                _totp_save(data)
                return True
        return False
    digest, norm = _recovery_hash(code)
    if norm and digest in (entry.get("recovery") or []):
        entry["recovery"] = [h for h in entry["recovery"]
                             if h != digest]
        entry["recovery_alert"] = {"ts": now_iso(), "by": user}
        if entry.get("status") == "pending":
            entry["status"] = "active"
            entry["activated_ts"] = now_iso()
        _totp_save(data)
        try:
            chain.append("RECOVERY_USED", {"user": user})
        except Exception:
            pass
        return True
    return False


def _totp_required(rec):
    """Does this account owe a second factor on this install?
    Enrolled HUMAN accounts do; machine identities never do; and
    the ONLY waiver is S4's server-side demo mode — a users file
    claiming "demo" waives nothing (round 7, 2FA-SCOPE)."""
    if DEMO_MODE:
        return False
    if not (roles_of(rec) & TOTP_HUMAN_ROLES):
        return False
    entry = _totp_load().get(rec["user"])
    return entry is not None


def _totp_status():
    """The /health view: enrollment counts and the accounts whose
    recovery-code use still awaits a supervisor's acknowledgment."""
    data = _totp_load()
    alerts = sorted(u for u, e in data.items()
                    if isinstance(e, dict)
                    and e.get("recovery_alert"))
    return {
        "enrolled_active": sum(
            1 for e in data.values()
            if isinstance(e, dict) and e.get("status") == "active"),
        "enrolled_pending": sum(
            1 for e in data.values()
            if isinstance(e, dict) and e.get("status") == "pending"),
        "must_reenroll": sum(
            1 for e in data.values()
            if isinstance(e, dict)
            and e.get("status") == "must_reenroll"),
        "recovery_alerts": alerts,
        "demo_waived": DEMO_MODE,
    }


_consume_restore_marker()


# ---------------- shared gates ----------------
_auth_fail_counts = {}
_auth_fail_flushed = set()
_auth_fail_global = {}
AUTH_FAIL_GLOBAL_CAP = 25


def _note_auth_fail(user):
    """S11: AUTH_FAIL chains a HASHED username — never the raw header
    an unauthenticated stranger typed — throttled to one entry per
    source per minute, with the minute's aggregate count chained
    when the minute rolls over. 1.2.1 (P13/A20): a GLOBAL cap joins
    the per-user throttle — 1.2 chained one entry per DISTINCT
    username per minute, so 300 throwaway usernames wrote 300
    permanent entries: the audit chain itself was the flood target.
    Past the cap the 401 still goes out; only the chaining stops."""
    if not user or KEY_LOCKED:
        return
    bucket = int(time.time() // 60)
    g = _auth_fail_global.get(bucket, 0) + 1
    _auth_fail_global[bucket] = g
    for k in [k for k in _auth_fail_global if k < bucket - 1]:
        del _auth_fail_global[k]
    if g > AUTH_FAIL_GLOBAL_CAP:
        return
    uh = sha(user)[:16]
    for k in [k for k in _auth_fail_counts if k[1] < bucket - 1]:
        del _auth_fail_counts[k]
    # 1.2.2 (Q15): the flushed markers live in their OWN set. 1.2.1
    # stored them in _auth_fail_counts under a 3-tuple key, and the
    # prune above compared k[1] — the username STRING for a marker
    # key — against the integer bucket: after a few mistyped
    # passwords the next failure raised TypeError, the 500 replaced
    # the 401, and failed-login logging stayed off for the life of
    # the process (round 5, Claude R5-01).
    prev = _auth_fail_counts.get((user, bucket - 1))
    if prev and prev > 1 and (user, bucket) not in _auth_fail_flushed:
        _auth_fail_flushed.add((user, bucket))
        try:
            chain.append("AUTH_FAIL", {"user_hash": uh, "count": prev,
                                       "aggregate": True})
        except Exception:
            pass
    n = _auth_fail_counts.get((user, bucket), 0) + 1
    _auth_fail_counts[(user, bucket)] = n
    if n == 1:
        try:
            chain.append("AUTH_FAIL", {"user_hash": uh, "count": 1})
        except Exception:
            pass  # the 401 still goes out


_chain_throttle = {}


def _chain_throttled(kind, key, fields, window_s=60):
    """Chain at most one `kind` entry per (kind, key) per window;
    suppressed repeats are counted and the count rides the next
    entry that does land (1.2.2, Q15). SHARE_BLOCKED and receipt
    refusals chain on UNAUTHENTICATED-adjacent paths — a partner (or
    a stranger with a partner's endpoint) hammering a closed gate
    could otherwise grow the permanent chain without bound, the
    flood AUTH_FAIL's global cap already closes for logins."""
    now = time.time()
    slot = _chain_throttle.get((kind, key))
    if slot and now - slot[0] < window_s:
        slot[1] += 1
        return False
    suppressed = slot[1] if slot else 0
    _chain_throttle[(kind, key)] = [now, 0]
    if len(_chain_throttle) > 512:
        for k in [k for k, v in _chain_throttle.items()
                  if now - v[0] > 3600]:
            del _chain_throttle[k]
    payload = dict(fields)
    if suppressed:
        payload["suppressed_repeats"] = suppressed
    try:
        chain.append(kind, payload)
    except Exception:
        pass
    return True


def _strict_id(value):
    """1.2.2 (Q12): an id at the API boundary is an int, or a string
    of decimal digits — nothing else. SQLite's type coercion made
    '1.0' act as hit 1 and '1garbage' bind a hold to hit 1 while
    the chain named no hit at all (round 5). Returns int or None.
    1.2.4 (S9): the value is also CLAMPED to SQLite's int64 —
    round 7 (Qwen F-C) showed a 30-digit id passing this check and
    dying as an OverflowError 500 at bind time, a >4300-digit
    string raising ValueError inside int() itself, and negative
    ints sailing through. Out-of-range is a 400 at every call
    site, never a 500."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 9223372036854775807 else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        if len(value) > 19:
            return None
        n = int(value)
        return n if n <= 9223372036854775807 else None
    return None


def roles_of(rec):
    """The role SET a user record carries (1.2.3, demo commission):
    a legacy single-"role" entry yields exactly that one role; an
    entry with a "roles" list yields all of them. Every role check
    in this file goes through role_is(), so a single-role record
    behaves exactly as the old rec["role"] comparisons did. Only
    the demo seed writes a multi-role entry — the `imperator`
    presenter account — and Janus refuses to start when that
    account exists outside a demo-flagged users file (see
    _imperator_guard)."""
    if rec.get("roles"):
        return set(rec["roles"])
    return {rec.get("role")}


def role_is(rec, *roles):
    return bool(roles_of(rec) & set(roles))


def only_role(rec, role):
    """Identity check, distinct from role_is()'s permission check
    (1.2.3, demo commission): True when the account carries this
    role and NO other. The chain_auditor fences (S9) are identity
    fences — they confine a DEDICATED chain_auditor account to the
    chain. A multi-role account (the demo's imperator) is not a
    dedicated chain_auditor: the fence lifts and the per-endpoint
    permission checks govern it, like any other holder of those
    roles. For every single-role account only_role(rec, r) is
    exactly rec["role"] == r, so the fences are unchanged."""
    return roles_of(rec) == {role}


def auth(handler):
    """Return the user record or None. Named individual accounts only;
    a disabled account cannot authenticate. Comparison is
    constant-time. 1.2.4 (S11): an enrolled HUMAN account must also
    present a valid second factor (X-Noctua-TOTP) — a stolen key
    alone no longer authenticates it. A failed or missing factor
    returns None here, so the refusal is the ordinary 401 and feeds
    the AUTH_FAIL throttle exactly like a bad key."""
    _reload_config()
    user = handler.headers.get("X-Noctua-User", "")
    key = handler.headers.get("X-Noctua-Key", "")
    rec = USERS.get(user)
    if not rec or rec.get("disabled"):
        return None
    if not hmac_mod.compare_digest(sha(key),
                                   str(rec.get("key_sha256", ""))):
        return None
    if _totp_required(rec):
        code = handler.headers.get("X-Noctua-TOTP", "")
        # One HTTP request, one authentication decision: do_GET's
        # verify pre-warm authenticates BEFORE the lock and _get
        # authenticates again inside it (Q18/P13) — with a
        # one-time code, the second call would read the first
        # call's acceptance as a REPLAY and refuse a legitimate
        # request. The memo lives on the handler (one instance
        # per request), so cross-request replay protection is
        # untouched: a code presented by a NEW request is judged
        # fresh against the counter.
        memo = getattr(handler, "_totp_memo", None)
        if memo == (user, code):
            return rec
        if not _totp_accept(user, code):
            return None
        try:
            handler._totp_memo = (user, code)
        except Exception:
            pass
    return rec


def case_gate(case_no):
    """(ok, reason_code) — THE case check. Every endpoint that takes
    a case number runs this one function: catch-all ban, then
    membership in the open-case list."""
    if any(p in (case_no or "").upper() for p in BANNED_CASE_PATTERNS):
        return False, "case_banned"
    if case_no not in CASES:
        return False, "case_invalid"
    return True, ""


CASE_GATE_MSGS = {
    "case_banned": "BLOCKED: catch-all case numbers are banned",
    "case_invalid": "BLOCKED: case number failed validation",
}


def janus_gate(user_rec, case_no):
    """Role + case gate for /search. 1.2.2: an ALLOW-list — 1.2.1
    denied named roles, so a hand-edited users.json role nobody
    enumerated could search (round 5, Claude seat 1 code-read)."""
    if not role_is(user_rec, "detective", "patrol", "supervisor"):
        return False, "role"
    ok, why = case_gate(case_no)
    if not ok:
        return False, why
    return True, ""


def validate_fragment(frag):
    """(normalized, reason_code). Fragments shorter than 3 characters
    or carrying SQL wildcards turn a search into a browse; they are
    refused on every search path. 1.2.2 (Q27): the fragment is
    CANONICALIZED like a plate — spaces and hyphens stripped — so
    'HYP-123' finds the HYP123 a camera stored (round 5, Claude
    R5-15: fragments were the one identifier never canonicalized)."""
    raw = (frag or "").strip()
    if not raw:
        return None, "fragment_required"
    if "%" in raw or "_" in raw:
        return None, "fragment_wildcard"
    f = normalize_plate(raw)
    if len(f) < 3:
        return None, "fragment_too_short"
    return f, ""


FRAGMENT_MSGS = {
    "fragment_required": "a plate fragment is required",
    "fragment_wildcard": "wildcards (% and _) are not searchable",
    "fragment_too_short": "plate fragment must be at least 3 characters",
}


def active_suppression_refs():
    return {r[0] for r in db.execute(
        "SELECT plate_ref FROM suppressions WHERE active=1")}


def _active_orders():
    """(plate_ref, plate, state) for every ACTIVE order — the one
    row set every suppression decision reads (1.2.4, S3)."""
    return db.execute(
        "SELECT plate_ref, plate, state FROM suppressions "
        "WHERE active=1").fetchall()


def _order_covers(ref, order_plate, order_state, plate):
    """Does ONE active order cover this plate? The decision every
    leg shares (1.2.4, S3): the order's stored ref equals the
    plate's CURRENT ref — or, for a plate-less order (a legacy
    record whose plate text is gone), the stored ref matches the
    plate under ANY historical formula for the order's recorded
    state (sentinel.key_ref_candidates). A plate-less order is
    never silently inert: it covers what its ref verifiably names,
    and migration_status counts the ones nothing can explain."""
    if not plate:
        return False
    if ref == plate_ref(plate):
        return True
    if not order_plate and AUDIT_KEY is not None:
        return ref in sentinel.key_ref_candidates(
            AUDIT_KEY, plate, order_state or "")
    return False


def is_suppressed(plate):
    """S3: suppression identity is the canonical plate alone. The
    state recorded with a read (or left unknown) is not part of it —
    a protection order follows the vehicle."""
    if not plate:
        return False
    return any(_order_covers(ref, oplate, ostate, plate)
               for ref, oplate, ostate in _active_orders())


# 1.2.4 (S3): the SQL legs decide by plate_ref too, through the
# registered noctua_plate_ref() function — the same primitive the
# Python legs use. 1.2–1.2.3 matched s.plate = <col> in SQL, so an
# active order with no plate text was invisible to run_search and
# to Tier 3 result resolution while the Python legs honored it:
# one predicate in name, two in fact (round 7, register B3).
_SUPPRESSED_SQL = (
    " NOT EXISTS (SELECT 1 FROM suppressions s WHERE s.active=1 "
    "AND s.plate_ref = noctua_plate_ref({col}))")

# A hit is suppressed when EITHER plate it carries (the plate as
# read, the plate as listed) is under an active order — evaluated
# against the suppressions table as it stands NOW (P3).
_SUPPRESSED_HIT_SQL = (
    " NOT EXISTS (SELECT 1 FROM suppressions s WHERE s.active=1 "
    "AND (s.plate_ref = noctua_plate_ref(hits.read_plate) OR "
    "s.plate_ref = noctua_plate_ref(hits.entry_plate)))")


def hit_suppressed_now(read_plate, entry_plate=None):
    """P3: suppression as a property of the plate AT QUERY TIME.
    1.2 stamped hits.suppressed at ingest and every disclosure path
    read the stamp, so a protection order entered after a hit left
    the hit fully visible — verifiable and exportable by the very
    people the order exists to keep it from. The hits.suppressed
    column is now a CACHE (it still routes the ingest-time alert);
    every read path asks this question live, by canonical plate_ref
    against the active orders."""
    orders = _active_orders()
    for plate in (read_plate, entry_plate):
        if plate and any(_order_covers(ref, oplate, ostate, plate)
                         for ref, oplate, ostate in orders):
            return True
    return False


def _recover_order_for_plate(plate, state):
    """On-sight recovery (1.2.4, S3): a plate-less ACTIVE order
    whose stored ref matches this plate under any historical
    formula (for its own recorded state, or the state this read
    carries) is recovered NOW — plate and current plate_ref
    written together, the S2 rule — so from this read onward the
    order is an ordinary current-ref order on every leg, SQL
    included. Boot repair can only recover orders for plates the
    system already knows; this closes the other half (an order
    for a vehicle first seen after the upgrade). Chained as
    SUPPRESSION_RECOVERED. Returns True when a recovery landed."""
    if KEY_LOCKED or not plate:
        return False
    canon = normalize_plate(plate)
    if not canon:
        return False
    landed = False
    for sid, ref, ostate in db.execute(
            "SELECT id, plate_ref, state FROM suppressions WHERE "
            "active=1 AND (plate IS NULL OR plate='')").fetchall():
        states = {(ostate or ""), (state or "")}
        if any(ref in sentinel.key_ref_candidates(AUDIT_KEY, canon,
                                                  st)
               for st in states):
            db.execute(
                "UPDATE suppressions SET plate=?, state=?, "
                "plate_ref=? WHERE id=?",
                (canon, (ostate or state or "").upper() or None,
                 plate_ref(canon), sid))
            chain.append("SUPPRESSION_RECOVERED", {
                "order": sid, "plate_ref": plate_ref(canon),
                "how": "on_sight"})
            landed = True
    return landed


def run_search(frag, scope="full"):
    """Execute a read search. scope='tier2' applies the temporal wall
    IN SQL: only reads received within TIER2_WINDOW_H hours are
    visible. scope='full' is the Tier 3 scope.

    Suppressed plates are EXCLUDED for every viewer, in SQL, BEFORE
    the LIMIT (S3): no stub, no marker, and no count difference an
    observer can use — filtering after the limit would leak the
    suppressed row's existence through the page size. The match
    workflow (GET /suppressed-hits) is the only disclosure path."""
    frag = (frag or "").upper()
    window = ""
    params = ["%" + frag + "%"]
    if scope == "tier2":
        since = (datetime.now(timezone.utc)
                 - timedelta(hours=TIER2_WINDOW_H)).strftime(
                     "%Y-%m-%dT%H:%M:%SZ")
        window = " AND ts>=?"
        params.append(since)
    rows = db.execute(
        "SELECT id,ts,cam,plate,state FROM reads WHERE plate LIKE ?"
        + window + " AND" + _SUPPRESSED_SQL.format(col="reads.plate")
        + " ORDER BY ts DESC LIMIT 200", params).fetchall()
    hit_rows = db.execute(
        "SELECT id,ts,cam,read_plate,state,status FROM hits "
        "WHERE read_plate LIKE ?" + window
        + " AND" + _SUPPRESSED_HIT_SQL
        + " ORDER BY ts DESC LIMIT 50", params).fetchall()
    return {
        "reads": [dict(zip(("id", "ts", "cam", "plate", "state"), r))
                  for r in rows],
        "hits": [dict(zip(("id", "ts", "cam", "plate", "state",
                           "status"), r)) for r in hit_rows]}


def jobs_status():
    """Dead-man status for the monitored jobs. A job that reported
    ok:false is degraded NOW, not when it goes stale."""
    now = datetime.now(timezone.utc)
    rows = {r[0]: r for r in db.execute(
        "SELECT job, ts, ok, detail FROM heartbeats")}
    jobs, overdue = {}, []
    for job, max_age in JOB_MAX_AGE_S.items():
        r = rows.get(job)
        if not r:
            jobs[job] = {"last": None, "ok": False, "overdue": True,
                         "status": "never reported"}
            overdue.append(job)
            continue
        try:
            last = parse_ts(r[1])
            age = int((now - last).total_seconds())
        except (ValueError, TypeError):
            age = None
        od = age is None or age > max_age or not r[2]
        jobs[job] = {"last": r[1], "ok": bool(r[2]), "detail": r[3],
                     "age_s": age, "overdue": od,
                     "status": ("reported failure" if not r[2]
                                else "overdue" if od else "ok")}
        if od:
            overdue.append(job)
    for job, r in rows.items():
        if job not in jobs:
            jobs[job] = {"last": r[1], "ok": bool(r[2]), "detail": r[3],
                         "overdue": False}
    return jobs, overdue


def retention_oldest_read_age_h():
    row = db.execute("SELECT MIN(ts) FROM reads").fetchone()
    if not row or not row[0]:
        return None
    try:
        age = (datetime.now(timezone.utc) - parse_ts(row[0]))
        return round(age.total_seconds() / 3600.0, 2)
    except (ValueError, TypeError):
        return None


def cameras_status():
    """Per-camera health against the CONFIG REGISTRY (S5): every
    registered camera appears — never_reported if it has never sent
    a read, silent if its last read is older than CAMERA_SILENCE_S.
    (1.1 computed health from the reads table alone, so a camera
    that died before its first read was invisible.)"""
    now = datetime.now(timezone.utc)
    last_by_cam = dict(db.execute(
        "SELECT cam, MAX(ts) FROM reads GROUP BY cam").fetchall())
    out, silent = {}, []
    names = list(CAMERAS) + [c for c in last_by_cam if c not in CAMERAS]
    for cam in names:
        last = last_by_cam.get(cam)
        registered = cam in CAMERAS
        if last is None:
            out[cam] = {"last_read": None, "age_s": None,
                        "registered": registered,
                        "status": "never_reported"}
            silent.append(cam)
            continue
        try:
            age = int((now - parse_ts(last)).total_seconds())
        except (ValueError, TypeError):
            age = None
        status = "ok" if (age is not None and age <= CAMERA_SILENCE_S) \
            else "silent"
        out[cam] = {"last_read": last, "age_s": age,
                    "registered": registered, "status": status}
        if status != "ok":
            silent.append(cam)
    return out, silent


def overdue_holds():
    """Active holds whose review DATE has passed (P13: review_by is
    a date; an overdue hold is an operational alarm in /health, and
    it no longer protects anything in retention)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [dict(zip(("id", "scope", "ref", "placed_by", "review_by"), r))
            for r in db.execute(
                "SELECT id, scope, ref, placed_by, review_by FROM holds "
                "WHERE active=1 AND review_by IS NOT NULL "
                "AND date(review_by) < ?", (today,))]


def evidence_destroy_overdue():
    """S17: released bundles past their destroy_by date, still on
    disk — a registered store in breach, surfaced by name."""
    return db.execute(
        "SELECT COUNT(*) FROM evidence WHERE destroyed_ts IS NULL "
        "AND destroy_by IS NOT NULL AND destroy_by < ?",
        (now_iso(),)).fetchone()[0]


# ---------------- backfill aggregation ----------------
# A camera clock behind receipt by >5 min on a replayed backlog is
# not "skew" — it is store-and-forward doing its job. Backfills
# aggregate into at most one BACKFILL chain entry per camera per
# hour; buckets flush on hour rollover, at 1000 reads, or when idle
# longer than NOCTUA_BACKFILL_FLUSH_S (default 3600).
BACKFILL_FLUSH_S = int(os.environ.get("NOCTUA_BACKFILL_FLUSH_S", "3600"))
_backfill = {}


def _backfill_flush(key):
    b = _backfill.pop(key, None)
    if b:
        chain.append("BACKFILL", {"cam": key[0], "hour": key[1],
                                  "count": b["count"],
                                  "max_delay_s": b["max_delay_s"]})


def _backfill_note(cam, delay_s):
    hour = now_iso()[:13]
    for k in [k for k in _backfill if k[0] == cam and k[1] != hour]:
        _backfill_flush(k)
    b = _backfill.setdefault((cam, hour),
                             {"count": 0, "max_delay_s": 0,
                              "last": time.time()})
    b["count"] += 1
    b["max_delay_s"] = max(b["max_delay_s"], delay_s)
    b["last"] = time.time()
    if b["count"] >= 1000:
        _backfill_flush((cam, hour))


def _backfill_flush_idle():
    now = time.time()
    for k in [k for k, b in _backfill.items()
              if now - b["last"] > BACKFILL_FLUSH_S]:
        _backfill_flush(k)


# ---------------- report computation (S14) ----------------
def tier3_stats(frm, to):
    """K8: the Tier 3 emergency share. S14: the denominator is
    EXECUTED Tier 3 searches only — pending and denied requests are
    not searches, and counting them diluted the very signal K8
    exists to catch."""
    EXEC = "status IN ('EXECUTED','EMERGENCY','REVIEWED')"

    def _counts(a, b):
        total = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE created_ts>=? "
            "AND created_ts<=? AND " + EXEC, (a, b)).fetchone()[0]
        emerg = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE created_ts>=? "
            "AND created_ts<=? AND emergency=1 AND " + EXEC,
            (a, b)).fetchone()[0]
        return total, emerg
    total, emerg = _counts(frm, to)
    try:
        to_dt = parse_ts(to) if len(to) > 10 else datetime.now(timezone.utc)
        if to_dt.year > 9000:
            to_dt = datetime.now(timezone.utc)
    except (ValueError, TypeError):
        to_dt = datetime.now(timezone.utc)
    r_from = (to_dt - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r_total, r_emerg = _counts(r_from, to)
    r_share = (r_emerg / r_total) if r_total else 0.0
    return {
        "tier3_actions": total, "emergencies": emerg,
        "emergency_share": round(emerg / total, 4) if total else 0.0,
        "rolling_3mo": {
            "actions": r_total, "emergencies": r_emerg,
            "share": round(r_share, 4), "threshold": 0.25,
            "state": "tripped" if r_total and r_share > 0.25 else "ok"}}


def compute_report(frm, to):
    """SS 12-12-1805 aggregates. Match-side figures derive ONLY from
    outcomes and lists_checked — never from the hits table, which
    retention deletes. Outcomes are created at ALERT time with
    status=unresolved (S14) and updated at verification, so an
    unreviewed hit that ages out stays counted as unresolved
    forever instead of vanishing. Prosecutions are NULL until the
    prosecutor feedback loop reports them; per-list figures get the
    same 'not yet reported' treatment as the totals."""
    scanned = db.execute(
        "SELECT COALESCE(SUM(reads),0) FROM counters "
        "WHERE day>=? AND day<=?", (frm[:10], to[:10])).fetchone()[0]
    names = {r[0] for r in db.execute(
        "SELECT list_name FROM lists_checked WHERE day>=? AND day<=?",
        (frm[:10], to[:10]))}
    names |= {r[0] for r in db.execute(
        "SELECT DISTINCT list_name FROM outcomes WHERE hit_ts>=? "
        "AND hit_ts<=?", (frm, to))}
    lists = {}
    for name in sorted(names):
        # 1.2.2 (Q5): WITHDRAWN outcomes (a superseded OCR's pending
        # hit) are marked, never deleted, and excluded from every
        # figure — a withdrawn alert was not a match that failed to
        # correspond; it was a reading that was corrected.
        row = db.execute(
            "SELECT COALESCE(SUM(confirmed),0), "
            "COALESCE(SUM(CASE WHEN reviewed=1 AND confirmed=0 "
            "THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN reviewed=0 THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(arrest),0), "
            "COALESCE(SUM(CASE WHEN prosecution=1 THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN prosecution IS NOT NULL "
            "THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN arrest=1 AND prosecution=1 "
            "THEN 1 ELSE 0 END),0) "
            "FROM outcomes WHERE list_name=? AND hit_ts>=? AND hit_ts<=? "
            "AND status<>'withdrawn'",
            (name, frm, to)).fetchone()
        lists[name] = {
            "confirmed_matches": row[0], "non_corresponding": row[1],
            "unresolved": row[2], "arrests": row[3],
            "prosecutions": (row[4] if row[5] else "not yet reported"),
            "prosecutions_reported": row[5],
            "arrests_and_prosecutions": row[6]}
    tot = db.execute(
        "SELECT COALESCE(SUM(confirmed),0), "
        "COALESCE(SUM(CASE WHEN reviewed=1 AND confirmed=0 "
        "THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN reviewed=0 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(arrest),0), "
        "COALESCE(SUM(CASE WHEN prosecution=1 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN prosecution IS NOT NULL "
        "THEN 1 ELSE 0 END),0), COUNT(*) FROM outcomes "
        "WHERE hit_ts>=? AND hit_ts<=? AND status<>'withdrawn'",
        (frm, to)).fetchone()
    prosecutions = tot[4] if tot[5] else "not yet reported"
    return {
        "from": frm, "to": to, "plates_scanned": scanned,
        "plates_scanned_source": "counters (cumulative at ingest; "
                                 "survives retention deletes)",
        "lists": lists,
        "confirmed_matches": tot[0],
        "matches_not_corresponding": tot[1],
        "unresolved": tot[2],
        "arrests": tot[3],
        "prosecutions": prosecutions,
        "prosecutions_coverage": {"reported": tot[5], "total": tot[6]},
        "tier3": tier3_stats(frm, to),
        "overdue_holds": len(overdue_holds())}


# ---------------- custody excerpt (S17) ----------------
def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def custody_excerpt(hit_id):
    """The Sentinel entries that mention this hit, found with an
    INDEXED, paged scan over the entry kinds that can carry a hit
    id. S17: hit ids are compared as INTS on both sides — a string
    '7' in an old payload and an int 7 in the query are the same
    hit, and type drift must not silently empty a custody record."""
    kinds = ("ALERT", "VERIFY", "HOLD_PLACE", "HOLD_RELEASE",
             "OUTCOME_UPDATE",
             "EVIDENCE_EXPORT", "EVIDENCE_RELEASE", "EVIDENCE_DESTROY",
             "EVIDENCE_DISPOSITION", "EVIDENCE_DISPOSITION_CONFIRM")
    out, offset = [], 0
    while True:
        rows = db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "WHERE kind IN (%s) ORDER BY seq LIMIT 500 OFFSET ?"
            % ",".join("?" * len(kinds)), (*kinds, offset)).fetchall()
        for seq, ts, kind, payload, prev, h in rows:
            fields = {k: v for k, v in json.loads(payload).items()
                      if k not in ("ts", "kind")}
            if _as_int(fields.get("hit")) == hit_id:
                out.append({"seq": seq, "ts": ts, "kind": kind,
                            "fields": fields, "prev": prev, "hash": h})
        if len(rows) < 500:
            return out
        offset += 500


def _tier3_covers(case_no, hit_rec):
    """1.2.2 (Q10): the id of an EXECUTED Tier 3 request that covers
    this case and this hit's plate — by stored hit id, or by a
    fragment that matches the plate — else None. Evidence expansion
    is a Tier 3 disclosure and borrows its authority from the
    two-key workflow instead of inventing a one-key side door."""
    plates = {normalize_plate(hit_rec.get("read_plate") or ""),
              normalize_plate(hit_rec.get("entry_plate") or "")}
    for rid, frag, hit_ids in db.execute(
            "SELECT id, plate_fragment, results_hit_ids FROM "
            "tier3_requests WHERE case_no=? AND status IN "
            "('EXECUTED','EMERGENCY','REVIEWED')",
            (case_no,)).fetchall():
        try:
            ids = json.loads(hit_ids) if hit_ids else []
        except ValueError:
            ids = []
        if hit_rec.get("id") in ids:
            return rid
        if frag and not frag.startswith("pref:"):
            nf = normalize_plate(frag)
            if nf and any(nf in p for p in plates if p):
                return rid
    return None


# ---------------- chain verification cache (S5) ----------------
_chain_cache = {"ts": 0.0, "result": None}


_chain_verify_lock = threading.Lock()


def _verify_verdict():
    """The cached verification as /health may CLAIM it (1.2.4,
    S10): a cached ok is served marked stale only while its age
    is within VERIFY_MAX_STALE_S. Past the bound the verdict is
    ok:False, reason 'verify overdue' — round 7 (Claude seat p4)
    showed the 1.2.3 shape reporting chain_ok:true on a tampered
    chain INDEFINITELY under saturating ingest, because DBLOCK
    was always held when /health asked and the stale copy had no
    expiry. Freshness is now bounded and the bound is stated (in
    the SYSTEM entry and in this verdict's fields)."""
    result = _chain_cache["result"]
    if result is None:
        return None
    age = time.time() - _chain_cache["ts"]
    if result.get("ok") and age > VERIFY_MAX_STALE_S:
        out = dict(result)
        out["ok"] = False
        out["stale"] = True
        out["age_s"] = round(age, 1)
        out["reason"] = ("verify overdue: the last completed "
                         "verification is %.0fs old, past the %gs "
                         "freshness bound "
                         "(NOCTUA_VERIFY_MAX_STALE_S)"
                         % (age, VERIFY_MAX_STALE_S))
        out["last_verified_ok"] = True
        return out
    if age <= 60:
        return result
    out = dict(result)
    out["stale"] = True
    out["age_s"] = round(age, 1)
    return out


def chain_ok_cached():
    """verify() costs a full scan; /health caches it for <=60s and
    computes it on a DETACHED read-only connection — never while
    holding the write lock, never through the shared connection's
    possibly-open transaction. 1.2.2 (Q18): the computation is
    SINGLE-FLIGHT — round 5 pointed six concurrent callers at a
    250k-entry chain and got six simultaneous full scans (memory
    growing ~180 MB per caller) because the cache check-and-set was
    unlocked. A caller that finds a scan already running serves the
    last known result (marked stale) instead of starting another.
    1.2.3 (R4): the computation NEVER runs while DBLOCK is held —
    round 6 (seat 2 F3) showed the in-lock callers (the /health
    and /audit/verify handlers) still paying the full scan under
    the lock whenever the cache expired between the pre-warm and
    the in-lock read. Under the lock, a stale cache serves the
    last result marked stale (or a 'verify pending' placeholder
    before the first computation); only the lock-free pre-warm
    computes. 1.2.4 (S10): what the stale path may CLAIM is bounded
    — see _verify_verdict."""
    if DBLOCK.locked():
        verdict = _verify_verdict()
        if verdict is not None:
            return verdict
        return {"ok": False, "reason": "verify pending",
                "stale": True}
    now = time.time()
    if _chain_cache["result"] is not None \
            and now - _chain_cache["ts"] <= 60:
        return _chain_cache["result"]
    if not _chain_verify_lock.acquire(blocking=False):
        verdict = _verify_verdict()
        if verdict is not None:
            return verdict
        # First-ever verify and someone else is computing it: wait
        # for that one scan rather than starting a second.
        _chain_verify_lock.acquire()
        try:
            return _chain_cache["result"] or {
                "ok": False, "reason": "verify error"}
        finally:
            _chain_verify_lock.release()
    try:
        try:
            _chain_cache["result"] = sentinel.verify_detached(DB_PATH)
        except Exception:
            _chain_cache["result"] = {"ok": False,
                                      "reason": "verify error"}
        _chain_cache["ts"] = time.time()
        return _chain_cache["result"]
    finally:
        _chain_verify_lock.release()


def read_newest_checkpoint():
    """The newest checkpoint CONSISTENT WITH THE CURRENT CHAIN, or
    None. 1.2.2 (ChatGPT F7): 1.2.1 took max-by-entries over the
    whole file, so after an accepted restore to a shorter chain the
    OLD, longer checkpoint stayed 'newest' forever — partners could
    never receipt the checkpoint the chain actually has, and the
    share gate died when the stale one aged out. A checkpoint is
    usable only when the chain's hash at its entry count IS its
    root; anything else is the anchor disagreement the two-key
    acceptance flow exists for."""
    cps, err = _load_checkpoints()
    if err or not cps:
        return None
    valid = [c for c in cps if isinstance(c.get("entries"), int)]
    if not valid:
        return cps[-1]
    try:
        consistent = [
            c for c in valid
            if chain.hash_at_seq(c["entries"]) == c.get("root")]
    except Exception:
        consistent = []
    if not consistent:
        return None
    return max(consistent, key=lambda c: c["entries"])


def share_gate_missing(agency):
    """The Compact share gate, evaluated AT QUERY TIME (1.2.1, P7):
    returns None when the gate is open, else the coded reason it is
    closed. One helper, consumed by _share_query and by
    share_gate_open, so the gate the partner list DISPLAYS is the
    gate the share endpoint ENFORCES. 1.2's legs were checked
    piecemeal and each had a fail-open seam: a missing newest
    checkpoint passed (`if newest and ...`), a receipt's age was
    checked only when it was POSTed (a years-old receipt opened the
    gate forever), and verified=0 receipts counted. Now: the newest
    checkpoint must EXIST, the latest receipt must match it, carry
    verified=1, and its checkpoint_ts must be <=26h old — all read
    fresh on every call."""
    row = db.execute("SELECT status FROM partners WHERE agency=?",
                     (agency,)).fetchone()
    if not row or row[0] != "active":
        return "partner_inactive"
    # 1.2.2 (Q21): the gate reads the latest audit BY REPORT TIME —
    # 1.2.1 read by filing order (id), so re-filing an older signed
    # pass after a failure reopened the gate (Claude R5-06). Filing
    # now refuses stale/duplicate reports (see _compact_post), and
    # the gate's own read agrees with that ordering.
    a = db.execute("SELECT ok, ts FROM compact_audits WHERE agency=? "
                   "ORDER BY ts DESC, id DESC LIMIT 1",
                   (agency,)).fetchone()
    if not a or not a[0]:
        return "cross_audit_ok"
    try:
        audit_age_s = (datetime.now(timezone.utc)
                       - parse_ts(a[1])).total_seconds()
        if audit_age_s > 26 * 3600 or audit_age_s < -3600:
            return "cross_audit_ok"
    except (ValueError, TypeError):
        return "cross_audit_ok"
    newest = read_newest_checkpoint()
    if not newest:
        return "checkpoint_receipt"
    r = db.execute(
        "SELECT root, entries, checkpoint_ts, verified FROM "
        "compact_receipts WHERE agency=? ORDER BY id DESC LIMIT 1",
        (agency,)).fetchone()
    if not r:
        return "checkpoint_receipt"
    if r[0] != newest.get("root") or r[1] != newest.get("entries"):
        return "checkpoint_receipt"
    if not r[3]:
        return "checkpoint_receipt"
    try:
        age_s = (datetime.now(timezone.utc)
                 - parse_ts(r[2])).total_seconds()
        # 1.2.3 (R7/Gemini M1): freshness is a WINDOW, not a
        # one-sided bound — a future-dated checkpoint passed the
        # 26h check forever (its age is negative), so a receipt
        # naming it kept the gate open indefinitely.
        if age_s > 26 * 3600 or age_s < -3600:
            return "checkpoint_receipt"
    except (ValueError, TypeError):
        return "checkpoint_receipt"
    return None


def share_gate_open(agency):
    """S8/S10 + P7: the gate as share_gate_missing judges it now."""
    return share_gate_missing(agency) is None


def list_registry_names():
    return [r[0] for r in db.execute(
        "SELECT list_name FROM list_registry ORDER BY list_name")]


def hit_public(rec, show_suppressed=False):
    """A hit as the API returns it. S3: a suppressed hit's plate
    text reaches ONLY the supervisor queue — every other viewer
    gets the keyed ref, so the listing cannot confirm the very
    plate the suppression exists to hide. P3: 'suppressed' here is
    the LIVE evaluation (hit_suppressed_now), not the ingest-time
    cache column — the record is re-judged on every read."""
    rec = dict(rec)
    live = hit_suppressed_now(rec.get("read_plate"),
                              rec.get("entry_plate"))
    rec["suppressed"] = 1 if live else 0
    if live and not show_suppressed:
        rec["plate_ref"] = plate_ref(rec.get("read_plate") or "")
        rec["read_plate"] = None
        if rec.get("entry_plate") is not None:
            rec["entry_plate"] = None
    return rec


def stats_body():
    jobs, overdue = jobs_status()
    # P3: the pending split is computed LIVE — a hit whose plate was
    # suppressed after ingest counts as suppressed-pending NOW.
    pend = db.execute(
        "SELECT read_plate, entry_plate FROM hits WHERE "
        "status='PENDING'").fetchall()
    n_supp_pend = sum(1 for rp, ep in pend if hit_suppressed_now(rp, ep))
    return {
        "reads": db.execute("SELECT COUNT(*) FROM reads").fetchone()[0],
        "hits": db.execute("SELECT COUNT(*) FROM hits").fetchone()[0],
        "hits_pending": len(pend),
        "pending": len(pend) - n_supp_pend,
        "suppressed_pending": n_supp_pend,
        "chain_entries": chain.count(),
        "plates_scanned_total": db.execute(
            "SELECT COALESCE(SUM(reads),0) FROM counters").fetchone()[0],
        "jobs_overdue": overdue,
        "retention_days": RETENTION_DAYS,
        "registry_version": REGISTRY_VERSION}


def retention_breach():
    """S1/S5 + P10: the registered stores past their retention
    class, named store by store. 1.2.1: this is a thin wrapper over
    sentinel.registry_breaches — the ONE breach implementation,
    shared with sentinel_audit.py and mirroring retention.py's
    purge semantics exactly (round 4 found Janus, the audit tool,
    and the purge disagreeing about the same database: scrubbed
    fragments failed the audit, scope='case' holds were invisible
    to Janus, and NOCTUA_BACKUP_DIR was honored by neither check).
    Returns the breached store names ([] = clean)."""
    breaches = sentinel.registry_breaches(
        db, RETENTION_DAYS, HOLD_DAYS, db_path=DB_PATH,
        evidence_dir=EVIDENCE_DIR)
    return sorted(breaches)


def _designated_witness(members, auditor, audited, round_no):
    """(designated, self_attestation): the round's witness
    (1.2.4, S5). The witness is a member who is NEITHER the round's
    auditor nor its audited. With exactly one such member, it is
    that member. With two or more (n>=4), designation ROTATES
    deterministically among them by round number — 1.2.3 fell back
    to the auditor (self-attestation) for EVERY n>=4 round
    (round 7, ChatGPT R7-12), so the independent-witness guarantee
    silently never engaged in larger compacts. With none (n=2),
    the round's auditor attests its own audit: the fallback is
    honest about the absence of a third party, and status output
    LABELS it (self_attestation=True) instead of dressing it as
    an independent check."""
    others = [m for m in members if m not in (auditor, audited)]
    if len(others) == 1:
        return others[0], False
    if len(others) >= 2:
        return others[(round_no - 1) % len(others)], False
    return auditor, True


class Server(ThreadingHTTPServer):
    daemon_threads = True


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def setup(self):
        super().setup()
        # A stalled client must not freeze the service.
        self.connection.settimeout(30)

    # Responses are CAPTURED, not written, while the DB lock is held;
    # the wrapper serializes and writes after the lock is released,
    # so the lock covers database work only.
    def send_json(self, code, obj):
        self._resp = (code, obj)
        return None

    def _flush_response(self):
        code, obj = getattr(self, "_resp", None) or (
            500, {"error": "internal: handler produced no response"})
        body = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def body_json(self):
        return getattr(self, "_json", {})

    def _read_body(self):
        """Read + parse the request body BEFORE the lock, capped at
        1 MB. Returns False if the request has already been answered
        (413/400)."""
        self._json = {}
        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            n = 0
        if n < 0:
            # P13: a negative Content-Length is a malformed request,
            # not a zero-length body (BaseHTTPRequestHandler would
            # otherwise read(-1) — the whole stream).
            self._resp = (400, {"error": "negative Content-Length"})
            self._flush_response()
            return False
        if n > BODY_CAP:
            self._resp = (413, {"error": "request body exceeds the "
                                         "1 MB cap"})
            self._flush_response()
            return False
        raw = self.rfile.read(n) if n else b""
        if raw:
            try:
                self._json = json.loads(raw)
            except ValueError:
                self._resp = (400, {"error": "body must be JSON"})
                self._flush_response()
                return False
            if not isinstance(self._json, dict):
                self._resp = (400, {"error": "body must be a JSON object"})
                self._flush_response()
                return False
        return True

    def need_auth(self):
        rec = auth(self)
        if not rec:
            user = self.headers.get("X-Noctua-User", "")
            if user:
                _note_auth_fail(user)
            self.send_json(401, {"error": "authentication failed — "
                                          "named individual accounts only"})
        return rec

    def locked_out(self):
        if KEY_LOCKED:
            self.send_json(503, {"error": "audit key %s — Janus is "
                                          "locked (see /health)"
                                          % KEY_LOCK_REASON})
            return True
        return False

    def config_closed(self):
        """S13 + 1.2.3 (R12): the stale-config fence, cause-aware.
        A stale config FILE closes everything, as before. A stale
        case-list FEED closes the DISCLOSURE surface (this method
        guards reads, Tier 3, evidence, shares, report) — round 6
        seat 2 (F12) showed a 72h-old feed also refusing ingest and
        protection orders behind a message that blamed "config";
        safety writes use config_safety_closed() instead. Either
        way the 503 names the input that is actually stale."""
        st = config_status()
        if not st["fail_closed"]:
            return False
        reasons = st["closed_reasons"]
        if reasons["files"]:
            self.send_json(503, {"error": "configuration file(s) %s "
                                          "have been stale >24h — "
                                          "the data surface is "
                                          "closed until a clean "
                                          "reload"
                                          % ", ".join(reasons["files"])})
        else:
            self.send_json(503, {"error": "the case-list feed is "
                                          "stale (age %sh, limit "
                                          "%sh) — data reads are "
                                          "closed until a fresh "
                                          "export lands"
                                          % (reasons["feed_age_hours"],
                                             CASES_MAX_AGE_H)})
        return True

    def config_safety_closed(self, rec, path):
        """R12: safety writes — ingest (/reads) and protection-
        order placement/release — do not wait for the case FEED:
        a stale feed must never stop a camera read or a court
        order from landing (F12). They DO wait for a stale config
        FILE: users/cameras/cases files are the trust root. A
        feed-stale write proceeds with a throttled chained
        warning, so the exception is on the record, not silent."""
        st = config_status()
        if not st["fail_closed"]:
            return False
        if st["closed_reasons"]["files"]:
            return self.config_closed()
        _chain_throttled("CONFIG_FEED_STALE_WRITE", path, {
            "path": path, "user": rec["user"],
            "feed_age_hours": st["closed_reasons"]["feed_age_hours"]})
        return False

    def deny_service_role(self, rec, action):
        """Service and partner accounts move data; they never read
        it. chain_auditor (S9) is fenced to its five paths by the
        dispatcher; this answers role failures on data endpoints."""
        chain.append("BLOCKED", {"user": rec["user"], "action": action,
                                 "reason": "role"})
        msg = ("service accounts cannot read data"
               if role_is(rec, *SERVICE_ROLES)
               else "role cannot read this data")
        return self.send_json(403, {"error": msg})

    # ---------------- POST ----------------
    def do_POST(self):
        self._resp = None
        if not self._read_body():
            return
        with DBLOCK:
            try:
                _flush_config_chain()
                self._post()
                if db.in_transaction:
                    db.commit()
            except Exception as exc:  # a handler bug must still answer
                try:
                    db.rollback()
                except Exception:
                    pass
                self._resp = (500, {"error": f"internal: {exc}"})
            # P11 + 1.2.2 (Q16): sink copies stream only AFTER the
            # commit lands, and the flush runs INSIDE the lock —
            # 1.2.1 flushed after releasing it, while another
            # request could hold an open transaction on the shared
            # connection, and the presence check read that
            # transaction's uncommitted rows (a rolled-back
            # TIER3_EXECUTE reached the sink: round 5, Vesper F1).
            # sentinel's check now also runs on its own read-only
            # connection; the two fixes are independent.
            try:
                chain.flush_deferred()
            except Exception:
                pass
        self._flush_response()

    def _post(self):
        path = urlparse(self.path).path
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        if only_role(rec, "chain_auditor"):
            # S9: a dedicated chain_auditor has NO write surface
            # at all. (Identity fence — see only_role.)
            return self.send_json(403, {"error": "chain_auditor is "
                                                "read-only"})
        if path in ("/reads", "/suppressions",
                    "/suppressions/release"):
            # 1.2.3 (R12): safety writes — a stale case FEED does
            # not stop ingest or protection orders; a stale config
            # FILE still does.
            if self.config_safety_closed(rec, path):
                return
        elif path not in ("/heartbeat", "/audit/anchor-accept") \
                and self.config_closed():
            # 1.2.2 (Q9): the stale-config fail-closed rule is
            # enforced HERE, at dispatch, for every data endpoint —
            # 1.2.1 checked it inside some handlers and not others,
            # so POST /hotlist, /verify, /holds, /suppressions and
            # /report/compile all stayed open on a stale config
            # (round 5, Gemini N6 / Qwen F3). Heartbeats (how the
            # jobs report the failure) and anchor acceptance (the
            # recovery action) stay reachable.
            return
        if path == "/reads":
            return self._post_reads(rec)
        if path == "/heartbeat":
            if not role_is(rec, "jobs"):
                return self.send_json(403, {"error": "heartbeats are the "
                                                   "jobs role only"})
            d = self.body_json()
            job = str(d.get("job", "")).strip()
            if not job:
                return self.send_json(400, {"error": "job is required"})
            # ok must be EXPLICIT. A heartbeat that does not say
            # ok:true is recorded as a failure — silence about
            # success is not success.
            ok = d.get("ok") is True
            db.execute(
                "INSERT INTO heartbeats(job,ts,ok,detail) VALUES(?,?,?,?) "
                "ON CONFLICT(job) DO UPDATE SET ts=excluded.ts, "
                "ok=excluded.ok, detail=excluded.detail",
                (job, now_iso(), 1 if ok else 0,
                 str(d.get("detail", ""))[:500]))
            chain.append("HEARTBEAT", {"job": job, "ok": ok})
            db.commit()
            return self.send_json(200, {"result": "heartbeat recorded",
                                        "job": job, "ok": ok})
        if path == "/hotlist":
            return self._post_hotlist(rec)
        if path == "/lists":
            if not role_is(rec, "supervisor"):
                return self.send_json(403, {"error": "the list registry "
                                                   "is supervisor-managed"})
            d = self.body_json()
            name = (d.get("list_name") or "").strip()
            if not name or re.search(r"\b\d{4}-\d+\b", name):
                return self.send_json(400, {
                    "error": "list_name is required and must not carry "
                             "a case number — list names print in the "
                             "public report"})
            db.execute("INSERT OR IGNORE INTO list_registry(list_name,"
                       " created_by, ts) VALUES(?,?,?)",
                       (name, rec["user"], now_iso()))
            chain.append("LIST_REGISTER", {"list": name,
                                           "by": rec["user"]})
            db.commit()
            return self.send_json(201, {"result": "list registered",
                                        "list_name": name})
        if path == "/verify":
            return self._post_verify(rec)
        if path == "/outcomes":
            if not role_is(rec, "detective", "supervisor"):
                return self.send_json(403, {"error": "role cannot update "
                                                   "outcomes"})
            d = self.body_json()
            hit_id = _strict_id(d.get("hit_id"))
            if hit_id is None:
                return self.send_json(400, {
                    "error": "hit_id must be an integer"})
            row = db.execute("SELECT arrest, prosecution FROM outcomes "
                             "WHERE hit_id=?", (hit_id,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no outcome record "
                                                   "for that hit — verify "
                                                   "the hit first"})
            arrest = (1 if d["arrest"] else 0) if "arrest" in d else row[0]
            if "prosecution" in d:
                pros = None if d["prosecution"] is None \
                    else (1 if d["prosecution"] else 0)
            else:
                pros = row[1]
            db.execute("UPDATE outcomes SET arrest=?, prosecution=?, "
                       "updated_by=?, updated_ts=? WHERE hit_id=?",
                       (arrest, pros, rec["user"], now_iso(), hit_id))
            chain.append("OUTCOME_UPDATE", {
                "hit": hit_id, "arrest": arrest,
                "prosecution": ("unreported" if pros is None else pros),
                "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "outcome updated",
                                        "hit": hit_id,
                                        "arrest": arrest,
                                        "prosecution": pros})
        if path == "/holds":
            return self._post_holds(rec)
        if path == "/holds/release":
            return self._post_hold_release(rec)
        if path == "/suppressions":
            return self._post_suppression(rec)
        if path == "/suppressions/release":
            return self._post_suppression_release(rec)
        if path.startswith("/tier3/"):
            if self.config_closed():
                return
            return self._tier3_post(path, rec)
        if path.startswith("/evidence/"):
            if self.config_closed():
                return
            return self._evidence_post(path, rec)
        if path.startswith("/compact/") or path == "/share/query":
            return self._compact_post(path, rec)
        if path == "/report/compile":
            return self._report_compile(rec)
        if path == "/auth/2fa/reenroll":
            return self._totp_reenroll(rec)
        if path == "/auth/2fa/acknowledge":
            return self._totp_acknowledge(rec)
        if path == "/audit/anchor-accept":
            return self._anchor_accept(rec)
        return self.send_json(404, {"error": "no such route"})

    # ---------------- ingest (S3, S4, S14) ----------------
    def _hits_for_read(self, plate, state, ts, cam, read_id=None):
        """Hot-list matching for one stored read: lists_checked
        provenance (S14), membership matching on the canonical
        plate, hit + outcome births, ALERT chains. Shared by fresh
        ingest and by the supersede path (P13) so a corrected read
        is matched by exactly the rules a fresh read is."""
        # 1.2.4 (S3): on-sight recovery first — if a plate-less
        # legacy order names this plate, it becomes a current-ref
        # order BEFORE matching, so the hit it generates is born
        # suppressed and every leg agrees about it.
        _recover_order_for_plate(plate, state)
        # Provenance (S14): every read is checked against every
        # active list; record which lists those were, per day, so
        # the statutory report can name lists with zero matches.
        for (ln,) in db.execute(
                "SELECT DISTINCT list_source FROM hotlist_members "
                "WHERE active=1").fetchall():
            db.execute("INSERT OR IGNORE INTO lists_checked(day,"
                       "list_name) VALUES(?,?)", (ts[:10], ln))
        # Match: memberships on the canonical plate. State rule: an
        # entry matches when its state is unknown, the read's state
        # is unknown, or they agree — a state is a bridge's guess,
        # not a vehicle's identity (S3).
        memberships = db.execute(
            "SELECT plate, state, list_source, case_no, category, "
            "expires_ts FROM hotlist_members WHERE plate=? AND "
            "active=1 AND (state=? OR state='' OR ?='')",
            (plate, state, state)).fetchall()
        hit_ids = []
        for m_plate, m_state, m_list, m_case, m_cat, m_exp in memberships:
            if m_exp and m_exp <= ts:
                # An expired entry alerts no one. It auto-deactivates;
                # the expiry is chained in the same transaction.
                db.execute(
                    "UPDATE hotlist_members SET active=0 WHERE "
                    "plate=? AND state=? AND list_source=? AND "
                    "case_no=?", (m_plate, m_state, m_list, m_case))
                chain.append("HOTLIST_EXPIRED", {
                    "plate_ref": plate_ref(plate), "by": "ingest"})
                continue
            # A hit on a suppressed plate is flagged at ingest so it
            # routes to the supervisor-only queue and never surfaces
            # in /hits or search results. (The flag is a cache; P3
            # judges suppression live at every read.)
            supp = 1 if is_suppressed(plate) else 0
            cur = db.execute(
                "INSERT INTO hits(ts,cam,read_plate,entry_plate,state,"
                "list_name,category,suppressed,read_id) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (ts, cam, plate, m_plate, state, m_list, m_cat, supp,
                 read_id))
            hit_id = cur.lastrowid
            hit_ids.append(hit_id)
            # S14: the outcome record is born at ALERT time,
            # unresolved. Verification updates it; nothing deletes
            # it inside the 18-month window.
            db.execute(
                "INSERT INTO outcomes(hit_id, list_name, category, "
                "confirmed, arrest, prosecution, reviewed, status, "
                "hit_ts) VALUES(?,?,?,0,0,NULL,0,'unresolved',?)",
                (hit_id, m_list, m_cat, ts))
            chain.append("ALERT", {"hit": hit_id, "cam": cam,
                                   "category": category_enum(m_cat)})
        return hit_ids

    def _post_reads(self, rec):
        if not role_is(rec, "ingest"):
            return self.send_json(403, {"error": "ingest is the "
                                               "ingest role only"})
        d = self.body_json()
        raw_plate = d.get("plate")
        cam = d.get("cam")
        if not raw_plate or not cam:
            return self.send_json(400, {"error": "plate and cam are "
                                               "required"})
        plate = normalize_plate(raw_plate)
        if cam not in CAMERAS:
            # S4: an unregistered camera is not a data source. "No
            # new cameras without a vote" is a config fact now, not
            # a hope — the registry is the vote's record. 1.2.2
            # (Q19): the chain entry carries a HASH of the caller's
            # camera string and a coded reason, throttled — 1.2.1
            # chained the raw caller-supplied string unthrottled,
            # an unbounded injection channel into the permanent
            # record (round 5, Claude R5-12).
            _chain_throttled("INGEST_REJECTED", rec["user"], {
                "cam_ref": sha(str(cam))[:16],
                "plate_ref": plate_ref(plate),
                "user": rec["user"],
                "reason": "unregistered_camera"})
            return self.send_json(403, {
                "error": "camera %s is not in the camera registry — "
                         "its reads are not accepted" % cam})
        # S4: honesty about what the camera did NOT say. Missing
        # state is "" (unknown), missing confidence is NULL. 1.0/1.1
        # fabricated "AR" and 0.95 — a confidence the camera never
        # produced ended up in evidence files.
        state = (d.get("state") or "").upper()
        conf = d.get("conf")
        if conf is not None:
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = None
        event_id = d.get("event_id") or None
        ts = now_iso()
        cam_ts = d.get("ts")
        skew_s = None
        if cam_ts:
            try:
                ct = parse_ts(cam_ts)
                st = parse_ts(ts)
                skew_s = int((st - ct).total_seconds())
            except (ValueError, TypeError):
                cam_ts = None  # unparseable camera time: ignore
        # 1.2.2 (Q5): reads are append-only VERSIONS of an event,
        # and ONE decision function judges currency. 1.2.1 rewrote
        # the stored read in place whenever a redelivery carried a
        # different plate — any confidence, any order — and DELETED
        # the pending hit the earlier OCR produced: Frigate's normal
        # update stream could end on its WORST guess with the
        # stolen-plate alert gone, and the read behind a VERIFIED
        # hit could be overwritten out from under the evidence
        # (round 5, Claude R5-03/R5-16, Qwen F6). Now:
        #   * every delivery is its own row, linked by `supersedes`
        #     when it takes currency from the version before it;
        #   * currency = max by (event phase: end > update, then
        #     confidence, then arrival) — a pure function of the
        #     version set, so no delivery order can end with less
        #     alerting than the event's best read earns;
        #   * when currency changes PLATE, the old version's
        #     PENDING hits are WITHDRAWN (status, never deleted —
        #     a hit id the API returned never 404s) and the new
        #     version is matched fresh; DECIDED hits are history;
        #   * a same-plate improvement takes currency silently —
        #     the standing hits stand, ids stable;
        #   * a delivery that does not take currency is recorded
        #     and answered 'duplicate' with the current read id.
        phase = (d.get("event_type") or d.get("type") or "").lower()
        phase_rank = 2 if phase == "end" else 1
        if event_id:
            versions = db.execute(
                "SELECT id, plate, conf, phase FROM reads WHERE "
                "cam=? AND event_id=? ORDER BY id",
                (cam, event_id)).fetchall()
            if versions:
                def _rank(v):
                    return (2 if (v[3] or "") == "end" else 1,
                            v[2] if v[2] is not None else -1.0, v[0])
                cur_v = max(versions, key=_rank)
                cur_id, cur_plate = cur_v[0], cur_v[1]
                new_key = (phase_rank,
                           conf if conf is not None else -1.0)
                # Currency changes on a strictly better (phase,
                # confidence), or on a different plate at an equal
                # rank (arrival breaks the tie — the newest belief
                # wins). An exact replay — same plate, phase and
                # confidence — is a duplicate.
                if new_key < _rank(cur_v)[:2] or (
                        new_key == _rank(cur_v)[:2]
                        and plate == cur_plate):
                    cur = db.execute(
                        "INSERT INTO reads(ts,cam,plate,plate_raw,"
                        "state,conf,cam_ts,skew_s,event_id,phase) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (ts, cam, plate, str(raw_plate), state, conf,
                         cam_ts, skew_s, event_id, phase or None))
                    db.commit()
                    return self.send_json(200, {
                        "result": "duplicate", "read_id": cur_id,
                        "version_read_id": cur.lastrowid})
                # The new delivery takes currency.
                cur = db.execute(
                    "INSERT INTO reads(ts,cam,plate,plate_raw,state,"
                    "conf,cam_ts,skew_s,event_id,supersedes,phase) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (ts, cam, plate, str(raw_plate), state, conf,
                     cam_ts, skew_s, event_id, cur_id, phase or None))
                read_id = cur.lastrowid
                if plate == cur_plate:
                    standing = [r[0] for r in db.execute(
                        "SELECT id FROM hits WHERE read_id=? AND "
                        "status IN ('PENDING','VERIFIED','REJECTED')",
                        (cur_id,)).fetchall()]
                    # 1.2.3 (R9): the event's PENDING hits follow
                    # currency to the new version. 1.2.2 left them
                    # pointing at the old read, so when a LATER
                    # delivery changed the plate, the withdrawal
                    # looked up hits by the then-current read and
                    # never found them — the original PENDING hit
                    # stayed live against a plate the event no
                    # longer believed (round 6, Gemini F8).
                    # DECIDED hits keep their read: their history
                    # is the read they were decided on, and the
                    # read behind a VERIFIED hit is immutable (Q5).
                    db.execute(
                        "UPDATE hits SET read_id=? WHERE read_id=? "
                        "AND status='PENDING'", (read_id, cur_id))
                    db.commit()
                    resp = {"result": "superseded",
                            "read_id": read_id}
                    if standing:
                        resp["hit_id"] = standing[0]
                        resp["hit_ids"] = standing
                    return self.send_json(200, resp)
                stale = [r[0] for r in db.execute(
                    "SELECT id FROM hits WHERE read_id=? AND "
                    "status='PENDING'", (cur_id,)).fetchall()]
                for hid in stale:
                    db.execute(
                        "UPDATE hits SET status='WITHDRAWN', "
                        "decided_by='system:supersede', decided_ts=? "
                        "WHERE id=?", (ts, hid))
                    db.execute(
                        "UPDATE outcomes SET status='withdrawn', "
                        "reviewed=1, updated_by='system:supersede', "
                        "updated_ts=? WHERE hit_id=?", (ts, hid))
                chain.append("READ_SUPERSEDED", {
                    "read": read_id, "supersedes": cur_id, "cam": cam,
                    "plate_ref": plate_ref(plate),
                    "withdrawn_hits": len(stale)})
                hit_ids = self._hits_for_read(plate, state, ts, cam,
                                              read_id)
                db.execute(
                    "INSERT INTO counters(day,camera_id,reads,alerts) "
                    "VALUES(?,?,0,?) ON CONFLICT(day,camera_id) DO "
                    "UPDATE SET alerts=alerts+excluded.alerts",
                    (ts[:10], cam, len(hit_ids)))
                db.commit()
                resp = {"result": "superseded", "read_id": read_id,
                        "withdrawn_hits": len(stale)}
                if hit_ids:
                    resp = {"result": "ALERT", "hit_id": hit_ids[0],
                            "hit_ids": hit_ids, "read_id": read_id,
                            "superseded": True,
                            "withdrawn_hits": len(stale)}
                return self.send_json(200, resp)
        cur = db.execute(
            "INSERT INTO reads(ts,cam,plate,plate_raw,state,conf,"
            "cam_ts,skew_s,event_id,phase) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (ts, cam, plate, str(raw_plate), state, conf, cam_ts,
             skew_s, event_id, phase or None))
        read_id = cur.lastrowid
        hit_ids = self._hits_for_read(plate, state, ts, cam, read_id)
        # Cumulative counters: the six-month report's plates_scanned
        # must survive the retention deletes, so it is counted here,
        # at ingest, in a table retention never touches (for reads).
        db.execute(
            "INSERT INTO counters(day,camera_id,reads,alerts) "
            "VALUES(?,?,1,?) ON CONFLICT(day,camera_id) DO UPDATE "
            "SET reads=reads+1, alerts=alerts+excluded.alerts",
            (ts[:10], cam, len(hit_ids)))
        db.commit()
        if skew_s is not None:
            if skew_s < -5:
                # Camera clock AHEAD of receipt: real skew.
                chain.append("CLOCK_SKEW", {"cam": cam,
                                            "skew_s": skew_s})
            elif skew_s > 300:
                # Far behind receipt: a replayed backlog, not skew.
                _backfill_note(cam, skew_s)
        _backfill_flush_idle()
        resp = {"result": "stored", "read_id": read_id}
        if skew_s is not None:
            resp["clock_skew_s"] = skew_s
        if hit_ids:
            resp = {"result": "ALERT", "hit_id": hit_ids[0],
                    "hit_ids": hit_ids, "read_id": read_id}
            if skew_s is not None:
                resp["clock_skew_s"] = skew_s
        return self.send_json(201, resp)

    # ---------------- hot list (S14 membership) ----------------
    def _post_hotlist(self, rec):
        if not role_is(rec, "detective", "supervisor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hotlist add",
                                     "reason": "role"})
            return self.send_json(403, {"error": "role cannot add "
                                               "hot-list entries"})
        d = self.body_json()
        ok, reason = case_gate(d.get("case"))
        if not ok:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hotlist add",
                                     "reason": reason})
            return self.send_json(403, {"error": CASE_GATE_MSGS[reason]})
        plate = normalize_plate(d.get("plate"))
        state = (d.get("state") or "").upper()
        if not plate:
            return self.send_json(400, {"error": "plate is required"})
        if is_suppressed(plate):
            # Listing a protected plate would route its reads into a
            # workflow the order forbids. Refused, and the conflict
            # itself is chained. 1.2.2: the REASON is supervisor-only
            # information — 1.2.1's message told any detective that
            # the plate they just typed is under a protection order,
            # an existence oracle for the very fact the order seals
            # (round 5, Claude seat 2 code-read).
            chain.append("SUPPRESSION_CONFLICT", {
                "plate_ref": plate_ref(plate), "by": rec["user"],
                "action": "hotlist add"})
            if role_is(rec, "supervisor"):
                return self.send_json(403, {
                    "error": "that plate is under a protection-order "
                             "suppression — it cannot be hot-listed"})
            return self.send_json(403, {
                "error": "that plate is not eligible for listing"})
        list_name = (d.get("list_name") or "Local agency list").strip()
        if not db.execute("SELECT 1 FROM list_registry WHERE "
                          "list_name=?", (list_name,)).fetchone():
            # S14: report list names come from a controlled
            # vocabulary — a supervisor registers the list first.
            # (1.1 sanitized free text; a sanitizer is a hope, a
            # registry is a fact.)
            return self.send_json(400, {
                "error": "list_name %r is not in the list registry — "
                         "a supervisor must register it first "
                         "(POST /lists)" % list_name})
        if not d.get("category"):
            return self.send_json(400, {"error": "category is "
                                               "required"})
        # 1.2.2 (Q4): expiry is a parsed INSTANT or a 400 — never
        # free text stored for a string comparison (see
        # sentinel.parse_expiry for the stolen-listing failure).
        expires = None
        if d.get("expires"):
            expires = sentinel.parse_expiry(d.get("expires"))
            if expires is None:
                return self.send_json(400, {
                    "error": "expires must be an ISO-8601 date or "
                             "datetime (e.g. 2027-06-30 or "
                             "2027-06-30T17:00:00Z)"})
        db.execute(
            "INSERT INTO hotlist_members(plate,state,list_source,"
            "case_no,category,added_by,added_ts,expires_ts,active) "
            "VALUES(?,?,?,?,?,?,?,?,1) ON CONFLICT(plate,state,"
            "list_source,case_no) DO UPDATE SET "
            "category=excluded.category, added_by=excluded.added_by, "
            "added_ts=excluded.added_ts, "
            "expires_ts=excluded.expires_ts, active=1",
            (plate, state, list_name, d.get("case"), d.get("category"),
             rec["user"], now_iso(), expires))
        chain.append("HOTLIST_ADD", {
            "plate_ref": plate_ref(plate),
            "category": category_enum(d.get("category")),
            "by": rec["user"], "case_hash": case_hash(d.get("case"))})
        db.commit()
        return self.send_json(201, {"result": "added"})

    # ---------------- verify (S3, S14) ----------------
    def _post_verify(self, rec):
        if not role_is(rec, "detective", "patrol", "supervisor"):
            return self.send_json(403, {"error": "role cannot verify "
                                               "hits"})
        d = self.body_json()
        decision = str(d.get("decision", "")).lower()
        if decision not in ("confirm", "reject"):
            return self.send_json(400, {
                "error": "decision must be 'confirm' or 'reject'"})
        hit_id = _strict_id(d.get("hit_id"))
        if hit_id is None:
            return self.send_json(400, {
                "error": "hit_id must be an integer"})
        ok, reason = case_gate(d.get("case"))
        if not ok:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hit verification",
                                     "hit": hit_id,
                                     "reason": reason})
            return self.send_json(403, {"error": CASE_GATE_MSGS[reason]})
        hit = db.execute("SELECT entry_plate, category, ts, list_name, "
                         "suppressed, read_plate FROM hits WHERE id=? "
                         "AND status='PENDING'",
                         (hit_id,)).fetchone()
        if not hit:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hit verification",
                                     "hit": hit_id,
                                     "reason": "hit_not_pending"})
            return self.send_json(409, {"error": "hit not found or "
                                               "already decided"})
        if hit_suppressed_now(hit[5], hit[0]) \
                and not role_is(rec, "supervisor"):
            # S3: a suppressed hit moves ONLY through the supervisor
            # queue — a detective cannot verify it directly, however
            # they learned its id.
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hit verification",
                                     "hit": hit_id,
                                     "reason": "suppressed_queue"})
            return self.send_json(403, {
                "error": "that hit is under a protection-order "
                         "suppression — it moves through the "
                         "supervisor queue only"})
        status = "VERIFIED" if decision == "confirm" else "REJECTED"
        db.execute("UPDATE hits SET status=?, decided_by=?, case_no=?, "
                   "decided_ts=? WHERE id=? AND status='PENDING'",
                   (status, rec["user"], d["case"], now_iso(),
                    hit_id))
        # The outcome record was created at ALERT time (S14);
        # verification resolves it. prosecution stays NULL — unknown
        # until the prosecutor feedback loop reports it.
        db.execute(
            "UPDATE outcomes SET confirmed=?, reviewed=1, "
            "status='reviewed', updated_by=?, updated_ts=? "
            "WHERE hit_id=?",
            (1 if decision == "confirm" else 0, rec["user"], now_iso(),
             hit_id))
        chain.append("VERIFY", {"hit": hit_id, "result": status,
                                "by": rec["user"],
                                "case_hash": case_hash(d["case"])})
        db.commit()
        return self.send_json(200, {"result": status})

    # ---------------- holds (S17, Q12) ----------------
    def _post_holds(self, rec):
        # 1.2.2 (Q12): spec SS4/SS9 put holds in the Administrator's
        # hands, standing on a documented case. 1.2.1 let any
        # detective place one with no case at all — round 5 held a
        # REJECTED misread hit that way and kept its plate past 150
        # days (Claude R5-09). Placement is supervisor-only and
        # every hold names the validated case it stands on.
        if not role_is(rec, "supervisor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hold place",
                                     "reason": "role"})
            return self.send_json(403, {"error": "holds are placed "
                                               "by a supervisor"})
        d = self.body_json()
        if d.get("scope") not in ("case", "hit"):
            return self.send_json(400, {"error": "scope must be "
                                               "'case' or 'hit'"})
        hold_case = d.get("case") if d["scope"] == "hit" \
            else d.get("ref")
        ok, reason = case_gate(hold_case)
        if not ok:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hold place",
                                     "reason": reason})
            return self.send_json(403,
                                  {"error": CASE_GATE_MSGS[reason]})
        ref = d.get("ref")
        if d["scope"] == "hit":
            hid = _strict_id(ref)
            if hid is None:
                return self.send_json(400, {
                    "error": "a hit hold's ref must be the hit's "
                             "integer id"})
            hit = db.execute("SELECT case_no FROM hits WHERE id=?",
                             (hid,)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no hit with "
                                                   "that id"})
            if hit[0] and hit[0] != hold_case:
                return self.send_json(400, {
                    "error": "the hold must stand on the hit's own "
                             "case (%s)" % hit[0]})
            ref = str(hid)
        # P13: review_by is a real DATE in (today, today+HOLD_DAYS].
        # 1.2 stored whatever string arrived — "9999-12-31" made a
        # hold immortal and kept its hit past the 150-day statutory
        # cap while /health stayed green. A hold is a review
        # appointment, not a retention override.
        today = datetime.now(timezone.utc).date()
        raw_rb = d.get("review_by")
        if raw_rb:
            try:
                rb_date = date.fromisoformat(str(raw_rb)[:10])
                if len(str(raw_rb)[:10]) != 10:
                    raise ValueError("not a date")
            except ValueError:
                return self.send_json(400, {
                    "error": "review_by must be a real ISO date "
                             "(YYYY-MM-DD)"})
            if rb_date <= today or rb_date > today + timedelta(
                    days=HOLD_DAYS):
                return self.send_json(400, {
                    "error": "review_by must be after today and no "
                             "later than today + HOLD_DAYS (%d days)"
                             % HOLD_DAYS})
            review_by = rb_date.isoformat()
        else:
            review_by = (today + timedelta(
                days=min(90, HOLD_DAYS))).isoformat()
        cur = db.execute(
            "INSERT INTO holds(scope, ref, reason, placed_by, "
            "placed_ts, active, review_by, case_no) "
            "VALUES(?,?,?,?,?,1,?,?)",
            (d["scope"], str(ref), d.get("reason", ""),
             rec["user"], now_iso(), review_by, hold_case))
        fields = {"hold": cur.lastrowid, "scope": d["scope"],
                  "by": rec["user"], "review_by": review_by,
                  "case_hash": case_hash(hold_case)}
        if d["scope"] == "hit":
            # S17: HOLD entries carry hit_id, so custody excerpts
            # find them by the hit they protect.
            fields["hit"] = hid
        chain.append("HOLD_PLACE", fields)
        db.commit()
        return self.send_json(201, {"result": "hold placed",
                                    "hold_id": cur.lastrowid,
                                    "review_by": review_by})

    def _post_hold_release(self, rec):
        if not role_is(rec, "supervisor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hold release",
                                     "reason": "role"})
            return self.send_json(403, {"error": "hold release is "
                                               "supervisor-only"})
        d = self.body_json()
        hold_id = _strict_id(d.get("hold_id"))
        if hold_id is None:
            return self.send_json(400, {
                "error": "hold_id must be an integer"})
        row = db.execute("SELECT active, scope, ref FROM holds "
                         "WHERE id=?", (hold_id,)).fetchone()
        if not row or not row[0]:
            return self.send_json(404, {"error": "no active hold "
                                               "with that id"})
        # 1.2.2 (Q12): release takes DOCUMENTED AUTHORITY —
        # prosecutor sign-off or case closure, named in the chain.
        # 1.2.1 released on one supervisor's bare say-so while
        # placement of the companion suppression demands an order
        # reference (round 5, Claude R5-09).
        authority = d.get("authority")
        if authority not in ("prosecutor_signoff", "case_closed"):
            return self.send_json(400, {
                "error": "authority is required: 'prosecutor_signoff' "
                         "or 'case_closed'"})
        if not (d.get("authority_ref") or "").strip():
            return self.send_json(400, {
                "error": "authority_ref is required (the sign-off or "
                         "closure reference)"})
        fields = {"hold": hold_id, "by": rec["user"],
                  "authority": authority,
                  "authority_ref_hash": why_hash(d["authority_ref"])}
        if row[1] == "case":
            # The gate runs at release too — its result is chained,
            # but a release is never BLOCKED by it: a case closing
            # must not trap held data past its review date.
            ok, _r = case_gate(row[2])
            fields["case_gate_ok"] = ok
            fields["case_hash"] = case_hash(row[2])
        elif row[1] == "hit":
            hid = _strict_id(row[2])
            if hid is not None:
                fields["hit"] = hid
        db.execute("UPDATE holds SET active=0, released_by=?, "
                   "released_ts=? WHERE id=?",
                   (rec["user"], now_iso(), hold_id))
        chain.append("HOLD_RELEASE", fields)
        db.commit()
        return self.send_json(200, {"result": "hold released"})

    # ---------------- suppressions (S3) ----------------
    def _post_suppression(self, rec):
        if not role_is(rec, "supervisor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "suppression place",
                                     "reason": "role"})
            return self.send_json(403, {"error": "suppressions are "
                                               "supervisor-only"})
        d = self.body_json()
        # A suppression is placed against the protection ORDER (its
        # court reference), not against a case number. A case may be
        # supplied for the file; when it is, it runs the shared gate.
        order_ref = (d.get("order_ref") or "").strip()
        if not order_ref:
            return self.send_json(400, {
                "error": "order_ref (the protection order's number / "
                         "court) is required"})
        if d.get("case"):
            ok, reason = case_gate(d["case"])
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression place",
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
        plate = normalize_plate(d.get("plate"))
        # The state is RECORDED (the order may name one) but is not
        # part of the suppression's identity (S3).
        state = (d.get("state") or "").upper()
        if not plate:
            return self.send_json(400, {"error": "plate is required"})
        ref = plate_ref(plate)
        # 1.2.3 (R1): an order is a RECORD. The conflict target is
        # (plate_ref, order_ref): placing a second order for the
        # same vehicle inserts its own row and leaves the first
        # untouched — 1.2.2's ON CONFLICT(plate_ref) overwrote the
        # first order's record wholesale, so releasing the second
        # order later stripped protection the first still owed
        # (round 6, both Claude seats' forced change).
        db.execute(
            "INSERT INTO suppressions(plate_ref, plate, state, "
            "order_ref, placed_by, case_no, ts, active) "
            "VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(plate_ref, "
            "order_ref) DO UPDATE SET active=1, "
            "plate=excluded.plate, state=excluded.state, "
            "placed_by=excluded.placed_by, "
            "case_no=excluded.case_no, ts=excluded.ts, "
            "release_requested_by=NULL, release_order_ref=NULL, "
            "released_ts=NULL",
            (ref, plate, state, order_ref, rec["user"],
             d.get("case"), now_iso()))
        chain.append("SUPPRESSION_PLACE", {"plate_ref": ref,
                                           "order_ref": order_ref,
                                           "by": rec["user"]})
        db.commit()
        # Near-match warning: raw plate forms already in the data
        # that canonicalize to this plate (a camera read it with a
        # space, an operator typed a hyphen) — the operator should
        # know the raw forms on file. (Identity is canonical either
        # way; the warning is about the RECORD, not the matching.)
        variants = set()
        for (raw,) in db.execute(
                "SELECT DISTINCT plate_raw FROM reads").fetchall():
            if raw and raw != plate and normalize_plate(raw) == plate:
                variants.add(raw)
        return self.send_json(201, {
            "result": "suppression placed",
            "warning_near_matches": sorted(variants)})

    def _post_suppression_release(self, rec):
        if not role_is(rec, "supervisor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "suppression release",
                                     "reason": "role"})
            return self.send_json(403, {"error": "suppression release "
                                               "is supervisor-only"})
        d = self.body_json()
        plate = normalize_plate(d.get("plate"))
        ref = plate_ref(plate)
        # 1.2.3 (R1): a release names ONE order. The order_ref, when
        # supplied, selects it; with several live orders and no
        # order_ref the request is ambiguous and refused — a
        # release must never lift protection another order still
        # requires. With exactly one live order, {plate} alone
        # still works, as it always has.
        want = (d.get("order_ref") or "").strip()
        rows = db.execute(
            "SELECT id, order_ref, release_requested_by FROM "
            "suppressions WHERE plate_ref=? AND active=1 ORDER BY "
            "id", (ref,)).fetchall()
        if not rows:
            return self.send_json(404, {"error": "no active suppression "
                                               "for that plate"})
        if want:
            rows = [r for r in rows if r[1] == want]
            if not rows:
                return self.send_json(400, {
                    "error": "order_ref does not match any active "
                             "order for that plate"})
        if len(rows) > 1:
            return self.send_json(400, {
                "error": "that plate has %d active protection "
                         "orders — name the order_ref to release "
                         "one" % len(rows)})
        sid, order_ref, requested_by = rows[0]
        # Two-key release: the first supervisor requests, a DIFFERENT
        # supervisor confirms — and the order reference on file must
        # be repeated, so a release cannot ride on a misremembered
        # order.
        if requested_by is None:
            db.execute("UPDATE suppressions SET "
                       "release_requested_by=?, release_order_ref=? "
                       "WHERE id=?",
                       (rec["user"], d.get("order_ref"), sid))
            chain.append("SUPPRESSION_RELEASE_REQUEST", {
                "plate_ref": ref, "order_ref": order_ref,
                "by": rec["user"]})
            db.commit()
            return self.send_json(200, {
                "result": "release requested — a second supervisor "
                          "must confirm with the order reference"})
        if requested_by == rec["user"]:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "suppression release",
                                     "reason": "two_key"})
            return self.send_json(403, {
                "error": "BLOCKED: the two-key rule forbids "
                         "confirming your own suppression release"})
        if (d.get("order_ref") or "") != order_ref:
            return self.send_json(400, {
                "error": "order_ref does not match the order on file"})
        db.execute("UPDATE suppressions SET active=0, "
                   "release_requested_by=NULL, release_order_ref=NULL, "
                   "released_ts=? WHERE id=?",
                   (now_iso(), sid))
        chain.append("SUPPRESSION_RELEASE", {
            "plate_ref": ref, "order_ref": order_ref,
            "by": rec["user"], "requested_by": requested_by})
        db.commit()
        return self.send_json(200, {"result": "suppression released"})


    def _totp_reenroll(self, rec):
        """Two-key re-enrollment (1.2.4, S11): a supervisor records
        the request; the AUDITOR — a different person — confirms,
        and only then is a fresh secret issued (shown once, in the
        confirm response, to be handed to the individual in
        person, exactly like provision.py's raw keys). The new
        enrollment is PENDING until its first valid code. Every
        step chains."""
        d = self.body_json()
        target = (d.get("user") or "").strip()
        trec = USERS.get(target)
        if not trec or not (roles_of(trec) & TOTP_HUMAN_ROLES):
            return self.send_json(400, {
                "error": "no enrolled-eligible human account by "
                         "that name (machine identities stay "
                         "key-only)"})
        pending = None
        raw = _meta_get("totp_reenroll_by")
        if raw:
            try:
                pending = json.loads(raw)
            except ValueError:
                pending = None
        if pending and pending.get("target") != target:
            pending = None
        if role_is(rec, "supervisor") and not pending:
            db.execute(
                "INSERT INTO meta(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value",
                ("totp_reenroll_by", json.dumps({
                    "by": rec["user"], "target": target,
                    "ts": now_iso()})))
            chain.append("TOTP_REENROLL_REQUEST", {
                "user": target, "by": rec["user"]})
            db.commit()
            return self.send_json(200, {
                "result": "re-enrollment recorded — the auditor "
                          "must confirm to issue a new secret"})
        if role_is(rec, "auditor") and pending:
            if rec["user"] == pending.get("by"):
                return self.send_json(403, {
                    "error": "the two-key rule forbids confirming "
                             "your own re-enrollment request"})
            try:
                fresh = (datetime.now(timezone.utc)
                         - parse_ts(pending.get("ts") or "")
                         ).total_seconds() <= 24 * 3600
            except (ValueError, TypeError):
                fresh = False
            if not fresh:
                db.execute("DELETE FROM meta WHERE "
                           "key='totp_reenroll_by'")
                db.commit()
                return self.send_json(409, {
                    "error": "the pending re-enrollment is stale "
                             "(>24h) and has been cleared"})
            secret = base64.b32encode(
                secrets.token_bytes(20)).decode()
            codes = []
            hashes = []
            for _ in range(10):
                c = secrets.token_hex(5).upper()
                codes.append("%s-%s" % (c[:5], c[5:]))
                hashes.append(_recovery_hash(c)[0])
            data = _totp_load()
            data[target] = {
                "secret": secret, "status": "pending",
                "last_counter": -1, "recovery": hashes,
                "enrolled_ts": now_iso(),
                "enrolled_by": "two-key reenroll"}
            _totp_save(data)
            db.execute("DELETE FROM meta WHERE "
                       "key='totp_reenroll_by'")
            chain.append("TOTP_REENROLL", {
                "user": target, "by": rec["user"],
                "requested_by": pending.get("by")})
            db.commit()
            return self.send_json(200, {
                "result": "re-enrolled — the secret and recovery "
                          "codes are shown ONCE; hand them to the "
                          "individual in person",
                "user": target, "totp_secret": secret,
                "recovery_codes": codes})
        return self.send_json(403, {
            "error": "re-enrollment is supervisor-then-auditor, "
                     "two keys"})

    def _totp_acknowledge(self, rec):
        """A supervisor acknowledges a recovery-code use (1.2.4,
        S11): the account's /health flag clears, and the
        acknowledgment chains."""
        if not role_is(rec, "supervisor"):
            return self.send_json(403, {
                "error": "recovery acknowledgment is "
                         "supervisor-only"})
        d = self.body_json()
        target = (d.get("user") or "").strip()
        data = _totp_load()
        entry = data.get(target)
        if not entry or not entry.get("recovery_alert"):
            return self.send_json(404, {
                "error": "no unacknowledged recovery-code use for "
                         "that account"})
        entry.pop("recovery_alert", None)
        _totp_save(data)
        chain.append("TOTP_RECOVERY_ACK", {
            "user": target, "by": rec["user"]})
        db.commit()
        return self.send_json(200, {
            "result": "recovery use acknowledged", "user": target})

    def _report_compile(self, rec):
        # 1.2.2 (Q9): POST /report/compile takes GET /report's fence
        # — supervisor or auditor. 1.2.1 let any detective compile
        # (and thereby READ) the full statutory report while GET
        # /report refused them (round 5, Vesper F4 / Gemini N6).
        if not role_is(rec, "supervisor", "auditor"):
            return self.send_json(403, {"error": "role cannot compile "
                                                "reports"})
        d = self.body_json()
        frm = d.get("from", "")
        to = d.get("to", "9999-12-31T23:59:59Z")
        body = compute_report(frm, to)
        body_json = json.dumps(body, sort_keys=True)
        cur = db.execute(
            "INSERT INTO report_snapshots(from_ts, to_ts, compiled_by, "
            "compiled_ts, body) VALUES(?,?,?,?,?)",
            (frm, to, rec["user"], now_iso(), body_json))
        # S14: the compile chains a HASH of the snapshot contents —
        # a snapshot whose body is later edited no longer matches
        # its chain entry, which is the point of compiling one.
        chain.append("REPORT_COMPILE", {
            "snapshot": cur.lastrowid, "by": rec["user"],
            "body_hash": sha(body_json)})
        db.commit()
        return self.send_json(201, {"result": "snapshot compiled",
                                    "snapshot_id": cur.lastrowid,
                                    "report": body})

    def _anchor_accept(self, rec):
        """Two-key clearing of a startup anchor mismatch: a
        supervisor records acceptance, then the AUDITOR — a
        different person, outside the chain of command — confirms.
        The accepted state (the disagreeing checkpoints) is recorded
        (S6), so a restart on the same state does not re-trigger;
        a NEW disagreement does."""
        if not anchor_mismatch():
            return self.send_json(200, {"result": "no anchor mismatch "
                                                  "to accept"})
        # 1.2.4 (S9): acceptance clears a DISAGREEMENT — specific
        # checkpoints whose contents the two keys have seen and
        # accepted. 1.2.3 let the same flow "accept" a mismatch
        # whose reason was checkpoints_unreadable or
        # checkpoints_missing (DeepSeek-chat residual): it recorded
        # zero checkpoint ids, deleted the mismatch, and the
        # condition re-triggered at the next boot — an acceptance
        # that accepted nothing. Those reasons are repaired
        # (restore the checkpoints file), never accepted.
        try:
            _detail = json.loads(_meta_get("anchor_mismatch")
                                 or "{}")
        except ValueError:
            _detail = {}
        if _detail.get("reason") != "checkpoint_disagreement":
            return self.send_json(409, {
                "error": "the current anchor mismatch is %s — only "
                         "a checkpoint_disagreement can be accepted "
                         "by two keys; an unreadable or missing "
                         "checkpoints file must be repaired, not "
                         "accepted" % (_detail.get("reason")
                                        or "unknown")})
        pending = _meta_get("anchor_accept_by")
        if role_is(rec, "supervisor") and not pending:
            # P11: meta write + chain entry + commit are ONE
            # transaction (1.2's _meta_set committed first).
            db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                       "ON CONFLICT(key) DO UPDATE SET "
                       "value=excluded.value",
                       ("anchor_accept_by", rec["user"]))
            db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                       "ON CONFLICT(key) DO UPDATE SET "
                       "value=excluded.value",
                       ("anchor_accept_ts", now_iso()))
            chain.append("ANCHOR_ACCEPT_REQUEST", {"by": rec["user"]})
            db.commit()
            return self.send_json(200, {
                "result": "acceptance recorded — the auditor must "
                          "confirm to clear the mismatch"})
        if role_is(rec, "auditor") and pending:
            if rec["user"] == pending:
                return self.send_json(403, {"error": "the two-key rule "
                                                   "forbids self-confirm"})
            # 1.2.2: a pending acceptance EXPIRES after 24h — a
            # request recorded against one disagreement must not be
            # confirmable against another, weeks later (round 5,
            # DeepSeek F6).
            req_ts = _meta_get("anchor_accept_ts")
            try:
                fresh = req_ts and (datetime.now(timezone.utc)
                                    - parse_ts(req_ts)).total_seconds() \
                    <= 24 * 3600
            except (ValueError, TypeError):
                fresh = False
            if not fresh:
                db.execute("DELETE FROM meta WHERE key IN "
                           "('anchor_accept_by','anchor_accept_ts')")
                db.commit()
                return self.send_json(409, {
                    "error": "the pending acceptance is stale "
                             "(>24h) and has been cleared — a "
                             "supervisor must record a fresh one"})
            # P11/A15: record the IDS of the checkpoints that
            # disagree NOW. They stay accepted; tomorrow's new
            # checkpoint is judged on its own facts.
            accepted = _accepted_checkpoint_ids()
            for cp in _bad_checkpoints():
                accepted.add(tuple(_checkpoint_id(cp)))
            db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                       "ON CONFLICT(key) DO UPDATE SET "
                       "value=excluded.value",
                       ("anchor_accepted_ids",
                        json.dumps(sorted(
                            [list(x) for x in accepted],
                            key=lambda x: str(x)))))
            db.execute("DELETE FROM meta WHERE key IN "
                       "('anchor_mismatch','anchor_accept_by',"
                       "'anchor_accepted','anchor_accept_ts')")
            chain.append("ANCHOR_ACCEPT", {"requested_by": pending,
                                           "by": rec["user"],
                                           "accepted_checkpoints":
                                           len(accepted)})
            db.commit()
            return self.send_json(200, {"result": "anchor mismatch "
                                                  "cleared"})
        return self.send_json(403, {
            "error": "anchor acceptance is supervisor-then-auditor, "
                     "two keys"})

    # ---------------- Tier 3 two-key workflow (S2) ----------------
    def _tier3_post(self, path, rec):
        d = self.body_json()
        if path == "/tier3/request":
            if not role_is(rec, "detective", "patrol", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot request "
                                                   "Tier 3 searches"})
            case_no = d.get("case_id", "")
            why = (d.get("why") or "").strip()
            frag, ferr = validate_fragment(d.get("plate_fragment"))
            basis = (d.get("auth_basis") or "").strip()
            basis_type = (d.get("basis_type") or "other").strip().lower()
            if basis_type not in TIER3_BASIS_TYPES:
                # Q11: only a CONFIGURED instrument executes. The
                # default configuration is judicial instruments
                # only — "other" (a lieutenant's verbal OK) is not
                # one, whatever the free text says.
                return self.send_json(400, {
                    "error": "basis_type must be one of "
                             + ", ".join(TIER3_BASIS_TYPES)
                             + " — Tier 3 executes only on a "
                               "configured instrument"})
            if not why:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "no_justification"})
                return self.send_json(403, {"error": "BLOCKED: Tier 3 "
                                                   "requests require a "
                                                   "justification (why)"})
            if ferr:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": ferr})
                return self.send_json(400,
                                      {"error": FRAGMENT_MSGS[ferr]})
            if not basis:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "no_basis"})
                return self.send_json(403, {"error": "BLOCKED: Tier 3 "
                                                   "requests require "
                                                   "auth_basis (the warrant "
                                                   "or court order on file)"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "case_hash": case_hash(case_no),
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, basis_type, status, "
                "created_ts) VALUES(?,?,?,?,?,?,'PENDING',?)",
                (rec["user"], case_no, why, frag, basis, basis_type,
                 now_iso()))
            # S11: the chain carries the coded basis_type and the
            # fragment's ref — the warrant's free text stays in the
            # DB (and is itself retention-classed, S1).
            chain.append("TIER3_REQUEST", {
                "request": cur.lastrowid, "by": rec["user"],
                "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "basis_type": basis_type})
            db.commit()
            return self.send_json(201, {
                "result": "PENDING — nothing was searched",
                "request_id": cur.lastrowid})
        if path == "/tier3/approve":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "reason": "role"})
                return self.send_json(403, {"error": "Tier 3 approval is "
                                                   "supervisor-only"})
            req_id = _strict_id(d.get("request_id"))
            if req_id is None:
                return self.send_json(400, {
                    "error": "request_id must be an integer"})
            row = db.execute(
                "SELECT requester, case_no, why, plate_fragment, "
                "auth_basis, basis_type, status FROM tier3_requests "
                "WHERE id=?", (req_id,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            requester, case_no, why, frag, basis, basis_type, status = row
            if status != "PENDING":
                return self.send_json(409, {"error": "request is not "
                                                   "pending (status: %s)"
                                                   % status})
            if why is None or basis is None:
                # 1.2.2 (Q27): retention scrubbed the request's
                # detail at class age — it EXPIRES. 1.2.1 executed
                # it anyway: the approver approved a blank form and
                # the search ran (Claude R5-16).
                db.execute(
                    "UPDATE tier3_requests SET status='EXPIRED' "
                    "WHERE id=?", (req_id,))
                chain.append("TIER3_EXPIRE", {"request": req_id,
                                              "by": rec["user"]})
                db.commit()
                return self.send_json(409, {
                    "error": "the request's justification and basis "
                             "have aged out under retention — the "
                             "request is EXPIRED, not executable"})
            if basis_type not in TIER3_BASIS_TYPES:
                # Q11: the instrument set is re-judged at EXECUTION —
                # a request filed while 'other' was configured does
                # not execute after the configuration closes.
                return self.send_json(403, {
                    "error": "basis_type %r is not a configured Tier "
                             "3 instrument (configured: %s)"
                             % (basis_type,
                                ", ".join(TIER3_BASIS_TYPES))})
            if rec["user"] == requester:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "request": req_id,
                                         "reason": "two_key"})
                return self.send_json(403, {"error": "BLOCKED: the two-key "
                                                   "rule forbids approving "
                                                   "your own Tier 3 "
                                                   "request"})
            # The case gate re-runs at execution — a case that closed
            # while the request waited no longer opens.
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "request": req_id,
                                         "reason": reason})
                return self.send_json(403, {
                    "error": "BLOCKED at execution: "
                             + CASE_GATE_MSGS[reason]})
            results = run_search(frag, "full")
            read_ids = [r["id"] for r in results["reads"]]
            hit_ids = [r["id"] for r in results["hits"]]
            n = len(read_ids) + len(hit_ids)
            # S2: store ONLY the matched ids. The result body is
            # resolved live at read time, through whatever the
            # suppression layer and the case list say THEN — a
            # stored body could do neither, and outlived everything.
            db.execute(
                "UPDATE tier3_requests SET status='EXECUTED', "
                "decided_by=?, decided_ts=?, results_count=?, "
                "results=NULL, results_read_ids=?, results_hit_ids=? "
                "WHERE id=?",
                (rec["user"], now_iso(), n, json.dumps(read_ids),
                 json.dumps(hit_ids), req_id))
            chain.append("TIER3_APPROVE", {
                "request": req_id, "by": rec["user"],
                "requester": requester, "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "basis_type": basis_type})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 approved search",
                "tier": 3, "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "result_count": n,
                "via_request": req_id, "emergency": False})
            db.commit()
            # The approver does NOT receive the results. The
            # requester retrieves them, and that retrieval is chained.
            return self.send_json(200, {
                "result": "EXECUTED", "request_id": req_id,
                "results_count": n,
                "results_url": f"/tier3/results/{req_id}"})
        if path == "/tier3/deny":
            req_id = _strict_id(d.get("request_id"))
            if req_id is None:
                return self.send_json(400, {
                    "error": "request_id must be an integer"})
            row = db.execute(
                "SELECT requester, status FROM tier3_requests WHERE id=?",
                (req_id,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            if not role_is(rec, "supervisor") and rec["user"] != row[0]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 deny",
                                         "reason": "role"})
                return self.send_json(403, {"error": "deny requires a "
                                                   "supervisor or the "
                                                   "requester"})
            if row[1] != "PENDING":
                return self.send_json(409, {"error": "request is not "
                                                   "pending"})
            db.execute(
                "UPDATE tier3_requests SET status='DENIED', decided_by=?, "
                "decided_ts=? WHERE id=?",
                (rec["user"], now_iso(), req_id))
            chain.append("TIER3_DENY", {"request": req_id,
                                        "by": rec["user"],
                                        "requester": row[0]})
            db.commit()
            return self.send_json(200, {"result": "DENIED",
                                        "request_id": req_id})
        if path == "/tier3/emergency":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": "role"})
                return self.send_json(403, {"error": "the Tier 3 emergency "
                                                   "path is supervisor-only"})
            case_no = d.get("case_id", "")
            why = (d.get("why") or "").strip()
            frag, ferr = validate_fragment(d.get("plate_fragment"))
            basis = (d.get("auth_basis") or "").strip()
            basis_type = (d.get("basis_type") or "other").strip().lower()
            if basis_type not in TIER3_BASIS_TYPES:
                return self.send_json(400, {
                    "error": "basis_type must be one of "
                             + ", ".join(TIER3_BASIS_TYPES)
                             + " — Tier 3 executes only on a "
                               "configured instrument"})
            if not why:
                return self.send_json(400, {"error": "why is required"})
            if ferr:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": ferr})
                return self.send_json(400,
                                      {"error": FRAGMENT_MSGS[ferr]})
            if not basis:
                # The emergency path requires auth_basis too —
                # exigency explains speed, not the absence of a basis.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": "no_basis"})
                return self.send_json(403, {"error": "BLOCKED: the "
                                                   "emergency path requires "
                                                   "auth_basis"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "case_hash": case_hash(case_no),
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            # An unreviewed emergency older than 72h locks the
            # emergency path for that user until it is reviewed.
            stale = db.execute(
                "SELECT COUNT(*) FROM tier3_requests WHERE requester=? "
                "AND emergency=1 AND needs_review=1 AND created_ts < ?",
                (rec["user"], (datetime.now(timezone.utc)
                               - timedelta(hours=72)).strftime(
                                   "%Y-%m-%dT%H:%M:%SZ"))).fetchone()[0]
            if stale:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": "unreviewed_emergency"})
                return self.send_json(403, {
                    "error": "BLOCKED: you have an unreviewed emergency "
                             "use older than 72 hours — it must be "
                             "reviewed before the emergency path opens "
                             "again"})
            results = run_search(frag, "full")
            read_ids = [r["id"] for r in results["reads"]]
            hit_ids = [r["id"] for r in results["hits"]]
            n = len(read_ids) + len(hit_ids)
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, basis_type, status, "
                "created_ts, decided_by, decided_ts, emergency, "
                "needs_review, results_count, results, "
                "results_read_ids, results_hit_ids) "
                "VALUES(?,?,?,?,?,?,'EMERGENCY',?,?,?,1,1,?,NULL,?,?)",
                (rec["user"], case_no, why, frag, basis, basis_type,
                 now_iso(), rec["user"], now_iso(), n,
                 json.dumps(read_ids), json.dumps(hit_ids)))
            chain.append("TIER3_EMERGENCY", {
                "request": cur.lastrowid, "by": rec["user"],
                "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "basis_type": basis_type,
                "review": "mandatory post-hoc review queued"})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 emergency search",
                "tier": 3, "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "result_count": n,
                "via_request": cur.lastrowid, "emergency": True})
            db.commit()
            return self.send_json(200, {
                "result": "EXECUTED — flagged EMERGENCY, post-hoc "
                          "review queued",
                "request_id": cur.lastrowid, "results": results})
        if path == "/tier3/review":
            if not role_is(rec, "supervisor", "auditor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 review",
                                         "reason": "role"})
                return self.send_json(403, {"error": "post-hoc review is "
                                                   "supervisor/auditor "
                                                   "only"})
            # The finding is an enum — a bare "ok" is not a review.
            # The prose note stays in the DB.
            finding = (d.get("finding") or "").strip().lower()
            if finding not in REVIEW_FINDINGS:
                return self.send_json(400, {
                    "error": "finding must be one of "
                             + ", ".join(REVIEW_FINDINGS)})
            req_id = _strict_id(d.get("request_id"))
            if req_id is None:
                return self.send_json(400, {
                    "error": "request_id must be an integer"})
            row = db.execute(
                "SELECT requester, needs_review, emergency, "
                "auditor_reviewed_by FROM tier3_requests "
                "WHERE id=?", (req_id,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            if rec["user"] == row[0]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 review",
                                         "request": req_id,
                                         "reason": "own_use_review"})
                return self.send_json(403, {"error": "BLOCKED: you cannot "
                                                   "review your own "
                                                   "emergency use"})
            if role_is(rec, "auditor"):
                # 1.2.2 (Q13): the outside auditor's review is
                # INDEPENDENT — spec SS8 requires it "in all cases"
                # for emergency uses. 1.2.1 ran both reviews through
                # the one needs_review flag, so a supervisor's
                # 'justified' consumed the review and the auditor's
                # own attempt 409'd as already-reviewed: the outside
                # check was pre-emptible by the chain of command
                # (round 5, Claude R5-08). The auditor's fields are
                # separate; neither review satisfies the other.
                if not row[2]:
                    return self.send_json(409, {
                        "error": "the auditor reviews emergency uses; "
                                 "this was not one"})
                if row[3]:
                    return self.send_json(409, {
                        "error": "the auditor has already reviewed "
                                 "this use"})
                db.execute(
                    "UPDATE tier3_requests SET "
                    "auditor_review_finding=?, auditor_reviewed_by=?, "
                    "auditor_reviewed_ts=? WHERE id=?",
                    (finding, rec["user"], now_iso(), req_id))
                chain.append("TIER3_AUDITOR_REVIEW", {
                    "request": req_id, "by": rec["user"],
                    "finding": finding})
                db.commit()
                return self.send_json(200, {
                    "result": "AUDITOR REVIEWED", "request_id": req_id})
            if not row[1]:
                return self.send_json(409, {"error": "that use is not "
                                                   "awaiting review"})
            db.execute(
                "UPDATE tier3_requests SET status='REVIEWED', "
                "needs_review=0, review_finding=?, review_note=?, "
                "reviewed_by=?, reviewed_ts=? WHERE id=?",
                (finding, (d.get("note") or None), rec["user"],
                 now_iso(), req_id))
            chain.append("TIER3_REVIEW", {"request": req_id,
                                          "by": rec["user"],
                                          "finding": finding})
            db.commit()
            return self.send_json(200, {"result": "REVIEWED",
                                        "request_id": req_id})
        return self.send_json(404, {"error": "no such route"})

    # ---------------- evidence lifecycle (S3, S17) ----------------
    def _evidence_post(self, path, rec):
        d = self.body_json()
        if path == "/evidence/export":
            if not role_is(rec, "detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot export "
                                                   "evidence"})
            case_no = d.get("case_id", "")
            hit_id = _strict_id(d.get("hit_id"))
            if hit_id is None:
                return self.send_json(400, {
                    "error": "hit_id must be an integer"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit_id,
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            hit = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,list_name,"
                "category,status,decided_by,case_no,decided_ts,"
                "suppressed FROM hits WHERE id=?",
                (hit_id,)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no such hit"})
            hkeys = ("id", "ts", "cam", "read_plate", "entry_plate",
                     "state", "list_name", "category", "status",
                     "decided_by", "case_no", "decided_ts", "suppressed")
            hit_rec = dict(zip(hkeys, hit))
            # P3: the export gate judges suppression LIVE — the
            # stored stamp is a cache, never the authority.
            hit_rec["suppressed"] = 1 if hit_suppressed_now(
                hit_rec["read_plate"], hit_rec["entry_plate"]) else 0
            if hit_rec["suppressed"] and not role_is(rec, "supervisor"):
                # S3: a suppressed hit's evidence moves only through
                # the supervisor queue.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit[0],
                                         "reason": "suppressed_queue"})
                return self.send_json(403, {
                    "error": "that hit is under a protection-order "
                             "suppression — export is supervisor-only"})
            # Only a VERIFIED hit is evidence, and only under the
            # case it was verified under.
            if hit_rec["status"] != "VERIFIED":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit[0],
                                         "reason": "hit_not_verified"})
                return self.send_json(409, {
                    "error": "evidence export requires a VERIFIED hit "
                             "(status: %s)" % hit_rec["status"]})
            if hit_rec["case_no"] != case_no:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit[0],
                                         "reason": "case_mismatch"})
                return self.send_json(403, {
                    "error": "case_id does not match the case the hit "
                             "was verified under"})
            # Scope: the hit plus reads of the same plate within
            # +/- 1 hour. A supervisor may expand to full history only
            # with an explicit reason (kept in the DB, not the chain).
            expand = bool(d.get("expand"))
            reason_txt = (d.get("reason") or "").strip()
            if expand and not role_is(rec, "supervisor"):
                return self.send_json(403, {"error": "expansion beyond "
                                                   "the +/-1h window is "
                                                   "supervisor-only"})
            if expand and not reason_txt:
                return self.send_json(400, {"error": "expand requires a "
                                                   "reason"})
            via_tier3 = None
            if expand:
                # 1.2.2 (Q10): expansion IS a Tier 3 search wearing
                # another hat — 1.2.1 let one supervisor pull a
                # plate's FULL retained history on a free-text
                # reason, with no TIER3 entry, no basis, no second
                # key (round 5, Claude R5-20). It now requires an
                # EXECUTED Tier 3 request covering this case and
                # this hit's plate, and the reason is chained
                # (hashed) like every other justification.
                via_tier3 = _tier3_covers(case_no, hit_rec)
                if via_tier3 is None:
                    chain.append("BLOCKED", {
                        "user": rec["user"], "action": "evidence export",
                        "hit": hit[0], "reason": "expand_needs_tier3"})
                    return self.send_json(403, {
                        "error": "expansion requires an executed "
                                 "Tier 3 request for this case "
                                 "covering this plate — run the "
                                 "two-key Tier 3 workflow first"})
            plates = {hit[3], hit[4]}
            if expand:
                read_rows = db.execute(
                    "SELECT id,ts,cam,plate,state,conf,cam_ts,skew_s "
                    "FROM reads WHERE plate IN (%s) ORDER BY ts"
                    % ",".join("?" * len(plates)), tuple(plates)).fetchall()
                scope = "full"
            else:
                hit_dt = parse_ts(hit[1])
                lo = (hit_dt - timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                hi = (hit_dt + timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                read_rows = db.execute(
                    "SELECT id,ts,cam,plate,state,conf,cam_ts,skew_s "
                    "FROM reads WHERE plate IN (%s) AND ts>=? AND ts<=? "
                    "ORDER BY ts" % ",".join("?" * len(plates)),
                    (*plates, lo, hi)).fetchall()
                scope = "window_1h"
            reads = [dict(zip(("id", "ts", "cam", "plate", "state",
                               "conf", "cam_ts", "skew_s"), r))
                     for r in read_rows]
            outcome = db.execute(
                "SELECT hit_id,list_name,category,confirmed,arrest,"
                "prosecution,updated_by,updated_ts,hit_ts FROM outcomes "
                "WHERE hit_id=?", (hit[0],)).fetchone()
            outcome_rec = (dict(zip(
                ("hit_id", "list_name", "category", "confirmed", "arrest",
                 "prosecution", "updated_by", "updated_ts", "hit_ts"),
                outcome)) if outcome else None)
            excerpt = custody_excerpt(hit[0])
            # S17: a re-export deletes the PRIOR bundle in the same
            # operation — 1.1 left the old bundle orphaned on disk,
            # a plate archive nobody's retention knew about (S1).
            # 1.2.2 (Q7): the operation is FAILURE-ATOMIC and the
            # lifecycle RESETS. 1.2.1 deleted the old bundle BEFORE
            # the row update committed (a locked DB left the row
            # pointing at a deleted bundle and the new one orphaned
            # — ChatGPT F2), and its UPSERT cleared destroyed_* but
            # not released_ts / destroy_by, so a fresh bundle
            # inherited the OLD bundle's destruction clock and was
            # destroyed unreleased (Vesper F3). Now: write the new
            # bundle, update the row (full lifecycle reset), chain,
            # COMMIT — and only then delete the old bundle. Any
            # failure before the commit removes the NEW bundle and
            # leaves the old one exactly as it was.
            prior = db.execute("SELECT bundle FROM evidence WHERE "
                               "hit_id=?", (hit[0],)).fetchone()
            prior_bundle = prior[0] if prior else None
            os.makedirs(EVIDENCE_DIR, mode=0o700, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bundle_name = "hit-%d-%s" % (hit[0], stamp)
            bundle_path = os.path.join(EVIDENCE_DIR, bundle_name)
            files = {}
            try:
                os.makedirs(bundle_path, mode=0o700, exist_ok=True)

                def put(name, obj):
                    data = json.dumps(obj, indent=1,
                                      sort_keys=True).encode()
                    p = os.path.join(bundle_path, name)
                    with open(p, "wb") as f:
                        f.write(data)
                    os.chmod(p, 0o600)
                    files[name] = hashlib.sha256(data).hexdigest()

                put("hit.json", hit_rec)
                put("reads.json", reads)
                put("outcome.json", outcome_rec)
                put("audit-excerpt.json", excerpt)
                manifest = {"hit_id": hit[0], "case_no": case_no,
                            "exported_by": rec["user"],
                            "exported_ts": now_iso(), "scope": scope,
                            "files": files}
                mhash = sha(json.dumps(manifest, sort_keys=True,
                                       separators=(",", ":")))
                manifest["manifest_hash"] = mhash
                put("manifest.json", manifest)
                db.execute(
                    "INSERT INTO evidence(hit_id, export_ts, "
                    "export_by, manifest_hash, bundle, scope, "
                    "expand_reason) VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(hit_id) DO UPDATE SET "
                    "export_ts=excluded.export_ts, "
                    "export_by=excluded.export_by, "
                    "manifest_hash=excluded.manifest_hash, "
                    "bundle=excluded.bundle, scope=excluded.scope, "
                    "expand_reason=excluded.expand_reason, "
                    "prosecutor_name=NULL, prosecutor_date=NULL, "
                    "released_by=NULL, released_ts=NULL, "
                    "destroyed_ts=NULL, destroyed_by=NULL, "
                    "destroy_by=NULL, disp_outcome=NULL, disp_by=NULL, "
                    "disp_date=NULL, disp_note=NULL, "
                    "disp_posted_by=NULL, disp_confirmed_by=NULL, "
                    "disp_confirmed_ts=NULL, disp_ts=NULL",
                    (hit[0], manifest["exported_ts"], rec["user"],
                     mhash, bundle_name, scope, reason_txt or None))
                export_fields = {
                    "hit": hit[0], "case_hash": case_hash(case_no),
                    "manifest": mhash, "scope": scope,
                    "expanded": expand, "by": rec["user"]}
                if expand:
                    export_fields["expand_reason_hash"] = why_hash(
                        reason_txt)
                    export_fields["via_tier3"] = via_tier3
                chain.append("EVIDENCE_EXPORT", export_fields)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                if os.path.isdir(bundle_path):
                    shutil.rmtree(bundle_path, ignore_errors=True)
                return self.send_json(500, {
                    "error": "export failed — the previous bundle "
                             "is unchanged"})
            if prior_bundle and prior_bundle != bundle_name:
                old_path = os.path.join(EVIDENCE_DIR, prior_bundle)
                if os.path.isdir(old_path):
                    shutil.rmtree(old_path)
            return self.send_json(201, {"result": "exported",
                                        "bundle": bundle_name,
                                        "manifest_hash": mhash,
                                        "scope": scope, "files": files})
        if path == "/evidence/release":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "evidence release is "
                                                   "supervisor-only"})
            so = d.get("prosecutor_signoff") or {}
            pname = (so.get("name") or d.get("prosecutor_name")
                     or "").strip()
            pdate = (so.get("date") or d.get("prosecutor_date")
                     or "").strip()
            if not pname or not pdate:
                return self.send_json(400, {
                    "error": "prosecutor_signoff with name and date is "
                             "required"})
            hit_id = _strict_id(d.get("hit_id"))
            if hit_id is None:
                return self.send_json(400, {
                    "error": "hit_id must be an integer"})
            # 1.2.2 (Q7): the lifecycle keys on the EVIDENCE record.
            # 1.2.1 required the hits row to exist, so once
            # retention purged the hit, its bundle could never be
            # released, dispositioned, or destroyed — stranded
            # forever, invisible to /health (Gemini N1).
            ev = db.execute("SELECT export_ts FROM evidence WHERE "
                            "hit_id=?", (hit_id,)).fetchone()
            if not ev or not ev[0]:
                # There is nothing to release until an export exists —
                # a sign-off cannot precede the evidence.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence release",
                                         "hit": hit_id,
                                         "reason": "no_export"})
                return self.send_json(409, {
                    "error": "no export exists for that hit — release "
                             "requires an export first"})
            released = now_iso()
            # S17: release starts the destruction clock — the bundle
            # must be destroyed by release + 30 days, and /health
            # names it when the date passes.
            destroy_by = (parse_ts(released)
                          + timedelta(days=30)).strftime(
                              "%Y-%m-%dT%H:%M:%SZ")
            db.execute(
                "UPDATE evidence SET prosecutor_name=?, "
                "prosecutor_date=?, released_by=?, released_ts=?, "
                "destroy_by=? WHERE hit_id=?",
                (pname, pdate, rec["user"], released, destroy_by,
                 hit_id))
            chain.append("EVIDENCE_RELEASE", {"hit": hit_id,
                                              "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "released",
                                        "hit": hit_id,
                                        "destroy_by": destroy_by})
        if path == "/evidence/destroy":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence destroy",
                                         "reason": "role"})
                return self.send_json(403, {"error": "evidence destruction "
                                                   "is supervisor-only"})
            hit_id = _strict_id(d.get("hit_id"))
            if hit_id is None:
                return self.send_json(400, {
                    "error": "hit_id must be an integer"})
            ev = db.execute(
                "SELECT bundle, released_ts, disp_confirmed_ts, "
                "destroyed_ts FROM evidence WHERE hit_id=?",
                (hit_id,)).fetchone()
            if not ev or not ev[0]:
                return self.send_json(404, {"error": "no export bundle "
                                                   "for that hit"})
            if ev[3]:
                return self.send_json(409, {"error": "bundle already "
                                                   "destroyed"})
            if not ev[1] and not ev[2]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence destroy",
                                         "hit": hit_id,
                                         "reason": "not_released"})
                return self.send_json(409, {
                    "error": "destruction requires a release (prosecutor "
                             "sign-off or a confirmed disposition) first"})
            # 1.2.4 (S7): destruction is ordered RECORD FIRST.
            # 1.2.3 deleted the files and only then updated the row
            # and chained the act — a failure between the two left
            # evidence deleted but unchained (round 7, Gemini
            # F12). Now the row update and the EVIDENCE_DESTROY
            # entry COMMIT before any file moves; if the file
            # deletion then fails, the state is destroyed-on-paper
            # — visible in the registry breach check and remediated
            # by the next retention run — never the reverse.
            bundle_path = os.path.join(EVIDENCE_DIR, ev[0])
            db.execute("UPDATE evidence SET destroyed_ts=?, "
                       "destroyed_by=? WHERE hit_id=?",
                       (now_iso(), rec["user"], hit_id))
            chain.append("EVIDENCE_DESTROY", {"hit": hit_id,
                                              "by": rec["user"]})
            db.commit()
            files_removed = True
            if os.path.isdir(bundle_path):
                try:
                    shutil.rmtree(bundle_path)
                except OSError:
                    files_removed = False
            return self.send_json(200, {
                "result": "bundle destroyed"
                          if files_removed else
                          "bundle destruction recorded — file "
                          "removal failed and is queued for "
                          "retention remediation",
                "hit": hit_id, "files_removed": files_removed})
        if path == "/evidence/disposition":
            if not role_is(rec, "detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence disposition",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot record "
                                                   "dispositions"})
            outcome = (d.get("outcome") or "").strip()
            if outcome not in ("no_charges", "charges_concluded"):
                return self.send_json(400, {
                    "error": "outcome must be 'no_charges' or "
                             "'charges_concluded'"})
            hit_id = _strict_id(d.get("hit_id"))
            if hit_id is None:
                return self.send_json(400, {
                    "error": "hit_id must be an integer"})
            # Q7: a disposition may be recorded while the hit lives
            # OR after it purged (against its evidence record) — but
            # not for a hit that never existed anywhere.
            known = db.execute("SELECT 1 FROM hits WHERE id=?",
                               (hit_id,)).fetchone() or db.execute(
                "SELECT 1 FROM evidence WHERE hit_id=?",
                (hit_id,)).fetchone()
            if not known:
                return self.send_json(404, {"error": "no such hit"})
            # SS 12-12-1804(b) has two exits — charges that concluded,
            # and an investigation that never became charges. A
            # disposition records the second (and the conclusion of
            # the first) and, once CONFIRMED by a different
            # supervisor, releases the data for deletion exactly as a
            # prosecutor sign-off does. Free text stays in the DB.
            db.execute(
                "INSERT INTO evidence(hit_id, disp_outcome, disp_by, "
                "disp_date, disp_note, disp_posted_by, "
                "disp_confirmed_by, disp_confirmed_ts, disp_ts) "
                "VALUES(?,?,?,?,?,?,NULL,NULL,?) ON CONFLICT(hit_id) DO "
                "UPDATE SET disp_outcome=excluded.disp_outcome, "
                "disp_by=excluded.disp_by, disp_date=excluded.disp_date, "
                "disp_note=excluded.disp_note, "
                "disp_posted_by=excluded.disp_posted_by, "
                "disp_confirmed_by=NULL, disp_confirmed_ts=NULL, "
                "disp_ts=excluded.disp_ts",
                (hit_id, outcome, (d.get("by") or "").strip(),
                 (d.get("date") or "").strip(), d.get("note"),
                 rec["user"], now_iso()))
            chain.append("EVIDENCE_DISPOSITION", {
                "hit": hit_id, "outcome": outcome, "by": rec["user"],
                "status": "awaiting confirmation"})
            db.commit()
            return self.send_json(201, {
                "result": "disposition recorded — a different supervisor "
                          "must confirm it before it releases anything",
                "hit": hit_id})
        if path == "/evidence/disposition/confirm":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "disposition confirm",
                                         "reason": "role"})
                return self.send_json(403, {"error": "disposition "
                                                   "confirmation is "
                                                   "supervisor-only"})
            hit_id = _strict_id(d.get("hit_id"))
            if hit_id is None:
                return self.send_json(400, {
                    "error": "hit_id must be an integer"})
            row = db.execute(
                "SELECT disp_outcome, disp_posted_by, disp_confirmed_ts "
                "FROM evidence WHERE hit_id=?",
                (hit_id,)).fetchone()
            if not row or not row[0]:
                return self.send_json(404, {"error": "no disposition on "
                                                   "file for that hit"})
            if row[2]:
                return self.send_json(409, {"error": "disposition already "
                                                   "confirmed"})
            if rec["user"] == row[1]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "disposition confirm",
                                         "hit": hit_id,
                                         "reason": "two_key"})
                return self.send_json(403, {
                    "error": "BLOCKED: the two-key rule forbids "
                             "confirming a disposition you posted"})
            confirmed = now_iso()
            destroy_by = (parse_ts(confirmed)
                          + timedelta(days=30)).strftime(
                              "%Y-%m-%dT%H:%M:%SZ")
            db.execute("UPDATE evidence SET disp_confirmed_by=?, "
                       "disp_confirmed_ts=?, destroy_by=? WHERE hit_id=?",
                       (rec["user"], confirmed, destroy_by, hit_id))
            chain.append("EVIDENCE_DISPOSITION_CONFIRM", {
                "hit": hit_id, "outcome": row[0], "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "disposition confirmed "
                                                  "— data released for "
                                                  "deletion",
                                        "hit": hit_id,
                                        "destroy_by": destroy_by})
        return self.send_json(404, {"error": "no such route"})


    # ---------------- Compact / shares / rotation (S7–S10, S12) ----------------
    def _compact_post(self, path, rec):
        d = self.body_json()
        if path == "/share/query":
            return self._share_query(rec, d)
        if path == "/compact/partners":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner add",
                                         "reason": "role"})
                return self.send_json(403, {"error": "partner management "
                                                   "is supervisor-only"})
            agency = (d.get("agency") or "").strip()
            endpoint = (d.get("endpoint") or "").strip()
            # S7: the partner's Ed25519 PUBLIC key is what a Compact
            # agency registers; its audit key (the plate-HMAC secret)
            # is NEVER sent or stored here — it never leaves the
            # partner's box either. Registration stores the
            # fingerprint of the supplied public key.
            pubkey_pem = (d.get("pubkey_pem") or "").strip()
            if not agency or not endpoint:
                return self.send_json(400, {"error": "agency and "
                                                   "endpoint are "
                                                   "required"})
            if not pubkey_pem:
                return self.send_json(400, {
                    "error": "pubkey_pem (the partner's Ed25519 public "
                             "key, PEM) is required"})
            try:
                fp = sentinel.pubkey_fingerprint(pubkey_pem)
            except (ValueError, TypeError):
                fp = None
            if not fp:
                return self.send_json(400, {"error": "pubkey_pem is not "
                                                   "a readable Ed25519 "
                                                   "public key"})
            if "://" not in endpoint:
                return self.send_json(400, {"error": "endpoint must be a "
                                                   "URL"})
            db.execute(
                "INSERT INTO partners(agency, endpoint, "
                "audit_key_fingerprint, pubkey_pem, agreement_ref, "
                "status, added_by, added_ts) VALUES(?,?,?,?,?,'active',"
                "?,?) ON CONFLICT(agency) DO UPDATE SET "
                "endpoint=excluded.endpoint, "
                "pubkey_pem=excluded.pubkey_pem, "
                "audit_key_fingerprint=excluded.audit_key_fingerprint, "
                "agreement_ref=excluded.agreement_ref",
                (agency, endpoint, fp, pubkey_pem,
                 (d.get("agreement_ref") or "").strip() or None,
                 rec["user"], now_iso()))
            chain.append("PARTNER_ADD", {"agency": agency, "by": rec["user"],
                                         "audit_key_fingerprint": fp})
            db.commit()
            return self.send_json(201, {
                "result": "partner registered", "agency": agency,
                "audit_key_fingerprint": fp})
        if path == "/compact/audit-result":
            # OUR auditor records the result of OUR audit of a
            # partner. S8: the REPORT is signed with OUR Ed25519
            # signing key (compact.py signs it), and the hash of the
            # report is what this endpoint records. The signature is
            # verified against OUR OWN public key first — this row
            # attests to work THIS agency's auditor did, so this
            # agency's key is the one that must have signed it. A
            # report that does not verify is not recorded at all.
            if not role_is(rec, "auditor", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "compact audit-result",
                                         "reason": "role"})
                return self.send_json(403, {"error": "audit results are "
                                                   "recorded by the "
                                                   "auditor role"})
            agency = (d.get("agency") or "").strip()
            report = d.get("report")
            sig = (d.get("report_sig") or "").strip()
            if not isinstance(report, dict) or not sig:
                return self.send_json(400, {
                    "error": "report (object) and report_sig (base64 "
                             "Ed25519 signature) are required"})
            partner = db.execute(
                "SELECT 1 FROM partners WHERE agency=?",
                (agency,)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            if not SIGNING_PUB_PEM:
                return self.send_json(503, {
                    "error": "this agency has no signing key — signed "
                             "audit reports cannot be verified"})
            ok = sentinel.verify_bytes(
                SIGNING_PUB_PEM, sentinel.canonical_bytes(report), sig)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "compact audit-result",
                                         "agency": agency,
                                         "reason": "bad_report_sig"})
                return self.send_json(403, {
                    "error": "the report signature does not verify "
                             "against this agency's signing key"})
            if not isinstance(report.get("ok"), bool):
                return self.send_json(400, {"error": "report.ok must be "
                                                   "a boolean"})
            # P7/A3: the report is BOUND to its subject and its
            # moment. 1.2 verified the signature and nothing else —
            # a signed report from 2025 was stamped fresh with
            # now_iso(), and the same signed body could be re-filed
            # as a passing audit of a DIFFERENT partner. Now the
            # report must name the agency it is filed under, its own
            # ts must be within 26h, and the row stores the REPORT's
            # ts — the freshness the gate later reads is the
            # report's, not the filing's.
            if report.get("agency") != agency:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "compact audit-result",
                                         "agency": agency,
                                         "reason": "report_agency_mismatch"})
                return self.send_json(400, {
                    "error": "report.agency does not match the agency "
                             "the report is filed under"})
            try:
                report_age = (datetime.now(timezone.utc)
                              - parse_ts(report.get("ts") or "")
                              ).total_seconds()
            except (ValueError, TypeError):
                return self.send_json(400, {
                    "error": "report.ts must be a valid timestamp"})
            if report_age > 26 * 3600 or report_age < -3600:
                return self.send_json(409, {
                    "error": "report.ts is not within 26h — a stale "
                             "signed report cannot be re-filed as a "
                             "fresh audit"})
            report_hash = sha(sentinel.canonical_bytes(report).decode())
            # 1.2.2 (Q21): the gate is a function of audit TIME, not
            # filing order. A report whose hash is already on file,
            # or whose ts is OLDER than the newest report on file
            # for this partner, is refused — 1.2.1 stored it, the
            # gate read 'latest' by id, and re-filing yesterday's
            # signed pass after this morning's failure reopened
            # sharing (round 5, Claude R5-06). A report exactly as
            # new as the newest (same second, different audit) is
            # accepted; ordering within the second falls to id.
            if db.execute(
                    "SELECT 1 FROM compact_audits WHERE agency=? AND "
                    "report_hash=?", (agency, report_hash)).fetchone():
                return self.send_json(409, {
                    "error": "that exact report is already on file — "
                             "a duplicate filing changes nothing"})
            newest_ts = db.execute(
                "SELECT MAX(ts) FROM compact_audits WHERE agency=?",
                (agency,)).fetchone()[0]
            if newest_ts and report["ts"] < newest_ts:
                return self.send_json(409, {
                    "error": "report.ts is older than the newest "
                             "report on file for this partner — the "
                             "gate follows audit time, not filing "
                             "order"})
            ok_val = report.get("ok")
            db.execute(
                "INSERT INTO compact_audits(agency, ok, detail, "
                "report_hash, ts) VALUES(?,?,?,?,?)",
                (agency, 1 if ok_val else 0,
                 json.dumps(report, sort_keys=True)[:2000], report_hash,
                 report["ts"]))
            chain.append("COMPACT_AUDIT_RESULT", {
                "agency": agency, "ok": ok_val,
                "report_hash": report_hash, "by": rec["user"]})
            db.commit()
            return self.send_json(201, {"result": "audit result recorded",
                                        "agency": agency,
                                        "report_hash": report_hash})
        if path == "/compact/checkpoint-receipt":
            # S8: a receipt must name OUR NEWEST checkpoint, and the
            # partner's Ed25519 signature over (root, entries,
            # checkpoint_ts, agency) must verify against the registered
            # public key. A replay of an old receipt fails here: its
            # root/entries no longer match the newest checkpoint.
            agency = (d.get("agency") or "").strip()
            root = (d.get("checkpoint_root") or "").strip()
            entries = d.get("checkpoint_entries")
            cts = (d.get("checkpoint_ts") or "").strip()
            sig = (d.get("signature") or "").strip()
            if not agency or not root or not isinstance(entries, int) \
                    or not cts or not sig:
                return self.send_json(400, {
                    "error": "agency, checkpoint_root, checkpoint_entries, "
                             "checkpoint_ts and signature are required"})
            if not role_is(rec, "partner") or rec["user"] != agency:
                # A receipt is the partner agency's own attestation,
                # posted under its own partner identity — an
                # operator account cannot file one on its behalf.
                _chain_throttled("BLOCKED", "receipt:identity", {
                    "user": rec["user"], "action": "checkpoint-receipt",
                    "agency": agency, "reason": "partner_identity"})
                return self.send_json(403, {
                    "error": "checkpoint receipts are posted by the "
                             "partner agency's own partner identity"})
            partner = db.execute(
                "SELECT pubkey_pem FROM partners WHERE agency=?",
                (agency,)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            newest = read_newest_checkpoint()
            if not newest:
                _chain_throttled("BLOCKED", "receipt:no_checkpoint", {
                    "user": rec["user"], "action": "checkpoint-receipt",
                    "agency": agency, "reason": "no_checkpoint"})
                return self.send_json(409, {"error": "this agency has no "
                                                   "checkpoint yet — "
                                                   "nothing to attest"})
            # Freshness is measured from the checkpoint's OWN
            # timestamp, not from when the receipt arrived: a receipt
            # attesting a stale checkpoint is not a live check.
            if newest.get("root") != root or \
                    newest.get("entries") != entries or \
                    newest.get("ts") != cts:
                _chain_throttled("BLOCKED", "receipt:stale_checkpoint", {
                    "user": rec["user"], "action": "checkpoint-receipt",
                    "agency": agency, "reason": "stale_checkpoint"})
                return self.send_json(409, {
                    "error": "receipt does not name this agency's newest "
                             "checkpoint (root/entries/ts mismatch)"})
            payload = {"agency": agency, "checkpoint_ts": cts,
                       "entries": entries, "root": root}
            ok = sentinel.verify_bytes(
                partner[0], sentinel.canonical_bytes(payload), sig)
            if not ok:
                _chain_throttled("BLOCKED", "receipt:bad_receipt_sig", {
                    "user": rec["user"], "action": "checkpoint-receipt",
                    "agency": agency, "reason": "bad_receipt_sig"})
                return self.send_json(403, {
                    "error": "the receipt signature does not verify "
                             "against the registered public key"})
            try:
                age_s = (datetime.now(timezone.utc)
                         - parse_ts(cts)).total_seconds()
            except (ValueError, TypeError):
                return self.send_json(400, {"error": "checkpoint_ts is not "
                                                   "a valid timestamp"})
            if age_s > 26 * 3600:
                return self.send_json(409, {
                    "error": "the newest checkpoint is older than 26h — "
                             "publish a fresh checkpoint before asking "
                             "for an attestation"})
            if age_s < -3600:
                # R7/Gemini M1: a future-dated checkpoint is not
                # fresh — it is wrong, and no receipt may attest it
                # into the gate.
                return self.send_json(409, {
                    "error": "the newest checkpoint is dated in the "
                             "future — a receipt cannot attest it"})
            # A re-posted receipt for the SAME checkpoint is a
            # legitimate duplicate (compact.py attests after every
            # audit; retries and second auditors re-post) — the
            # table's UNIQUE(agency, root, entries) makes the bare
            # INSERT a 500. Answer idempotently instead: the fact
            # is already on file and verified.
            dup = db.execute(
                "SELECT 1 FROM compact_receipts WHERE agency=? "
                "AND root=? AND entries=? AND verified=1",
                (agency, root, entries)).fetchone()
            if dup:
                return self.send_json(201, {
                    "result": "receipt already recorded — duplicate "
                              "attestation ignored",
                    "agency": agency, "checkpoint_root": root})
            db.execute(
                "INSERT INTO compact_receipts(agency, root, entries, "
                "sig, checkpoint_ts, verified, received_ts) "
                "VALUES(?,?,?,?,?,1,?)",
                (agency, root, entries, sig, cts, now_iso()))
            chain.append("COMPACT_RECEIPT", {
                "agency": agency, "checkpoint_root": root,
                "checkpoint_entries": entries, "verified": True})
            db.commit()
            return self.send_json(201, {"result": "receipt recorded and "
                                                  "verified",
                                        "agency": agency,
                                        "checkpoint_root": root})
        if path == "/compact/suspend":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner suspend",
                                         "reason": "role"})
                return self.send_json(403, {"error": "partner suspension "
                                                   "is supervisor-only"})
            # P11/A21b: suspending a partner that does not exist is
            # an error, not a 200 with the caller's raw text chained.
            # (The agency field is scrubber-exempt because REGISTERED
            # agency ids are configuration; unregistered text never
            # reaches the chain through this endpoint now.)
            partner = db.execute("SELECT 1 FROM partners WHERE "
                                 "agency=?", (d.get("agency"),)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            db.execute("UPDATE partners SET status='suspended' WHERE "
                       "agency=?", (d.get("agency"),))
            chain.append("PARTNER_SUSPEND", {"agency": d.get("agency"),
                                             "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "partner suspended",
                                        "agency": d.get("agency")})
        if path == "/compact/reinstate":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner reinstate",
                                         "reason": "role"})
                return self.send_json(403, {"error": "partner "
                                                   "reinstatement is "
                                                   "supervisor-only"})
            # Reinstatement requires a FRESH audit — the stale record
            # a partner fell behind on cannot be re-validated by age.
            partner = db.execute("SELECT 1 FROM partners WHERE agency=?",
                                 (d.get("agency"),)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            # 1.2.2 (Q21): the latest audit is the newest by
            # REPORT TIME (see share_gate_missing) — filing order
            # no longer governs anything about the gate.
            row = db.execute(
                "SELECT ok, ts FROM compact_audits WHERE agency=? "
                "ORDER BY ts DESC, id DESC LIMIT 1",
                (d.get("agency"),)).fetchone()
            if not row or not row[0] or (datetime.now(timezone.utc)
                                         - parse_ts(row[1])).total_seconds() \
                    > 26 * 3600:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner reinstate",
                                         "agency": d.get("agency"),
                                         "reason": "no_fresh_audit"})
                return self.send_json(409, {
                    "error": "reinstatement requires a fresh (≤26h) "
                             "passing audit — submit one first"})
            db.execute("UPDATE partners SET status='active' WHERE "
                       "agency=?", (d.get("agency"),))
            chain.append("PARTNER_REINSTATE", {"agency": d.get("agency"),
                                               "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "partner reinstated",
                                        "agency": d.get("agency")})
        if path == "/compact/rotation":
            if not role_is(rec, "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "rotation publish",
                                         "reason": "role"})
                return self.send_json(403, {"error": "rotation publishing "
                                                   "is supervisor-only"})
            return self._rotation_publish(rec, d)
        if path == "/compact/rotation/commit":
            return self._rotation_commit(rec, d)
        if path == "/compact/rotation/contribute":
            return self._rotation_contribution(rec, d, reveal=False)
        if path == "/compact/rotation/reveal":
            return self._rotation_contribution(rec, d, reveal=True)
        if path == "/compact/rotation/cancel":
            return self._rotation_cancel(rec, d)
        if path == "/compact/rotation/void":
            latest = db.execute(
                "SELECT id FROM rotation_schedules ORDER BY id DESC "
                "LIMIT 1").fetchone()
            if not latest:
                return self.send_json(409, {"error": "no rotation cycle "
                                                   "exists to void"})
            pending = _meta_get("rotation_void_by")
            pending_by = None
            pending_cycle = None
            if pending:
                try:
                    rec_p = json.loads(pending)
                    pending_by = rec_p.get("by")
                    pending_cycle = rec_p.get("schedule_id")
                except ValueError:
                    pending_by = pending  # 1.2.1's bare-username form
            if role_is(rec, "supervisor") and not pending:
                # P11: one transaction — meta write, chain entry,
                # commit (1.2's _meta_set committed before the chain
                # append, splitting the act from its record).
                # 1.2.2 (Q23): the request is BOUND to the cycle that
                # exists when it is made — 1.2.1's confirm deleted
                # whatever cycle was latest when the auditor got to
                # it (round 5, Claude R5-10).
                db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                           "ON CONFLICT(key) DO UPDATE SET "
                           "value=excluded.value",
                           ("rotation_void_by", json.dumps(
                               {"by": rec["user"],
                                "schedule_id": latest[0]})))
                chain.append("ROTATION_VOID_REQUEST", {"by": rec["user"],
                                                       "schedule": latest[0]})
                db.commit()
                return self.send_json(200, {
                    "result": "void recorded — the auditor must confirm"})
            if role_is(rec, "auditor") and pending:
                if rec["user"] == pending_by:
                    return self.send_json(403, {"error": "the two-key "
                                                       "rule forbids "
                                                       "self-confirm"})
                if pending_cycle is not None \
                        and pending_cycle != latest[0]:
                    db.execute("DELETE FROM meta WHERE "
                               "key='rotation_void_by'")
                    db.commit()
                    return self.send_json(409, {
                        "error": "the cycle changed since the void "
                                 "was requested — the stale request "
                                 "is cleared; a supervisor must "
                                 "request a void of the current cycle"})
                voided = db.execute(
                    "SELECT cycle_start FROM rotation_schedules "
                    "WHERE id=?", (latest[0],)).fetchone()
                db.execute("DELETE FROM rotation_schedules WHERE id=?",
                           (latest[0],))
                db.execute("DELETE FROM meta WHERE key='rotation_void_by'")
                if voided:
                    # 1.2.3 (R6/Gemini F2): voiding clears the
                    # cycle's contributions too — 1.2.2 left them,
                    # so the voided cycle's revealed nonces were
                    # forced onto any replacement cycle opened for
                    # the same start date. 1.2.4 (S5): they are
                    # TOMBSTONED first — cleared from the new
                    # ceremony, and barred from replaying into it.
                    self._rotation_tombstone(voided[0])
                    db.execute(
                        "DELETE FROM rotation_contributions WHERE "
                        "cycle_start=?", (voided[0],))
                    pend = _meta_get("rotation_pending")
                    if pend:
                        try:
                            if json.loads(pend).get(
                                    "cycle_start") == voided[0]:
                                db.execute(
                                    "DELETE FROM meta WHERE "
                                    "key='rotation_pending'")
                        except ValueError:
                            pass
                    db.execute("DELETE FROM meta WHERE "
                               "key='rotation_cancel_by'")
                chain.append("ROTATION_VOID", {"requested_by": pending_by,
                                               "by": rec["user"]})
                db.commit()
                return self.send_json(200, {"result": "rotation cycle "
                                                  "voided"})
            return self.send_json(403, {
                "error": "rotation void is supervisor-then-auditor, "
                         "two keys"})
        if path == "/compact/witness":
            # S12: the witness attests, per round of the active
            # cycle, that it verified the round auditor's checkpoint
            # signature and chain state. The attestation names the
            # cycle and round it covers — a free-floating "ok" would
            # attest nothing.
            # P9/A25: 1.2 let ANY authenticated role file one, with
            # no signature and no chain entry — the ingest service
            # account attested for another agency and history kept
            # no record. Now the filer is either a SUPERVISOR of
            # this agency, or the partner's REGISTERED AUDITOR
            # identity: an Ed25519 signature over the attestation,
            # verified against the public key registered for the
            # agency the attestation is about. Either way the filing
            # chains WITNESS_ATTEST in the same transaction.
            agency = (d.get("agency") or "").strip()
            cycle_start = (d.get("cycle_start") or "").strip()
            round_no = d.get("round")
            ok_val = d.get("ok")
            if not agency or not cycle_start \
                    or not isinstance(round_no, int) \
                    or isinstance(round_no, bool) \
                    or not isinstance(ok_val, bool):
                return self.send_json(400, {
                    "error": "agency, cycle_start, round (integer) and "
                             "ok (boolean) are required"})
            # 1.2.2 (Q24): the attestation must be ABOUT a round of
            # a published cycle, and the filer must have standing
            # for the agency it names. Round 5 (ChatGPT F3): a
            # local supervisor attested for an ARBITRARY partner —
            # 201, and rotation_status counted it as that partner's
            # witness duty done. Now the cycle must exist, the
            # agency must be one of its members, a supervisor files
            # only for the HOME agency, and any other filing must
            # carry the named agency's registered signature (below).
            sched = db.execute(
                "SELECT schedule FROM rotation_schedules WHERE "
                "cycle_start=? ORDER BY id DESC LIMIT 1",
                (cycle_start,)).fetchone()
            if not sched:
                return self.send_json(400, {
                    "error": "no published rotation cycle starts %s"
                             % cycle_start})
            try:
                sched_doc = json.loads(sched[0])
            except ValueError:
                sched_doc = {}
            members = sched_doc.get("members", [])
            if agency not in members:
                return self.send_json(400, {
                    "error": "%s is not a member of the %s cycle"
                             % (agency, cycle_start)})
            if role_is(rec, "supervisor"):
                if agency != AGENCY:
                    return self.send_json(403, {
                        "error": "a supervisor attests for the home "
                                 "agency only — a partner's "
                                 "attestation must carry that "
                                 "partner's signature"})
                attested_by = rec["user"]
            else:
                partner = db.execute(
                    "SELECT pubkey_pem FROM partners WHERE agency=?",
                    (agency,)).fetchone()
                sig = (d.get("signature") or "").strip()
                attestation = {"agency": agency,
                               "cycle_start": cycle_start,
                               "round": round_no, "ok": ok_val}
                if not partner or not sig or not sentinel.verify_bytes(
                        partner[0],
                        sentinel.canonical_bytes(attestation), sig):
                    chain.append("BLOCKED", {
                        "user": rec["user"],
                        "action": "witness attestation",
                        "reason": "unverified_attestation"})
                    return self.send_json(403, {
                        "error": "witness attestations require a "
                                 "supervisor, or the partner's "
                                 "registered-key Ed25519 signature "
                                 "over the attestation"})
                attested_by = agency
            # 1.2.3 (R6): the attestation must name a round that
            # exists, and the agency must be that round's
            # DESIGNATED attester — the member neither auditing nor
            # audited in it (in a two-member cycle, the round's
            # auditor). 1.2.2 accepted a filing from any member for
            # any round, and _rotation_status counted filings under
            # the auditor's name — duty could be satisfied by
            # someone who never held it (round 6, Vesper F8).
            # Checked AFTER standing, so a filing that fails both
            # still answers with the standing refusal.
            round_rec = None
            for r in sched_doc.get("rounds", []):
                if r.get("round") == round_no:
                    round_rec = r
                    break
            if round_rec is None:
                return self.send_json(400, {
                    "error": "the %s cycle has no round %s"
                             % (cycle_start, round_no)})
            # 1.2.4 (S5): designation is the shared helper — at
            # n>=4 it rotates among the eligible others instead of
            # falling back to the auditor (see _designated_witness).
            designated, _self_att = _designated_witness(
                members, round_rec.get("auditor"),
                round_rec.get("audited"), round_no)
            if agency != designated:
                return self.send_json(400, {
                    "error": "%s is not the designated attester "
                             "for round %s of the %s cycle — that "
                             "duty is %s's"
                             % (agency, round_no, cycle_start,
                                designated)})
            db.execute(
                "INSERT INTO witness_attestations(agency, cycle_start, "
                "round_no, ok, detail, ts) VALUES(?,?,?,?,?,?)",
                (agency, cycle_start, round_no, 1 if ok_val else 0,
                 (d.get("detail") or "")[:500], now_iso()))
            chain.append("WITNESS_ATTEST", {
                "agency": agency, "cycle_start": cycle_start,
                "round": round_no, "ok": ok_val, "by": attested_by})
            db.commit()
            return self.send_json(201, {"result": "witness attestation "
                                                  "recorded"})
        return self.send_json(404, {"error": "no such route"})

    # ---------- rotation ceremony (Q23) ----------
    def _rotation_tombstone(self, cycle_start):
        """Record a ceremony's contributions as RETIRED before
        they are deleted (1.2.4, S5): a cancelled or voided
        ceremony's commitments and reveals must not replay into a
        restarted ceremony for the same cycle_start. 1.2.3 deleted
        the rows and forgot them; the signatures bind only
        (agency, cycle_start, kind, value), so the same signed
        values verified again in the new ceremony (round 7,
        Gemini F7 / ChatGPT R7-05). The tombstone is the memory:
        filings are checked against it (_contribution_retired)
        for as long as it is kept (bounded, newest 512)."""
        rows = db.execute(
            "SELECT agency, nonce_hash, nonce FROM "
            "rotation_contributions WHERE cycle_start=?",
            (cycle_start,)).fetchall()
        if not rows:
            return
        try:
            retired = json.loads(
                _meta_get("rotation_retired_contribs") or "[]")
        except ValueError:
            retired = []
        for agency, nh, nonce in rows:
            retired.append({"cycle_start": cycle_start,
                            "agency": agency, "nonce_hash": nh,
                            "nonce": nonce})
        db.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("rotation_retired_contribs",
             json.dumps(retired[-512:])))

    def _contribution_retired(self, cycle_start, agency,
                              nonce_hash=None, nonce=None):
        try:
            retired = json.loads(
                _meta_get("rotation_retired_contribs") or "[]")
        except ValueError:
            return False
        for r in retired:
            if r.get("cycle_start") == cycle_start \
                    and r.get("agency") == agency:
                if nonce_hash and r.get("nonce_hash") == nonce_hash:
                    return True
                if nonce and r.get("nonce") == nonce:
                    return True
        return False

    def _rotation_params(self, d):
        """Validate the members/cycle_start/period triple shared by
        the commit and publish calls. Returns (members, cycle_start,
        period) or None after sending the error."""
        members = d.get("members")
        if not isinstance(members, list) or not members:
            self.send_json(400, {"error": "members must be a "
                                          "non-empty list of agency "
                                          "names"})
            return None
        members = sorted({str(m).strip() for m in members})
        if len(members) != len(d.get("members")):
            self.send_json(400, {"error": "members contains "
                                          "duplicates — rotation "
                                          "members must be unique"})
            return None
        if len(members) < 2:
            self.send_json(400, {
                "error": "a rotation cycle needs at least 2 members"})
            return None
        partner_names = {r[0] for r in db.execute(
            "SELECT agency FROM partners WHERE status='active'").fetchall()}
        # P9: the HOME agency may be a rotation member without
        # registering as its own partner.
        if not set(members) <= (partner_names | {AGENCY}):
            self.send_json(400, {
                "error": "rotation members must be registered, "
                         "non-suspended partners (or this agency)"})
            return None
        cycle_start = (d.get("cycle_start") or "").strip()
        try:
            date.fromisoformat(cycle_start)
        except ValueError:
            self.send_json(400, {"error": "cycle_start must be a "
                                          "real date (YYYY-MM-DD)"})
            return None
        period = d.get("period_days")
        if not isinstance(period, int) or isinstance(period, bool) \
                or period < 7 or period > 120:
            self.send_json(400, {"error": "period_days must be an "
                                          "integer between 7 and 120"})
            return None
        return members, cycle_start, period

    def _rotation_chaining_error(self, cycle_start):
        """Q23: a cycle's start is fixed by rule, not chosen.
        The first cycle may not be backdated; every later cycle
        starts exactly when the previous one ends. Returns an error
        string or None."""
        today = datetime.now(timezone.utc).date()
        latest = db.execute(
            "SELECT cycle_start, period_days, members_count FROM "
            "rotation_schedules ORDER BY id DESC LIMIT 1").fetchone()
        if not latest:
            if date.fromisoformat(cycle_start) < today:
                return ("the first cycle may not start in the past "
                        "(%s < %s)" % (cycle_start, today.isoformat()))
            return None
        end = date.fromisoformat(latest[0]) + timedelta(
            days=latest[1] * latest[2])
        if today < end:
            return ("an active rotation cycle already exists "
                    "(started %s, ends %s) — void it (supervisor + "
                    "auditor two-key) before opening a replacement"
                    % (latest[0], end.isoformat()))
        if cycle_start != end.isoformat():
            return ("cycle_start is fixed by rule: the previous "
                    "cycle ends %s, so the next cycle starts %s"
                    % (end.isoformat(), end.isoformat()))
        return None

    def _rotation_commit(self, rec, d):
        # Q23: publishing a rotation is a COMMIT-REVEAL ceremony.
        # Round 5 (both Claude seats): 1.2.1's "derived" seed was
        # SHA-256(members ‖ cycle_start ‖ chain root) — and the
        # publisher chose cycle_start AND could move the root with
        # an ordinary read, so the pairing was still grindable
        # offline (R5-07/R5-12). Now every member commits a hash of
        # a secret nonce BEFORE any nonce is revealed; the seed is
        # SHA-256 over the revealed nonces, which no party —
        # publisher included — can predict or bias without breaking
        # a commitment. cycle_start is fixed by rule (see
        # _rotation_chaining_error), so it cannot be ground either.
        if not role_is(rec, "supervisor"):
            return self.send_json(403, {
                "error": "opening a rotation cycle is supervisor-only"})
        if d.get("seed"):
            return self.send_json(400, {
                "error": "the rotation seed comes from the members' "
                         "revealed nonces — a publisher-supplied seed "
                         "is refused"})
        params = self._rotation_params(d)
        if params is None:
            return
        members, cycle_start, period = params
        err = self._rotation_chaining_error(cycle_start)
        if err:
            return self.send_json(409, {"error": err})
        pending = _meta_get("rotation_pending")
        if pending:
            try:
                pdoc = json.loads(pending)
            except ValueError:
                pdoc = {}
            if pdoc.get("cycle_start") != cycle_start:
                return self.send_json(409, {
                    "error": "a rotation commit is already open for "
                             "cycle %s — complete it before opening "
                             "another" % pdoc.get("cycle_start")})
        hashes = d.get("nonce_hashes") or {}
        if not isinstance(hashes, dict):
            return self.send_json(400, {
                "error": "nonce_hashes must be an object mapping "
                         "agency -> sha256 hex of its secret nonce"})
        for agency, h in hashes.items():
            if agency not in members:
                return self.send_json(400, {
                    "error": "nonce_hashes names %s, not a member of "
                             "this cycle" % agency})
            if not isinstance(h, str) or len(h) != 64 or any(
                    c not in "0123456789abcdef" for c in h.lower()):
                return self.send_json(400, {
                    "error": "nonce_hash for %s must be a sha256 hex "
                             "digest" % agency})
        # 1.2.4 (S5 / Qwen F-A): bulk commitments are AUTHORED,
        # exactly as single contributions are. 1.2.3's bulk path
        # took nonce_hashes with no authorship check at all — a
        # supervisor could author every partner's commitment (and
        # thereby choose the seed's inputs and strand the real
        # partners' filings against the no-overwrite rule). Now
        # each bulk entry for a partner must carry that partner's
        # Ed25519 signature over the commitment (the same signed
        # portion _rotation_contribution verifies); the home
        # agency's own entry is the supervisor's to author, as
        # there. One unsigned entry refuses the whole bulk commit.
        sigs = d.get("signatures") or {}
        if not isinstance(sigs, dict):
            return self.send_json(400, {
                "error": "signatures must be an object mapping "
                         "agency -> base64 Ed25519 signature over "
                         "its commitment"})
        for agency, h in hashes.items():
            if self._contribution_retired(cycle_start, agency,
                                           nonce_hash=h.lower()):
                return self.send_json(409, {
                    "error": "that commitment for %s belonged to "
                             "a retired ceremony for cycle %s — "
                             "retired contributions do not replay"
                             % (agency, cycle_start)})
            if agency == AGENCY:
                continue
            prow = db.execute(
                "SELECT pubkey_pem FROM partners WHERE agency=?",
                (agency,)).fetchone()
            sig = (sigs.get(agency) or "").strip()
            att = {"agency": agency, "cycle_start": cycle_start,
                   "kind": "commit", "nonce_hash": h.lower()}
            if not prow or not prow[0] or not sig \
                    or not sentinel.verify_bytes(
                        prow[0], sentinel.canonical_bytes(att),
                        sig):
                chain.append("BLOCKED", {
                    "user": rec["user"],
                    "action": "rotation bulk commit",
                    "agency": agency,
                    "reason": "unsigned_bulk_commit"})
                db.commit()
                return self.send_json(403, {
                    "error": "bulk commitment for %s carries no "
                             "valid signature from that partner — "
                             "a supervisor transports a partner's "
                             "commitment only with the partner's "
                             "Ed25519 signature over it" % agency})
        # 1.2.3 (R6): the pending marker, the contributions and
        # the chain entry commit in ONE transaction — 1.2.2's
        # _meta_set committed the marker before the append
        # (Gemini M5). Bulk hashes follow the ceremony's rules:
        # the commit phase freezes at the first reveal, and a
        # commitment on file is never overwritten by a different
        # hash (a re-commit of the SAME hash is a no-op).
        # 1.2.4 (S5): the freeze is TOTAL — after the first
        # reveal, /commit is closed in ALL shapes. 1.2.3's guard
        # was `any_reveal and hashes`, so an EMPTY-hashes repeat
        # commit still rewrote the pending marker with mutated
        # members/period_days and re-opened seed grinding against
        # the known nonces (round 7, Gemini F6).
        any_reveal = db.execute(
            "SELECT COUNT(*) FROM rotation_contributions WHERE "
            "cycle_start=? AND nonce IS NOT NULL",
            (cycle_start,)).fetchone()[0]
        if any_reveal:
            return self.send_json(409, {
                "error": "the commit phase closed at the first "
                         "reveal — commitments for cycle %s are "
                         "frozen" % cycle_start})
        for agency, h in hashes.items():
            row = db.execute(
                "SELECT nonce_hash FROM rotation_contributions "
                "WHERE cycle_start=? AND agency=?",
                (cycle_start, agency)).fetchone()
            if row and row[0] and row[0] != h.lower():
                return self.send_json(409, {
                    "error": "%s already committed a different "
                             "nonce hash — commitments are never "
                             "overwritten" % agency})
        # 1.2.4 (S5): the ceremony-instance id — minted when the
        # cycle opens, preserved across re-commits of the same
        # open cycle, and recorded on every contribution row and
        # in the chain entry, so a contribution names the ceremony
        # it belongs to (and a retired ceremony's filings can be
        # told apart from a restarted one's).
        ceremony_id = None
        if pending:
            try:
                ceremony_id = json.loads(pending).get("ceremony_id")
            except ValueError:
                ceremony_id = None
        if not ceremony_id:
            ceremony_id = secrets.token_hex(8)
        db.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("rotation_pending", json.dumps({
                "cycle_start": cycle_start, "period_days": period,
                "members": members, "by": rec["user"],
                "ceremony_id": ceremony_id})))
        for agency, h in hashes.items():
            db.execute(
                "INSERT INTO rotation_contributions(cycle_start, "
                "agency, nonce_hash, committed_ts, ceremony_id) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(cycle_start, agency) DO UPDATE SET "
                "nonce_hash=excluded.nonce_hash, "
                "committed_ts=excluded.committed_ts, "
                "ceremony_id=excluded.ceremony_id WHERE "
                "rotation_contributions.nonce IS NULL",
                (cycle_start, agency, h.lower(), now_iso(),
                 ceremony_id))
        chain.append("ROTATION_COMMIT", {
            "cycle_start": cycle_start, "period_days": period,
            "members": members, "by": rec["user"],
            "ceremony_id": ceremony_id,
            "commitments": len(hashes)})
        db.commit()
        have = {r[0] for r in db.execute(
            "SELECT agency FROM rotation_contributions WHERE "
            "cycle_start=? AND nonce_hash IS NOT NULL",
            (cycle_start,)).fetchall()}
        return self.send_json(201, {
            "result": "rotation cycle committed — members reveal "
                      "their nonces, then publish",
            "cycle_start": cycle_start, "period_days": period,
            "members": members, "ceremony_id": ceremony_id,
            "awaiting_commitments": [m for m in members
                                     if m not in have]})

    def _rotation_contribution(self, rec, d, reveal):
        pending_raw = _meta_get("rotation_pending")
        if not pending_raw:
            return self.send_json(409, {
                "error": "no rotation cycle is open — a supervisor "
                         "commits the cycle first"})
        pending = json.loads(pending_raw)
        cycle_start = (d.get("cycle_start") or "").strip()
        if cycle_start != pending["cycle_start"]:
            return self.send_json(409, {
                "error": "the open cycle starts %s"
                         % pending["cycle_start"]})
        agency = (d.get("agency") or "").strip()
        if agency not in pending["members"]:
            return self.send_json(400, {
                "error": "%s is not a member of the open cycle"
                         % agency})
        # Standing and AUTHORSHIP (1.2.3, R6). 1.2.2 let a
        # supervisor TRANSPORT any member's value unsigned — and
        # transport silently became authorship: one supervisor
        # could file a commitment hash AND its reveal for every
        # member and choose the schedule outright (round 6,
        # Gemini F2 / seat 2 F6b). Now a filing is authored by
        #   (a) the member itself (partner identity — its API key
        #       IS its authorship), or
        #   (b) for the HOME agency, a supervisor (the home
        #       agency's own officer), or
        #   (c) a supervisor TRANSPORTING a value that carries the
        #       member's Ed25519 signature over the contribution,
        #       verified against the member's registered key.
        # Anything else is refused, chained.
        def _authorized(value_fields):
            if role_is(rec, "partner") and rec["user"] == agency:
                return True
            if role_is(rec, "supervisor") and agency == AGENCY:
                return True
            if role_is(rec, "supervisor"):
                prow = db.execute(
                    "SELECT pubkey_pem FROM partners WHERE "
                    "agency=?", (agency,)).fetchone()
                sig = (d.get("signature") or "").strip()
                att = {"agency": agency,
                       "cycle_start": cycle_start}
                att.update(value_fields)
                if prow and prow[0] and sig and \
                        sentinel.verify_bytes(
                            prow[0],
                            sentinel.canonical_bytes(att), sig):
                    return True
                chain.append("BLOCKED", {
                    "user": rec["user"],
                    "action": "rotation contribution",
                    "agency": agency,
                    "reason": "unsigned_transport"})
                db.commit()
                self.send_json(403, {
                    "error": "a supervisor transports a partner's "
                             "contribution only with the partner's "
                             "Ed25519 signature over it — transport "
                             "is not authorship"})
                return False
            self.send_json(403, {
                "error": "a contribution comes from the member "
                         "itself, or a supervisor carrying the "
                         "member's signature"})
            return False

        if not reveal:
            h = (d.get("nonce_hash") or "").strip().lower()
            if len(h) != 64 or any(c not in "0123456789abcdef"
                                   for c in h):
                return self.send_json(400, {
                    "error": "nonce_hash must be a sha256 hex digest"})
            if not _authorized({"kind": "commit", "nonce_hash": h}):
                return
            # R6: the PHASE BARRIER — commitments freeze at the
            # first reveal. 1.2.2's commit-path UPSERT overwrote an
            # existing nonce_hash unconditionally, so a commitment
            # filed (or re-filed) AFTER other members revealed
            # could be ground offline against the known nonces
            # (round 6, Vesper F1 / seat 2 F6a).
            any_reveal = db.execute(
                "SELECT COUNT(*) FROM rotation_contributions WHERE "
                "cycle_start=? AND nonce IS NOT NULL",
                (cycle_start,)).fetchone()[0]
            if any_reveal:
                return self.send_json(409, {
                    "error": "the commit phase closed at the first "
                             "reveal — commitments for cycle %s are "
                             "frozen" % cycle_start})
            # 1.2.4 (S5): a retired ceremony's commitment does not
            # replay into a restarted one (see _rotation_tombstone).
            if self._contribution_retired(cycle_start, agency,
                                           nonce_hash=h):
                return self.send_json(409, {
                    "error": "that commitment belonged to a "
                             "retired ceremony for cycle %s — "
                             "retired contributions do not replay"
                             % cycle_start})
            row = db.execute(
                "SELECT nonce_hash FROM rotation_contributions "
                "WHERE cycle_start=? AND agency=?",
                (cycle_start, agency)).fetchone()
            if row and row[0]:
                if row[0] == h:
                    return self.send_json(201, {
                        "result": "commitment already recorded",
                        "agency": agency})
                return self.send_json(409, {
                    "error": "%s already committed a different "
                             "nonce hash — commitments are never "
                             "overwritten" % agency})
            db.execute(
                "INSERT INTO rotation_contributions(cycle_start, "
                "agency, nonce_hash, committed_ts, ceremony_id) "
                "VALUES(?,?,?,?,?)",
                (cycle_start, agency, h, now_iso(),
                 pending.get("ceremony_id")))
            fields = {"agency": agency, "cycle_start": cycle_start}
            if rec["user"] != agency:
                fields["filed_by"] = rec["user"]
            chain.append("ROTATION_CONTRIBUTION", fields)
            db.commit()
            return self.send_json(201, {"result": "commitment "
                                                  "recorded",
                                        "agency": agency})
        nonce = d.get("nonce")
        if not isinstance(nonce, str) \
                or not (16 <= len(nonce) <= 256):
            return self.send_json(400, {
                "error": "nonce must be a string of 16-256 "
                         "characters"})
        if not _authorized({"kind": "reveal", "nonce": nonce}):
            return
        # 1.2.4 (S5): a retired ceremony's revealed nonce does not
        # replay either — its commitment is refused above, and this
        # catches a reveal filed against a fresh commitment whose
        # hash was re-committed over the retired value's slot.
        if self._contribution_retired(cycle_start, agency,
                                       nonce=nonce):
            return self.send_json(409, {
                "error": "that nonce belonged to a retired "
                         "ceremony for cycle %s — retired "
                         "contributions do not replay" % cycle_start})
        row = db.execute(
            "SELECT nonce_hash, nonce FROM rotation_contributions "
            "WHERE cycle_start=? AND agency=?",
            (cycle_start, agency)).fetchone()
        if not row or not row[0]:
            return self.send_json(409, {
                "error": "%s has no commitment on file for this "
                         "cycle — commit before revealing" % agency})
        if row[1]:
            return self.send_json(409, {
                "error": "%s has already revealed" % agency})
        if sha(nonce) != row[0]:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "rotation reveal",
                                     "agency": agency,
                                     "reason": "nonce_mismatch"})
            db.commit()
            return self.send_json(400, {
                "error": "the nonce does not match the commitment "
                         "hash on file"})
        db.execute(
            "UPDATE rotation_contributions SET nonce=?, "
            "revealed_ts=? WHERE cycle_start=? AND agency=?",
            (nonce, now_iso(), cycle_start, agency))
        fields = {"agency": agency, "cycle_start": cycle_start}
        if rec["user"] != agency:
            fields["filed_by"] = rec["user"]
        chain.append("ROTATION_REVEAL", fields)
        db.commit()
        return self.send_json(201, {"result": "nonce revealed",
                                    "agency": agency})

    def _rotation_cancel(self, rec, d):
        """1.2.3 (R6): an OPEN (unpublished) cycle can be
        cancelled. 1.2.2 had no such path: a member who withheld
        its reveal past the cycle start — or a single mistyped
        cycle_start — deadlocked the ceremony permanently
        (publish 409s forever, a new commit 409s, the pending
        marker never clears; recovery was manual SQL — round 6,
        Gemini F2 / seat 2 F6c). Before any reveal, a supervisor
        cancels alone. Once a reveal exists, nonces are public
        and the cancel is two-key: a supervisor requests, the
        auditor confirms — the same pattern as ROTATION_VOID,
        bound to the cycle_start it was requested against."""
        pending_raw = _meta_get("rotation_pending")
        if not pending_raw:
            return self.send_json(409, {
                "error": "no rotation cycle is open — nothing to "
                         "cancel"})
        pending = json.loads(pending_raw)
        cycle_start = pending["cycle_start"]
        named = (d.get("cycle_start") or "").strip()
        if named and named != cycle_start:
            return self.send_json(409, {
                "error": "the open cycle starts %s" % cycle_start})
        revealed = db.execute(
            "SELECT COUNT(*) FROM rotation_contributions WHERE "
            "cycle_start=? AND nonce IS NOT NULL",
            (cycle_start,)).fetchone()[0]

        def _clear(by_fields):
            # 1.2.4 (S5): tombstone BEFORE the delete — the
            # cancelled ceremony's contributions must not replay
            # into a restarted ceremony for the same cycle_start.
            self._rotation_tombstone(cycle_start)
            db.execute(
                "DELETE FROM rotation_contributions WHERE "
                "cycle_start=?", (cycle_start,))
            db.execute("DELETE FROM meta WHERE "
                       "key='rotation_pending'")
            db.execute("DELETE FROM meta WHERE "
                       "key='rotation_cancel_by'")
            chain.append("ROTATION_CANCEL", dict(
                {"cycle_start": cycle_start, "reveals": revealed},
                **by_fields))
            db.commit()

        if revealed == 0:
            if not role_is(rec, "supervisor"):
                return self.send_json(403, {
                    "error": "cancelling an open cycle is "
                             "supervisor-only"})
            _clear({"by": rec["user"]})
            return self.send_json(200, {
                "result": "open rotation cycle cancelled",
                "cycle_start": cycle_start})
        cancel_raw = _meta_get("rotation_cancel_by")
        cancel_rec = {}
        if cancel_raw:
            try:
                cancel_rec = json.loads(cancel_raw)
            except ValueError:
                cancel_rec = {}
        if role_is(rec, "supervisor") \
                and cancel_rec.get("cycle_start") != cycle_start:
            db.execute(
                "INSERT INTO meta(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value",
                ("rotation_cancel_by", json.dumps(
                    {"by": rec["user"], "cycle_start": cycle_start})))
            chain.append("ROTATION_CANCEL_REQUEST", {
                "cycle_start": cycle_start, "by": rec["user"]})
            db.commit()
            return self.send_json(200, {
                "result": "cancel recorded — the auditor must "
                          "confirm (reveals already exist for this "
                          "cycle)"})
        if role_is(rec, "auditor") and cancel_rec.get(
                "cycle_start") == cycle_start:
            if rec["user"] == cancel_rec.get("by"):
                return self.send_json(403, {
                    "error": "the two-key rule forbids confirming "
                             "your own cancel request"})
            _clear({"requested_by": cancel_rec.get("by"),
                    "by": rec["user"]})
            return self.send_json(200, {
                "result": "open rotation cycle cancelled",
                "cycle_start": cycle_start})
        return self.send_json(403, {
            "error": "with reveals on file, cancel is "
                     "supervisor-then-auditor, two keys"})

    def _rotation_publish(self, rec, d):
        # Q23: publish completes the commit-reveal ceremony opened
        # by _rotation_commit. The seed is SHA-256 over the members'
        # REVEALED nonces — committed before any reveal, so no
        # party (the publisher included) could predict or bias the
        # pairing. A client-supplied seed is still refused outright.
        if d.get("seed"):
            return self.send_json(400, {
                "error": "the rotation seed comes from the members' "
                         "revealed nonces — a publisher-supplied "
                         "seed is refused"})
        params = self._rotation_params(d)
        if params is None:
            return
        members, cycle_start, period = params
        pending_raw = _meta_get("rotation_pending")
        if not pending_raw:
            return self.send_json(409, {
                "error": "no rotation cycle is open — commit the "
                         "cycle and collect every member's reveal "
                         "first (POST /compact/rotation/commit)"})
        pending = json.loads(pending_raw)
        if pending["cycle_start"] != cycle_start \
                or pending["period_days"] != period \
                or sorted(pending["members"]) != members:
            return self.send_json(409, {
                "error": "publish must match the open commit "
                         "(cycle %s, %d days, members %s)"
                         % (pending["cycle_start"],
                            pending["period_days"],
                            ", ".join(sorted(pending["members"])))})
        err = self._rotation_chaining_error(cycle_start)
        if err:
            return self.send_json(409, {"error": err})
        rows = db.execute(
            "SELECT agency, nonce FROM rotation_contributions WHERE "
            "cycle_start=?", (cycle_start,)).fetchall()
        nonces = {a: n for a, n in rows if n}
        missing = [m for m in members if m not in nonces]
        if missing:
            return self.send_json(409, {
                "error": "cannot publish — nonces not yet revealed "
                         "for: %s" % ", ".join(missing)})
        seed = sha(sentinel.canonical_bytes({
            "members": members, "cycle_start": cycle_start,
            "nonces": {m: nonces[m] for m in members}}).decode())
        built = sentinel.rotation_schedule(members, seed)
        rounds = built["rounds"]
        mode = built["mode"]
        # S7: a rotation schedule is signed with the Ed25519 signing
        # key when one is available. 1.2.2 (Q23): the signed portion
        # covers members, seed, rounds, cycle_start AND period_days
        # (sentinel.rotation_signed_portion) — 1.2.1's portion left
        # the period alterable under a valid signature.
        sched_doc = {"version": "1.2.4", "members": members,
                     "seed": seed, "rounds": rounds,
                     "cycle_start": cycle_start,
                     "period_days": period,
                     "nonces": {m: nonces[m] for m in members},
                     "chain_root": chain.root(), "mode": mode}
        sig = None
        if SIGNING_PRIV:
            sig = sentinel.sign_bytes(
                SIGNING_PRIV, sentinel.canonical_bytes(
                    sentinel.rotation_signed_portion(sched_doc)))
        if sig:
            sched_doc["sig"] = sig
            sched_doc["sig_alg"] = "ed25519"
            # 1.2.3 (R6/Gemini M4): the publisher's public key
            # travels WITH the schedule — 1.2.2 omitted it, so
            # rotation.py --verify --pubkey-fingerprint could
            # never be satisfied from a Janus-published document.
            # The signed portion now also binds the nonces
            # (sentinel.rotation_signed_portion), so a stripped
            # or substituted nonce breaks the signature.
            sched_doc["pubkey"] = SIGNING_PUB_PEM
        sched_json = json.dumps(sched_doc, sort_keys=True)
        sched_hash = sha(sched_json)
        db.execute(
            "INSERT INTO rotation_schedules(cycle_start, period_days, "
            "members_count, schedule_hash, schedule, published_by, "
            "published_ts) VALUES(?,?,?,?,?,?,?)",
            (cycle_start, period, len(members), sched_hash, sched_json,
             rec["user"], now_iso()))
        db.execute("DELETE FROM meta WHERE key='rotation_pending'")
        db.execute("DELETE FROM meta WHERE key='rotation_void_by'")
        chain.append("ROTATION_PUBLISH", {
            "cycle_start": cycle_start, "period_days": period,
            "members": members, "seed_hash": sha(seed)[:16],
            "sched_hash": sched_hash, "signed": bool(sig),
            "ceremony": "commit-reveal", "by": rec["user"]})
        db.commit()
        return self.send_json(201, {
            "result": "rotation schedule published",
            "cycle_start": cycle_start, "period_days": period,
            "members": members, "schedule": rounds,
            "sched_hash": sched_hash, "seed": seed,
            "sig": sig, "sig_alg": "ed25519" if sig else None})

    def _share_query(self, rec, d):
        # S8/S10: reciprocal-audit data sharing. The caller must BE
        # the partner (a partner-role account whose username IS the
        # agency). The gate has two legs, both read fresh on every
        # call: (a) the LATEST compact_audits row for the partner is
        # ok AND <=26h old — any newer failure closes the gate
        # immediately, no manual suspension needed; (b) the partner's
        # latest verified receipt names our NEWEST checkpoint.
        # Shares are capped at Tier 2, require case_ref + why +
        # basis_type, and the partner's free text is stored in the
        # DB only — the chain carries why_hash (S11). The
        # stale-config fail-closed rule applies (S10/S13).
        if self.config_closed():
            return
        agency = (d.get("agency") or "").strip()
        # A21: the agency field is scrubber-EXEMPT because registered
        # agency ids are configuration. Caller-supplied text that is
        # NOT a registered partner is not configuration — it is a
        # stranger's string, and it never reaches the permanent
        # chain raw: unregistered agencies chain as a hash.
        registered = db.execute(
            "SELECT 1 FROM partners WHERE agency=?",
            (agency,)).fetchone() is not None

        def chain_agency():
            return {"agency": agency} if registered else {
                "agency_hash": sha(agency)[:16]}

        def blocked(missing, **extra):
            fields = dict(chain_agency())
            fields["missing"] = missing
            fields["user"] = rec["user"]
            fields.update(extra)
            # 1.2.2 (Q15): a refused share is still chained — but
            # throttled, so a partner (or an impersonator)
            # hammering the gate cannot grow the permanent chain
            # without bound. 1.2.3 (R13): the throttle keys on the
            # AUTHENTICATED identity, never on caller-supplied
            # text — 1.2.2 keyed it on the agency string in the
            # request body, so varying that string minted one
            # permanent, unattributed chain entry per request
            # (round 6, seat 2 F8). The entry names the caller.
            _chain_throttled("SHARE_BLOCKED",
                             rec["user"] + "|" + missing, fields)
            db.commit()
            return self.send_json(403, {"error": "SHARE_BLOCKED",
                                        "missing": missing,
                                        "agency": agency})
        if not role_is(rec, "partner") or rec["user"] != agency:
            return blocked("partner_identity")
        prow = db.execute("SELECT status FROM partners WHERE agency=?",
                          (agency,)).fetchone()
        if not prow or prow[0] != "active":
            return blocked("partner_inactive")
        # P1/A2: the Tier 2 cap is the Compact's core promise, and
        # 1.2 enforced it with `tier > 2 or tier < 1` on a value it
        # then branched on loosely — tier=1 (and JSON true, which
        # Python reads as 1) ran a FULL historical search. Now the
        # ONLY accepted share tier is the integer 2; anything else
        # is SHARE_BLOCKED with the refused tier chained as a coded
        # value (type + value, never free text).
        tier = d.get("tier", 2)
        if type(tier) is not int or tier != 2:
            coded = tier if isinstance(tier, (int, bool)) \
                else type(tier).__name__
            return blocked("tier", tier_refused=coded)
        basis_type = (d.get("basis_type") or "").strip().lower()
        if basis_type not in BASIS_TYPES:
            return blocked("basis_type")
        # P7: the gate is evaluated at query time by the one helper
        # (fresh audit, existing newest checkpoint, matching +
        # verified + fresh receipt).
        missing = share_gate_missing(agency)
        if missing:
            return blocked(missing)
        why = (d.get("why") or "").strip()
        case_ref = (d.get("case_ref") or "").strip()
        if not why or not case_ref:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "agency": agency,
                                     "reason": "no_justification"})
            return self.send_json(403, {
                "error": "share queries require case_ref and why"})
        # The partner's case_ref is THEIR reference — it is recorded
        # as such, never validated against our case list (we cannot
        # validate another agency's cases; the Compact's audit is
        # what vouches for their gatekeeping). The catch-all ban
        # still applies: a partner may not launder a query through
        # a PATROL/TEST reference either.
        if any(p in case_ref.upper() for p in BANNED_CASE_PATTERNS):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "agency": agency,
                                     "reason": "case_banned"})
            return self.send_json(403, {"error": CASE_GATE_MSGS[
                "case_banned"]})
        # 60 queries per partner per rolling hour (S10), counted
        # from the SHARE_OUT chain entries themselves — the limit
        # survives even a cleared share_queries table.
        hour_ago = (datetime.now(timezone.utc)
                    - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        count = db.execute(
            "SELECT COUNT(*) FROM audit WHERE kind='SHARE_OUT' AND "
            "ts>=? AND payload LIKE ?",
            (hour_ago, '%"agency":' + json.dumps(agency) + '%')
        ).fetchone()[0]
        if count >= 60:
            chain.append("SHARE_RATE_LIMIT", {"agency": agency,
                                              "window": "1h", "cap": 60})
            db.commit()
            return self.send_json(429, {
                "error": "share rate limit: 60 queries per partner per "
                         "hour"})
        frag, ferr = validate_fragment(d.get("plate_fragment"))
        if ferr:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "agency": agency,
                                     "reason": ferr})
            return self.send_json(400, {"error": FRAGMENT_MSGS[ferr]})
        results = run_search(frag, "tier2")
        n = len(results["reads"]) + len(results["hits"])
        # 1.2.2 (Q7): the partner's case_ref is stored KEYED, like
        # every other case reference in the system — 1.2.1 stored
        # it raw, and the registry had to allowlist the column,
        # which made partner-controlled permanent plate-text
        # storage possible (round 5, ChatGPT F5C).
        db.execute(
            "INSERT INTO share_queries(agency, case_ref, why, "
            "basis_type, plate_ref, tier, result_count, outcome, ts) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (agency, case_hash(case_ref), why, basis_type,
             frag_ref(frag), tier, n, "completed", now_iso()))
        out_fields = {"agency": agency, "tier": tier,
                      "case_hash": case_hash(case_ref),
                      "why_hash": why_hash(why),
                      "plate_ref": frag_ref(frag),
                      "result_count": n}
        if "tier" not in d:
            # Q27: the accepted default is visible in the record,
            # not just in the code.
            out_fields["tier_defaulted"] = True
        chain.append("SHARE_OUT", out_fields)
        db.commit()
        return self.send_json(200, {"result": "share completed",
                                    "agency": agency, "tier": tier,
                                    "results": results})
    def _rotation_status(self):
        row = db.execute(
            "SELECT cycle_start, period_days, schedule_hash, schedule, "
            "published_ts FROM rotation_schedules ORDER BY id DESC "
            "LIMIT 1").fetchone()
        if not row:
            return self.send_json(200, {"active": False})
        start, period, sched_hash, sched_json, published_ts = row
        doc = json.loads(sched_json)
        members = doc.get("members", [])
        rounds_def = doc.get("rounds", [])
        start_date = date.fromisoformat(start)
        cycle_end = start_date + timedelta(days=period * len(members))
        rounds = []
        # 1.2.2: cycle arithmetic is UTC (1.2.1 used the host's
        # local date — round 5, Gemini N9).
        today = datetime.now(timezone.utc).date()
        for i, rd in enumerate(rounds_def):
            ws = start_date + timedelta(days=i * period)
            we = ws + timedelta(days=period - 1)
            auditor = rd.get("auditor")
            audited = rd.get("audited")
            lo = ws.isoformat() + "T00:00:00Z"
            hi = we.isoformat() + "T23:59:59Z"
            # P9: "filed" is direction-correct and success-only.
            # Audits OF us are the auditor's verified receipts in
            # compact_receipts; audits BY us are our ok=1 rows in
            # compact_audits against the AUDITED agency. 1.2 counted
            # both tables against the auditor regardless of
            # direction and regardless of ok — a failed audit
            # 'filed', and a receipt about someone else counted.
            filed_of = db.execute(
                "SELECT COUNT(*) FROM compact_receipts WHERE agency=? "
                "AND verified=1 AND received_ts>=? AND received_ts<=?",
                (auditor, lo, hi)).fetchone()[0]
            filed_by = db.execute(
                "SELECT COUNT(*) FROM compact_audits WHERE agency=? "
                "AND ok=1 AND ts>=? AND ts<=?",
                (audited, lo, hi)).fetchone()[0]
            # 1.2.3 (R6): witness duty belongs to the round's
            # DESIGNATED attester — the member neither auditing
            # nor audited (or, in a two-member cycle, the round's
            # auditor). 1.2.2 counted attestations filed under the
            # AUDITOR's name, so the duty could be 'done' by a
            # filing the witness rules would never have accepted
            # from that agency (round 6, Vesper F8).
            # 1.2.4 (S5): the same designation helper the filing
            # endpoint enforces, and the count DISTINGUISHES a
            # positive attestation from an adverse one — 1.2.3
            # counted filings, so a witness reporting a FAILED
            # verification satisfied the duty exactly like one
            # reporting a pass (round 7, ChatGPT R7-12). At n=2
            # the designated witness is the round's own auditor
            # and the round is labeled a self-attestation.
            designated, self_att = _designated_witness(
                members, auditor, audited, i + 1)
            witness = db.execute(
                "SELECT COUNT(*) FROM witness_attestations WHERE "
                "agency=? AND cycle_start=? AND round_no=?",
                (designated, start, i + 1)).fetchone()[0]
            witness_pos = db.execute(
                "SELECT COUNT(*) FROM witness_attestations WHERE "
                "agency=? AND cycle_start=? AND round_no=? "
                "AND ok=1", (designated, start, i + 1)).fetchone()[0]
            witness_adv = db.execute(
                "SELECT COUNT(*) FROM witness_attestations WHERE "
                "agency=? AND cycle_start=? AND round_no=? "
                "AND ok=0", (designated, start, i + 1)).fetchone()[0]
            # The auditor's OWN duty in this round, judged from the
            # table that records it: if the auditor is US, our duty
            # is the audit we owed the audited agency (compact_
            # audits); if the audited agency is US, the auditor's
            # duty is their receipt (compact_receipts). A round
            # between two OTHER members is witnessed, not recorded
            # here — it cannot ground a delinquency finding either
            # way, and says so.
            completed = we < today
            if auditor == AGENCY:
                filed = filed_by > 0
            elif audited == AGENCY:
                filed = filed_of > 0
            else:
                filed = None
            rounds.append({
                "round": i + 1, "auditor": auditor,
                "audited": audited,
                "window_start": ws.isoformat(),
                "window_end": we.isoformat(),
                "completed": completed,
                "audits_of_us_filed": filed_of,
                "audits_by_us_filed": filed_by,
                "witness_attestation_filed": witness > 0,
                "witness_designated": designated,
                "witness_attestations_positive": witness_pos,
                "witness_attestations_adverse": witness_adv,
                "witness_self_attestation": self_att,
                "delinquent": bool(completed and filed is False)})
        # P9 delinquency: PER AGENCY, across COMPLETED rounds only
        # — an agency that owed a filing in a completed round and
        # filed in none of its completed rounds. Future rounds never
        # count (1.2 listed a not-yet-started cycle's members as
        # delinquent on publication day).
        owed, filed_any = {}, {}
        for r in rounds:
            if not r["completed"]:
                continue
            a = r["auditor"]
            if a == AGENCY:
                owed[a] = owed.get(a, 0) + 1
                if r["audits_by_us_filed"]:
                    filed_any[a] = True
            elif r["audited"] == AGENCY:
                owed[a] = owed.get(a, 0) + 1
                if r["audits_of_us_filed"]:
                    filed_any[a] = True
        delinquent = sorted(a for a in owed if not filed_any.get(a))
        return self.send_json(200, {
            # 1.2.3 (R6/Gemini M3): the same UTC clock as the round
            # windows — 1.2.2 mixed host-local date.today() in here.
            "active": today < cycle_end,
            "cycle_start": start, "period_days": period,
            "members": members, "sched_hash": sched_hash,
            "published_ts": published_ts,
            "rounds": rounds,
            "delinquent_agencies": delinquent})

    # ---------------- DELETE ----------------
    def do_DELETE(self):
        self._resp = None
        if not self._read_body():
            return
        with DBLOCK:
            try:
                _flush_config_chain()
                self._delete()
                if db.in_transaction:
                    db.commit()
            except Exception as exc:  # a handler bug must still answer
                try:
                    db.rollback()
                except Exception:
                    pass
                self._resp = (500, {"error": f"internal: {exc}"})
            try:
                chain.flush_deferred()
            except Exception:
                pass
        self._flush_response()

    def _delete(self):
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        if self.config_closed():
            return
        if urlparse(self.path).path != "/hotlist":
            return self.send_json(404, {"error": "no such route"})
        if not role_is(rec, "supervisor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hotlist remove",
                                     "reason": "role"})
            return self.send_json(403, {"error": "hotlist removal is "
                                               "supervisor-only"})
        d = self.body_json()
        # P13/A24: removal DELETES the membership row. 1.2 only
        # deactivated — and deactivated the WRONG row silently when
        # the caller omitted the entry's state: it answered 200
        # "membership deactivated", chained HOTLIST_REMOVE, and the
        # entry stayed active. Now the membership is identified by
        # the fields given (plate, plus state / list_source /
        # case_no when supplied); exactly one ACTIVE membership
        # must match — no match is a 404, several matches without
        # enough identifiers is a 400 — and the row is deleted.
        plate = normalize_plate(d.get("plate") or "")
        if not plate:
            return self.send_json(400, {"error": "plate is required"})
        clauses = ["plate=?", "active=1"]
        params = [plate]
        if d.get("state"):
            clauses.append("state=?")
            params.append(str(d["state"]).strip().upper())
        source = d.get("list_source") or d.get("list_name")
        if source:
            clauses.append("list_source=?")
            params.append(str(source).strip())
        if d.get("case_no"):
            clauses.append("case_no=?")
            params.append(d["case_no"])
        rows = db.execute(
            "SELECT state, list_source, case_no FROM hotlist_members "
            "WHERE " + " AND ".join(clauses), params).fetchall()
        if not rows:
            return self.send_json(404, {
                "error": "no active hot-list membership matches — "
                         "nothing was removed"})
        if len(rows) > 1:
            return self.send_json(400, {
                "error": "that plate has %d active memberships — "
                         "name the state and list_source to remove "
                         "one" % len(rows)})
        m_state, m_source, m_case = rows[0]
        db.execute(
            "DELETE FROM hotlist_members WHERE plate=? AND state=? "
            "AND list_source=? AND case_no IS ?",
            (plate, m_state, m_source, m_case))
        chain.append("HOTLIST_REMOVE", {
            "plate_ref": plate_ref(plate), "by": rec["user"],
            "list_source": m_source})
        db.commit()
        return self.send_json(200, {"result": "membership deleted",
                                    "plate": plate,
                                    "list_source": m_source})

    # ---------------- GET ----------------
    def do_GET(self):
        self._resp = None
        # 1.2.2 (Q18 + P13/A18, composed): the chain verify must
        # satisfy BOTH rounds' findings — an anonymous caller must
        # never trigger a scan (round 5, Claude R5-02: six
        # concurrent anonymous calls at a 250k chain, ~180MB
        # apiece), AND the scan must never run under DBLOCK, where
        # it stalls every other request (round 4, A18). So: for the
        # two verify-consuming routes, authenticate FIRST against
        # the in-memory user table (auth() has no DB side effects
        # and chains nothing), warm the single-flight cache OUTSIDE
        # the lock, and let _get re-authenticate properly inside
        # it. Anonymous or bad-credential requests skip the warm
        # entirely and are refused inside, uncomputed.
        # 1.2.3 (R4): the warm is also ROLE-gated — round 6
        # (Gemini F6) showed ANY authenticated account, including a
        # patrol credential that will be refused the data, warming
        # (and paying for) the scan. Only roles that can consume a
        # verify warm it. auth() itself no longer chains (R4), so
        # the pre-auth path has no DB side effects at all now.
        _base = urlparse(self.path).path
        if _base in ("/health", "/audit/verify"):
            _rec0 = auth(self)
            if _rec0 and role_is(_rec0, "supervisor", "auditor", "chain_auditor", "jobs"):
                chain_ok_cached()
        with DBLOCK:
            try:
                _flush_config_chain()
                self._get()
                if db.in_transaction:
                    db.commit()
            except Exception as exc:  # a handler bug must still answer
                try:
                    db.rollback()
                except Exception:
                    pass
                self._resp = (500, {"error": f"internal: {exc}"})
            try:
                chain.flush_deferred()
            except Exception:
                pass
        self._flush_response()

    def _get(self):
        path = self.path
        base = urlparse(path).path
        # S5: the unauthenticated liveness probe is /ping, and it
        # answers with liveness only — nothing about the system.
        if base == "/ping":
            return self.send_json(200, {"alive": True})
        if self.locked_out():
            return
        # Authenticate once for everything else (S5: /health
        # requires auth now). The chain_auditor fence (S9) runs
        # before the per-endpoint role checks.
        rec = self.need_auth()
        if not rec:
            return
        if only_role(rec, "chain_auditor") \
                and base not in CHAIN_AUDITOR_GETS:
            return self.send_json(403, {
                "error": "the chain_auditor role may only read the "
                         "audit chain and the checkpoint"})
        q = parse_qs(urlparse(path).query)
        if base == "/health":
            if not role_is(rec, "supervisor", "auditor", "jobs"):
                return self.send_json(403, {"error": "health detail is "
                                                   "supervisor/auditor/"
                                                   "jobs only"})
            return self._health(rec)
        if base in ("/audit", "/audit/root", "/audit/verify",
                    "/audit/range"):
            if not role_is(rec, *AUDIT_READ_ROLES):
                return self.send_json(403, {"error": "audit chain is "
                                                   "supervisor/auditor/"
                                                   "chain_auditor only"})
            if base == "/audit":
                # P13/A17: the limit is a contract, not a clamp —
                # 1.2's min(limit, 1000) let limit=-1 through to
                # SQLite, where LIMIT -1 means UNLIMITED: the whole
                # chain in one response, under the global lock, for
                # any chain_auditor. Out-of-contract is a 400.
                raw_limit = q.get("limit", ["200"])[0]
                try:
                    limit = int(raw_limit)
                except (TypeError, ValueError):
                    return self.send_json(400, {
                        "error": "limit must be an integer in "
                                 "1..1000"})
                if limit < 1 or limit > 1000:
                    return self.send_json(400, {
                        "error": "limit must be an integer in "
                                 "1..1000"})
                rows = chain.entries(limit)
                return self.send_json(200, {"entries": rows})
            if base == "/audit/root":
                return self.send_json(200, {"root": chain.root(),
                                            "entries": chain.count()})
            if base == "/audit/verify":
                # P13: the SAME 60s cached, detached verify /health
                # uses — computed before DBLOCK was taken (do_GET),
                # never a fresh full scan under the lock.
                return self.send_json(
                    200, chain_ok_cached())
            # S8: the range endpoint the Compact auditor uses to
            # recompute our chain independently. Raw payloads only —
            # the verifier rehashes the exact bytes itself.
            # 1.2.4 (S9): through _strict_id — 1.2.3's raw int()
            # let to_seq=10**30 sail past the span check and die
            # at bind time (Qwen F-C).
            frm = _strict_id(q.get("from_seq", ["1"])[0])
            to = _strict_id(q.get("to_seq", ["0"])[0])
            if frm is None or to is None:
                return self.send_json(400, {"error": "from_seq and "
                                                   "to_seq must be "
                                                   "integers"})
            if frm < 1 or to < frm or to - frm > 1000:
                return self.send_json(400, {"error": "range must be "
                                                   "from_seq>=1, "
                                                   "to_seq>=from_seq, "
                                                   "span<=1000"})
            return self.send_json(200, {"entries": chain.entries_range(
                frm, to), "from_seq": frm, "to_seq": to})
        if base == "/search":
            # No DATA_ROLES pre-gate here: as in 1.1, patrol may run
            # Tier 2 searches; _run_tiered_search + janus_gate refuse
            # auditor/service/partner roles themselves.
            if self.config_closed():
                return
            body, err = self._run_tiered_search(rec, q)
            if err:
                return err
            return self.send_json(200, body)
        if base == "/hits":
            if not role_is(rec, *DATA_ROLES):
                return self.deny_service_role(rec, "hits read")
            if self.config_closed():
                return
            # S3 + P3: suppressed hits are not listed here AT ALL —
            # not even for a supervisor — and suppression is judged
            # LIVE (hit_suppressed_now), not by the ingest-time
            # stamp: a hit whose plate came under an order an hour
            # ago is in the supervisor queue NOW. They live in
            # /suppressed-hits, and nowhere else.
            # 1.2.2 (Qwen F2): the filter runs BEFORE the limit that
            # shapes the answer — 1.2.1 fetched 400 rows, filtered
            # in Python, then cut to 200, so a run of suppressed
            # hits both shrank the page and leaked their existence
            # through its size. The text leg filters in SQL; the
            # keyed leg pages by id until 200 visible rows are
            # collected or the table is exhausted.
            rows = []
            cursor = None
            while len(rows) < 200:
                sql = ("SELECT id,ts,cam,read_plate,entry_plate,"
                       "state,list_name,category,status,suppressed "
                       "FROM hits WHERE" + _SUPPRESSED_HIT_SQL)
                params = []
                if cursor is not None:
                    sql += " AND hits.id<?"
                    params.append(cursor)
                sql += " ORDER BY id DESC LIMIT 400"
                batch = db.execute(sql, params).fetchall()
                if not batch:
                    break
                cursor = batch[-1][0]
                rows.extend(r for r in batch
                            if not hit_suppressed_now(r[3], r[4]))
                if len(batch) < 400:
                    break
            rows = rows[:200]
            chain.append("HITS_VIEW", {"by": rec["user"],
                                       "count": len(rows)})
            return self.send_json(200, {"hits": [
                hit_public(dict(zip(("id", "ts", "cam", "read_plate",
                                     "entry_plate", "state", "list_name",
                                     "category", "status", "suppressed"),
                                    r)))
                for r in rows]})
        if base == "/suppressed-hits":
            if not role_is(rec, "supervisor"):
                return self.send_json(403, {"error": "the suppressed-hit "
                                                   "queue is supervisor-"
                                                   "only"})
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,"
                "list_name,category,status,suppressed FROM hits "
                "ORDER BY id DESC").fetchall()
            # P3: the queue is also live — a hit whose order was
            # RELEASED leaves the queue even if its stamp still says
            # suppressed, and a post-hoc order puts its hit here.
            rows = [r for r in rows if hit_suppressed_now(r[3], r[4])]
            chain.append("SUPPRESSED_HITS_VIEW", {"by": rec["user"],
                                                  "count": len(rows)})
            return self.send_json(200, {"hits": [
                hit_public(dict(zip(("id", "ts", "cam", "read_plate",
                                     "entry_plate", "state", "list_name",
                                     "category", "status", "suppressed"),
                                    r)), show_suppressed=True)
                for r in rows]})
        if base == "/hotlist":
            if not role_is(rec, *DATA_ROLES):
                return self.deny_service_role(rec, "hotlist read")
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT plate,state,list_source,category,case_no,"
                "expires_ts FROM hotlist_members WHERE active=1 "
                "ORDER BY plate, list_source").fetchall()
            chain.append("HOTLIST_VIEW", {"by": rec["user"],
                                          "count": len(rows)})
            return self.send_json(200, {"entries": [
                {"plate": r[0], "state": r[1], "list_source": r[2],
                 "category": r[3], "case_no": r[4], "expires": r[5]}
                for r in rows]})
        if base == "/lists":
            if not role_is(rec, "supervisor", "auditor"):
                return self.send_json(403, {"error": "the list registry "
                                                   "is supervisor/auditor "
                                                   "only"})
            if self.config_closed():
                return
            return self.send_json(200, {"lists": list_registry_names()})
        if base == "/stats":
            if not role_is(rec, *DATA_ROLES):
                return self.deny_service_role(rec, "stats read")
            if self.config_closed():
                return
            return self.send_json(200, stats_body())
        if base == "/report":
            if not role_is(rec, "supervisor", "auditor"):
                return self.send_json(403, {"error": "the effectiveness "
                                                   "report is supervisor/"
                                                   "auditor only"})
            if self.config_closed():
                return
            frm = q.get("from", [""])[0]
            to = q.get("to", ["9999-12-31T23:59:59Z"])[0]
            snap = q.get("snapshot", [None])[0]
            if snap:
                snap_id = _strict_id(snap)
                if snap_id is None:
                    return self.send_json(400, {
                        "error": "snapshot must be an integer id"})
                row = db.execute(
                    "SELECT body FROM report_snapshots WHERE id=?",
                    (snap_id,)).fetchone()
                if not row:
                    return self.send_json(404, {"error": "no such "
                                                       "snapshot"})
                # The frozen body, exactly as compiled — the
                # snapshot's immutability is the feature.
                return self.send_json(200, json.loads(row[0]))
            return self.send_json(200, compute_report(frm, to))
        if base == "/tier3/pending":
            if not role_is(rec, "supervisor", "auditor", "detective",
                                   "patrol"):
                return self.send_json(403, {"error": "role cannot read "
                                                   "the Tier 3 queue"})
            if self.config_closed():
                return
            # P12 (round 4, R17): the second key must be able to
            # JUDGE what it approves. Round 3 overcorrected this
            # queue to hashes only — an approver who cannot see the
            # fragment, the case, the justification, or the basis is
            # a rubber stamp with a key. A SUPERVISOR approver now
            # sees plate_fragment, case_no, why, auth_basis, tier,
            # requester. 1.2.2 (Q13): the AUDITOR sees the same —
            # round 5 found the outside auditor's emergency review
            # was blind (hashes only) as well as pre-emptible, and
            # spec SS8 makes that review the outside check on the
            # most sensitive path in the system. Detectives/patrol
            # see only their OWN requests and stay plate-free.
            if role_is(rec, "supervisor", "auditor"):
                rows = db.execute(
                    "SELECT id,requester,case_no,created_ts,emergency,"
                    "needs_review,plate_fragment,basis_type,why,"
                    "auth_basis FROM tier3_requests WHERE "
                    "status='PENDING' OR needs_review=1 ORDER BY id"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id,requester,case_no,created_ts,emergency,"
                    "needs_review,plate_fragment,basis_type,why,"
                    "auth_basis FROM tier3_requests WHERE "
                    "(status='PENDING' OR needs_review=1) AND "
                    "requester=? ORDER BY id",
                    (rec["user"],)).fetchall()
            out = []
            for r in rows:
                item = {"id": r[0], "request_id": r[0],
                        "requester": r[1], "created_ts": r[3],
                        "emergency": bool(r[4]),
                        "needs_review": bool(r[5]),
                        "basis_type": r[7], "tier": 3}
                if role_is(rec, "supervisor", "auditor"):
                    item.update({
                        "plate_fragment": r[6], "case_no": r[2],
                        "why": r[8], "auth_basis": r[9],
                        "case_hash": case_hash(r[2]),
                        "plate_ref": frag_ref(r[6] or "")})
                else:
                    item.update({
                        "case_hash": case_hash(r[2]),
                        "plate_ref": frag_ref(r[6] or "")})
                out.append(item)
            return self.send_json(200, {"pending": out})
        if base == "/tier3/reviews":
            if not role_is(rec, "supervisor", "auditor"):
                return self.send_json(403, {"error": "the Tier 3 review "
                                                   "queue is supervisor/"
                                                   "auditor only"})
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT id,requester,case_no,created_ts,emergency,"
                "plate_fragment,basis_type,why,auth_basis,"
                "auditor_reviewed_by,auditor_review_finding,"
                "needs_review FROM tier3_requests WHERE "
                "needs_review=1 OR (emergency=1 AND "
                "auditor_reviewed_by IS NULL AND status IN "
                "('EMERGENCY','REVIEWED')) ORDER BY id").fetchall()
            return self.send_json(200, {"reviews": [
                {"request_id": r[0], "requester": r[1],
                 "case_hash": case_hash(r[2]), "created_ts": r[3],
                 "emergency": bool(r[4]),
                 "plate_ref": frag_ref(r[5] or ""), "basis_type": r[6],
                 "plate_fragment": r[5], "case_no": r[2],
                 "why": r[7], "auth_basis": r[8],
                 "auditor_reviewed_by": r[9],
                 "auditor_review_finding": r[10],
                 "needs_review": bool(r[11]),
                 "auditor_review_pending": r[9] is None}
                for r in rows]})
        if base.startswith("/tier3/results/"):
            # S9: results are read by the requester and supervisors
            # ONLY. The auditor samples via refs and counts.
            # P13: the stale-config fail-closed rule applies here
            # too — 1.2 checked it on the POST routes and on search
            # but not on this read, the most sensitive one.
            if self.config_closed():
                return
            if not role_is(rec, "supervisor", "detective", "patrol"):
                return self.send_json(403, {
                    "error": "Tier 3 results are read by the requester "
                             "and supervisors only"})
            # 1.2.4 (S9): through _strict_id like every other id —
            # 1.2.3's raw int() here accepted negatives and died
            # as a 500 on >4300-digit strings (Qwen F-C).
            rid = _strict_id(base.rsplit("/", 1)[1])
            if rid is None:
                return self.send_json(400, {"error": "bad request id"})
            row = db.execute(
                "SELECT requester, case_no, status, results, "
                "results_count, results_read_ids, results_hit_ids, "
                "plate_fragment FROM tier3_requests WHERE id=?",
                (rid,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            requester, case_no, status, legacy_body, results_count, \
                read_ids_json, hit_ids_json, frag = row
            if not role_is(rec, "supervisor") and rec["user"] != requester:
                return self.send_json(403, {"error": "results are "
                                                   "returned to the "
                                                   "requester only"})
            if status not in ("EXECUTED", "EMERGENCY", "REVIEWED"):
                return self.send_json(409, {"error": "no results exist "
                                                   "for a request in "
                                                   "status %s" % status})
            # S2: the case gate revalidates AT READ TIME — a case
            # that closed since execution no longer opens its results.
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 results",
                                         "request": rid,
                                         "reason": reason})
                return self.send_json(403, {
                    "error": "BLOCKED at read: "
                             + CASE_GATE_MSGS[reason]})
            if legacy_body and not read_ids_json and not hit_ids_json:
                # A 1.0/1.1-era row: the stored body is legacy state
                # retention will NULL at class age. The 1.2 endpoint
                # never returns it — the detail is treated as expired.
                chain.append("TIER3_RESULTS_VIEW", {
                    "request": rid, "by": rec["user"],
                    "results_count": results_count or 0,
                    "stored_count": results_count or 0, "expired": True})
                return self.send_json(200, {
                    "result": "results detail expired (pre-1.2 stored "
                              "body)", "request_id": rid,
                    "results_count": results_count,
                    "plate_ref": frag_ref(frag or ""),
                    "expired": True})
            # S2: resolve the stored ids LIVE through the current
            # shaping layer. Suppressed rows are excluded NOW, not as
            # they were when the search ran.
            read_ids = json.loads(read_ids_json or "[]")
            hit_ids = json.loads(hit_ids_json or "[]")
            live_reads, live_hits = [], []
            if read_ids:
                placeholders = ",".join("?" * len(read_ids))
                live_reads = [dict(zip(
                    ("id", "ts", "cam", "plate", "state", "conf",
                     "cam_ts", "skew_s"), r)) for r in db.execute(
                    "SELECT id,ts,cam,plate,state,conf,cam_ts,skew_s "
                    "FROM reads WHERE id IN (%s) AND" % placeholders
                    + _SUPPRESSED_SQL.format(col="reads.plate")
                    + " ORDER BY ts",
                    tuple(read_ids)).fetchall()]
            if hit_ids:
                placeholders = ",".join("?" * len(hit_ids))
                live_hits = [dict(zip(
                    ("id", "ts", "cam", "read_plate", "entry_plate",
                     "state", "list_name", "category", "status"), r))
                    for r in db.execute(
                    "SELECT id,ts,cam,read_plate,entry_plate,state,"
                    "list_name,category,status FROM hits WHERE id IN "
                    "(%s) AND" % placeholders + _SUPPRESSED_HIT_SQL
                    + " ORDER BY ts",
                    tuple(hit_ids)).fetchall()]
            stored_n = len(read_ids) + len(hit_ids)
            live_n = len(live_reads) + len(live_hits)
            chain.append("TIER3_RESULTS_VIEW", {
                "request": rid, "by": rec["user"], "results_count": live_n,
                "stored_count": stored_n})
            if live_n == 0 and (stored_n or (results_count or 0)):
                # Everything aged out or was suppressed since
                # execution — or retention already nulled the stored
                # ids at class age (stored_n == 0 with a positive
                # execution count): the plate-free summary either
                # way. A search that truly matched nothing has
                # results_count == 0 and falls through to the empty
                # ok below.
                return self.send_json(200, {
                    "result": "results detail expired",
                    "request_id": rid,
                    "results_count": results_count,
                    "plate_ref": frag_ref(frag or ""),
                    "expired": True})
            return self.send_json(200, {
                "result": "ok", "request_id": rid,
                "results": {"reads": live_reads, "hits": live_hits},
                "results_count": live_n,
                "stored_count": stored_n,
                "expired": live_n < stored_n})
        if base == "/compact/partners":
            if not role_is(rec, "supervisor", "auditor"):
                return self.send_json(403, {"error": "partner list is "
                                                   "supervisor/auditor "
                                                   "only"})
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT agency, endpoint, status, "
                "audit_key_fingerprint FROM partners ORDER BY agency"
                ).fetchall()
            out = []
            for agency, endpoint, status, fp in rows:
                row = db.execute(
                    "SELECT ok, ts FROM compact_audits WHERE agency=? "
                    "ORDER BY ts DESC, id DESC LIMIT 1",
                    (agency,)).fetchone()
                out.append({
                    "agency": agency, "endpoint": endpoint,
                    "status": status, "suspended": status != "active",
                    "audit_key_fingerprint": fp,
                    "last_audit_ok": bool(row[0]) if row else None,
                    "last_audit_ts": row[1] if row else None,
                    "share_gate_open": share_gate_open(agency)})
            return self.send_json(200, {"partners": out})
        if base == "/compact/checkpoint":
            if not role_is(rec, "supervisor", "auditor",
                                   "chain_auditor"):
                return self.send_json(403, {"error": "checkpoint read is "
                                                   "supervisor/auditor/"
                                                   "chain_auditor only"})
            cp = read_newest_checkpoint()
            if not cp:
                return self.send_json(404, {"error": "no checkpoint "
                                                   "published yet"})
            return self.send_json(200, {"checkpoint": cp})
        if base == "/compact/rotation/status":
            if not role_is(rec, "supervisor", "auditor"):
                return self.send_json(403, {"error": "rotation status is "
                                                   "supervisor/auditor "
                                                   "only"})
            if self.config_closed():
                return
            return self._rotation_status()
        return self.send_json(404, {"error": "no such route"})

    def _run_tiered_search(self, rec, q):
        """GET /search — Tier 2 ONLY, as in 1.1 (the temporal wall,
        a required justification, the shared case gate, and the
        per-day case/fragment pattern ledger). 1.2 changes are the
        S11 ones: the chain carries case_hash/why_hash, never the
        raw case number or justification. Returns (body, None) or
        (None, error) — on error the response is already captured."""
        if role_is(rec, "auditor"):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "auditor_read_only"})
            return None, self._send_err(
                403, "auditors verify the system; they do not search it")
        raw_tier = q.get("tier", ["2"])[0]
        try:
            tier = int(raw_tier)
        except (TypeError, ValueError):
            return None, self._send_err(400, "tier must be numeric")
        if tier == 3:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "tier3_two_key"})
            return None, self._send_err(
                403, "Tier 3 search is not available at this endpoint "
                     "— use /tier3/request or /tier3/emergency")
        if tier != 2:
            return None, self._send_err(
                400, "tier must be 2 at this endpoint")
        # 'why' is the 1.0 parameter name; 'justification' is kept
        # as an accepted alias so both spellings work.
        justification = (q.get("why", [""])[0]
                         or q.get("justification", [""])[0]).strip()
        if not justification:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "no_justification"})
            return None, self._send_err(
                403, "BLOCKED: a plate search requires a justification")
        case_no = q.get("case", [""])[0] or q.get("case_id", [""])[0]
        ok, reason = janus_gate(rec, case_no)
        if not ok:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": reason})
            return None, self._send_err(
                403, CASE_GATE_MSGS.get(
                    reason, "BLOCKED: role cannot search"))
        frag, ferr = validate_fragment(q.get("plate", [""])[0])
        if ferr:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": ferr})
            return None, self._send_err(400, FRAGMENT_MSGS[ferr])
        if case_no:
            # Pattern signal: case_searches is the per-day
            # (case, fragment) ledger and case_flags marks a case's
            # first use each day — a case that suddenly starts
            # searching leaves a CASE_FLAG in the chain (with the
            # case's HASH, per S11).
            day = now_iso()[:10]
            new_case = db.execute(
                "INSERT OR IGNORE INTO case_flags(case_no, day) "
                "VALUES(?,?)", (case_no, day)).rowcount
            new_frag = db.execute(
                "INSERT OR IGNORE INTO case_searches(case_no, day, "
                "frag) VALUES(?,?,?)", (case_no, day, frag)).rowcount
            if new_case:
                chain.append("CASE_FLAG", {
                    "user": rec["user"], "case_hash": case_hash(case_no),
                    "flag": "CASE_FLAG"})
            if new_frag:
                chain.append("CASE_FLAG", {
                    "user": rec["user"], "case_hash": case_hash(case_no),
                    "flag": "CASE_FLAG (new fragment under case today)",
                    "plate_ref": frag_ref(frag)})
        results = run_search(frag, "tier2")
        n = len(results["reads"]) + len(results["hits"])
        chain.append("QUERY", {
            "user": rec["user"], "type": "tier2 search", "tier": 2,
            "case_hash": case_hash(case_no),
            "why_hash": why_hash(justification),
            "plate_ref": frag_ref(frag), "result_count": n,
            "window_hours": TIER2_WINDOW_H})
        db.commit()
        return results, None

    def _send_err(self, code, msg):
        self.send_json(code, {"error": msg})
        return (code, msg)

    def _health(self, rec):
        n_chain = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        n_reads = db.execute("SELECT COUNT(*) FROM reads").fetchone()[0]
        n_hits = db.execute("SELECT COUNT(*) FROM hits").fetchone()[0]
        n_pending = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE status='PENDING' "
            "OR needs_review=1").fetchone()[0]
        n_supp = db.execute("SELECT COUNT(*) FROM suppressions WHERE "
                            "active=1").fetchone()[0]
        jobs, overdue = jobs_status()
        cams, silent_cams = cameras_status()
        try:
            sink = chain.sink_status()
        except Exception:
            sink = {"enabled": False, "ok": True}
        # 1.2.4 (S1): health is not green over an unresolved
        # delivery gap — a sink with committed entries still
        # undelivered (pending > 0) degrades health BY NAME, where
        # 1.2.3's flush could discard the obligation and report
        # green over the hole (round 7, register A1/A2).
        sink_up = (not sink.get("enabled")) or (
            bool(sink.get("ok")) and sink.get("pending", 0) == 0)
        # 1.2.4 (S11): an unacknowledged recovery-code use holds
        # health down until a supervisor acknowledges it.
        totp = _totp_status()
        # S5: a broken chain degrades health BY NAME — 1.1 computed
        # chain_ok and then left it out of `degraded`, so a service
        # with a broken audit chain reported itself healthy.
        # P13: the verify was computed in do_GET BEFORE DBLOCK was
        # taken (detached + cached); it is never computed here,
        # under the lock.
        cv = chain_ok_cached()
        chain_ok = bool(cv.get("ok"))
        # S1/S5: a retention breach is named, store by store.
        breach = retention_breach()
        destroy_overdue = evidence_destroy_overdue()
        anchor_bad = anchor_mismatch()
        cfg = config_status()
        cfg_stale = any(v.get("stale") for k, v in cfg.items()
                        if isinstance(v, dict))
        # 1.2.2: three more named degradations join the ok
        # computation. Overdue holds (round 5, Claude R5-08: 1.2.1
        # REPORTED them but health stayed ok); cameras that have
        # reported before and gone silent (a never-reported camera
        # is an install state, reported by name but not a
        # degradation of a running system); and the Q1 migration
        # marker — legacy rows the upgrade could not repair stay
        # visible here until an operator resolves them. Stranded
        # evidence bundles surface through retention_breach (the
        # registry's evidence-folder branch, Q7).
        holds_overdue = overdue_holds()
        silent_after_report = [c for c, v in cams.items()
                               if v.get("status") == "silent"]
        migration_unrepaired = _meta_get("migration_unrepaired")
        # 1.2.3 (R2/R15): the migration's own status object —
        # installation readiness, distinct from the operational
        # degradations below it. A boot whose repairs are
        # incomplete, or that holds orders it cannot verify, says
        # so here by name; a key-locked boot reports
        # locked_pending (the repairs wait for the first unlocked
        # boot, Q2).
        mig_raw = _meta_get("migration_status")
        if mig_raw:
            try:
                migration_status = json.loads(mig_raw)
            except ValueError:
                migration_status = {"state": "unreadable"}
        elif KEY_LOCKED:
            migration_status = {"state": "locked_pending"}
        else:
            migration_status = {"state": "not_recorded"}
        # R15 (round 6 judgment call): the strip-not-raise scrubber
        # stands, but its activity is no longer invisible — the
        # count of CHAIN_SCRUB_FLAG entries rides in /health.
        n_scrub_flags = db.execute(
            "SELECT COUNT(*) FROM audit WHERE kind="
            "'CHAIN_SCRUB_FLAG'").fetchone()[0]
        ok_all = (chain_ok and not overdue and sink_up and not anchor_bad
                  and not breach and destroy_overdue == 0
                  and not holds_overdue and not silent_after_report
                  and not migration_unrepaired
                  and migration_status.get("state") != "incomplete"
                  and not cfg_stale and not cfg["fail_closed"]
                  and not totp["recovery_alerts"])
        return self.send_json(200, {
            "service": "janus", "version": VERSION, "ok": ok_all,
            # 1.2.4 (S4): the install mode is a health fact — a demo
            # install says so, and a users file CLAIMING demo on a
            # production install is visible as the inert flag it is.
            "demo_mode": DEMO_MODE,
            "demo_file_flag": USERS_FILE_DEMO,
            "degraded": {
                "jobs_overdue": overdue,
                "sink_up": sink_up,
                "chain_ok": chain_ok,
                "anchor_mismatch": anchor_bad,
                "anchor_detail": (json.loads(_meta_get("anchor_mismatch"))
                                  if anchor_bad else None),
                "config": cfg,
                "retention_breach": breach,
                "evidence_destroy_overdue": destroy_overdue,
                "cameras_silent": silent_cams,
                "cameras_silent_after_report": silent_after_report,
                "overdue_holds": len(holds_overdue),
                "migration_unrepaired": (json.loads(
                    migration_unrepaired) if migration_unrepaired
                    else None),
                "totp_recovery_alerts": totp["recovery_alerts"],
            },
            "totp": totp,
            "chain_entries": n_chain, "chain_ok": chain_ok,
            "chain_verify": cv,
            "retention_breach": bool(breach),
            "retention_days": RETENTION_DAYS,
            "hold_days": HOLD_DAYS,
            "tier2_window_hours": TIER2_WINDOW_H,
            "tier2_window_h": TIER2_WINDOW_H,
            "anchor_mismatch": anchor_bad,
            "cameras_silent": silent_cams,
            "cameras_silent_after_report": silent_after_report,
            "overdue_holds": len(holds_overdue),
            "migration_unrepaired": bool(migration_unrepaired),
            "migration_status": migration_status,
            "chain_scrub_flags": n_scrub_flags,
            "config_stale": any(v.get("stale") for k, v in cfg.items()
                                if isinstance(v, dict)),
            "config_stale_since": next(
                (v.get("stale_since") for k, v in cfg.items()
                 if isinstance(v, dict) and v.get("stale")), None),
            "sentinel_sink_ok": sink_up,
            "retention_oldest_read_age_h":
                retention_oldest_read_age_h(),
            "registry_version": REGISTRY_VERSION,
            "reads": n_reads, "hits": n_hits,
            "tier3_pending": n_pending,
            "active_suppressions": n_supp,
            "cameras": cams,
            "jobs": jobs,
            "sink": sink,
        })
# ---------------- rotation schedule builder (S12) ----------------
def build_schedule(members, seed):
    """1.2.2 (Q23): ONE schedule builder, owned by sentinel.py and
    shared with scripts/rotation.py by import — 1.2.1 carried two
    implementations that diverged at n=2 and disagreed about the
    fields a published document carries. The seed now comes from
    the commit-reveal ceremony (see _rotation_commit), never from
    a publisher-chosen input. Kept under this name for the
    in-tree consumers that import it."""
    return sentinel.rotation_schedule(members, seed)["rounds"]


if __name__ == "__main__":
    if KEY_LOCKED:
        # 1.2.2 (Q3): the refusal names the actual remediation for
        # the actual reason — 1.2.1 told env-key operators to "set
        # NOCTUA_AUDIT_KEY" when they already had (round 5,
        # DeepSeek N1/Qwen). 1.2.4 (S9): every remedy printed here
        # is one that WORKS. 1.2.3's first remedy — "write the key
        # to the file and restart" — was dead: Q3 removed
        # file-based trust-on-first-use, so the same unverifying
        # key in a file pins nothing. And its ceremony remedy
        # omitted --confirm, without which provision.py refuses.
        # The env precedence is stated because it bites: the env
        # key resolves BEFORE the key file, so a wrong env key
        # shadows a right file key.
        if KEY_LOCK_REASON == "unpinned_key_over_existing_chain":
            print("JANUS REFUSES TO START: the audit key is not "
                  "pinned for this database's existing chain, and "
                  "it does not verify against the keyed references "
                  "the chain already holds. Remedies that work: "
                  "(1) supply the key this chain was actually "
                  "written with — NOCTUA_AUDIT_KEY is resolved "
                  "FIRST, before the key file %s.audit_key, so a "
                  "wrong key in the environment shadows a right "
                  "one in the file; or (2) pin the key with the "
                  "two-operator ceremony: python3 "
                  "scripts/provision.py pin-audit-key --db %s "
                  "--fingerprint <sha256 of the key> --confirm "
                  "(--confirm is required; the fingerprint must be "
                  "confirmed out-of-band by a second operator). "
                  "Writing an unverified key to the key file does "
                  "NOT pin it." % (DB_PATH, DB_PATH),
                  file=sys.stderr)
        elif KEY_LOCK_REASON == "pre_restore_copies":
            print("JANUS REFUSES TO START: this directory holds "
                  ".pre-restore-* copies of a previous live system "
                  "but no database and no restore marker — minting "
                  "a fresh key and chain here would silently "
                  "re-found the installation over its own recovery "
                  "copies (1.2.4, S8). Complete the restore "
                  "(restore.py leaves the marker that exempts the "
                  "copies), restore one of the .pre-restore-* "
                  "copies by hand, or remove the copies "
                  "deliberately if this is truly a new install.",
                  file=sys.stderr)
        else:
            print("JANUS REFUSES TO START: audit key %s — restore "
                  "the key (env NOCTUA_AUDIT_KEY, which resolves "
                  "before the key file beside the database) and "
                  "restart" % KEY_LOCK_REASON, file=sys.stderr)
        sys.exit(3)
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    # S13: the effective config is part of the permanent record —
    # what retention ran under is a fact a later auditor can check,
    # not a log line that rotated away.
    try:
        chain.append("SYSTEM", {
            "event": "janus started", "version": VERSION,
            "retention_days": RETENTION_DAYS,
            "hold_days": HOLD_DAYS,
            "tier2_window_h": TIER2_WINDOW_H,
            "tier3_basis_types": sorted(TIER3_BASIS_TYPES),
            "cases_max_age_h": CASES_MAX_AGE_H,
            # 1.2.4 (S4/S10): the install mode and the verification
            # freshness bound are chain facts, like the rest of the
            # effective config (S13).
            "demo_mode": DEMO_MODE,
            "verify_max_stale_s": VERIFY_MAX_STALE_S,
            "config_hash": config_hash(),
            "bind": "%s:%d" % (BIND, PORT),
            "registry_version": REGISTRY_VERSION,
            "signing_pubkey_fingerprint":
                sentinel.pubkey_fingerprint(SIGNING_PUB_PEM)
                if SIGNING_PUB_PEM else None})
        chain.flush_deferred()
    except Exception as e:  # noqa: BLE001 — boot must not die on chain
        print("warning: SYSTEM chain entry failed: %s" % e,
              file=sys.stderr)
    print(f"janus {VERSION} listening on {BIND}:{PORT} db={DB_PATH}")
    Server((BIND, PORT), H).serve_forever()
