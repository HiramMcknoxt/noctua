<!-- VESPER · the evening watch -->

# NOCTUA Operator Console — UI build notes

This folder holds the operator-console UI drafts, published so they can be
opened and played with directly. **These are design prototypes, not the
production console** — they run on synthetic sample data shaped like the
converged NOCTUA 1.2.8 API, and no draft here is connected to a live
system.

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
