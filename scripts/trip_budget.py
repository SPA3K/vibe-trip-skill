#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vibe-trip-skill · 全包预算预估 Trip budget estimate（showcase）

一条命令提前算出整趟旅行的预计花费：
  机票 = 携程日历底价 API 实时价（CNY，按 orders 里的合计单展开，人手一张）
  酒店 = Booking/Agoda 房产页实时总价（CNY）
  餐饮/当地交通/景点体验 = 日预算 × 天数 × 人数（估算）
  保险 = 单人价 × 人数；机动费用 = 上述小计 × 比例（估算）
  估算部分给出 ±20% 区间，全包出「已确认 + 估算」总区间与人均。

用法:
  python trip_budget.py                      # 读同目录 vibe_trip_config.json
  python trip_budget.py --config my.json
  python trip_budget.py --json
配置需含 budget 段:
  "budget": {"flight_order": "grand", "persons": 2, "days": 11,
             "daily": {"food": 200, "transport": 100, "tickets": 150},
             "insurance_per_person": 200, "misc_pct": 0.1}
说明: 机票日历 API 只返回 CNY，预算统一以 CNY 汇总；酒店实时查询需要
playwright + 浏览器 CDP（同 monitor），约 40s/家。
坑: 日历 API 收城市码不是机场码——北京传 BJS 不传 PEK/PKX，否则返回全 0。
"""
import argparse
import datetime
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load_json(path, default=None):
    """返回 (obj, err)。err=None 正常；err='missing' 文件不存在；
    err='corrupt' 存在但 JSON 损坏（绝不悄悄降级为默认值——那会重置史低）。"""
    if not os.path.exists(path):
        return default, "missing"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, f"corrupt: {str(e)[:80]}"


def hotel_price(h):
    """实时查一家酒店的整段总价（CNY）。返回 (price|None, note)。"""
    try:
        if h.get("platform") == "agoda":
            from hotel_price_check import check_agoda
            res = check_agoda(h["url"], h["nights"])
        else:
            from hotel_price_check import check_booking_property
            res = check_booking_property(h["url"], h["checkin"], h["checkout"],
                                         h["nights"],
                                         room_must=h.get("room_must"))
    except Exception as e:
        return None, f"查询失败 {str(e)[:60]}"
    if not res.get("found"):
        return None, "未找到"
    if res.get("soldout"):
        return None, "该日期订满"
    return res.get("price"), res.get("room", "")


def main():
    ap = argparse.ArgumentParser(description="全包预算预估 / trip budget estimate")
    ap.add_argument("--config", default=os.path.join(HERE, "vibe_trip_config.json"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cfg, err = load_json(a.config)
    if err == "corrupt":
        print(f"⚠️ 配置文件损坏 config corrupt（不静默降级）: {a.config} | {err}")
        return 2
    if not cfg:
        print("⚠️ 缺少配置 config not found: " + a.config)
        return 1
    bg = cfg.get("budget") or {}
    if not bg:
        print("⚠️ 配置缺少 budget 段 / config missing 'budget' section: " + a.config)
        return 1

    persons = int(bg.get("persons", 2))
    flights_key = bg.get("flight_order") or ("grand" if any(
        o.get("key") == "grand" for o in cfg.get("orders", [])) else None)
    orders = {o["key"]: o for o in cfg.get("orders", [])}
    legs = {l["key"]: l for l in cfg.get("legs", [])}
    if not flights_key or flights_key not in orders:
        print("⚠️ budget.flight_order 指向的单不存在 / unknown order: " + str(flights_key))
        return 1
    flight_legs = orders[flights_key]["legs"]

    # 天数：显式 > 酒店日期跨度 > 机票日期跨度
    days = bg.get("days")
    if not days:
        ds = [h.get("checkin") for h in cfg.get("hotels", [])] + \
             [h.get("checkout") for h in cfg.get("hotels", [])] + \
             [l.get("date") for l in legs.values()]
        ds = sorted(d for d in ds if d)
        if len(ds) >= 2:
            days = (datetime.date.fromisoformat(ds[-1]) -
                    datetime.date.fromisoformat(ds[0])).days
    if not days:
        print("⚠️ 无法确定天数 / cannot derive days（在 budget.days 里写死）")
        return 1

    lines = []
    live_items, live_sum = [], 0
    missing_legs = []
    # ---- 机票（实时，去重后逐段查；日历接口偶发空返回，重试一次） ----
    from ctrip_lowest_price import fetch_lowest
    seen_lk = []
    for lk in flight_legs:
        if lk not in seen_lk:
            seen_lk.append(lk)
    for lk in seen_lk:
        lg = legs.get(lk)
        if not lg:
            continue
        price = 0
        for _attempt in (1, 2):
            try:
                cal = fetch_lowest(lg["dep"], lg["arr"], lg["date"])
                price = cal.get(lg["date"]) or 0
            except Exception as e:
                price = 0
                last_err = str(e)[:50]
            if price:
                break
        n = flight_legs.count(lk)
        name = f"✈ {lk} {lg['dep']}->{lg['arr']} {lg['date']}"
        if not price:
            # 0 = 重试后仍无数据：可能无航班，也可能接口空返回，两者不可区分
            missing_legs.append(lk)
            live_items.append((name, 0, n, 0))
            continue
        price = int(round(price))
        item = price * n
        live_sum += item
        live_items.append((name, price, n, item))
    live_block = live_items

    # ---- 酒店（实时） ----
    hotel_block = []
    for h in cfg.get("hotels", []):
        price, note = hotel_price(h)
        key = h.get("key", "?")
        if price:
            hotel_block.append((f"🏨 {key} {note}", price, 1, price))
            live_sum += price
        else:
            hotel_block.append((f"🏨 {key}", 0, 0, 0))
            lines.append(f"     ({key}: {note})")

    # ---- 估算 ----
    daily = bg.get("daily") or {}
    est_block, est_sum = [], 0
    daily_labels = {"food": "🍽 餐饮 Food", "transport": "🚕 当地交通 Local transport",
                    "tickets": "🎫 景点体验 Activities"}
    for k in ("food", "transport", "tickets"):
        v = daily.get(k)
        if v:
            amt = int(v) * days * persons
            est_sum += amt
            est_block.append((f"{daily_labels[k]} {int(v)}×{days}天×{persons}人", amt))
    ins = bg.get("insurance_per_person")
    if ins:
        amt = int(ins) * persons
        est_sum += amt
        est_block.append((f"🛡 保险 Insurance {int(ins)}×{persons}人", amt))
    misc_pct = float(bg.get("misc_pct", 0))
    if misc_pct:
        amt = int((live_sum + est_sum) * misc_pct)
        est_sum += amt
        est_block.append((f"🎒 机动费用 Misc buffer {misc_pct:.0%}", amt))

    lo, hi = int(est_sum * 0.8), int(est_sum * 1.2)
    total_lo, total_hi = live_sum + lo, live_sum + hi

    if a.json:
        print(json.dumps({
            "currency": "CNY", "persons": persons, "days": days,
            "basis": "flights=per-person one-way incl. tax; hotels=stay total incl. tax",
            "live": {"items": [{"name": n, "unit": p, "qty": q, "amount": t}
                               for n, p, q, t in live_block],
                     "hotels": [{"name": n, "amount": t}
                                for n, p, q, t in hotel_block if p],
                     "subtotal": live_sum,
                     "missing_legs": missing_legs},
            "estimate": {"items": [{"name": n, "amount": t} for n, t in est_block],
                         "subtotal": est_sum, "range": [lo, hi]},
            "total_range": [total_lo, total_hi],
            "per_person_range": [total_lo // persons, total_hi // persons],
        }, ensure_ascii=False, indent=1))
        return 0

    W = 54
    print("=== vibe-trip 全包预算预估 Trip budget estimate ===")
    print(f"人数 persons={persons}  天数 days={days}  币种 CNY")
    print("口径 basis: 机票=单人单程含税 · 酒店=整段总价含税 · 估算=日预算×天数×人数")
    print("[实时价 Live] 来源：携程日历底价API + Booking/Agoda 房产页")
    for n, p, q, t in live_block:
        qty = f" ×{q}" if q > 1 else ""
        if not p:
            print(f"  {n:<36}{'无报价':>9}{qty:<4}   ⚠️ 不计入合计")
        else:
            print(f"  {n:<36}{p:>9,}{qty:<4}={t:>9,}")
    for n, p, q, t in hotel_block:
        if p:
            print(f"  {n:<36}{p:>9,}{'':<4}={t:>9,}")
        else:
            print(f"  {n:<36}{'—':>9}")
    print(f"  {'实时小计 Live subtotal':<36}{'':>9}    {live_sum:>9,}")
    print("[估算 Estimate] 来源：日预算×天数×人数，区间 ±20%")
    for n, t in est_block:
        print(f"  {n:<48}{t:>9,}")
    print(f"  {'估算小计 Estimate subtotal':<48}{est_sum:>9,}  ({lo:,}~{hi:,})")
    print("-" * W)
    print(f"  💰 全包预计 Total   ¥{total_lo:,} ~ ¥{total_hi:,}"
          f"   人均/per person ¥{total_lo // persons:,} ~ ¥{total_hi // persons:,}")
    if missing_legs:
        print(f"  ⚠️ 未计入合计 not summed（接口空返回或无航班，两者不可区分）: "
              f"{', '.join(missing_legs)} — 重跑或用列表页复核")
    for x in lines:
        print("  " + x)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"⚠️ trip_budget fatal: {str(e)[:200]}")
        sys.exit(3)
