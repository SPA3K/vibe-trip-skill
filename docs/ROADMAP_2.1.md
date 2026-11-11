# Vibe Trip 2.1 改造方案（可执行 · 逐文件）

> 目标一句话：**从能用的个人旅行工具，升级为别人也能顺利使用的开源产品。**
> 图例：✅ 本批已完成（2026-11）｜🔜 下一步｜⬜ 计划中
> 追踪指标不是 Star，而是：成功安装 → 第一次规划 → 第一次查价 → 第一次盯价 → 案例回流。

## Phase 1 · 可靠性 P0

监控可靠性优先于新增平台：最伤信任的不是少支持一个网站，而是把错误价格当真实价格播报。

| 事项 | 文件 | 状态 |
|---|---|---|
| 事件分三类：建基线（首读）/ 破史低（标注监控期起点，非全网史低）/ 达参考价或跌破基准 | `scripts/vibe_trip_monitor.py` | ✅ |
| 0 价格 ≠ 无航班：重试一次后仍为 0 → 不写状态、保留可观测；全部航段无数据单独播报 | `scripts/vibe_trip_monitor.py` | ✅ |
| 预算脚本：接口空返回重试、缺失航段不计入合计并显式告警、显示与合计一致 | `scripts/trip_budget.py` | ✅ |
| 价格口径随播报：单人单程含税 / 整段总价含税 / 币种；播报头带数据源 + 查询时点 + 「价格随时变动」 | `monitor` / `trip_budget` | ✅ |
| 原子写状态（tmp + replace）；状态/配置损坏**拒绝静默降级**，非零退出（2=配置, 6=状态, 3=fatal, 4=超时, 5=入口异常） | `vibe_trip_monitor.py` `vibe_trip_entry.py` | ✅ |
| `--ss` 按名查酒店：搜索页只解析房产链接，价格在房产页取（搜索页对自动化会谎报无房） | `hotel_price_check.py` | ✅ 已复验 |
| `--validate` 配置体检命令：日期格式、退房>入住、航段 key 唯一、订单引用存在、重复航段语义显式化（traveler/quantity 而非靠数组重复）、酒店字段完整、预算数值合理、CDP 指向 127.0.0.1 | `vibe_trip_monitor.py --validate` | ⬜ |
| `tests/` + fixtures + GitHub Actions：首读≠新低、涨跌阈值状态机、页面改版/无房/登录墙/超时分类、同机配对不过度断言、并发 cron 不互踩、损坏状态不重置史低 | `tests/` `.github/workflows/test.yml` | ⬜ |
| 价格历史：`data/price_history.jsonl`（每次有效查询一条，带 source/口径/时间戳）→ 趋势、距监控低点、降价速度；标注「监控期最低 ≠ 全网史低」 | `scripts/vibe_trip_monitor.py` | ⬜ |
| 安全卫生：`.gitignore`（state/config/logs/profile/cookies）；CDP 仅允许 localhost；日志过滤 URL 个人参数；把发布脱敏检查脚本化 | 仓库根 `.gitignore` + `scripts/` | ⬜ |

## Phase 2 · 上手门槛 P0

| 事项 | 文件 | 状态 |
|---|---|---|
| 5 分钟跑通：零依赖 first-run 命令 + `pip install playwright` 说明 | `README.md` `README_EN.md` | ✅ |
| 盯价部署节（POSIX crontab / Windows 任务计划 / Hermes no_agent）+ 静默契约 | `README.md` `README_EN.md` | ✅ |
| 英文精简版流程（10 步 + 工具箱 + 关键 Gotchas） | `SKILL_EN.md` | ✅ |
| 关键报错双语（缺 playwright / 缺配置 / CDP 不通） | 各脚本 | ✅ |
| `QUICKSTART.md`：五个问题（能帮我做什么 / 支持哪些 Agent / 怎么装 / 第一次规划怎么说 / 怎么开盯价）+ **入口 A 只规划** 与 **入口 B 开盯价** 分开 | `QUICKSTART.md` | ⬜ |
| 自然语言生成配置：用户一句话 → agent 产出 config → `--validate` → `--verbose` 试跑 → 确认后建 cron（把 JSON 从用户面前拿走） | `SKILL.md` 工作流 | ⬜ |
| 首次运行诊断：chrome / CDP / playwright / config / 网络五项检查报告 | `vibe_trip_monitor.py --doctor` | ⬜ |
| 跨 Agent 实测矩阵（格式兼容 ≠ 运行环境兼容） | `README_EN.md` | ⬜ Hermes ✅，其余按实测填写 |

## Phase 3 · 旅行闭环 P1

把「生成行程」升级为陪用户走完整个旅行周期。四条最优先：**签证入境、航班可行性、预订后管理、旅行中应急**。

| 事项 | 文件 | 状态 |
|---|---|---|
| 酒店比价与订后四条（同条件才可比 / 房型身份核验 / 价格可比性 / 降价≠可无损退订） | `SKILL.md` 第 6 节 | ✅ |
| 退旧订新提醒措辞：先比取消截止日/退款额/房型，不自动建议退订 | `vibe_trip_monitor.py` | ✅ |
| `references/` 拆分：`visa-and-entry.md`（国籍/护照/中转/停留天数/电子入境卡/护照有效期）、`flight-comparability.md`（行李/转机时间/联程/机场转换/红眼/误机风险）、`ground-transport.md`（接送/城际/租车/停车/行李转运入预算）、`insurance.md`（医疗/取消/延误/租车/冒险活动保障对比）、`booking-management.md`（预订顺序：先订/可等/等签证；取消截止日/付款节点/证件信息/入住要求/活动预约/出发前提醒）、`in-trip-emergency.md`（航班取消/酒店无法入住/证件遗失/天气/医疗）、`post-trip-retro.md`（花费/评分/踩坑沉淀为下次偏好） | `references/` | ⬜ |
| `SKILL.md` 瘦身：只留流程、决策规则、触发条件；网页解析/部署细节迁入 `references/monitoring-notes.md`（渐进式加载） | `SKILL.md` | ⬜ |
| 价格历史趋势图（近 7/30 天、距监控低点、达成概率） | `scripts/` | ⬜ |

## Phase 4 · 可展示与传播 P1

| 事项 | 文件 | 状态 |
|---|---|---|
| 全包预算预估 showcase：一条命令出总区间/人均 | `scripts/trip_budget.py` + README 节 | ✅ |
| 两张「一眼看出能得到什么」的图（底价日历热力图、预算卡，真实脚本输出渲染，中英标注） | `assets/` | ✅ |
| About 改 GEO 问题式（真实问题引入 → 解法 → 方法好在哪），中英双语 | 仓库 About | ✅ |
| 措辞纪律：免 key → 「当前实测」；「全平台」→「多来源（当前：携程/Booking/Agoda）」；删除主动索要 Star | `README*` | ✅ |
| README 产品化重排：定位句「Plan by your vibe. Travel at the right price.」+ 三步开始（装 skill → 说出愿望预算 → 确认后可选开盯价） | `README*` | ⬜ |
| 脱敏端到端 Demo（从一句愿望到行程→酒店纠错→预算重算→交给盯价），替代单纯宣传 10 步 | `examples/` | ⬜ |
| `release v2.1.0` + `CHANGELOG.md` + `CONTRIBUTING.md` + issue 模板 | 仓库根 | ⬜ |
| 传播双线：开发者（GitHub / V2EX / Reddit Agent-Skills / Show HN / X 短视频）与大众（小红书/知乎/B站：AI 规划、酒店避坑、订后盯价、同机航班、整包预算五类内容，先结果后技术） | - | ⬜ |

## 结构演进（2.2+）

- `vibe-trip-planner`（规划方法论）与 `vibe-trip-monitor`（价格工具）可拆双 skill，主仓保留整合入口。
- 平台扩展按需：Trip.com（地理重定向待解）、携程酒店、Agoda 搜索 URL 解析。当前覆盖以 README 声明为准。
- 爬虫是工具，旅行决策才是产品：护城河是决策方法论（谁适合什么酒店、何时省钱、降价后是否值得重订）。

## P0 已转 GitHub Issues

配置体检、测试+CI、价格历史、安全卫生、QUICKSTART+自然语言配置 —— 见仓库 Issues 列表。
