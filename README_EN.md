# vibe-trip-skill 🌏✈️

**One-stop travel skill: driven by travel personality + needs + budget together (not budget alone) — from personality/needs discovery to destination selection, whole-platform price comparison, and continuous price monitoring.**

Formerly `trip-planner`, renamed to **vibe-trip-skill** at 2.0. Use it **standalone** (`python scripts/*.py`, no agent, no signup), load it as an **Agent Skill** (Hermes / Claude, etc.), or drive the browser parts through **cua-driver** (CDP attach to a real browser, shared login state).

[中文](README.md)

---

## One-stop pipeline

| Stage | What it does |
|---|---|
| 1️⃣ Personality & preference discovery | Travel pace (packed vs. slow), planner vs. spontaneous, photo/food/experience person, risk tolerance — derive "where to go" from "who you are" |
| 2️⃣ Needs collection | Dates, party size, total budget, beach/city/culture priorities, an explicit dislike list |
| 3️⃣ Destination selection | Score 2–3 destinations against the total budget + **two-layer safety gate** (CDC disease/fertility layer can veto; political-landscape layer checked at booking time and again 15 days before departure) |
| 4️⃣ Structure & budget | Allocate hotel budget by function (city cheap, resort splurge); nine-line budget table, re-calibrated on every change |
| 5️⃣ Hotel four-axis verification | Official info × real guest reviews × map location × like-for-like pricing; **identity hard rules** (chain ≠ brand; four elements before marking "booked") |
| 6️⃣ Daily itinerary | Transport first, never over-schedule a resort stay |
| 7️⃣ **Whole-platform price lookup** | Flights + hotels across platforms (below) |
| 8️⃣ **Continuous price watch** | Record lows, same-flight pairing, rebook-before-cancel (below) |

## Whole-platform price comparison

| Target | Source | Notes |
|---|---|---|
| Flight floor price | **Ctrip calendar lowest-price API** | 🆓 Free, no login, no API key; one call returns 366 days of daily lowest fares for any city pair |
| Flight details | **Ctrip list page** | Flight numbers, departure/arrival times, **all flight numbers of a through-itinerary** (basis for same-aircraft pairing); international routes degrade gracefully behind a flapping login wall |
| Hotel price | **Booking property page** | Room-type table with stay totals and refundable/non-refundable split (the search page lies with "no availability" to automation — the property page is the source of truth) |
| Hotel price | **Agoda property page** | Price-pair formula: pay = strikethrough − discount; non-refundable rate picked by DOM parent-walk to avoid cross-matching |

## Continuous price monitoring

- **Record-low state machine**: `values / mins / alerted` — only announce a new low, never repeat an unchanged value, clear the alert key when the price rises back above the threshold
- **Silent contract** (no_agent cron): zero output when nothing changes
- **Multi-leg, per-order tracking**: every leg, every order subtotal, and the grand total each keep their own record low
- **Same-aircraft pairing**: the shared return leg recommends one flight for both travellers; a through-itinerary's second segment is matched to the solo segment by flight number
- **Rebook-before-cancel watch**: booked refundable hotel — when the listed price drops below what you paid, you get a "cancel & rebook" alert; the decision window = the free-cancellation deadline
- **Reference-price threshold**: announce when an order total drops under your reference price

## Quick start (standalone)

```bash
# Flight floor price (stdlib only, runs on any Python)
python scripts/ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10 --window 3

# Flight list (needs playwright; attaches to an open browser via CDP or launches one)
python scripts/ctrip_flight_list.py --dep pek --arr bkk --date 2027-06-10

# Hotel price check (Booking property page; room keywords are AND-ed)
python scripts/hotel_price_check.py --platform booking \
  --url "https://www.booking.com/hotel/th/xxx.html" \
  --checkin 2027-06-10 --checkout 2027-06-17 --nights 7 --room-must Deluxe

# Multi-leg + multi-hotel price watch (one local run)
python scripts/vibe_trip_monitor.py --verbose
```

Config: copy `scripts/config.example.json` to a local `vibe_trip_config.json` (real itinerary parameters stay local and **never enter the repo**).

## Two ways to plug in

**① Standalone (CLI)** — `python scripts/xxx.py` on any machine, no agent required; wire it to a cron (use `vibe_trip_entry.py` as the entry on Windows, where cron shells have no bash) for unattended watching.

**② Agent + cua-driver** — browser scripts attach over CDP (default `http://127.0.0.1:9333`) to a **real browser**: QR-code login state is reused (scan once, valid for a long time), captchas and consent walls can be handled interactively in the session, and verification screenshots go straight into the chat. The agent drives the same browser via cua-driver / Playwright `connect_over_cdp`, sharing the profile with the CLI — no conflicts.

## Install as an Agent Skill

```bash
# Hermes
cp -r vibe-trip-skill ~/.hermes/skills/travel/
# Claude Code & friends
cp -r vibe-trip-skill ~/.claude/skills/
```

Once loaded, follow the ten-step flow in SKILL.md: needs → budget-based destination screening → safety checks → structure → hotel verification → itinerary → budget → price lookup → price watch → delivery (including the fixed 15-days-before-departure double re-check).

## Repository layout

```
vibe-trip-skill/
├── README.md / README_EN.md   # bilingual docs
├── SKILL.md                   # agent skill definition (10-step flow + toolbox + gotchas)
├── LICENSE
└── scripts/                   # standalone toolbox
    ├── ctrip_lowest_price.py  #   Ctrip calendar floor price (free API, stdlib only)
    ├── ctrip_flight_list.py   #   Ctrip flight list (numbers / times / through-stops)
    ├── hotel_price_check.py   #   Booking/Agoda hotel price check
    ├── vibe_trip_monitor.py   #   multi-leg + multi-hotel watchdog (silent contract)
    ├── vibe_trip_entry.py     #   cron entry (bridges Windows' no-bash cron shells)
    └── config.example.json    #   config template (placeholders only)
```

## Acknowledgments

- **Inspiration: the Xianyu price-watch skill** (`xianyu-monitoring`, built on ai-goofish-monitor) — this repo's sentinel cron, cursor-based de-duplication, silent price-drop contract, and watchlist baseline diffing all borrow from that Xianyu price-check/watch design. Thank you!
- The deep weeds of price watching (PIPL consent walls, region filters, anti-repeat alerting) are shared with the `web-price-monitoring` skill.

## Disclaimer

All prices are live page readings and may move with inventory, cabin class, exchange rates, and member benefits — **the checkout page is the authority**. For destination safety, always follow the latest advisories from embassies and authoritative bodies.

## License

MIT
