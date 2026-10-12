# fixtures/presence-parallel — 0 号宪法「在场并行」判定 fixtures

这些 fixture 校验的不是信封，而是 **0 号宪法 v2.1「在场并行」节 I-3 的生效档判定**：给定一组输入，
`生效档` 与「在场并行是否生效」必须是哪个值。`scripts/conformance.py` 用**另一套校验**
（`validate_presence_case` + 参考实现 `evaluate_presence_parallel`）跑它们，不与信封校验混淆。

每条 fixture：

```json
{
  "case": "唯一名",
  "rule": "出处",
  "description": "这条在钉什么",
  "input": {
    "account_cap": "六档之一",
    "group_rungs": ["六档之一", "..."],
    "session_rung": "六档之一（人设的会话档）",
    "presence": "present | absent | unknown（unknown = 判不出，按不在场处理）",
    "n_minutes": 10,
    "policy_enabled": true,
    "in_policy_scope": true,
    "is_large_group": false,
    "explicitly_listed": false,
    "sticky_exit": false,
    "anomaly_downgraded": false,
    "handles_ready": true,
    "backend_cancel": true,
    "item": {
      "action": "conversation_send | broadcast | destructive_write | first_contact",
      "draft_predates_presence": false,
      "trigger_predates_presence": false,
      "indicator_rendered": true,
      "t_first_elapsed": true,
      "within_rate_cap": true,
      "run_after_within_window": true,
      "rate": { "send_ordinal": 2, "gap_seconds": 30 },
      "t_first": { "ready_s": 30, "at_s": 30 }
    }
  },
  "expected": { "presence_parallel_active": true, "effective_rung": "六档之一" }
}
```

字段口径：

| 字段 | 含义（对应宪法条款） |
|---|---|
| `group_rungs` | 会话所属的全部授权组档，多组取最小；空列表 = 不属于任何授权组 → 取 `account_cap` |
| `n_minutes` | 人设定的 `N`；`≤ 0`、超过 `N_max`（10 分钟）或 `null`（读不到）= 配置不合法，在场并行不生效（I-1） |
| `in_policy_scope` | 当前在策略作用域内；`null` = 读不到 → 不生效（I-1 fail-closed）。显式列入不能让作用域之外的会话生效 |
| `is_large_group` / `explicitly_listed` | 成员数超过 `G`（10 人）的群，只有被显式逐个列入才生效；`is_large_group: null`（成员数判不出）按超过处理（I-2） |
| `sticky_exit` | 该会话有未恢复的退出 / 手动降档 / 异常自降（I-1 sticky 结束）；`null` = 读不到 → 视为有 |
| `anomaly_downgraded` | 本次在场内正处于异常自降（不变式 4，收缩到 `draft`） |
| `handles_ready` | I-6 除 `cancel` 外的必备手柄全部就绪且读得到（可见标识 / 一键退出 / 频次上限且不宽于 `R_max` / 逐条回交 / 审计） |
| `backend_cancel` | 该账号出站后端已声明 `cancel`（I-6 可撤单） |
| `item.*`（除 `action`） | 任一字段为 `null`（读不到）= 该条按 `semi`（I-3 单条级 fail-closed） |
| `item.trigger_predates_presence` | 这条回复所回应的入站消息在本次在场开始之前就已到达。口径 B（现行，待班迪审定）下不影响判定；口径 A 下为 `true` 即按 `semi`。参考实现常量 `N4_POLICY` |
| `item.within_rate_cap` | 本条交出不超出频次上限（最小间隔与单次在场条数）；超出的那一条按 `semi`，不排队延后（I-3） |
| `item.rate`（可选） | 用宪法上限 `R_max` 的具体数值钉边界时给出：`send_ordinal` = 本次在场以 `parallel` 交出的第几条（**含本条**，≥ 1）；`gap_seconds` = 与该会话上一条 Agent 发出的间隔（秒，≥ 0）。给出时，`within_rate_cap` 必须等于按 `R_max`（班迪 2026-10-12 审定：间隔 **≥ 30 秒**、条数 **≤ 7**）算出的结果——**恰好 30 秒不超出、29.9 秒超出；第 7 条不超出、第 8 条超出**。参考实现常量 `R_MAX_MIN_GAP_SECONDS` / `R_MAX_SENDS_PER_PRESENCE` |
| `item.draft_predates_presence` | 这条稿在本次在场开始之前就已拟好（I-3：仍按 `semi` 逐条放行） |
| `item.indicator_rendered` | 「在场并行中」标识已在该视图呈现（I-3：首条发出须晚于它） |
| `item.t_first_elapsed` | 距在场开始已过 `T_first`（I-3）；未过的那一条按 `semi`，不排队延后 |
| `item.t_first`（可选） | 用 `T_first` 的具体数值钉边界时给出：`ready_s` = 该条就绪待交出时距在场开始的秒数；`at_s` = 判定这一刻距在场开始的秒数（≥ `ready_s`）。给出时，`t_first_elapsed` 必须等于「`ready_s` ≥ 30」（班迪 2026-10-12 审定 `T_first` = **30 秒**）——**恰好 30 秒已过、29 秒未过；10 秒就绪的那一条到 30 秒也不改判**（不排队延后）。参考实现常量 `T_FIRST_SECONDS` |
| `item.run_after_within_window` | 出站后端回告的预计放出时刻存在、可解析，且不晚于 交出时刻 + `W`；回告缺失即为 `false`（I-3） |

覆盖的情形（58 条）：基本四条（不在场 / 在场 + 策略开 / 在场 + 策略关 / 判不出）· 会话档护栏（人设 `parallel` 但策略关、
人设 `draft`、人设 `off`）· 压顶（账号封顶、单组、多组取最小、授权组非空时的账号压顶）· 档位 ≥ `audit`（会话 `auto` 在场仍封顶
`parallel`、会话 `audit` 不在场为 `semi`）· 其余三类动作封顶 `semi` · 异常自降（在场 / 不在场）· sticky 结束 · 进入条件
（`N` 超上限、无 `cancel`、手柄不齐、大群未列入 / 已列入）· 逐条交出条件（积压稿、标识未呈现、未过 `T_first`、放出时刻超窗或回告缺失、离场期间到达消息的新生成回复 = 口径 B）· 读不到
（`N` / sticky / 作用域 / 群成员数为 `null`）· `N` 为 0、负数、10.5 · 会话档 `audit` 不忽略 sticky · 账号封顶 `draft` · 显式列入不越作用域 · 频次上限超出 / 读不到 · `R_max` 边界（第 7 条允许 / 第 8 条按 `semi`；间隔恰好 30 秒允许 / 29.9 秒按 `semi`）· `T_first` 边界（29 秒就绪按 `semi` / 恰好 30 秒允许 / 10 秒就绪到 30 秒仍按 `semi`）· 单条字段读不到（拟出时刻、触发时刻、标识、`T_first`、放出时刻回告）。

在场的**开始 / 维持 / 结束**（I-1）属运行时行为，fixture 只给出它的判定结果，不替代消费方对在场采集本身的测试。
消费方（如 AMR）实现生效档判定后，SHOULD 用同一批 fixture 做消费方侧自检（双向自检，同 `message-canonical/` 的做法）。
本目录不含任何真实会话 / 人名 / 账号。
