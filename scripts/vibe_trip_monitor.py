#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vibe-trip-skill · 查价盯价监控（no_agent cron 看门狗，静默契约）

契约: 无变化零输出（空 stdout = 静默）；新低 / 破参考价 / 配对变化 / 出错才播报。
      --verbose 附带全部读数（调试用）。

配置: vibe_trip_config.json（同目录，或 VIBE_TRIP_CONFIG 指定）——
  {
    "legs":    [{"key":"L1","dep":"AAA","arr":"BBB","date":"YYYY-MM-DD","label":"..."}, ...],
    "orders":  [{"key":"o1","legs":["L1","L2"],"label":"第一单 ..."}, ...],
    "pairing": {"recommend": "L2", "match": ["L1","L4"]},
    "reference": {"o1": 2000},
    "hotels":  [{"key":"h1","platform":"booking","ss":"...","checkin":"...",
                 "checkout":"...","nights":7,"must":["..."],"cap":null}],
    "chrome":  {"cdp":"http://127.0.0.1:9333","profile":""}
  }
价格源: 携程日历底价 API（免费/免登录）；配对用列表页（国际线未登录时降级提示）。
状态: vibe_trip_state.json（values/mins/alerted，破史低才报、值没变不复读）。
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
VERBOSE = "--verbose" in sys.argv
ALERTS, NOTES = [], []


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def note(msg):
    NOTES.append(msg)


def alert(msg):
    ALERTS.append(msg)


# ---------- 价格：携程日历底价 API（纯标准库，免登录） ----------
API = ("https://m.ctrip.com/restapi/soa2/15380/bjjson/"
       "FlightIntlAndInlandLowestPriceSearch")


def leg_price(dep, arr, date):
    body = {"departNewCityCode": dep.upper(), "arriveNewCityCode": arr.upper(),
            "startDate": date, "grade": 3, "flag": 1,
            "channelName": "FlightIntlOnline", "searchType": 2,
            "passengerList": [{"passengercount": 1, "passengertype": "Adult"}],
            "calendarSelections": [{"selectionType": 8, "selectionContent": ["3"]}]}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json",
                 "referer": "https://flights.ctrip.com/",
                 "user-agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    data = json.loads(raw)
    if data.get("responseStatus", {}).get("Ack") != "Success":
        raise RuntimeError("price api: " + raw[:160])
    for e in data.get("priceList") or []:
        m = re.search(r"/Date\((\d+)", e.get("departDate") or "")
        if not m:
            continue
        day = (datetime.datetime(1970, 1, 1) +
               datetime.timedelta(
                   milliseconds=int(m.group(1)) + 8 * 3600 * 1000)
               ).strftime("%Y-%m-%d")
        if day == date:
            return e.get("price") or 0
    return 0


# ---------- 配对：携程列表页（航班号） ----------
def fetch_list(chrome, dep, arr, date):
    os.environ.setdefault("VIBE_TRIP_CDP",
                           (chrome or {}).get("cdp", "http://127.0.0.1:9333"))
    prof = (chrome or {}).get("profile") or ""
    if prof:
        os.environ.setdefault("VIBE_TRIP_CHROME_PROFILE", prof)
    sys.path.insert(0, HERE)
    from ctrip_flight_list import fetch_flights
    return fetch_flights(dep, arr, date)


def do_pairing(cfg, st):
    """按配置做同航班配对；结果签名变化才播报。"""
    pr = cfg.get("pairing") or {}
    legs = {l["key"]: l for l in cfg.get("legs", [])}
    sig_parts, lines = [], []

    # 国际线列表降级提示（只报一次）
    gated_keys = []
    lists = {}
    for key in set((pr.get("match") or []) + ([pr.get("recommend")] if pr.get("recommend") else [])):
        lg = legs.get(key)
        if not lg:
            continue
        try:
            res = fetch_list(cfg.get("chrome"), lg["dep"], lg["arr"], lg["date"])
        except Exception as e:
            note(f"list {key} error: {str(e)[:80]}")
            continue
        if res.get("gated"):
            gated_keys.append(key)
            continue
        lists[key] = res

    if gated_keys and st.get("alerted", {}).get("intl_login") != "gated":
        alert("⚠️ 国际航班列表需携程登录（旅行浏览器扫码一次），配对核对暂降级；"
              "价格监控不受影响")
        st.setdefault("alerted", {})["intl_login"] = "gated"
    # 注意：intl_login 一旦设置不再清除 —— 携程登录墙时有时无（实测会翻转），
    # 清键会导致每次翻转都重复告警

    # 1) 共享航班（recommend 腿）：推荐两人同航班
    rec_key = pr.get("recommend")
    if rec_key and rec_key in lists and lists[rec_key]["flights"]:
        best = min(lists[rec_key]["flights"], key=lambda f: f["price"])
        line = (f"[{rec_key}] 建议两人同航班: {best['flight']} "
                f"{best['dep_time']}-{best['arr_time']} ¥{best['price']}")
        lines.append(line)
        sig_parts.append("rec:" + best["flight"])

    # 2) 同机航班（match 腿两段）：一段的行程里出现另一段的航班号 = 同一架飞机
    #    例：去程"城市A→城市B→城市C  AB1234+CD5678 经停"的第二段 与 中转段
    #    "城市B→城市C  CD5678"是同一架飞机
    mk = pr.get("match") or []
    if len(mk) == 2 and all(k in lists for k in mk):
        a_key, b_key = mk
        a_items = lists[a_key]["flights"]
        b_items = lists[b_key]["flights"]
        hits = []
        for fb in b_items:
            nums = set(fb.get("flights_all") or [fb["flight"]])
            for fa in a_items:
                common = nums & set(fa.get("flights_all") or [fa["flight"]])
                if common:
                    hits.append((sorted(common)[0], fa, fb))
                    break
        if hits:
            for fn, fa, fb in hits[:3]:
                lines.append(
                    f"[{a_key}×{b_key}] 同机 {fn}: {a_key} 行程 ¥{fa['price']} "
                    f"{fa['dep_time']}→{fa['arr_time']}（含该段） / "
                    f"{b_key} ¥{fb['price']} {fb['dep_time']}-{fb['arr_time']}")
            sig_parts.append("match:" + ",".join(h[0] for h in hits[:3]))
        else:
            lines.append(f"[{a_key}×{b_key}] 两段无同机航班（可接受不同航班）")
            sig_parts.append("match:none")

    if lines:
        sig = "|".join(sig_parts)
        if st.get("alerted", {}).get("pairing") != sig:
            alert("🔀 配对核对\n" + "\n".join(lines))
            st.setdefault("alerted", {})["pairing"] = sig
    return lines


def main():
    cfg_path = os.environ.get("VIBE_TRIP_CONFIG") or os.path.join(
        HERE, "vibe_trip_config.json")
    cfg = load_json(cfg_path, None)
    if not cfg:
        print(f"⚠️ vibe-trip monitor: 缺少配置 {cfg_path}")
        return
    st_path = os.path.join(HERE, "vibe_trip_state.json")
    st = load_json(st_path, {"values": {}, "mins": {}, "alerted": {}})
    values, mins, alerted = st.setdefault("values", {}), \
        st.setdefault("mins", {}), st.setdefault("alerted", {})

    # ---- 逐段价格（史低） ----
    for lg in cfg.get("legs", []):
        key = lg["key"]
        label = lg.get("label", key)
        try:
            cur = leg_price(lg["dep"], lg["arr"], lg["date"])
        except Exception as e:
            alert(f"⚠️ 价格查询失败({key}): {str(e)[:90]}")
            continue
        if not cur:
            note(f"{key}: no price")
            continue
        prev = mins.get(key)
        values[key] = cur
        if prev is None or cur < prev:
            mins[key] = cur
            alert(f"✈ {label} 新低 ¥{cur:g}（原低 ¥{prev:g}）" if prev
                  else f"✈ {label} 首次读数 ¥{cur:g}")
        if VERBOSE:
            note(f"[{key}] {lg['dep']}-{lg['arr']} {lg['date']} = ¥{cur:g} (min ¥{mins.get(key, cur):g})")

    # ---- 单合计（史低 + 参考价） ----
    for od in cfg.get("orders", []):
        key = od["key"]
        label = od.get("label", key)
        vals = [values.get(k) for k in od["legs"]]
        if any(v is None or v <= 0 for v in vals):
            continue
        total = sum(vals)
        prev = mins.get(key)
        values[key] = total
        if prev is None or total < prev:
            mins[key] = total
            alert(f"🧮 {label} 合计新低 ¥{total:g}（原低 ¥{prev:g}）" if prev
                  else f"🧮 {label} 合计首次读数 ¥{total:g}")
        ref = (cfg.get("reference") or {}).get(key)
        if ref and total <= ref and alerted.get(key) != total:
            alert(f"🎯 {label} ¥{total:g} ≤ 参考价 ¥{ref:g}")
            alerted[key] = total
        elif ref and total > ref:
            alerted.pop(key, None)
        if VERBOSE:
            note(f"[{key}] total=¥{total:g} ref={ref}")

    # ---- 配对核对（列表页，尽力而为） ----
    try:
        do_pairing(cfg, st)
    except Exception as e:
        note(f"pairing skipped: {str(e)[:80]}")

    # ---- 酒店（配置驱动，空列表 = 跳过） ----
    for h in cfg.get("hotels", []):
        key = h.get("key", "?")
        try:
            sys.path.insert(0, HERE)
            if h.get("platform") == "agoda":
                from hotel_price_check import check_agoda
                res = check_agoda(h["url"], h["nights"])
            elif h.get("url"):
                # Booking 房产页直查（搜索页会被降级成"无空房"，实测）
                from hotel_price_check import check_booking_property
                res = check_booking_property(h["url"], h["checkin"], h["checkout"],
                                             h["nights"],
                                             room_must=h.get("room_must"))
            else:
                from hotel_price_check import check_booking
                res = check_booking(h["ss"], h["checkin"], h["checkout"],
                                    h["nights"], must=h.get("must") or [h["ss"]])
        except Exception as e:
            alert(f"⚠️ 酒店监控失败({key}): {str(e)[:90]}")
            continue
        if not res.get("found"):
            alert(f"🏨 {key}: 未找到酒店卡片")
            continue
        if res.get("soldout"):
            if alerted.get(key + "_na") != h.get("checkin"):
                alert(f"🏨 {key}: 订满/无空房")
                alerted[key + "_na"] = h.get("checkin")
            continue
        price = res.get("price")
        if price:
            alerted.pop(key + "_na", None)
            prev = mins.get(key)
            values[key] = price
            if prev is None or price < prev:
                mins[key] = price
                alert(f"🏨 {key} 新低 {price}元/{h['nights']}晚（原低 {prev or '—'}）")
            cap = h.get("cap")
            if cap and price <= cap and alerted.get(key) != price:
                alert(f"🏨 {key} 达预算 {price}元 ≤ {cap}元")
                alerted[key] = price
            elif cap and price > cap:
                alerted.pop(key, None)
            # 跌破基准线（如已订可退款价）= 退旧订新机会，严格小于才报
            below = h.get("alert_below")
            if below and price < below and alerted.get(key + "_below") != price:
                alert(f"🔔 {key} 跌破基准 {price}元 < {below}元"
                      f"（已订可退款 → 可退旧订新）")
                alerted[key + "_below"] = price
            elif below and price >= below:
                alerted.pop(key + "_below", None)
        if VERBOSE:
            note(f"[hotel {key}] {json.dumps(res, ensure_ascii=False)[:160]}")

    st["runs"] = st.get("runs", 0) + 1
    st["last"] = time.strftime("%Y-%m-%d %H:%M")
    save_json(st_path, st)

    if VERBOSE:
        print("RUN", st["runs"], st["last"])
        for n in NOTES:
            print("  ", n)
        print("  values:", json.dumps(values, ensure_ascii=False))
        print("  mins:", json.dumps(mins, ensure_ascii=False))
    if ALERTS:
        print("✈ vibe-trip 查价播报 " + time.strftime("%m-%d %H:%M"))
        for a in ALERTS:
            print(a)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"⚠️ vibe-trip monitor fatal: {str(e)[:200]}")
        sys.exit(0)
