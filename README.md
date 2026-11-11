# vibe-trip-skill 🌏✈️

**一条龙旅行技能：旅行性格 + 需求 + 预算共同驱动（不是纯预算驱动）—— 从性格/需求探讨到定地点，再到全平台查价比价与持续价格监控。**

原名 `trip-planner`，2.0 更名为 **vibe-trip-skill**。既可以直接 `python scripts/*.py` **即拿即用**（无需 Agent、无需注册），也可以作为 **Agent Skill** 加载（Hermes / Claude 等），浏览器类能力同时支持 **cua-driver 接入**（CDP 附着真实浏览器，共享登录态）。

[English](README_EN.md)

---

## 一条龙工作流

| 阶段 | 内容 |
|---|---|
| 1️⃣ 性格与偏好探讨 | 出行节奏（暴走 vs 躺平）、计划型 vs 随性型、拍照/美食/体验党、风险容忍度 —— 从「你是谁」推导「去哪」 |
| 2️⃣ 需求收集 | 日期、人数、总预算、海岛/城市/人文优先级、明确的「不喜欢清单」 |
| 3️⃣ 定地点 | 按总包预算横评 2-3 个目的地 + **安全度两层硬门槛**（CDC 疾病/备孕健康层可一票否决；政治地貌层订票时 + 出发前 15 天复核） |
| 4️⃣ 行程结构与预算 | 按功能分配住宿预算（城市省、海岛花），九项预算表反复校准 |
| 5️⃣ 酒店四维核验 | 官方信息 × 真实住客评论 × 地图位置 × 同条件比价；**身份硬核验**（集团 ≠ 品牌，「已订」四要素） |
| 6️⃣ 每日行程 | 交通先行，度假地不排满 |
| 7️⃣ **全平台查价** | 机票 + 酒店多平台比价（见下） |
| 8️⃣ **持续盯价** | 史低告警、同机航班配对、退旧订新（见下） |

## 全平台查价比价

| 目标 | 数据源 | 特点 |
|---|---|---|
| 机票底价 | **携程日历底价 API** | 🆓 免费、免登录、免 key；任意城市对一次返回 366 天每日最低价 |
| 航班详情 | **携程列表页** | 航班号、起降时刻、经停行程的全部航班号（同机配对的依据）；国际线登录墙时有会优雅降级 |
| 酒店价格 | **Booking 房产页** | 房型表 + 整段总价 + 可取消/不可退款分档（搜索页会对自动化谎报「无房」，房产页才是真库存） |
| 酒店价格 | **Agoda 房产页** | 价格对公式：实付 = 划线价 − 已减；不可退款档 DOM 上溯配对 |

## 持续价格监控

- **史低状态机**：`values / mins / alerted` 三键 —— 破历史低才报新低、值没变不复读、涨破阈值清键
- **静默契约**（no_agent cron）：无变化零输出，有事件才打扰
- **多航段分单盯价**：每段 + 每单合计 + 全程合计，全部独立史低
- **同机航班配对**：共享返程腿推荐两人同航班；去程经停行程与中转段按航班号识别**同机抵达**
- **退旧订新**：已订可退款酒店挂牌价跌破实付价 → 提醒退旧订新，决策窗口 = 免费取消截止日
- **单合计参考价阈值**：合计 ≤ 参考价即播报

## 快速开始（即拿即用）

```bash
# 机票底价（纯标准库，任何 Python 直接跑）
python scripts/ctrip_lowest_price.py --dep PEK --arr BKK --date 2027-06-10 --window 3

# 航班列表（需 playwright；走 CDP 附着已开的浏览器或自动拉起）
python scripts/ctrip_flight_list.py --dep pek --arr bkk --date 2027-06-10

# 酒店比价（Booking 房产页，房型关键词为 AND 语义）
python scripts/hotel_price_check.py --platform booking \
  --url "https://www.booking.com/hotel/th/xxx.html" \
  --checkin 2027-06-10 --checkout 2027-06-17 --nights 7 --room-must 豪华间

# 多航段 + 多酒店持续盯价（本地跑一轮）
python scripts/vibe_trip_monitor.py --verbose
```

配置：复制 `scripts/config.example.json` 为本地 `vibe_trip_config.json`（真实行程参数只存本地，**不进仓库**）。

## 两种接入方式

**① 即拿即用（CLI）** —— 任何机器 `python scripts/xxx.py` 直接出结果；配合 cron（Windows 用 `vibe_trip_entry.py` 入口）即成无人值守盯价。

**② Agent + cua-driver** —— 浏览器脚本统一走 CDP（默认 `http://127.0.0.1:9333`）附着**真实浏览器**：扫码登录态复用（一次扫码长期有效）、验证码/同意墙可在会话内人工处理、核验截图直接发到对话里看。Agent 侧用 cua-driver / Playwright `connect_over_cdp` 驱动同一浏览器，与 CLI 共享 profile，互不打架。

## 作为 Agent Skill 安装

```bash
# Hermes
cp -r vibe-trip-skill ~/.hermes/skills/travel/
# Claude Code 等
cp -r vibe-trip-skill ~/.claude/skills/
```

加载后按 SKILL.md 的十步流程走：需求 → 预算筛选 → 安全排查 → 结构 → 酒店核验 → 行程 → 预算 → 查价 → 盯价 → 交付（含出发前 15 天双复核清单）。

## 仓库结构

```
vibe-trip-skill/
├── README.md / README_EN.md   # 中英双语说明
├── SKILL.md                   # Agent Skill 定义（十步流程 + 工具箱 + Gotchas）
├── LICENSE
└── scripts/                   # 即拿即用工具箱
    ├── ctrip_lowest_price.py  #   携程日历底价（免费 API，纯标准库）
    ├── ctrip_flight_list.py   #   携程航班列表（航班号/时刻/经停）
    ├── hotel_price_check.py   #   Booking/Agoda 酒店比价
    ├── vibe_trip_monitor.py   #   多航段+多酒店盯价看门狗（静默契约）
    ├── vibe_trip_entry.py     #   cron 入口（Windows 无 bash 的转交器）
    └── config.example.json    #   配置模板（占位符）
```

## 致谢 / Acknowledgments

- **灵感来源：闲鱼查价监控 skill**（`xianyu-monitoring`，基于 ai-goofish-monitor 的实践）—— 本仓库的哨兵 cron、状态游标（`last_id` 防重报）、降价静默契约、关注清单基线对比，均借鉴自那套闲鱼查价/盯价设计，特此致谢！
- 盯价技术深水区（PIPL 同意墙、区域过滤、告警防复读十坑）与 `web-price-monitoring` skill 同源互补。

## 免责声明

所有价格为页面实时读数，可能随库存、舱位、汇率、会员权益变动；**以实际下单页价格为准**。目的地安全信息请以使领馆与权威机构最新公告为准。

## License

MIT
