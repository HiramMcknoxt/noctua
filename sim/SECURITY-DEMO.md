# NOCTUA — Security Demo Script (council / voters, ≈9 minutes)

Everything below is done live in the CPD console (`cpd-console.html`).
The through-line to say out loud, early and often:

> "Flock's security model is *trust the vendor*. NOCTUA's is *don't trust
> anyone — including us — and make cheating mathematically visible*."

Open the console on the Operations view. Note the gold banner: synthetic
data, not connected to anything. And read the line under it out loud —
*"this console simulates its backend; the production console is this same
interface wired to the Janus API."* Say it before anyone asks. That honesty
is part of the pitch.

---

## Beat 1 — The door only opens the right way (Janus) · ~90 sec

Go to **Search Reads**. Say: *"Every lookup in this system goes through one
front door called Janus. There is no other way in — no shared logins, no
direct database access, no fishing."*

1. Search a plate with case number `NOPE` → **BLOCKED**, and point at the
   message: the block itself is written to the audit log.
2. Switch the operator (top bar) to **auditor.external** and try again →
   blocked: the outside auditor can *check* the system but can never *use* it.
3. Pick Tier 3 (historical), no authorization → **BLOCKED**.
4. Check the authorization box, valid case `2027-1001` → the search runs,
   and is logged with your name on it.

**Line:** *"A deputy with a hunch and no case number gets nothing — and the
attempt is on the record forever."*

## Beat 2 — An alert is not a conviction (Hit Review) · ~90 sec

Open **Hit Review**, click a pending alert. Walk the screen: camera
snapshot, plate close-up, what the computer *read* vs. what the hot list
*says*. Try to confirm with a bogus case number → refused.

Then open one of the wrong-state alerts (ask Vesper to inject one first if
the queue is clean — the **Inject test alert** button): the number matches,
the state doesn't. Reject it.

**Line:** *"Under the vendor system, this alert goes to a patrol car. Under
ours, a human has to swear the plate and the state both match, under a case
number, before anyone gets stopped. In the simulation, wrong-state
lookalikes were the single biggest source of alerts — that's who gets
protected by this screen."*

## Beat 3 — Try to cheat the log (Sentinel tamper test) · ~2 min

This is the centerpiece. Go to **Audit Log**.

1. Press **Verify chain** → green: every entry's hash checks out.
2. Say: *"Now let's be the bad guy. A dishonest insider — or a vendor
   employee — edits history to hide a search they shouldn't have run."*
   Press **Simulate insider tampering**. One entry's case number quietly
   changes. Nothing alarms — tampering never announces itself.
3. Press **Verify chain** again → **BROKEN at entry #N**, the exact entry.
4. Press **Restore entry**, verify once more → green again.

**Line:** *"Every record is chained to the one before it, like links. Edit
one link in secret and the whole chain after it fails inspection. Now —
someone sharp is already thinking: 'what if the insider doesn't just edit
one link? What if he rewrites the whole chain?' Hold that thought. It's
Beat 5, and it's the most important one here."*

## Beat 4 — Try to go around the front door (bypass test) · ~1 min

Stay in **Audit Log**, scroll to **Try to go around Janus**. Say: *"Every
control you've seen assumes people use the front door. So let's not."*

Press **Attempt direct Frigate / database read** and narrate the three
refusals as they appear: the camera software has no human-reachable
interface in the hardened design — it's a sensor, not a server; its own
store holds only a rolling buffer of minutes, not an archive; and the plate
database isn't sitting on a share anyone can open. The attempt returns **no
plate data** — and the attempt itself lands in the audit log as a
`BYPASS_ATTEMPT` under your name. Point at it in the table.

**Line:** *"There is no side door to be quiet about using. And trying the
side doors is itself on the record. One honesty note, because you'll hear
it from me before you hear it from a critic: this shows the hardened
configuration the deploy package requires — the demo can't prove a
production install is configured that way. That's what the independent
pre-deployment test in the spec is for."*

## Beat 5 — Rewrite history itself (full-chain rewrite vs. checkpoints) · ~2 min

**This is the new centerpiece.** Still in **Audit Log**, scroll to
**Full-chain rewrite — the sophisticated insider**.

Setup, say it plainly: *"The tamper test in Beat 3 catches a careless
insider — one edit, hashes left stale. A sophisticated insider does the
math: edit the entry, then recompute every hash after it, so the chain is
perfectly consistent again. Watch."*

0. First, point at the **Daily signed checkpoints** table: every day, the
   chain's root hash and entry count are signed and published *outside*
   this system — the City Clerk holds them. (If today's row is thin, press
   **Publish checkpoint now** so the table covers the current log.)
1. Press **Simulate full-chain rewrite**. An entry is edited and the whole
   chain recomputed. The live feed pauses — history is being rewritten.
2. Press **Verify chain** → **it PASSES.** Let that land. *"Chain
   verification alone says this forged history is genuine. If the chain
   were all we had, the rewrite worked."*
3. Press **Check published checkpoints** → **CHECKPOINT MISMATCH**: the
   root after N entries no longer equals the root the Clerk published.
   *"The insider can recompute his own chain. He cannot recompute the
   Clerk's copies — they left the building before he started."*
4. Press **Restore witnessed chain**, then Verify chain and Check
   published checkpoints again → both pass.

**Line:** *"That's the whole design in one beat. The chain catches the
careless. The outside witness catches the careful. Nobody has to be
trusted — not the vendor, not the department, not the person running this
demo — because the proof lives somewhere the proof-maker can't reach."*

## Beat 6 — The shredder (retention) · ~45 sec

Back on **Operations**, point at the "Reads deleted" counter and the System
page policy table.

**Line:** *"Arkansas law lets a vendor keep your movements for 150 days.
Flock keeps them 30. This system deletes every non-hit read at 14 days —
automatically, and every deletion run is itself logged, so the shredder
can't be quietly turned off. What's not kept can't be breached, sold, or
subpoenaed."*

## Beat 7 — Close · ~30 sec

**Line:** *"Nothing here asks you to trust the police department, the
vendor, or me. The case numbers are validated, the searches are logged, the
log is chained, the chain is witnessed by the Clerk, the side doors are
closed and watched, and the data deletes itself. That's what
'city-controlled' means when you build it instead of buying it."*

---

### If something goes sideways live
- No pending alerts → **Hit Review → Inject test alert**.
- Someone asks "is this console the real system?" → don't improvise: point
  at the disclosure line under the gold banner. The console simulates its
  backend; production is this same interface wired to the Janus API. The
  governance rules being demonstrated (case validation, logging, chaining,
  witnessing) are the production rules — the data and the plumbing behind
  the screen are simulated.
- The checkpoint table looks thin during Beat 5 → press **Publish
  checkpoint now** before running the rewrite, so a checkpoint covers the
  current log.
- A question about cost → the spec's qualified estimate: pilot hardware
  ≈ $3–10k for 3 cameras, software licenses $0, and the honest caveat that
  CJIS Path B and staff time are the unpriced lines, gated before any vote.
- A question about hot-list access → "That's the ACIC decision gate in the
  spec. Nothing goes live until ACIC answers in writing; if they say
  vendor-only, the pilot stops. The ordinance comes first, the cameras
  second."
- Never claim the mapped camera locations are an official inventory —
  they're community-mapped points; say so if asked (System page carries the
  provenance note).
