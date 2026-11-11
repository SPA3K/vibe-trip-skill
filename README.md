# vibe-trip-skill 🌏✈️

[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](scripts/)
[![i18n](https://img.shields.io/badge/i18n-%E4%B8%AD%E8%8B%B1%E5%8F%8C%E8%AF%AD-brightgreen)](README_EN.md)

**旅行性格 + 需求 + 预算共同驱动的一条龙旅行技能**：从性格与需求探讨出发推导目的地和行程，再全平台查价比价，最后交给 cron 持续盯价。原名 `trip-planner`，2.0 更名。

[English](README_EN.md)

| 即拿即用脚本 | 日历底价 | API 依赖 | 播报方式 | 文档 |
|---|---|---|---|---|
| **5** 个 | **366** 天/次调用 | **0** key · 机票底价免登录 | 无变化零输出 | 中英双语 |

## 痛点 → 解法

| 你大概率遇到过 | 这个仓库怎么解 |
|---|---|
| 比价开十个网页，看到的还是过期价 | 机票底价一条命令返回 366 天日历；酒店直查房产页房型表 |
| 盯价脚本半夜疯狂刷屏 | 静默契约：无变化零输出，破历史低才播报一次 |
| Booking 搜索页对自动化谎报「无空房」 | 改走房产页 `#hprt-table` 房型表，还能按房型关键词锁定你订的那间 |
| 携程国际线登录墙时有时无 | 检测到 `needUserLogin` 就降级到免登录日历 API，价格监控不断档 |
| Windows 的 cron 没有 bash，`.sh` 跑不起来 | `vibe_trip_entry.py` 纯标准库转交器，自动挑带 playwright 的 Python |
| 两个人要坐同一班飞机，靠人眼比航班号 | 同机配对：经停行程与中转段按航班号自动对上，返程直接推荐同航班 |

## 一条龙工作流

| 阶段 | 内容 |
|---|---|
| 1️⃣ 性格与偏好探讨 | 出行节奏、计划型还是随性型、拍照/美食/体验党、风险容忍度 |
| 2️⃣ 需求收集 | 日期、人数、总预算、优先级、明确的「不喜欢清单」 |
| 3️⃣ 定地点 | 按总包横评 2-3 个目的地，安全度两层硬门槛（CDC 疾病层可一票否决；政治层订票时 + 出发前 15 天复核） |
| 4️⃣ 行程结构与预算 | 住宿预算按功能分配，九项预算表反复校准 |
| 5️⃣ 酒店四维核验 | 官方信息 × 住客评论 × 地图位置 × 同条件比价；身份硬核验（集团 ≠ 品牌） |
| 6️⃣ 每日行程 | 交通先行，度假地不排满 |
| 7️⃣ 全平台查价 | 机票 + 酒店多平台比价（见下表） |
| 8️⃣ 持续盯价 | 史低告警、同机配对、退旧订新（见下节） |

## 全平台查价比价

| 目标 | 数据源 | 关键事实（2026-11 实测） |
|---|---|---|
| 机票底价 | 携程日历底价 API | 免费、免登录、免 key；任意城市对一次返回 366 天每日最低价 |
| 航班详情 | 携程列表页 | 航班号、起降时刻、经停行程的全部航班号；国际线撞登录墙时优雅降级 |
| 酒店价格 | Booking 房产页 | 房型表 + 整段总价 + 可取消/不可退款分档，按房型关键词过滤 |
| 酒店价格 | Agoda 房产页 | 实付 = 划线价 − 已减；不可退款档用 DOM 上溯配对，防止串档 |

## 持续价格监控

- **史低状态机**：`values / mins / alerted` 三键，破历史低才报新低，值没变不复读，涨破阈值清键
- **静默契约**：no_agent cron 空 stdout = 静默，有事件才打扰
- **多航段分单盯价**：每段、每单合计、全程合计各自维护独立史低
- **同机航班配对**：共享返程腿推荐两人同航班；经停行程与中转段按航班号识别同机抵达
- **退旧订新**：已订可退款酒店挂牌价跌破实付价即提醒，决策窗口 = 免费取消截止日
- **参考价阈值**：单合计 ≤ 参考价额外播报一条

## 架构

![架构：性格需求预算 → 十步流程 → 查价 → 盯价](assets/architecture.svg)

## 接入方式：skill 整包

```bash
# Hermes
cp -r vibe-trip-skill ~/.hermes/skills/travel/
# Claude Code 等
cp -r vibe-trip-skill ~/.claude/skills/
```

整包包含两层能力，装完即用：

**规划层**：加载 `SKILL.md`，按十步流程走（需求 → 预算筛选目的地 → 安全排查 → 结构 → 酒店核验 → 行程 → 校准 → 查价 → 盯价 → 交付，含出发前 15 天双复核清单）。

**工具层**：`scripts/` 五个脚本可直接命令行调用。

```bash
python scripts/ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10 --window 3
python scripts/ctrip_flight_list.py --dep pek --arr bkk --date 2027-06-10
python scripts/hotel_price_check.py --platform booking \
  --url "https://www.booking.com/hotel/th/xxx.html" \
  --checkin 2027-06-10 --checkout 2027-06-17 --nights 7 --room-must 豪华间
python scripts/vibe_trip_monitor.py --verbose   # 本地跑一轮盯价
```

浏览器类脚本走 CDP 挂真实浏览器（cua-driver 与 Playwright 都能驱动同一端点），扫码登录态可长期复用。配置复制 `scripts/config.example.json` 为本地 `vibe_trip_config.json`，真实行程参数只存本地，不进仓库。

## 仓库结构

```
vibe-trip-skill/
├── README.md / README_EN.md   # 中英双语说明
├── SKILL.md                   # skill 定义：十步流程 + 工具箱 + Gotchas
├── LICENSE
└── scripts/
    ├── ctrip_lowest_price.py  #   携程日历底价（免费 API，纯标准库）
    ├── ctrip_flight_list.py   #   携程航班列表（航班号/时刻/经停）
    ├── hotel_price_check.py   #   Booking/Agoda 酒店比价
    ├── vibe_trip_monitor.py   #   多航段 + 多酒店盯价看门狗
    ├── vibe_trip_entry.py     #   cron 入口（Windows 无 bash 转交器）
    └── config.example.json    #   配置模板（占位符）
```

## 致谢

- 灵感来源：[ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor)。本仓库的哨兵 cron、状态游标防重报、静默契约三件套，借鉴自基于它的**闲鱼查价监控 skill**（`xianyu-monitoring`），特此致谢。
- 盯价技术深水区（PIPL 同意墙、区域过滤、告警防复读）与本机 `devops/web-price-monitoring` skill 同源互补。

## 免责声明

价格为页面实时读数，随库存、舱位、汇率、会员权益变动，以下单页为准。目的地安全信息以使领馆与权威机构最新公告为准。

## License

MIT。觉得有用，点个 Star ⭐
