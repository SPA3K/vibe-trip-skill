# vibe-trip-skill — English quick reference

> Full documentation (Chinese): [SKILL.md](SKILL.md). This file is the condensed English edition for English-speaking agents and users.
> Docs: [README_EN.md](README_EN.md) · [中文 README](README.md)

## What this skill does

One-stop travel skill driven by travel personality, needs, and budget together. It covers the whole chain: discover preferences → pick a destination behind a two-layer safety gate → structure the trip → verify hotels → compare prices across platforms → keep watching prices until departure.

Use it when the user wants to plan a trip, compare flight/hotel prices, or watch prices over time. Do not use it for used-goods monitoring (use `xianyu-monitoring`) or generic scraping advice (use `web-price-monitoring`).

## The ten-step flow

1. **Personality and preference discovery.** Travel pace, planner vs. spontaneous, photo/food/experience focus, risk tolerance. Do not ask for a destination first.
2. **Needs collection.** Dates, party size, total budget, priorities, explicit dislike list. Record budget, dates, and party size as separate hard facts.
3. **Destination selection.** Score 2-3 options against the total budget (other countries always stay in the candidate set). Apply the safety gate in order: CDC disease layer can veto outright; political layer checked at booking time and re-checked 15 days before departure. Never substitute embassy advisories with "I heard".
4. **Structure and budget.** Allocate the hotel budget by function (city self-check stays cheap; island splurge lands on the stay itself). Keep a nine-line budget table and recalibrate it on every itinerary change. `scripts/trip_budget.py` computes the live version in one command.
5. **Hotel four-axis verification.** Official info × guest reviews × map location × like-for-like price comparison, plus the identity hard rules: ownership group ≠ brand, same hotel name in two cities is not the same hotel.
6. **Daily itinerary.** Transport first (cluster by geography, longest leg first), resort days stay unpacked.
7. **Price lookup.** See the toolbox below.
8. **Continuous price watch.** Deploy `vibe_trip_monitor.py` through cron; silent contract applies.
9. **Pre-departure double re-check** at 15 days out: political/flight/hotel/health, four items each. One item failing pauses the plan.
10. **Delivery and retro.** Itinerary, budget, hotel cards; ask the user for post-trip feedback.

## Toolbox (`scripts/`, all standalone CLI)

| Script | What it does | Python |
|---|---|---|
| `ctrip_lowest_price.py` | Ctrip fare calendar: 366 days of daily lows per city pair. Login-free and key-free as of 2026-11 (third-party endpoint), stdlib only. Pass **city codes, not airport codes** (Beijing = BJS; PEK returns all zeros) | any |
| `ctrip_flight_list.py` | Ctrip list page: flight numbers, times, through-itinerary segments; degrades gracefully when the login wall appears | playwright |
| `hotel_price_check.py` | Booking/Agoda hotel prices: by name (`--ss`, auto-resolves the property URL) or by property `--url`; `--room-must` filters room types; `--currency` for display | playwright |
| `trip_budget.py` | Trip budget estimate: live flight + hotel prices plus your daily estimates → total range and per-person | playwright |
| `vibe_trip_monitor.py` | Multi-leg + multi-hotel watchdog: record-low state machine, per-order totals, same-aircraft pairing, rebook alerts. Empty stdout means nothing changed | playwright |
| `vibe_trip_entry.py` | Cron entry for environments where the scheduler has no bash (bridges to a Python that has playwright) | stdlib |

## Key facts (verified 2026-11)

- Ctrip fare calendar API returns daily lows for any city pair in one call, no key, no login. CNY only.
- Ctrip list pages for international routes can flip behind a login wall; the monitor detects `needUserLogin` and falls back to the calendar API so price tracking never stops.
- Booking's **search results page lies to automation** (reports "no availability" even for hotels that have rooms). Read the property page room table (`#hprt-table`) instead; `--ss` resolves the URL from search and then reads the property page.
- Browser scripts attach to local Chrome over CDP (default `http://127.0.0.1:9333`), reusing one QR-code login across runs.

## Watch deployment (silent contract)

```bash
# POSIX cron: twice a day
30 9,21 * * * cd /path/to/vibe-trip-skill && python3 scripts/vibe_trip_monitor.py
```

State lives in `vibe_trip_state.json` (record lows, alerted keys). Copy `scripts/config.example.json` → `vibe_trip_config.json` locally; real itinerary parameters never enter the repo. The example config documents every field: legs, orders (per-person totals vs. grand total), pairing (shared-flight recommendation + same-aircraft match), reference price, hotels (`alert_below` = rebook threshold), and budget.

## Gotchas that matter

- Script output is Chinese; common setup errors print bilingually.
- The monitor must live next to `vibe_trip_config.json` / `vibe_trip_state.json` (same directory).
- Safety gate order (disease before political) and the 15-day political re-check are mandatory in this skill; do not skip them because "news seems quiet".
- Numbers: budgets from real quotes or labeled estimates; all converted into the user's budget currency.

## Acknowledgment

The sentinel-cron / state-cursor / silent-contract design borrows from the Xianyu price-watch skill built on [ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor).

## License

MIT.
