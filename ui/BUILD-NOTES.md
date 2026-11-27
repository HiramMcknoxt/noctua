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
