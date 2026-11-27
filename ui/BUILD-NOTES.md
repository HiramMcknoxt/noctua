<!-- VESPER · the evening watch -->

# SURNIA Operator Console — UI build notes

This folder holds the operator-console UI drafts, published so they can be
opened and played with directly. **These are design prototypes, not the
production console** — they run on synthetic sample data shaped like the
converged SURNIA 1.2.8 API, and no draft here is connected to a live
system.

**Rename note (Nov 27, 2026):** the system was renamed **SURNIA** on
Nov 27, 2026. Drafts 1–6 were published under the former name, NOCTUA,
and their entries below keep that name as written; draft 7 is the
first under SURNIA.

## Convention

- Every UI draft lands in this folder as a dated, self-contained HTML
  file: `console-draft-YYYY-MM-DD.html`.
- Each draft gets a dated entry in this file on the day it lands: what it
  is, what changed since the previous draft, and what is known to be
  missing or wrong with it.
- Drafts are never edited in place after publication — a fix is a new
  dated draft, so the design history stays readable.
- The production console is built against the final API only after a
  draft passes Corey's hands-on feel test.

## 2026-11-26 — first published draft

File: `console-draft-2026-11-26.html` (single self-contained HTML file;
open it in any browser).

**What it is.** The staging design prototype for the NOCTUA operator
console, built against the converged 1.2.8 API shape. All data is
synthetic sample data (fictional Cabot PD plates, cases, and cameras).

**Surfaces.**

- **Hits Queue** — unverified hits with plate, alert type, case,
  location, camera, and read confidence; disposition actions per hit.
- **Search** — tiered search; Tier 3 (historical) is gated behind a
  judicial instrument + case number + second-supervisor approval, with
  the pending state visible while approval is outstanding.
- **Suppressions & Holds** — suppression and hold management with
  two-key release; under the standing anchor fence the release is
  correctly refused and the attempt is chained to the audit log.
- **Hotlist Approvals** — pending listings with approve/reject.
- **Audit Log** — the hash-chained audit viewer, with keyed `href:`
  plate references.
- **Health** — anchor fence, ceremony, and enrollment states.

**Interaction details.**

- **Confirm & Dispatch** opens a confirmation step before anything is
  dispatched: the dialog summarizes the hit and requires the operator to
  tick **"I verified this plate read"** before the final Confirm button
  dispatches; Cancel leaves the hit untouched.
- **Demo / Clean toggle** in the header: Demo shows the sample data for
  trying flows; Clean shows the empty, production-shaped state (zeroed
  counts, clear queues, empty-state placeholders). Switching back
  restores Demo exactly.
- **Styling** — rounded, modern pass: 20px-radius cards, pill-shaped
  buttons, navigation, and segmented controls, rounded inputs and modal.
- **The NOCTUA owl mark hovers** over the sidebar — gentle idle
  levitation with a pulsing shadow, livelier on hover, blinking eyes;
  reduced-motion preferences are respected.

**Known gap (stated honestly).** This draft predates the
comparison-panels fix Corey directed on Nov 26: the dispatch
confirmation does not yet visually separate the **camera read** (the
plate image and vehicle that generated the alert) from the **hotlist
entry** (the plate and description the system is watching for), so it is
not obvious at a glance which plate is the read and which is the wanted
listing. That fix is in build now and will land as the next dated draft.

## 2026-11-26 — draft 2: the comparison-panels fix

File: `console-draft-2026-11-26-2.html` (single self-contained HTML file;
open it in any browser).

**What changed.** Every hit is now split into the two things an operator
is actually comparing, side by side, so the camera read can never again
be mistaken for the listing it matched:

- **1 — What the camera saw.** The camera frame for the alert, with a
  **Whole vehicle / Plate close-up** toggle; the plate as the camera read
  it; and the vehicle, camera location, time, and read confidence behind
  the read.
- **2 — What's on file in the system.** The watchlist plate, labeled as
  the plate being looked for; the vehicle on file; why it is wanted; and
  the source the listing came from.
- **How they compare.** A match bar under the two panels states the
  comparison in plain language — whether the plate the camera read
  matches the plate the system is looking for, and whether the vehicle
  matches too.
- **Dispatch dialog.** The Confirm & Dispatch confirmation repeats the
  same side-by-side comparison, and its attestation now reads **"I
  compared the camera side (left) with the record on file (right)"** —
  the operator attests to the comparison itself, not just to the read.

**Why.** This came straight out of Corey's hands-on test of draft 1: the
dispatch dialog showed one description and one plate number, and he
could not tell whether that plate was the one the camera had read or the
one the system was looking for. A verification step whose two sides are
indistinguishable makes the attestation meaningless, so the two sides
are now unmistakable at a glance — in the hit rows and again in the
dialog at the moment of dispatch.

Everything else from draft 1 carries over unchanged: the six surfaces,
the Tier 3 gate, two-key release, the Demo / Clean toggle, the rounded
styling, and the hovering owl mark. Still a design prototype on
synthetic sample data, awaiting Corey's hands-on feel test.

## 2026-11-26 — draft 3: the dispatch-dialog repair

File: `console-draft-2026-11-26-3.html` (single self-contained HTML file;
open it in any browser).

**What changed.** Draft 2 put the comparison panels in the hit rows, but
its Confirm & Dispatch dialog still opened on a single merged box — one
plate, one description, and no camera image anywhere — even though the
attestation asked the operator to confirm they had verified the read
"against the camera image." Corey screenshotted it and asked the only
question that matters: **"what am I comparing this to?"** The dialog
itself is now the comparison:

- **An explicit explainer opens the dialog** — "What you are comparing" —
  stating in plain language that confirming a dispatch means comparing
  two different things, and naming them before either is shown.
- **A — Camera photo.** The actual camera frame that generated the
  alert, with the **Whole vehicle / Plate close-up** toggle, and the
  plate read from that photo.
- **B — Hotlist record.** The record the system matched against: the
  plate being looked for — labeled, in the panel, **not a camera read** —
  plus the make/model on file and why it is wanted.
- **An A-vs-B divider** separates the two panels so the eye can never
  merge them into one record.
- **The match bar is rewritten** in the same A/B terms, stating how A
  and B compare.
- **The attestation checkbox names A vs B**: the operator ticks that
  they compared **A (the camera photo, left)** against **B (the hotlist
  record, right)** — the attestation finally describes the act it
  certifies.
- **Queue panels relabeled** to the same A/B terms, so the vocabulary is
  identical from the queue row through the dialog to the attestation.

**Why.** A verification dialog that shows only one side of the
comparison — and references an image it does not display — asks for an
attestation it does not support. Draft 2 fixed the queue and carried
the old dialog along; this draft fixes the dialog, which is where the
attestation actually happens.

Everything else carries over from draft 2: the six surfaces, the Tier 3
gate, two-key release, the Demo / Clean toggle, the rounded styling,
and the hovering owl mark. Still a design prototype on synthetic sample
data, awaiting Corey's hands-on feel test.

## 2026-11-26 — draft 4: the key, and real cars on real roads

File: `console-draft-2026-11-26-4.html` (single self-contained HTML
file; open it in any browser). This draft is larger than drafts 1–3
(1,353,774 bytes) because the four camera photos are real photographs,
inlined into the file as data URIs — the file still has no external
assets beyond the Google Fonts stylesheets drafts 1–3 also used.

**What changed — the fence is now a door with a key.** In drafts 1–3,
Suppressions & Holds stood behind the anchor fence, and every two-key
release was refused: correct behavior, but a dead end for anyone trying
the console. Corey's verdict: **"I've seen the door, now let me see the
key."** The refusal is now the start of a walkable ceremony instead of
the end of one:

- **The Answer Key.** Suppressions & Holds carries a 4-step answer key
  that walks the standing divergence **D-118** the way the real system
  resolves one: open the divergence and compare the two checkpoints
  side by side; accept it as a *second* supervisor; watch fence
  **F-07** clear; then release.
- **Refusals are logged, not just shown.** Acceptance is a two-key act:
  Sgt. Keller — the supervisor who raised the divergence — cannot
  accept his own checkpoint disagreement. Trying it is refused *and the
  refusal is chained to the audit log*; escalating instead is also
  offered, and also logged. A second supervisor (Lt. Osei) can accept,
  and the acceptance is what clears the fence.
- **The fence clears everywhere at once.** On acceptance, the header
  pill, the Audit Log fence state, and System Health all flip to
  Cleared / Unfenced together — one state, three views of it.
- **Releases then complete.** With the fence down, a Release… takes two
  different keys plus a reason, the row flips to **Released**, and the
  holds count drops. Nothing about the two-key rule relaxed to make
  this work — the ceremony was completed, not bypassed.
- **"What gets logged for a release."** An in-page panel in
  Suppressions & Holds answers the question Corey asked while testing:
  both key-turners, the item, the time (CT), the reason, the fence
  state, and the outcome are chained on *every* attempt — blocked
  attempts included — while a suppressed vehicle's raw plate is never
  logged, only its keyed `href:` reference.
- **The Audit Log updates live.** The acceptance, the fence clearing,
  blocked attempts, and completed releases appear at the top of the
  log as they happen, with prev → hash links and a rising entry count,
  so the whole ceremony can be watched in the chain.

**What changed — the camera photos are cars on roads.** Corey asked
for real pictures of vehicles matching the sample descriptions, the
way a roadside camera actually catches a car. All four camera frames
are now roadside-style photographs: a silver Ford F-150 stopped at a
red light in a crosswalk, a blue Toyota Camry in motion on a city road
(side profile), a white Chevrolet Tahoe rolling through an
intersection, and a grey Subaru Outback crossing an intersection. No
readable real plate appears in any of them; the sample plates and the
rendered plate close-ups are unchanged, and the captions say plainly
that the photos are stock stand-ins — the sample data is fictional, so
there is no actual vehicle to photograph. In the real system this
frame is the camera's own capture.

**Correction, recorded honestly.** The first Camry photograph in this
round was a car parked at a residential curb, and the caption under
the queue claimed all four photos were caught on the road in motion —
which overstated that one. The Camry photo was replaced with the
in-motion shot above and the caption corrected before this draft was
published.

Everything else carries over from draft 3: the six surfaces, the A/B
comparison panels and dispatch dialog, the Tier 3 gate, the Demo /
Clean toggle, the rounded styling, and the hovering owl mark. Still a
design prototype on synthetic sample data, awaiting Corey's hands-on
feel test.

## 2026-11-27 — draft 5: the owl, in the tab

File: `console-draft-2026-11-27.html` (single self-contained HTML
file; open it in any browser). The only change from draft 4 is the
page icon — everything else (the answer key, the logging panel, the
roadside photos, the A/B dialog) is draft 4 unchanged. The file grows
to 1,686,547 bytes because the PNG icon sizes are inlined as data
URIs alongside the four camera photos; still no external assets
beyond the Google Fonts stylesheets.

**What changed.** Draft 4's head carried an empty placeholder
favicon, so browser tabs and link cards had nothing to show and fell
back to the host's generic letter. Corey spotted it on his phone —
the console's link card wore a grey "H" — and asked for "the owl icon
you made." The head now declares the NOCTUA owl, the sidebar's own
gold-on-dark-navy mark:

- an **SVG favicon** — the owl mark itself, inlined into the head;
- **PNG icons at 192 and 512** for launchers and previews;
- an **apple-touch-icon at 180**, so a home-screen save gets the owl
  too;
- a **theme-color** matching the mark's dark navy;
- **Open Graph title, description, and image** (the 512 owl), so a
  shared link previews with the owl and the console's name instead of
  a placeholder letter.

## 2026-11-27 — draft 6: sign-ins, not name-pickers

File: `console-draft-2026-11-27-2.html` (single self-contained HTML
file; open it in any browser). The change from draft 5 is who the
console believes you are: the name-pickers are gone, replaced by
simulated sign-ins. Everything else — the A/B dispatch dialog, the
answer-key fence walk, the "What gets logged" panel, the roadside
photos, the owl icon — is draft 5 unchanged. The file grows slightly
to 1,702,855 bytes; still no external assets beyond the Google Fonts
stylesheets.

**What changed.** Playing the earlier drafts, Corey caught the hole
in the ceremony: asked how two users log in at the same time to turn
their keys, he said "It feels like I can just pick a name and do it."
He was right — the two-key flows let you choose whose name turned the
key from a dropdown, so the demo taught the choreography without the
identity check that makes it mean anything. Now the key that turns is
whoever is *signed in*:

- **Three demo accounts.** The answer key on Suppressions & Holds
  lists Keller, Osei, and Alvarez, each with a demo password and the
  6-digit authenticator code their app would generate — printed on
  purpose, because this is sample data. In the real system the
  password is secret and the code comes only from that person's own
  authenticator app or hardware key.
- **A sign-in dialog guards the keys.** Accepting divergence D-118
  and turning either key of a two-key release first opens a sign-in:
  pick the operator, enter *their* password plus their TOTP code —
  or take the simulated FIDO2 hardware-key tap instead. A hint under
  the dialog shows the selected operator's demo credentials.
- **Key 2 cannot be Key 1's person.** Sign in for the second key as
  the operator who turned the first and the sign-in is refused — two
  keys means two people, enforced the same way the real control
  enforces it.
- **Keller still cannot accept D-118.** The fence is holding Keller's
  own checkpoint disagreement; signing in as Keller to accept it is
  refused. The acceptance has to come from a different supervisor.
- **Every attempt is chained.** Each sign-in, failed attempt, and
  refusal is written live to the Audit Log — the chain records the
  refused attempts too, not just the successes. A session pill in the
  sidebar shows who is signed in and offers Switch user / Sign out;
  switching and signing out are logged as well.

## 2026-11-27 — seventh published draft (first as SURNIA)

File: `console-draft-2026-11-27-3.html` (single self-contained HTML
file; open it in any browser). The only change from draft 6 is the
name: the system was renamed **SURNIA** on Nov 27, 2026 (Corey's pick
from a conflict-screened shortlist; NOCTUA collided with a well-known
PC-cooling brand). Page title, link-card metadata, sidebar brand, the
owl's aria-label, body copy, and the footer now say SURNIA. Every
flow — simulated sign-ins, the two-key release, the answer-key fence
walk, the A/B dispatch dialog, the roadside photos — is draft 6
unchanged, and drafts 1–6 are untouched, byte for byte.

## 2026-11-27 — draft 8: the presentation build

File: `console-draft-2026-11-27-4.html` (single self-contained HTML
file; open it in any browser). This is draft 7 hardened for live
presentation — Corey will demo it to officials and colleagues with no
live API and no cameras behind it, so the pass was about the demo
never contradicting or stranding him: every control works, every flow
completes, and every number on every screen agrees with every other.
No design, layout, or feature changes; drafts 1–7 are untouched.

**What changed.**

- **Actions that said "written to audit chain" now write one.** In
  draft 7, hit dispositions (including dispatch confirmations),
  hotlist decisions, quick searches, Tier 3 submissions, and the
  health snapshot toasted a claim the Audit Log never backed — the
  entry count didn't move. All five now chain a real entry through the
  same addAuditEntry path the sign-ins and releases use, and the
  decided rows, result badges, and toasts cite the actual entry
  number.
- **Counts that went stale are live now.** The Verify-chain toast
  hardcoded "88,412 entries", the Refresh toast hardcoded "4
  unverified hits", and the topbar "3 approvals pending" pill never
  changed when approvals were decided. All three compute from the
  current state, and the Demo/Clean toggle keeps the pill truthful in
  both modes.
- **Three data contradictions fixed.** The "Oldest waiting" stat said
  11 minutes; the queue's own timestamps say 33 (oldest hit 22:18:57,
  chain head 22:52:03) — corrected, and it recomputes as hits are
  dispositioned. The decided-this-shift list cited audit #88397 for
  the 18:12 CAB-2026-1160 approval the chain records as #88405 —
  corrected. The verified RTA 610 card said "Confirmed by Ofc. Ruiz
  at 21:58" while the audit entry it cites (#88412) records Sgt.
  Keller at 22:52:03 — the card now matches the chain.
- **Quick search tells the truth about plates it doesn't know.** It
  used to return the same two reads for any plate typed. Results are
  now driven by the five sample reads themselves; an unknown plate
  gets an honest "no reads in the last 24 hours" (the search itself
  is still logged).
- **Live entries keep demo time.** New audit entries were stamped
  with the presenter's real wall clock, breaking the demo's
  Nov 26, 22:52 chronology mid-presentation. The clock now continues
  from the chain head (22:52:03 + elapsed time since page load).
- **Small truths.** A Tier 3 submission now names the operator
  actually signed in (it hardcoded Sgt. Keller), and the link-card
  description carries the framing too: "demonstration with simulated
  data".

**Verification.** Beyond the static audit (every control enumerated
and traced; every number, plate, case, and timestamp reconciled
across screens), the build was driven end-to-end in a headless
browser: 55 assertions covering all six views, the dispatch dialog's
attestation gate, both search tiers, hotlist decisions, the blocked
release under a standing fence, the refused Keller self-acceptance,
the Osei acceptance clearing F-07, the completed two-key release,
failed sign-ins, the hardware-key path, sign-out, the health
snapshot, and the Demo/Clean round-trip — 55/55 passed with zero
page errors. The full record is in the presentation kit's handoff
(`~/workspace/noctua-1.0/presentation/HANDOFF.md`).

## 2026-11-27 — draft 9: presentation build, Claude QA fixes applied

File: `console-draft-2026-11-27-5.html` (single self-contained HTML
file; open it in any browser). Draft 8 after an independent
click-through audit by a Claude seat (Opus 5.5, Medium), which walked
every flow and returned PRESENTABLE WITH FIXES: 3 blockers, 15
should-fixes, and five watch-list rulings. All of them are applied
here, plus the nits. No design or feature changes; drafts 1–8 are
untouched, and no audit rows were added or renumbered — the cited
entries (#88405, #88412) still point at the same events.

**What changed.**

- **Clean view is clean now.** The Demo/Clean toggle used to leave
  sample state behind: the "Oldest waiting" stat, per-camera reads,
  the ingest rate, the audit stats, the Tier 3 badge, and quick-search
  results all kept showing demo numbers in Clean. All are zeroed or
  neutralized in Clean and restored on return, live audit entries
  chained while in Clean stay visible there, and the Health view no
  longer reads as a live deployment — its subhead now says
  "Simulated posture of a fictional deployment" and the footer build
  string is `1.2.8-demo`.
- **Card headers tell the truth after a release.** Completing the
  answer-key release now recounts the Suppressions and Evidence Holds
  card badges ("3 active" / "2 active") instead of leaving them stale
  next to a row that says Released.
- **Refusals look like refusals.** Toasts carried a ✓ even when the
  system was refusing — a blocked release, a missing case number, a
  failed gate. Refusals and gates now carry a warning glyph; the
  Export and New-suppression toasts say plainly "not available in
  this demo", and every hit panel's Record source is prefixed
  "Sample:" so no fictional case reads as a real agency record.
- **The two-key rules hold under probing.** Signing out now refuses
  console actions until someone signs in (nothing silently acts as
  the previous operator); a detective can no longer accept the
  D-118 divergence — acceptance requires a supervisor, and the
  refusal is chained; a hardware-key tap no longer carries across
  operators when the sign-in picker changes; the same person can now
  actually attempt both keys, so the chained refusal the answer key
  promises is reachable in both orders; Escape inside a nested
  sign-in closes only the sign-in; and double-clicking Approve (or a
  disposition) can no longer duplicate entries.
- **Escalation no longer loops the message.** After escalating
  D-118, the blocked-release strings used to tell the presenter to
  "accept or escalate first" — including right after escalating.
  They now say the fence stands until D-118 is accepted by a second
  supervisor, noting that escalation keeps the fence up.
- **Search respects its own controls.** Quick search now filters by
  the camera selector, its label says "Full plate" (matching is
  exact), and a result for a hit already dispositioned no longer
  says "see Hits Queue". The Tier 3 form validates its From/To
  dates, names the missing field when it refuses, and clears after a
  successful submit.
- **The numbers reconcile (watch-list rulings).** The checkpoint
  table's on-file entry count is 88,408 — the head it names is the
  hash after #88408 — with the row marked "advances +1" and the text
  noting the counts "differ only by the checkpoint entry itself".
  Retention reads 14 days everywhere it appears (the Tier 3 default
  window now starts Nov 12, and the pending request whose window
  reaches past retention is annotated as held). Ingest is
  "≈13 reads / min (today's average)" — 512/min contradicted the
  day's 18,442 reads — and the per-camera last-hour counts are
  divided by ~10 to match. The Cameras card says "6 of 14 shown",
  and the Audit subtitle calls the listing what it is: an excerpt.

**Verification.** The draft-8 click-through harness was extended
with assertions for each fixed behavior (85 checks in total: the
original 55, two updated where a fix intentionally changed behavior
— the Key 2 picker is enabled by design now, and the harness signs
back in before the health snapshot because signed-out actions are
refused) and re-run against this build in a headless browser:
85/85 passed, zero page errors. Static greps: zero "NOCTUA",
zero "30-day", zero "512 reads". The full record is in the
presentation kit's fix-pass handoff
(`~/workspace/noctua-1.0/presentation/HANDOFF-DRAFT9.md`); the seat's
report is `~/workspace/noctua-1.0/presentation/claude-qa-report.md`.
