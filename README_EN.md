# vibe-trip-skill 🌏✈️

[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](scripts/)
[![i18n](https://img.shields.io/badge/i18n-%E4%B8%AD%E8%8B%B1%E5%8F%8C%E8%AF%AD-brightgreen)](README.md)

**A one-stop travel skill driven by travel personality, needs, and budget together**: start from who you are and what you want, derive the destination and itinerary, compare prices across platforms, then hand the watch job to a cron. Formerly `trip-planner`, renamed at 2.0.

[中文](README.md)

| Standalone scripts | Calendar floor price | API dependency | Delivery | Docs |
|---|---|---|---|---|
| **5** | **366** days per call | **0** keys, no login for airfare | silent when nothing changes | CN + EN |

## Pain points and fixes

| What usually goes wrong | What this repo does |
|---|---|
| Ten tabs open for comparison, stale prices everywhere | One command returns a 366-day fare calendar; hotels read straight from the property page room table |
| A price watcher spams you all night | Silent contract: zero output when nothing changes, one message on a record low |
| Booking's search page reports "no availability" to automation | Reads the property page `#hprt-table` instead, filtered by room-type keywords |
| Ctrip's international login wall appears and disappears | Falls back to the no-login calendar API the moment `needUserLogin` shows up, so price tracking never stops |
| Windows cron shells have no bash, `.sh` jobs die instantly | `vibe_trip_entry.py`, stdlib-only, picks a Python that has playwright |
| Keeping two travellers on the same flight means eyeballing flight numbers | Same-aircraft matching pairs a through-itinerary with its connecting segment by flight number; the shared return leg gets a single-flight recommendation |

## One-stop pipeline

| Stage | What happens |
|---|---|
| 1️⃣ Personality and preference discovery | Travel pace, planner vs. spontaneous, photo/food/experience focus, risk tolerance |
| 2️⃣ Needs collection | Dates, party size, total budget, priorities, an explicit dislike list |
| 3️⃣ Destination selection | Score 2-3 options against the total budget behind a two-layer safety gate (CDC disease layer can veto; political landscape checked at booking and 15 days before departure) |
| 4️⃣ Structure and budget | Hotel budget allocated by function, nine-line budget table recalibrated on every change |
| 5️⃣ Hotel four-axis verification | Official info × guest reviews × map location × like-for-like pricing; identity hard rules (chain ≠ brand) |
| 6️⃣ Daily itinerary | Transport first, resort days left unpacked |
| 7️⃣ Whole-platform price lookup | Flights and hotels across platforms (table below) |
| 8️⃣ Continuous price watch | Record lows, same-aircraft pairing, rebook-before-cancel (section below) |

## Whole-platform price comparison

| Target | Source | Verified facts (2026-11) |
|---|---|---|
| Flight floor price | Ctrip calendar API | Free, no login, no key; 366 days of daily lows for any city pair in one call |
| Flight details | Ctrip list page | Flight numbers, times, every flight number of a through-itinerary; degrades gracefully behind the login wall |
| Hotel price | Booking property page | Room table with stay totals and refundable/non-refundable split, filtered by room keyword |
| Hotel price | Agoda property page | Pay = strikethrough minus discount; non-refundable rate picked by DOM parent-walk to avoid cross-matching |

## Continuous price monitoring

- **Record-low state machine**: `values / mins / alerted` keys; announce only a new low, never repeat an unchanged value, clear the key when the price rises past the threshold
- **Silent contract**: an empty stdout from the no_agent cron means nothing happened
- **Per-leg and per-order tracking**: each leg, each order subtotal, and the grand total keep separate record lows
- **Same-aircraft pairing**: the shared return leg recommends one flight for both travellers; through-itineraries are matched to connecting segments by flight number
- **Rebook-before-cancel**: a booked refundable hotel alerts when the listed price drops below what you paid, with the free-cancellation deadline as the decision window
- **Reference threshold**: order totals also report when they fall under your reference price

## Architecture

![Architecture: personality, needs, budget to ten-step flow to price lookup to price watch](assets/architecture.svg)

## Integration: install the skill as a package

```bash
# Hermes
cp -r vibe-trip-skill ~/.hermes/skills/travel/
# Claude Code and friends
cp -r vibe-trip-skill ~/.claude/skills/
```

The package ships two layers, ready to use after copying:

**Planning layer**: load `SKILL.md` and follow the ten-step flow (needs → budget-based destination screening → safety checks → structure → hotel verification → itinerary → calibration → price lookup → price watch → delivery, including the fixed 15-days-before-departure double re-check).

**Tool layer**: the five scripts in `scripts/` run directly from the command line.

```bash
python scripts/ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10 --window 3
python scripts/ctrip_flight_list.py --dep pek --arr bkk --date 2027-06-10
python scripts/hotel_price_check.py --platform booking \
  --url "https://www.booking.com/hotel/th/xxx.html" \
  --checkin 2027-06-10 --checkout 2027-06-17 --nights 7 --room-must Deluxe
python scripts/vibe_trip_monitor.py --verbose   # one local watch run
```

Browser scripts attach over CDP to a real browser (cua-driver and Playwright both talk to the same endpoint), so a QR-code login state survives across runs. Copy `scripts/config.example.json` to a local `vibe_trip_config.json`; real itinerary parameters stay local and never enter the repo.

## Repository layout

```
vibe-trip-skill/
├── README.md / README_EN.md   # bilingual docs
├── SKILL.md                   # skill definition: ten-step flow + toolbox + gotchas
├── LICENSE
├── assets/
│   └── architecture.svg
└── scripts/
    ├── ctrip_lowest_price.py  #   Ctrip calendar floor price (free API, stdlib only)
    ├── ctrip_flight_list.py   #   Ctrip flight list (numbers / times / through-stops)
    ├── hotel_price_check.py   #   Booking/Agoda hotel price check
    ├── vibe_trip_monitor.py   #   multi-leg + multi-hotel watchdog
    ├── vibe_trip_entry.py     #   cron entry (bridges Windows' no-bash shells)
    └── config.example.json    #   config template (placeholders only)
```

## Acknowledgments

- Inspiration: [ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor). The sentinel cron, cursor-based de-duplication, and silent contract used here borrow from the **Xianyu price-watch skill** (`xianyu-monitoring`) built on it. Thank you.
- The deep weeds of price watching (PIPL consent walls, region filters, anti-repeat alerts) are shared with the local `devops/web-price-monitoring` skill.

## Disclaimer

Prices are live page readings that move with inventory, cabin class, exchange rates, and member benefits; the checkout page is the authority. For destination safety, follow the latest advisories from embassies and authoritative bodies.

## License

MIT. If this helps, drop a Star ⭐
