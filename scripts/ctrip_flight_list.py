#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vibe-trip-skill · 携程航班列表抓取（航班号/时刻/价格），CDP 附着真实浏览器

用法:
  python ctrip_flight_list.py --dep pek --arr bkk --date 2027-06-10
  python ctrip_flight_list.py --dep pek --arr bkk --date 2027-06-10 --json

环境变量:
  VIBE_TRIP_CDP            CDP 端点（默认 http://127.0.0.1:9333）
  VIBE_TRIP_CHROME_PROFILE Chrome user-data-dir（默认系统临时目录新建；已有浏览器在跑则直接附着）

已知边界（2026-11 实测）:
  - 国内航线列表免登录可抓（含航班号/起降时刻/价格）
  - 国际航线列表携程要求登录（batchSearch 返回 needUserLogin=true），未登录时
    页面只显示"未找到符合条件的航班"+ 推荐卡片 —— 本脚本返回 gated=true 而不是空结果
  - 登录一次（扫码）后同 profile 复用登录态即可正常抓取
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CDP = os.environ.get("VIBE_TRIP_CDP", "http://127.0.0.1:9333")
CHROME = os.environ.get(
    "VIBE_TRIP_CHROME",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE = os.environ.get("VIBE_TRIP_CHROME_PROFILE", "")


def ensure_chrome(timeout=30):
    try:
        urllib.request.urlopen(CDP + "/json/version", timeout=3).read()
        return
    except Exception:
        pass
    args = [CHROME, "--remote-debugging-port=" + CDP.rsplit(":", 1)[1],
            "--no-first-run", "--no-default-browser-check",
            "--new-window", "about:blank"]
    if PROFILE:
        args += ["--user-data-dir=" + PROFILE]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(timeout):
        time.sleep(1)
        try:
            urllib.request.urlopen(CDP + "/json/version", timeout=3).read()
            return
        except Exception:
            continue
    raise RuntimeError("chrome-cdp-unavailable: " + CDP)


def fetch_flights(dep: str, arr: str, date: str) -> dict:
    """返回 {gated: bool, flights: [{flight,dep_time,arr_time,price,raw}], min_price}"""
    from playwright.sync_api import sync_playwright

    url = (f"https://flights.ctrip.com/online/list/oneway-{dep.lower()}-{arr.lower()}"
           f"?depdate={date}&cabin=y_s&adult=1&child=0&infant=0")
    ensure_chrome()
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0] if b.contexts else b.new_context(locale="zh-CN")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        gated_holder = []
        page.on("response", lambda r: gated_holder.append(r)
                if "batchSearch" in r.url else None)
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(12000)
        for _ in range(3):
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(1500)

        gated = False
        for r in gated_holder:
            try:
                if '"needUserLogin":true' in r.text():
                    gated = True
            except Exception:
                pass

        flights = []
        items = page.locator("[class*='flight-item']")
        for i in range(min(items.count(), 40)):
            try:
                t = items.nth(i).inner_text(timeout=2500)
            except Exception:
                continue
            fm = re.search(r"\b([A-Z]{2}\d{3,4})\b", t)
            pm = re.search(r"[¥￥]\s*([\d,]{3,7})", t)
            times = re.findall(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", t)
            if not (fm and pm):
                continue
            # 经停/中转行程会同时展示两个航班号（如 AB1234+CD5678 经停中转），
            # 全量抓出用于"同机航班"配对
            allnums = sorted(set(re.findall(r"\b([A-Z]{2}\d{3,4})\b", t)))
            flights.append({
                "flight": fm.group(1),
                "flights_all": allnums,
                "dep_time": times[0] if len(times) > 0 else "",
                "arr_time": times[1] if len(times) > 1 else "",
                "price": int(pm.group(1).replace(",", "")),
                "raw": " | ".join(x.strip() for x in t.splitlines() if x.strip())[:200],
            })
        if gated and not flights:
            # 国际航线未登录：列表抓不到，但日历底价 API 不受影响
            return {"gated": True, "flights": [], "min_price": None}
        prices = [f["price"] for f in flights]
        return {"gated": gated, "flights": flights,
                "min_price": min(prices) if prices else None}


def main() -> int:
    ap = argparse.ArgumentParser(description="携程航班列表（航班号/时刻/价格）")
    ap.add_argument("--dep", required=True)
    ap.add_argument("--arr", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        res = fetch_flights(a.dep, a.arr, a.date)
    except Exception as e:
        print(f"ERROR {a.dep}-{a.arr} {a.date}: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if res["gated"]:
        print("GATED: 国际航线列表需携程登录（扫码一次），价格请用 ctrip_lowest_price.py")
        return 2
    print(f"{a.dep.upper()}->{a.arr.upper()} {a.date}: "
          f"{len(res['flights'])} 班, 最低 ¥{res['min_price']}")
    for f in sorted(res["flights"], key=lambda x: x["price"])[:10]:
        print(f"  ¥{f['price']:<5} {f['flight']} {f['dep_time']}-{f['arr_time']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
