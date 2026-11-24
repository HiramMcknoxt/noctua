# NOCTUA 1.0 — Network Architecture: How Cameras Reach the Server

*What this document is: the deployable network design for connecting NOCTUA camera sites to the city server. What it is not: a site survey. Every site gets surveyed before install (mount, power, connectivity — spec v2 §6); this document tells the surveyor what "connected" has to mean.*

*Labeling: figures marked **[record]** come from the Cabot record or the adopted spec. Figures marked **[estimate]** are planning estimates from the Clark County research hub or the November 16, 2026 plan, applied to Cabot. Figures marked **[assumption]** are engineering assumptions made in this document and labeled so a reviewer can challenge them.*

---

## 1. The shape of the network

```
  CAMERA SITE (pole / building)                CITY SERVER (police facility)
 ┌───────────────────────────────┐            ┌──────────────────────────────┐
 │ LPR camera ──PoE──► switch /  │            │  Camera VLAN interface       │
 │              injector         │  backhaul  │        │                     │
 │ Edge buffer (Frigate, on the  │ ═════════► │        ▼                     │
 │ server — see §2 note)         │  (tunnel)  │  Frigate ──reads──► Janus    │
 │ Site router / modem           │            │  Office LAN interface ──►    │
 └───────────────────────────────┘            │  console users (TLS, §8)     │
                                              └──────────────────────────────┘
```

Three rules govern everything below:

1. **Cameras never face the internet.** No port forwarding, no vendor cloud, no P2P remote access, no camera-initiated connection to anything except the city server through the tunnel. Camera onboard storage and cloud/P2P features are disabled before install (spec v2 §6, amendment 10).
2. **The camera network has no internet route.** The camera VLAN can reach exactly one thing: the Frigate host, through the tunnel, on the ports Frigate needs. A compromised camera cannot phone home, join a botnet, or be reached from outside.
3. **Only reads travel.** NOCTUA is not a video system. What crosses the backhaul is plate-read events — metadata plus a plate-crop snapshot — not continuous video (spec v2 §3: raw video is not a function of this system and is not retained). This is what makes cheap backhaul possible; §7 does the math.

**Where Frigate runs.** In the reference deployment Frigate runs on the city server and pulls camera streams through the tunnel (§5). For sites whose backhaul is LTE, §6 describes the store-and-forward variant: the same Frigate pull model, with an edge buffer at the site holding events until the tunnel is up. A site never *pushes* unrequested data at the server, and no site component holds a lasting plate store of its own — Frigate at the edge is a buffer with a short fuse, not a second database (spec v2 §4, sensor lockdown).

## 2. Per-site bill of materials

One site = one camera covering one approach (add a second camera line for a second approach; the rest of the BOM is shared).

| Item | What / why | Planning figure |
|---|---|---|
| LPR camera, NDAA §889-compliant, native RTSP/ONVIF, ≥1/1000s shutter (1/2000s night/speed), IR with focus-shift compensation, motorized varifocal | The sensor. §889 compliance is a requirement, not a preference (spec v2 §4), so no later funding change can disqualify the installed base | Commodity class ~$300–450 **[estimate — Clark County research 04]**; named option Axis Q1800-LE $1,779 MSRP **[record — Nov. 16 plan §3]** |
| PoE injector or PoE switch port (802.3af/at per camera spec) | The camera price excludes power delivery (spec v2 §6) | Included in install allowance below |
| Weatherproof cabinet / enclosure, pole or wall mount | Houses injector, modem/router, surge protection. The mount may not be reusable from the leased installation — reusability is **not** assumed (spec v2 §6) | Included in install allowance below |
| Surge protection + grounding | Pole electronics die by lightning and surges, not old age | Included in install allowance below |
| Site router/modem | Terminates the backhaul (§3) and the WireGuard tunnel (§4). LTE sites: an LTE/5G router with external antenna option. Fiber/PtP sites: a small managed router or the PtP radio itself | Included in site figures below |
| Power source | City-controlled AC where available; solar + battery only where no AC exists | Off-grid premium is the difference between the wired and off-grid site figures below |
| Cabling | Outdoor-rated Cat6, conduit where the survey requires it | Included in install allowance below |

**Per-site installed cost (planning estimates, pick one basis per site — do not add both):**

| Site type | Figure | Basis |
|---|---|---|
| Existing powered, wired city site | ~$150 install allowance + camera | **[record/estimate]** Nov. 16 plan installation schedule, low case (existing infrastructure) |
| Standard install (existing pole, power available, new mount/cabling) | ~$650 install allowance + camera | **[record/estimate]** Nov. 16 plan installation schedule, standard case |
| New pole with solar (off-grid) | ~$1,900 install allowance + camera, **or** ~$800–$2,500 all-in per site | **[estimate]** Nov. 16 plan schedule high case; Clark County all-in off-grid estimate (camera + edge + modem + solar + battery). The site survey picks one basis per site; the two overlap and must not be double-counted (spec v2 §12) |
| LTE service, per camera | $20–50 / month | **[estimate — Clark County research 04]** |

Worked example, 9 sites, all standard installs, commodity cameras: 9 × ($375 camera midpoint + $650 install) ≈ **$9,225** hardware/install, plus LTE where applicable. With Axis cameras at all 9: 9 × ($1,779 + $650) ≈ **$21,861**. Both are planning arithmetic on labeled estimates, not quotes; the survey replaces them. (For scale: the November 16 plan's 9-camera purchase-model Year 1 estimate was $21,861–$37,611 — a different model, quoted here only because the low end happens to coincide.)

## 3. Backhaul: three options, in preference order

Scattered pole sites are the normal case, not the exception. Pick per site, in this order; a deployment will usually mix all three.

### Option 1 — City fiber / municipal LAN (preferred where it exists)

Use when the site is on or near a city building, signal cabinet, or any city-owned conduit/fiber path.

- Camera plugs into the city network as a camera-VLAN port (§4); no tunnel needed inside city plant, though WireGuard is harmless if already configured.
- Cost: near zero recurring; install is the cabling.
- Latency: milliseconds. Store-and-forward almost never engages.
- Limit: most pole sites are not on city fiber. Do not let "run fiber later" block a site — take Option 2 or 3 and revisit.

### Option 2 — Point-to-point (PtP) wireless

Use when the site has line-of-sight to a city facility (water tower, city hall roof, fire station) within the radio's range — typically up to a few kilometres for the unlicensed 5 GHz class, farther for licensed links **[assumption — radio-class dependent; the survey confirms per site]**.

- A matched pair of radios forms a transparent bridge; the camera VLAN extends across it. WireGuard still runs over the bridge (§4) so a radio compromise is not a network compromise.
- Cost: one-time radio pair + mounting, inside the standard install allowance at most sites **[estimate]**; no recurring carrier fee.
- Latency: single-digit milliseconds. Weather fade is the failure mode — heavy rain attenuates 5 GHz; link budget and alignment are survey items.
- Limit: needs line-of-sight and a powered, city-controlled far end. Trees grow; re-survey annually.

### Option 3 — LTE / 5G with WireGuard (the default for scattered poles)

Use when neither fiber nor line-of-sight exists — expected to be the majority of pole sites.

- Site router holds a persistent WireGuard tunnel to the server (§4). The carrier provides transport only: it sees encrypted tunnel traffic to one city endpoint, never plate data (see CLOUD.md).
- Cost: $20–50/camera/month **[estimate — Clark County research 04]**.
- Latency: typically 40–150 ms **[assumption — carrier dependent]**. Irrelevant for reads; NOCTUA makes no real-time guarantee over LTE (see CANT-DO.md).
- Data volume is small (§7): a metered plan sized at 25 GB/site/month covers the design traffic with headroom **[assumption — sized from §7 math]**.
- Limit: carrier outages and dead zones are outside city control — which is exactly what store-and-forward (§6) is for.

## 4. VLAN and tunnel design

| Segment | Who lives there | Can reach | Cannot reach |
|---|---|---|---|
| **Camera VLAN** (e.g. VLAN 40, 10.10.1.0/24 in the reference config) | Cameras, site routers' camera-side interfaces | The Frigate host only, on RTSP (554/tcp) and ONVIF (80/tcp) pull ports, through the tunnel where one exists | The internet (no default route out), the office LAN, other cameras, each other |
| **Server camera interface** | Frigate host | Camera VLAN (initiates all connections) | — |
| **Office LAN** | Officer workstations, the console, Janus via the TLS proxy (INSTALL.md §5) | Janus HTTPS endpoint; normal city IT services | Cameras directly (no route from office LAN to camera VLAN except through Frigate's host, which does not forward) |
| **Management** | System Administrator, via SSH to the server | Server administration | Not a user path: no plate data is accessed over SSH as a workflow; Janus is the only data door |

Rules that make this real rather than diagrammatic:

- **No internet route means no route.** The camera VLAN has no NAT, no default gateway to the internet, and firewall rules that drop camera-VLAN traffic to anything but the Frigate host. Camera DNS/NTP point at the server (§5), never at public resolvers.
- **Cameras cannot talk to each other.** Same-VLAN lateral traffic is blocked at the switch/router (client isolation). A camera's compromise ends at that camera.
- **WireGuard topology is hub-and-spoke.** The server is the hub; each site router is a spoke with its own keypair. A spoke can reach only the server's Frigate ports. Spoke keys are per-site: revoking one site never touches another. Keys are generated at provisioning (INSTALL.md §6), stored in the site router and the server's WireGuard config — never in `cameras.yaml`, which stays shareable.
- **The tunnel is not the security boundary for data.** Even inside the tunnel, Frigate authenticates to each camera, the bridge authenticates to Janus as role `system`, and Janus authenticates every human. The tunnel keeps strangers out; Janus's rules govern insiders.

## 5. Pull model, time sync

**RTSP/ONVIF pull.** Frigate initiates every connection: it pulls each camera's RTSP stream (ONVIF for discovery/PTZ-class functions where applicable) through the tunnel. Cameras accept connections only from the Frigate host's tunnel address. Nothing at a site initiates a connection to the server except the site router maintaining the WireGuard tunnel itself. Consequences: no inbound ports anywhere at a site; a camera with a malicious or buggy firmware "call home" has nowhere to go (no internet route, §4); and ingest into Janus happens only through `POST /reads` from the Frigate bridge, authenticated as role `system` — the only ingest path there is.

**NTP / time sync — read timestamps are evidence.** A read with a wrong timestamp is a defective record; a camera clock drifting silently corrupts the retention math and any court presentation.

- The server runs an NTP service (chrony or equivalent, OS package) disciplined by upstream time sources on the office LAN side, and serves time to the camera VLAN. Cameras and site routers sync to the server, never directly to the internet.
- Frigate stamps each read with the **camera's** timestamp. On ingest, Janus compares it to server time: **skew greater than 5 seconds is flagged on the read and counted in /health** (INTERFACE.md). A site that drifts repeatedly is a maintenance ticket, not a shrug.
- All timestamps in Janus, Sentinel, and reports are UTC at rest; the console renders local time. Retention is computed on server-received age cross-checked against camera timestamps, so a camera clock set wrong cannot extend a read's life past the 14-day cap — the cap runs from the earlier of the two clocks, and skew beyond 5 s is visible, not silent.

## 6. Store-and-forward during outages

Backhaul fails: storms, carrier outages, a cut PtP alignment, a tripped breaker. The design assumption is that it *will* fail, per site, for hours at a time.

- **What happens:** the site's Frigate edge buffer (LTE/PtP sites) holds detected read events — metadata + plate crops — in a local queue. The camera keeps watching; detection continues locally; nothing is discarded for being offline.
- **On reconnect:** the buffer drains to the server in timestamp order through the normal `POST /reads` path. Janus accepts backfilled reads, marks them with their true camera timestamps and a `backfilled` flag, and runs hot-list matching on arrival — a hit discovered late is still a hit, presented to the reviewer *as* late, with the delay visible.
- **Buffer sizing [assumption]:** at 4,936 reads/camera/day **[record]** and ~100 KB per event (metadata + crop, §7), a full day is ~0.5 GB. A 32 GB edge buffer holds weeks of events; the binding limit is policy, not space: **buffered events older than the 14-day retention cap are deleted at the edge unsent** — an outage must never become a way for data to outlive the cap. In practice the buffer alarms long before that (§6, OPERATIONS.md dead-man rules): the server notices a silent site within one heartbeat interval.
- **What store-and-forward is not:** it is not a second plate store. The buffer is encrypted at rest on the edge device, holds no query interface, exposes no UI, and drains-or-deletes — it never accumulates a searchable history. If the edge device is stolen, the contingency is in CONTINGENCIES.md.
- **Centralized sites (fiber):** Frigate is on the server; a fiber cut means the stream stops and detection pauses — there is no edge buffer to steal and no backfill. The outage is alarmed the same way. This asymmetry is deliberate: buffering exists where the backhaul is unreliable, not by default everywhere.

## 7. Bandwidth math (per camera)

Basis: **4,936 reads/camera/day [record — CPD-reported Jan.–Jun. 2026 volume ÷ 9 cameras ÷ 181 days]**. What travels per read **[assumption — labeled so the Commission can substitute measured Stage 0 values]**:

| Per-read payload | Size assumption | Daily per camera | Monthly per camera |
|---|---|---|---|
| Event metadata (plate text, timestamp, site, confidence) | ~2 KB | ~10 MB | ~0.3 GB |
| Plate-crop snapshot (the image a reviewer verifies) | ~100 KB | ~494 MB | ~15 GB |
| **Design total** | **~102 KB** | **~0.5 GB** | **~15 GB** |
| Full-frame snapshot per read (NOT the design — shown to explain why) | ~400 KB | ~2.0 GB | ~60 GB |
| Continuous video (NOT sent, NOT retained — shown for contrast) | 2 Mbps stream | ~21 GB | ~630 GB |

Derived rates for the design total: ~46 kbps average; busy-hour peaks run roughly 10× average, ~0.5 Mbps **[assumption — diurnal traffic pattern]**. Any of the three backhauls carries this trivially. The design consequences:

- **LTE plans are sized by the crop, not the video.** 25 GB/site/month covers the design total with ~65% headroom for retransmits, backfill bursts, and firmware-free overhead. If a quote assumes video backhaul pricing, it is pricing a different system.
- **Crops, not frames, are the default payload.** The verifying image is the plate crop. Full frames stay at the edge inside Frigate's short media retention (≤14 days, matched to the read cap — spec v2 §4) and are not backhauled per-read.
- **Backfill bursts are bounded.** A 3-day outage drains ~1.5 GB; at even 5 Mbps effective LTE uplink that is ~40 minutes of catch-up, throttled so it cannot starve live reads **[assumption — throttle set at provisioning]**.

## 8. What the server side looks like

The server is dual-homed: one interface on the camera VLAN (or tunnel termination), one on the office LAN. Janus itself binds to localhost; officer access is through a TLS-terminating reverse proxy on the office-LAN interface only (decision and reasoning: INSTALL.md §5). Frigate's UI is not exposed on any interface — maintenance is by SSH tunnel to the host (v0.9 lockdown, carried forward). The Sentinel sink and checkpoint publication leave by the office-LAN side to storage the Police Department does not control (INSTALL.md §6, OPERATIONS.md).

## 9. Pre-install survey checklist (per site)

1. Mount: what the camera attaches to, who owns it, written permission if not the City's. (Leased-installation mounts are not assumed reusable.)
2. Power: source, city-controlled or not, PoE run length, surge protection, solar/battery sizing if off-grid.
3. Backhaul: fiber present? Line-of-sight to a city facility? LTE signal measured at the pole (not at the street) on the intended carrier?
4. Camera geometry: lane coverage, approach speed, plate angle, IR performance at night at that geometry — the Stage 0 accuracy protocol (spec Appendix C) is re-run per site class.
5. Addressing: site assigned its camera-VLAN address and WireGuard keypair; recorded in `cameras.yaml` (address only — credentials in `.env` / router config, never in the YAML).

*End of NETWORK.md.*
