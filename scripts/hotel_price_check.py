#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vibe-trip-skill · 酒店比价查询（Booking / Agoda 配方，CDP 附着真实浏览器）

用法:
  python hotel_price_check.py --platform booking --ss "酒店完整名称" \
      --checkin 2027-06-10 --checkout 2027-06-17 --nights 7 --must 关键词
  python hotel_price_check.py --platform agoda --url "https://www.agoda.cn/...hotel...html?..." \
      --nights 7
  追加 --json 输出机器可读结果。

环境变量: VIBE_TRIP_CDP / VIBE_TRIP_CHROME_PROFILE（同 ctrip_flight_list.py）

配方要点（本机实测沉淀，详见 SKILL.md）:
  - Booking: searchresults.html?ss=...&selected_currency=CNY&order=price；
    PIPL 同意墙用 JS 按 index 点隐藏 input（locator.check() 必超时）；
    晚数正向匹配 "N晚"（防促销文案「连住2晚」劫持）；订满关键词去重告警
  - Agoda: 房产页带 checkIn/checkOut/currency=CNY 参数（会转 .cn 但参数保留）；
    价格对公式 实付 = 划线价 − 已减；不可退款档用 DOM 上溯配对防串档
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CDP = os.environ.get("VIBE_TRIP_CDP", "http://127.0.0.1:9333")
CHROME = os.environ.get(
    "VIBE_TRIP_CHROME",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE = os.environ.get("VIBE_TRIP_CHROME_PROFILE", "")
SOLDOUT_KW = ("订满", "无空房", "不可订", "没有空房", "已订完", "无法预订")


def ensure_chrome(timeout=30):
    try:
        urllib.request.urlopen(CDP + "/json/version", timeout=3).read()
        return
    except Exception:
        pass
    import subprocess
    import time
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


def _page():
    from playwright.sync_api import sync_playwright
    ensure_chrome()
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context(locale="zh-CN")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, page


def check_booking(ss, checkin, checkout, nights, must=None, alt=None):
    """返回 {found, price, soldout, name, nights_ok}。must = 卡片必须含的关键词列表。"""
    must = must or [ss]
    p, page = _page()

    def search(qss):
        url = ("https://www.booking.com/searchresults.html"
               f"?ss={urllib.parse.quote(qss)}&checkin={checkin}&checkout={checkout}"
               "&group_adults=2&no_rooms=1&selected_currency=CNY&lang=zh-cn")
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(7000)
        if "pipl" in page.url or "需同意" in page.title():
            for idx in (1, 2, 4, 3):  # 隐藏 input 必须 JS 点，check() 必超时
                page.evaluate(
                    """(i)=>{const e=document.querySelectorAll(
                       'input[type=checkbox]')[i]; if(e&&!e.checked)e.click();}""", idx)
            page.locator("button:has-text('同意')").first.click(timeout=4000)
            page.wait_for_timeout(6000)
        cards = page.locator('[data-testid="property-card"]')
        for _ in range(12):
            for i in range(min(cards.count(), 40)):
                try:
                    t = cards.nth(i).inner_text(timeout=2000)
                except Exception:
                    continue
                if any(k.lower() in t.lower() for k in must):
                    return t, cards.count()
            page.mouse.wheel(0, 2600)
            page.wait_for_timeout(1200)
        return None, cards.count()

    try:
        t, _ = search(ss)
        if t is None and alt:
            t, _ = search(alt)
        if t is None:
            return {"found": False}
        sold = any(kw in t for kw in SOLDOUT_KW)
        nights_ok = bool(re.search(rf"(?<!\d){nights}\s*晚", t))
        m = (re.search(r"价格\s*([\d,]+)\s*元", t)
             or re.search(r"([\d,]{3,7})\s*元", t)
             or re.search(r"[¥￥]\s*([\d,]{3,7})", t))
        price = int(m.group(1).replace(",", "")) if m else None
        lines = [x.strip() for x in t.splitlines() if x.strip()]
        return {"found": True, "soldout": sold, "price": price,
                "nights_ok": nights_ok, "name": lines[0] if lines else ""}
    finally:
        p.stop()


def check_agoda(url, nights):
    """Agoda 房产页：返回 {found, price(估算总价), nightly, soldout}。
    价格对公式：实付 = 划线价 − 已减；不可退款档 DOM 上溯配对。"""
    p, page = _page()
    try:
        page.goto(url, timeout=50000, wait_until="domcontentloaded")
        for _ in range(3):
            page.wait_for_timeout(5000)
            page.mouse.wheel(0, 1800)
        page.wait_for_timeout(2500)
        txt = page.inner_text("body")
        sold = any(kw in txt for kw in SOLDOUT_KW)
        # 走不可退款档最低夜价（DOM 配对，防串档）
        blocks = page.evaluate(r"""() => {
            const kws = ['不可取消','不可退款','不退款','不可修改','非退款','不得取消'];
            const payOf = (t) => {
                const m = t.match(/已减([\d,]+)\s*RMB[\s\S]{0,60}?¥\s*([\d,]{3,7})/);
                if (!m) return null;
                const d = parseInt(m[1].replace(/,/g,''));
                const s = parseInt(m[2].replace(/,/g,''));
                return s > d ? s - d : null;
            };
            const out = [];
            document.querySelectorAll('span,div,p,li').forEach(el => {
                const t = (el.textContent || '').trim();
                if (t.length >= 4 && t.length < 60 && kws.some(k => t.includes(k))) {
                    let node = el, best = null;
                    for (let i = 0; i < 9 && node; i++) {
                        const nt = node.textContent || '';
                        if (/已减[\d,]+\s*RMB/.test(nt)) { best = nt; break; }
                        node = node.parentElement;
                    }
                    const pay = best ? payOf(best) : null;
                    if (pay) out.push(pay);
                }
            });
            return out;
        }""")
        if blocks:
            nightly = min(blocks)
            return {"found": True, "soldout": sold, "nightly": nightly,
                    "price": nightly * nights}
        return {"found": True, "soldout": sold, "nightly": None, "price": None}
    finally:
        p.stop()


def check_booking_property(url, checkin, checkout, nights, room_must=None):
    """房产页直查（推荐路线）。

    2026-11 实测：Booking 搜索结果页会对自动化访问降级成"暂无空房"（连大型酒店
    近期日期都谎报），但房产页带日期参数的房型表是真实库存 —— 用房产页。
    返回 {found, soldout, price, refundable_price, room, offers:[{room,price,refundable}]}
    price = 匹配房型的可取消价（无则最低价），均为整段住宿总价（含税）。
    room_must = 房型名关键词（AND 语义，如 ["豪华间","阳台"]）；缺省取全店最低。
    """
    base = url.split("?")[0]
    pu = (f"{base}?checkin={checkin}&checkout={checkout}"
          "&group_adults=2&no_rooms=1&selected_currency=CNY&lang=zh-cn")
    p, page = _page()
    try:
        page.goto(pu, timeout=50000, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        page.evaluate("""() => {
            const el = document.querySelector('#hprt-table');
            if (el) el.scrollIntoView(); else window.scrollBy(0, 3000);
        }""")
        page.wait_for_timeout(5000)
        for _ in range(3):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(2000)
        page.wait_for_timeout(3000)
        rows = page.evaluate(r"""() => {
            const tbl = document.querySelector('#hprt-table');
            if (!tbl) return null;
            return Array.from(tbl.querySelectorAll('tr')).map(tr => ({
                cls: (tr.className || ''),
                txt: (tr.innerText || '').replace(/\s+/g, ' ').slice(0, 600)
            }));
        }""")
        body = page.inner_text("body")
        if rows is None:
            sold = any(k in body for k in ("暂无空房", "无空房", "此日期"))
            return {"found": True, "soldout": sold, "price": None,
                    "refundable_price": None, "room": "", "offers": []}
        offers, cur = [], ""
        for r in rows:
            t = r["txt"]
            if "适合：" in t:            # 带房型名的行（同房型的第二行是不可退款报价）
                cur = t.split("适合：")[0].strip()
            m = re.search(r"现价\s*([\d,]+)元", t)
            if not m or not cur:
                continue
            offers.append({
                "room": cur,
                "price": int(m.group(1).replace(",", "")),
                "refundable": "可免费取消" in t,
            })
        if not offers:
            return {"found": True, "soldout": True, "price": None,
                    "refundable_price": None, "room": "", "offers": []}
        sel = offers
        if room_must:
            sel = [o for o in offers
                   if all(k.lower() in o["room"].lower() for k in room_must)]
            if not sel:                # 目标房型没了 = 该房型订满
                return {"found": True, "soldout": True, "price": None,
                        "refundable_price": None, "room": "", "offers": offers}
        ref = [o for o in sel if o["refundable"]]
        pick = min(ref or sel, key=lambda o: o["price"])
        ref_prices = [o["price"] for o in sel if o["refundable"]]
        return {"found": True, "soldout": False, "price": pick["price"],
                "refundable_price": min(ref_prices) if ref_prices else None,
                "room": pick["room"], "offers": offers}
    finally:
        p.stop()


def main() -> int:
    ap = argparse.ArgumentParser(description="酒店比价（Booking/Agoda）")
    ap.add_argument("--platform", choices=["booking", "agoda"], required=True)
    ap.add_argument("--ss", help="Booking 搜索词（酒店完整名称）")
    ap.add_argument("--url", help="Booking 房产页 URL（推荐，绕过搜索页降级）或 Agoda 房产页 URL")
    ap.add_argument("--room-must", action="append", default=[],
                    help="房型名关键词（AND），如 --room-must 豪华间 --room-must 阳台")
    ap.add_argument("--checkin")
    ap.add_argument("--checkout")
    ap.add_argument("--nights", type=int, required=True)
    ap.add_argument("--must", action="append", default=[],
                    help="Booking 卡片必须含的关键词，可重复")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        if a.platform == "booking":
            if a.url:
                res = check_booking_property(a.url, a.checkin, a.checkout,
                                             a.nights, room_must=a.room_must or None)
            elif a.ss and a.checkin and a.checkout:
                res = check_booking(a.ss, a.checkin, a.checkout, a.nights,
                                    must=a.must or [a.ss])
            else:
                ap.error("booking 需要 --url 或 (--ss --checkin --checkout)")
        else:
            if not a.url:
                ap.error("agoda 需要 --url")
            res = check_agoda(a.url, a.nights)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
