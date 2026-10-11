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
      "indicator_rendered": true,
      "run_after_within_window": true
    }
  },
  "expected": { "presence_parallel_active": true, "effective_rung": "六档之一" }
}
```

字段口径：

| 字段 | 含义（对应宪法条款） |
|---|---|
| `group_rungs` | 会话所属的全部授权组档，多组取最小；空列表 = 不属于任何授权组 → 取 `account_cap` |
| `n_minutes` | 人设定的 `N`；超过 `N_max`（10 分钟）或不为正 = 配置不合法，在场并行不生效（I-1） |
| `is_large_group` / `explicitly_listed` | 成员数达到阈值 `G`（或成员数判不出）的群，只有被显式逐个列入才生效（I-2） |
| `sticky_exit` | 该会话有未恢复的退出 / 手动降档 / 异常自降（I-1 sticky 结束） |
| `anomaly_downgraded` | 本次在场内正处于异常自降（不变式 4，收缩到 `draft`） |
| `handles_ready` | I-6 除 `cancel` 外的必备手柄全部就绪（可见标识 / 一键退出 / 频次上限 / 逐条回交 / 审计） |
| `backend_cancel` | 该账号出站后端已声明 `cancel`（I-6 可撤单） |
| `item.draft_predates_presence` | 这条稿在本次在场开始之前就已拟好（I-3：仍按 `semi` 逐条放行） |
| `item.indicator_rendered` | 「在场并行中」标识已在该视图呈现（I-3：首条发出须晚于它） |
| `item.run_after_within_window` | 预计放出时刻不晚于 交出时刻 + `W`（I-3） |

覆盖的情形（29 条）：基本四条（不在场 / 在场 + 策略开 / 在场 + 策略关 / 判不出）· 会话档护栏（人设 `parallel` 但策略关、
人设 `draft`、人设 `off`）· 压顶（账号封顶、单组、多组取最小、授权组非空时的账号压顶）· 档位 ≥ `audit`（会话 `auto` 在场仍封顶
`parallel`、会话 `audit` 不在场为 `semi`）· 其余三类动作封顶 `semi` · 异常自降（在场 / 不在场）· sticky 结束 · 进入条件
（`N` 超上限、无 `cancel`、手柄不齐、大群未列入 / 已列入）· 逐条交出条件（积压稿、标识未呈现、放出时刻超窗）。

在场的**开始 / 维持 / 结束**（I-1）属运行时行为，fixture 只给出它的判定结果，不替代消费方对在场采集本身的测试。
消费方（如 AMR）实现生效档判定后，SHOULD 用同一批 fixture 做消费方侧自检（双向自检，同 `message-canonical/` 的做法）。
本目录不含任何真实会话 / 人名 / 账号。
