# NOCTUA 1.0 — What This System Cannot Do

*Written to be read aloud. Every limit below is stated the way we would want it stated to us: plainly, specifically, and before the vote — not discovered after it. If a presentation about this system ever sounds stronger than this document, this document is the correction.*

---

## Technical limits — what the machine cannot do

**It cannot read every plate.** Dirt, mud, snow, a bent or missing plate, a plate cover, extreme angle, glare, heavy rain at night, a trailer hitch or bike rack in the way — any of these can make a plate unreadable, and some vehicles have no readable plate at all. The pilot measures accuracy instead of promising it: the proposed pass marks are 90% of plates read correctly at a slow site and 85% at a high-speed site, with plate *text* and plate *state* scored separately, because reading the right letters with the wrong state is not a correct read. Any number better than the measured one, quoted by anyone, is a sales number.

**It cannot guarantee real-time alerts over LTE.** Where a site connects by cellular, a read may arrive seconds or minutes after the vehicle passes — and during an outage, hours later, marked as late. This system produces verified leads. It does not promise anyone that a wanted vehicle will be stopped because a camera saw it.

**It cannot prove a negative about its own administrator.** The audit log is hash-chained, streamed to a copy outside the Police Department, and anchored by a signed checkpoint published daily. That catches edits, rewrites, and deletions — *unless* the person attacking it is a fully privileged insider who holds both the chain and the signing key, under the default setup where the key lives on the server. There are stronger key-custody options, and choosing one is a decision this Council will make explicitly and on the record. But no option makes the sentence "our own administrator could not possibly have tampered with this" a true sentence. What the system guarantees is narrower and real: *every action taken through the front door is logged, and history cannot be rewritten without breaking a chain that outsiders hold copies of.*

**It cannot distinguish a legitimate search from a well-disguised illegitimate one at the moment it happens.** It requires a real case number and a stated reason, it refuses catch-all cases, and it flags unusual patterns — but a user with a genuine case and a plausible sentence can still search for the wrong reason. What catches that is the outside auditor sampling searches against case files, month after month, and consequences when a sample fails. That is supervision, not software, and it only works if the auditor role is funded and filled.

**It cannot make a hot list true.** A list entry can be stale — a recovered car still listed, a stolen car not yet listed. The system records how old the list was and forces a human to verify through dispatch before any action, but it cannot fix the list itself.

**It cannot recover data it was designed to destroy.** Reads delete at 14 days, held evidence excepted, and the deletion is real — the database is scrubbed, not just flagged. If a question arises on day 20 about a vehicle that was never a hit, the answer is that the data is gone. That is the promise the system makes to every driver in Cabot, and it binds the City exactly when it is inconvenient.

**It cannot run itself.** It needs a named administrator and a named backup, updates applied by a person, cameras re-aimed by a person, and an auditor who actually audits. The license cost is zero; the labor is not, and this system will report the hours rather than hide them.

## Legal limits — what the law does not let it do

**It has no NCIC or ACIC access of its own.** Hot-list matching against state and national lists happens only the way ACIC says it may. Until ACIC answers in writing, the design *assumes* matching stays on the ACIC/dispatch side — an assumption, labeled as one, not a fact.

**If ACIC says the city server is a CJIS system, this build does not qualify.** A CJIS build is a separate, priced project — audits, fingerprinting, FIPS-validated encryption, the works. Nothing in this package claims that compliance, and anyone who says otherwise about it is wrong.

**If ACIC says only approved vendors may receive hot-list data, the pilot stops.** That outcome is designed in, with a name: Path C, kill condition K1. There is no workaround, and routing the data anyway would be a violation, not a solution.

**It cannot create a legal authorization the law doesn't have.** Arkansas law has no ALPR court-order mechanism. Historical searches are gated behind a judicial authorization — in practice likely a warrant — and the exact instrument is a question for the City Attorney and the judges who would sign them, answered before go-live. The software enforces an authorization; it does not invent one.

**It cannot shield the City from the statute's teeth.** Arkansas law makes improperly obtained plate data inadmissible (§ 12-12-1806) and gives an injured person a private right of action with $1,000 liquidated damages plus costs (§ 12-12-1807). Operating outside the adopted policy is not a paperwork issue; it is priced, per person, in the statute.

## By design — what it refuses to do

**No facial recognition.** The capability is not present, not licensed, and not a setting. Adding it would take a public policy change and new procurement — it cannot be switched on.

**No national network.** Reads are never uploaded to a shared national database, never searchable by other agencies through this system, and never sold, traded, or exchanged — Arkansas law forbids the sale, and the policy forbids the rest. There is no vendor cloud for the data to leak into; there is barely a cloud at all (see CLOUD.md).

**No data sharing by default.** The only disclosures are a specific, case-tied one authorized in writing and logged, or one the law or a court compels — likewise logged, and named in the public report. "By default" is doing work in that sentence: the default answer is no.

**No other purposes.** Not parking enforcement, not code enforcement, not immigration enforcement, not revenue, not building movement records of people who are not suspected of anything. The permitted uses are a written list; a use not on the list is not a gray area, it is a prohibited one — and asking another agency or a private network to do what the policy forbids is itself forbidden.

**No quiet expansion.** Every camera is at a location the Council has seen; the pilot's count cannot grow by configuration. More cameras, new purposes, longer retention — each is a public vote, not an update.

**No back door around the vote.** If the pilot fails its measures, the result is a report that says so. A failed pilot does not renew the current vendor, does not extend itself, and does not convert into a different system. Discontinuation is an outcome this design treats as legitimate from the first page.

---

*The short version, for the record: this system reads most plates, at nine places, for fourteen days, through one door, with an outsider watching — and it cannot read all of them, cannot watch itself perfectly, cannot touch the state and national lists on its own authority, and will not do the several things it was built specifically to refuse. That is the whole claim. It is enough to test, and it is not more than that.*

*End of CANT-DO.md.*
