# fixtures/outbox-presence — 在场并行任务（形态 B）的出站派发判定 fixtures

这些 fixture 校验的不是信封，而是 `outbox/dispatch.md` v1.1（rev4）与 `control-and-voice/control-and-voice.md §8.1`
里**可机器判定**的三处规则。`scripts/conformance.py` 用**另一套校验**（`validate_outbox_presence_case` + 三个参考实现）
跑它们，不与信封校验混淆。期望与参考实现不一致即红。

| `check` | 谁做判定 | 参考实现 | 出处 |
|---|---|---|---|
| `enqueue` | 后端受理 `POST /api/outbox` | `evaluate_outbox_enqueue` → `(HTTP 状态, code)` | `outbox/dispatch.md §2.3` 表（按序） |
| `claim` | 后端 worker 对一条 `queued` 任务的处置 | `evaluate_outbox_claim` → `run \| hold \| expire \| cancel` | `outbox/dispatch.md §3` + `control-and-voice.md §8.1` PP-4 |
| `handover` | 消费方能否以形态 B 交出这一条 | `evaluate_outbox_handover` → `presence_parallel \| semi` | `outbox/dispatch.md §0 / §7.1` + `control-and-voice.md §8.1` PP-2…PP-5 |

每条 fixture：

```json
{
  "case": "唯一名",
  "check": "enqueue | claim | handover",
  "rule": "出处",
  "description": "这条在钉什么",
  "input": { "...": "按 check 不同，见下" },
  "expected": { "...": "按 check 不同，见下" }
}
```

- **enqueue**：`input` = `caps`（后端 `outbox` 能力位）· `request`（下单体中与本判定有关的字段）· `control_state`
  （`agent` / `human`）· `run_after_beyond_deadline`（受理时是否已知预计放出时刻晚于截止时刻）；`expected` = `status` + `code`
  （受理时 `code` 为 `null`）。`WRONG_ACCOUNT` 校验照旧最先，不在此建模。
- **claim**：`input` = `authorization` · `control_state` · `secs_since_accept` · `presence_ttl_secs` · `paused`；
  `expected` = `action`。
- **handover**：`input` = `outbox_caps` · `control_caps`（`control-and-voice.md §6.2`）· `control_state`（`agent` / `human` /
  `unknown`，`unknown` = 拉不到，按 HUMAN）· `constitution_item_parallel`（0 号宪法 v2.1「在场并行」节 I-3「单条可按
  `parallel` 交出」的判定结果；该判定本身的 fixture 在 `fixtures/presence-parallel/`，随 PR #25）· `via_outbox`；
  `expected` = `form`（`semi` = 只能按形态 A 逐条人审确认）。

**fixture 不替代的东西**：在场的开始 / 维持 / 结束（0 号宪法 I-1）、HUMAN 检测、GUI 互斥锁（PP-2a）都是运行时行为，
需要各自实现方的测试；这里只钉判定结果。

> 合成占位（公开仓铁律）：`ps_test_*` 在场会话 id，无真实 PII。
