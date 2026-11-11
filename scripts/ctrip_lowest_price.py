#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vibe-trip-skill · 携程日历底价查询（免费 API，无需登录、无需 key，纯标准库）

用法:
  python ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10
  python ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10 --window 7
  python ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10 --json

输出: 目标日期的该航线最低价（元，CNY）；--window N 附带前后 N 天价格。
price=0 表示该日无航班/无价格。口径 = 携程低价日历（可能含中转/邻近机场最低舱位），
与列表页"¥XX起"可能略有差异，以实际可订价为准。
"""
import argparse
import datetime
import json
import re
import sys
import urllib.request

API = ("https://m.ctrip.com/restapi/soa2/15380/bjjson/"
       "FlightIntlAndInlandLowestPriceSearch")


def fetch_lowest(dep: str, arr: str, start_date: str) -> dict:
    """返回 {YYYY-MM-DD: price}，覆盖 start_date 起约 366 天的低价日历。"""
    body = {
        "departNewCityCode": dep.upper(),
        "arriveNewCityCode": arr.upper(),
        "startDate": start_date,
        "grade": 3,
        "flag": 1,
        "channelName": "FlightIntlOnline",
        "searchType": 2,
        "passengerList": [{"passengercount": 1, "passengertype": "Adult"}],
        "calendarSelections": [{"selectionType": 8, "selectionContent": ["3"]}],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "referer": "https://flights.ctrip.com/",
            "user-agent": "Mozilla/5.0",
        },
    )
    raw = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    data = json.loads(raw)
    if data.get("responseStatus", {}).get("Ack") != "Success":
        raise RuntimeError("API error: " + raw[:200])
    out = {}
    for e in data.get("priceList") or []:
        m = re.search(r"/Date\((\d+)", e.get("departDate") or "")
        if not m:
            continue
        # 携程时间戳为北京时间零点（UTC+8），纯算术换算，跨时区机器也稳
        day = (datetime.datetime(1970, 1, 1) +
               datetime.timedelta(
                   milliseconds=int(m.group(1)) + 8 * 3600 * 1000)
               ).strftime("%Y-%m-%d")
        out[day] = e.get("price")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="携程日历底价（免费API）")
    ap.add_argument("--dep", required=True, help="出发机场/城市三字码, 如 PEK")
    ap.add_argument("--arr", required=True, help="到达三字码, 如 BKK")
    ap.add_argument("--date", required=True, help="目标日期 YYYY-MM-DD")
    ap.add_argument("--window", type=int, default=0, help="附带前后 N 天价格")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()

    try:
        cal = fetch_lowest(a.dep, a.arr, a.date)
    except Exception as e:
        print(f"ERROR {a.dep}-{a.arr} {a.date}: {e}", file=sys.stderr)
        return 1

    price = cal.get(a.date)
    if a.json:
        out = {"route": f"{a.dep.upper()}-{a.arr.upper()}",
               "date": a.date, "price": price}
        if a.window:
            days = sorted(cal)
            if a.date in days:
                i = days.index(a.date)
                out["nearby"] = {d: cal[d] for d in
                                 days[max(0, i - a.window): i + a.window + 1]}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    tag = "无航班/无价" if not price else f"¥{price:g}"
    print(f"{a.dep.upper()}->{a.arr.upper()} {a.date} 最低价: {tag}")
    if a.window and a.date in cal:
        days = sorted(cal)
        i = days.index(a.date)
        for d in days[max(0, i - a.window): i + a.window + 1]:
            mark = " <=" if d == a.date else ""
            print(f"  {d}: {'-' if not cal[d] else '¥%g' % cal[d]}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
