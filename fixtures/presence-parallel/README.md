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
    "group_rung": "六档之一 | null（不属于任何授权组 → 取 account_cap）",
    "session_rung": "六档之一（人设的会话档）",
    "presence": "present | absent | unknown（unknown = 判不出，按不在场处理）",
    "policy_enabled": true,
    "in_policy_scope": true,
    "anomaly_downgraded": false,
    "action": "conversation_send | broadcast | destructive_write | first_contact"
  },
  "expected": { "presence_parallel_active": true, "effective_rung": "六档之一" }
}
```

覆盖的情形：

| fixture | 钉住的规则 |
|---|---|
| `absent_policy_on` | 不在场 → `semi` |
| `present_policy_on` | 在场 + 策略开启 → `parallel` |
| `present_policy_off` | 在场 + 策略未开 → 保持会话档，封顶 `semi` |
| `present_policy_off_session_parallel` | 会话档人手设 `parallel` 但策略未开 → 仍封顶 `semi` |
| `presence_unknown_policy_on` | 在场判不出 → fail-closed → `semi` |
| `present_policy_on_session_draft` | 人有意设低的会话（`draft`）不被在场抬高 |
| `present_policy_on_account_cap_semi` | 账号封顶档压顶，在场并行不越过 |
| `present_policy_on_out_of_scope` | 不在策略作用域 → `semi` |
| `present_policy_on_anomaly` | 本次在场已异常自降 → 不生效，收缩到 `draft` |
| `present_policy_on_broadcast` | 只作用于会话内 send，广播仍封顶 `semi` |

消费方（如 AMR）实现生效档判定后，SHOULD 用同一批 fixture 做消费方侧自检（双向自检，同
`message-canonical/` 的做法）。本目录不含任何真实会话 / 人名 / 账号。
