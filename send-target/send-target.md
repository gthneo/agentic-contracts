# 发送目标契约 v1 — Send Target Contract（冷会话自动翻出）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`send-target/` → AMR/@gthneo）。

> **日期** 2026-06-28 ｜ **状态** 提案（待 fullwechat 后端实现）
> **from** AgenticMessageRouter (AMR) ｜ **to** fullwechat 后端
> **真相源** `agentic-contracts` 仓（本文件）—— AMR 定义契约，fullwechat 实现。
> **姊妹契约** `../message/canonical.md`（读）/ `../moments/read-like.md`（朋友圈）

---

## §0 这份契约修什么（交互缺陷）

**现状缺陷（王总 2026-06-28 钦定为契约 bug）**：fullwechat 发送只能发给**当前在微信"近期会话列表"里、能选中**的会话；目标若不在（冷会话），AMR 适配器（`fullwechat.send`，`_live_chat_ids` 预检）**拒发并要人去 VNC 手工打开**那个对话。

这把**后端的 UI 局限甩给了人**——像「王珺熙」这种**已知联系人**（AMR 早有她稳定的 `chat_id`/`wxid`），系统理应**自己把她翻出来**（搜索→打开会话→发），不该让人手工去 VNC 翻。

**本契约要求**：发送端对**任何已知 `chat_id`**，在目标不在近期列表时**自动解析 + 打开会话**再发，把"先手动开聊天"这步**自动化掉**。

---

## §1 硬性要求

1. **可发任意已知会话**：发送端接受一个稳定 `chat_id`（AMR 从读契约/入库数据里早已持有），**不要求它当前可选中**。
2. **不可选中 → 自动翻出**：目标不在近期列表时，后端**自动搜索联系人 + 打开其会话**（进入可选中态）后再发。这一步是**机械动作（找到正确窗口），不是决策**——人已经在 AMR 侧确认过发什么（HITL 不变）。
3. **按稳定 id 解析，绝不模糊猜**：解析以 `chat_id`/`wxid`（稳定标识）为准。**严禁按显示名模糊匹配后误发给同名/相近的人**。若 `chat_id` 解析不到唯一会话 → **返回可执行错误**（`ok:false` + 原因），**绝不瞎发**（保留现有 "Never guesses a target" 安全底线）。
4. **回执标明是否自动翻出**：成功响应里带 `opened`（bool）—— `true` = 后端为这次发送自动打开了冷会话；`false` = 本就可选中。供 AMR 留痕/可观测。

---

## §2 端点形态

复用现有发送端点（AMR 经 `fullwechat.send_text(chat_id, body)` 调）。语义升级为：

**请求**：发送某 `chat_id`（不再前置要求它在近期列表）。

**成功**：
```json
{ "ok": true, "chat_id": "wxid_test_wangjunxi", "opened": true }
```
（`opened:true` = 后端自动翻出并打开了该冷会话）

**失败（解析不到唯一会话，不猜不发）**：
```json
{ "ok": false, "chat_id": "wxid_test_wangjunxi", "code": "CONTACT_NOT_FOUND", "error": "wxid 不是联系人，解析不到可发会话" }
```

### §2.1 口径定稿（2026-06-28 实现回执后 AMR 拍板）

回应 fullwechat 实现回执的 5 问，**真相源定论如下**：

1. **响应键名 = `ok`（canonical）**。`success` 为旧端点遗留，**过渡期后端两个都返回**（`ok` 镜像 `success`）；**AMR 改为读 `ok`（缺失时回落 `success`）**。AMR 部署"读 `ok`"版本后，后端**可去掉 `success`**（去不去都不破，但 canonical 以 `ok` 为准）。
2. **`chat_id` 一律 snake_case**（与 message.canonical 的 `chat_id`/`msg_id` 同族）。响应里就叫 `chat_id`，不要 `chatId`。（注:既有 `/api/messages/send` 请求体历史用 `chatId`，那是旧端点入参、不在本契约约束面;本契约约束的是**响应/信封字段**,统一 snake。）
3. **`opened` 三态接受**：本就在近期列表→`false`；自动翻出→`true`；没走到 open 就失败（未登录等）→`false`。语义=**「本次是否触发了自动翻出」,仅在 `ok:true` 时有意义**；失败时 `false`。AMR 留痕接受。
4. **失败带结构化 `code` + 自由 `error`**（两个都要）。`code` 闭枚举（**v1.1 起以本条为唯一清单**，§6.3 只引用不另列），
   按「会不会已经发出」分两组 —— **按下回车 / 点发送是分界线**：
   - **发前失败（确定没发出）**：`CONTACT_NOT_FOUND`（wxid 非联系人）/ `AMBIGUOUS`（多匹配，不猜）/ `NOT_LOGGED_IN`（后端未登录）/
     `SEND_IN_FLIGHT`（同键或同正文的一次发送仍在执行）/ `SEND_BUSY`（排队等发送锁超过预算，见 §6.2-4）/
     `INVALID_IMAGE` / `INVALID_REQUEST`（§6.1）/ `SEND_FAILED_PRESEND`（清草稿 / 粘贴等发前步骤失败，§6.2）。
   - **发后未确认（可能已经发出）**：`SEND_UNCONFIRMED`（按下回车之后没能确认，§6.3）。
   - `SEND_FAILED`（v1 旧码，分不出回车前后）：文本请求过渡期仍可用；**图片请求不得再用**；消费方一律按「可能已经发出」处理。
   AMR 按 `code` 分支（如 `AMBIGUOUS`→请人消歧、`NOT_LOGGED_IN`→提示登录），`error` 给人看的话。成功无 `code`。
5. **撤预检握手时序 = 确认**（见 §3/§5）：后端**部署+真机验证冷会话能翻出后**，才让 `capabilities.send.auto_open:true` 正式生效并通知 AMR；**在此之前 AMR 保留 `_live_chat_ids` 预检 fallback，绝不提前撤**。AMR 读到 `auto_open:true` 且收到你的 verified 通知后，才放宽预检。

---

## §3 能力声明 + 优雅降级

后端在 `/api/capabilities` 增加 `send` 项：
```json
{ "send": { "auto_open": true } }
```

| `send.auto_open` | AMR 行为 |
|---|---|
| `true` | AMR **直接发任意已知 chat_id**，撤掉 `_live_chat_ids` 预检拒发；冷会话由后端自动翻出，**人不再去 VNC 手工开**。 |
| `false`（或缺失） | AMR 保留现状：`_live_chat_ids` 预检 + 冷会话给"先在微信打开 TA 的对话再发"的可执行提示（过渡期 fallback，不阻塞）。 |

这样后端**未实现前**AMR 不报错（现状 fallback），**实现并声明后**AMR 自动启用直发——平滑切换。

---

## §4 HITL + 安全（不破底线）

- **HITL 不变**：发送仍只在**人设定的协作档**内发（0 号宪法六档；`semi` 及以下由人点确认才发，如「选 1/3 话术 → 确认 → 发」）。后端"自动打开会话"是**机械寻址**，不替人决定发不发。
- **不误发**：解析以稳定 id 为锚；模糊/多匹配 → 报错不发（保留 "Never guesses a target"）。**自动翻出 ≠ 自动乱发**。
- **留痕**：`opened` 字段进 AMR 审计（这次是否触发了自动翻出）。

---

## §5 AMR 侧职责

- 收到 `send.auto_open:true` 能力声明后：**放宽** `src/jl/channels/fullwechat.py` 的 `send()` —— 不再用 `_live_chat_ids()` 预先拒发，直接把 `chat_id` 交后端（后端负责翻出）。失败仍按 `ok:false` 的 error 展示 + 「重试」。
- 能力为 `false`/缺失时：维持现状（预检 + 手动 fallback 提示）。
- AMR 永远按**稳定 chat_id** 发，不向后端传模糊名。

---

## §6 发图片（v1.1 · 2026-10-12 · AMR #287）

> **为什么现在写**：AMR #287「在 AMR 里发图片」要用发送端点的 `image` 字段。这个字段**后端早已实现**
> （`/Users/neo/as/fullwechet/packages/agent-server-rust/src/router/messages.rs` 的 `SendParams.image`，发送流程在
> `/Users/neo/as/fullwechet/packages/agent-server-rust/src/plans/send_message.rs`），但**从没写进契约**。
> 按治理铁律，AMR 不得私自依赖未写进契约的字段 —— 先把它写下来。
>
> **本节是带能力闸的行为变更，不是纯增量**：后端声明 `capabilities.send.image`（§6.6）即表示按本节实现；
> 本节对 `image` 请求的若干行为与后端现状**不兼容**（见 §6.7 影响面）。未声明的后端，消费方**不得**发图片。

### §6.0 核对后端现状发现的静默行为（每条都对应下面一条 MUST）

| # | 现状 | 后果 | 对应条款 |
|---|---|---|---|
| S1 | 图片分支**不先清空输入框**（文字分支有 `ctrl+a`，图片分支没有），直接粘贴图片再回车（`/Users/neo/as/fullwechet/packages/agent-server-rust/src/plans/send_message.rs` Inputting 阶段） | 人在微信里**没发出去的草稿**会跟着图片一起发给对方 | §6.2-1 |
| S2 | `paste-image` 的退出码**被忽略**；随后照样按回车；确认阶段只看「发送按钮变灰」—— 输入框为空时按钮本来就是灰的（同上文件 Confirming 阶段） | 粘贴失败 → 什么都没发，却回 `ok:true` | §6.2-2/3 |
| S3 | 回车之后 5 次确认都没等到按钮变灰 → 回 `ok:false`、**不带码** | 图片可能已经发出，调用方却读成「失败」、可能重发 | §6.3 |
| S4 | base64 解不开 → 图片被静默丢掉，发送流程照跑（`/Users/neo/as/fullwechet/packages/agent-server-rust/src/router/messages.rs`） | 结果不可预期 | §6.1-2 |
| S5 | 白名单外的 `mimeType` 一律当 `.png` 落临时文件（同上） | 类型错配 | §6.1-1 |
| S6 | `image` 与 `text` 同时给 → 只发图片，`text` 静默丢（同上 + send_message.rs） | 调用方以为配文也发了 | §6.1-4 |
| S7 | 全局 `PLAN_LOCK` 的等待**没有上限**，300 秒执行预算从**拿到锁之后**才开始算（`/Users/neo/as/fullwechet/packages/agent-server-rust/src/execution/mod.rs` 第 16 / 47 行） | 前一件卡住时，这一件可以无限期排队；调用方早已超时放弃，后端却在几分钟后才真发 | §6.2-4 |
| S8 | 发送端点每次新建一个从不取消的 `CancellationToken`（messages.rs `send_message`） | 调用方断开连接后，后端照样把这一件发完 | §6.2-5 |

另：12 秒防重与在飞守卫**只以正文为键**，只发图片时两道都没有键（§6.4）。

### §6.1 请求

复用 `POST /api/messages/send`（与文本同一端点）：

```json
{ "chatId": "wxid_test_zhangsan",
  "idempotencyKey": "amr-img-42-9f3c0e7a1b2d4c5e6f708192",
  "image": { "mimeType": "image/png", "data": "<标准 base64，不带 data: 前缀>", "sha256": "<解码后字节的 SHA-256，小写十六进制>" } }
```

1. **`mimeType` 白名单 = `image/jpeg` / `image/png` / `image/gif`**（键名沿用后端现有的驼峰 `mimeType`）。
   后端 **MUST** 按文件头（magic bytes）核对与 `mimeType` 一致；不在白名单或不一致 → `INVALID_IMAGE`（S5）。
2. base64 解不开 → **MUST** 回 `INVALID_IMAGE`，不进发送流程（S4）。
3. **单张上限：解码后 ≤ 20 MiB**（班迪 2026-10-12 定），且不超过 `capabilities.send.image.max_bytes`。超了 → `INVALID_IMAGE`。
   注意 base64 膨胀 4/3：20 MiB 的图，请求体约 **26.7 MiB（≈ 28 MB）**，仍在后端请求体上限 50 MB 之内；
   调用方与后端的请求体上限都必须按**膨胀后**的大小设。
4. **一次请求只发一样东西**：`image` 与 `text`（或 `file`）**不得同时出现**；同时出现 → `INVALID_REQUEST`（S6）。配文由调用方另发一条文本。
5. `image.sha256` 调用方 **SHOULD** 带；给了后端 **MUST** 核对解码后的字节，不符 → `INVALID_IMAGE`。
6. **`idempotencyKey`**：调用方生成、不透明、1–64 个字符（`[A-Za-z0-9._:-]`），**每一次发送尝试唯一**；
   同一次尝试的任何重试 **MUST** 复用同一个键（见 §6.4）。

### §6.2 发送流程的硬要求（后端）

1. **先清空输入框再粘贴**（与文字分支同样的 `ctrl+a` + 删除，或等价操作）；清空失败 → `SEND_FAILED_PRESEND`，不按回车（S1）。
2. **粘贴必须核实成功**：`paste-image` 退出码非 0，或粘贴后输入区里看不到图片 → `SEND_FAILED_PRESEND`，**不按回车**（S2）。
3. 确认阶段**不得**只凭「发送按钮变灰」判成功（输入框为空时它本来就是灰的）；须看到输入区由「有图片」变为「空」，
   或会话里出现一条新的出站图片。
4. **端到端预算从收到请求那一刻起算**（S7）：等发送锁的时间 + 执行时间合计不超过 `send.image.max_runtime_ms`；
   等锁就已超出预算 → 在任何界面动作之前回 `SEND_BUSY`（发前失败、确定没发出）。
5. **调用方断开连接 → 后端 MUST NOT 再开始或继续任何可能发出东西的界面动作**（S8）：还没按回车就放弃并把这个键记成
   `not_sent`；已经按了回车就照常确认、把结果记在键上供 §6.4 查询。

### §6.3 失败语义：发前失败 vs 发后未确认（**按下回车是分界线**）

失败码的唯一清单见 **§2.1 第 4 条**（按「发前 / 发后」分组）。调用方对不可重复的发送（图片）只能依据这一条判断「能不能重发」：

| 时机 | 返回 | 含义 | 调用方 |
|---|---|---|---|
| 任何可能把东西发出去的界面动作（回车 / 点发送）**之前** | HTTP 4xx，或 `ok:false` + §2.1 的**发前失败码** | **确定没发出** | 可以让人改了再发 |
| 按下回车**之后**没能确认 | `ok:false` + **`SEND_UNCONFIRMED`** | **可能已经发出** | 判「结果未知」，交人核对或按 §6.4 查，**不得自动重发** |
| 确认发出 | `ok:true` | 已提交（送达以会话回流为准） | 等回流核实 |

- 后端 **MUST** 只在按下回车之前返回发前失败码；按下回车之后的任何失败 **MUST** 返回 `SEND_UNCONFIRMED`（S3）。
- 图片请求 **MUST NOT** 用 `SEND_FAILED`；消费方读到 `SEND_FAILED`、不带码、或认不出的码，一律按「结果未知」处理。

### §6.4 防重与幂等键（**发图片不是幂等的**；班迪 2026-10-12 定：方案 A）

1. **12 秒窗口（纵深防御，保留）**：后端对图片发送用 `(chatId, sha256(解码后字节))` 作 12 秒防重与在飞守卫的键。
   12 秒内同键已成功 → 返回 `ok:true` **且带 `"deduped": true`**（让调用方知道这次没真发）；同键仍在执行 → `ok:false` + `SEND_IN_FLIGHT`。
   发前失败时清掉该键的 12 秒记录。
2. **调用方幂等键 + 查询端点（方案 A，主防线）**：
   - 后端 **MUST** 在任何界面动作**之前**把 `idempotencyKey → {state, chatId, sha256, receivedAt, sentAt?, code?}` **持久**记下
     （后端重启不丢），保留**至少 24 小时**。`state ∈ in_flight / sent / not_sent / unknown`
     （`unknown` = 后端自己也说不清，即返回过 `SEND_UNCONFIRMED`）。
   - **同一个键再来一次 POST**：键为 `in_flight` / `sent` / `unknown` → **MUST NOT 再发**，原样回记下的结果并带 `"idempotent": true`
     （`sent` → `ok:true`；`in_flight` → `SEND_IN_FLIGHT`；`unknown` → `SEND_UNCONFIRMED`）；键为 `not_sent` → 可以按这次请求再试一次。
     同一个键但 `chatId` / `sha256` 不同 → `INVALID_REQUEST`。
   - **查询端点** `GET /api/messages/send/{idempotencyKey}`（与发送同一套鉴权）→ `200 {state, chatId, sha256, receivedAt, sentAt?, code?}`；
     **`404` = 后端从没见过这个键 = 确定没发出**（正因为键在任何界面动作之前就已持久记下）。超过保留期的键可以 `404`，
     所以调用方 **MUST NOT** 把保留期之外的 `404` 当成「没发出」。
   - 能力位 `send.image.idempotency: true` 声明本条已实现。
3. **为什么选 A 而不是 #36 异步下单**：#36（`outbox/dispatch.md`）还没上线；方案 A 在现有同步端点上补齐「结果未知可以查」，
   改动面最小、AMR 与后端都能独立验证。**迁移说明**：#36 上线后，图片发送迁到异步下单新增 `kind: send_image`，
   下单的幂等键沿用本节同一套语义（同键不重发、按键查结果）；迁移后本节的同步端点保留为过渡兼容。

### §6.5 调用方职责（AMR）

- **人亲手逐条确认**：每张图片都由人亲手点确认才发；不进批量、排期、自动发。引擎自动发图片不在 v1.1 范围内（宪法敏感，另议）。
- **账号守恒**：只经会话所属账号的后端与凭据发；账号没配后端或凭据就是发不了，**不回落**到别的后端或默认凭据。
- **按 §6.3 判结果**：只有「请求没完整送出」（连不上 / 送体中途断）、HTTP 4xx、§2.1 发前失败码才判「确定没发出」；
  其余（`SEND_UNCONFIRMED`、`SEND_FAILED`、不带码、认不出的码、超时、5xx、看不懂的响应）→ **结果未知**，**不自动重发**。
- **结果未知怎么了结**：后端声明 `send.image.idempotency` → 按键查询（`sent` → 已提交；`404` / `not_sent` → 确定没发出；
  其余仍交人）；否则交人核对。
- **重发规则**（与 AMR 实现一致）：
  - **在飞挡死**：同一张图还在发（调用方还在等回话），或没等到回话、且还没过后端最长运行时间 → 不许再发，原因也越不过。
  - **结果未知可越过、须写原因并留痕**：后端回了话但说不清的，或已过后端最长运行时间的；以及刚发过、被人核对为「没发出」的同一张图。
- **人核对的最早时刻** ≥ 认领 + 后端声明的最长运行时间（`max_runtime_ms`）+ 一轮回流同步 + 余量；
  后端回过话但说不清的件，人写理由可当场改判（留痕）。
- 等待时长 ≥ 后端最长运行时间 + 余量（调用方可设上限，但「人能核对的时刻」仍按后端声明的运行时间算）。
- `ok:true` 只记「已提交」，会话回流对上之后才算送达。

### §6.6 能力声明（闸）

`GET /api/capabilities` 的 `send` 项增加：

```json
{ "send": { "image": { "mimes": ["image/jpeg","image/png","image/gif"], "max_bytes": 20971520,
                       "dedup": "sha256", "idempotency": true, "max_runtime_ms": 300000 } } }
```

- 后端声明 `send.image` = 承诺 §6.1–§6.4 全部做到；`dedup` **MUST** 为 `"sha256"`；`idempotency` **MUST** 为 `true`
  （§6.4-2 已实现）；`max_runtime_ms` = §6.2-4 的端到端预算。
- **消费方 MUST NOT 在后端声明 `send.image`（含 `idempotency: true`）之前打开图片发送**（AMR：`jl image-send on` 开之前机器核对
  每个在用账号的后端都已声明、且 vendor 进来的契约含本节；确认发送那一刻再按本账号后端核一次类型 / 大小）。

### §6.7 影响面（为什么是能力闸后的行为变更，而不是「不破坏的 minor」）

- `image` + `text` 同发：现状「只发图片、text 静默丢」→ 本节 `INVALID_REQUEST`。
- 白名单外类型、base64 错：现状静默处理 → 本节 `INVALID_IMAGE`。
- 回车后确认失败：现状 `ok:false` 不带码 → 本节 `SEND_UNCONFIRMED`。
- 等锁超预算：现状无限期排队 → 本节 `SEND_BUSY`；调用方断开：现状照发 → 本节不再发。
- 新增：请求字段 `idempotencyKey`、查询端点 `GET /api/messages/send/{idempotencyKey}`、响应字段 `deduped` / `idempotent`。
- 已知调用方：**AMR**（#287，只在后端声明 `send.image` 后才发，且从不同发 image+text）。powerdata-wx 自身的界面 / MCP 工具若也调这个端点
  发图片，**PD仁德 须在切换前核对**（本仓无法看到所有调用方）。文本请求（无 `image`）的行为**不变**。
- 版本：契约文本 v1 → v1.1；兼容性由能力位 `send.image` 承担 —— 未声明的后端保持旧行为、消费方不对它发图片。

### §6.8 一致性夹具

`fixtures/send-target-image/valid/*.json` 必须全部通过、`invalid/*.json` 必须每条都被判出至少一处违规；两个目录都**不得为空**
（`scripts/conformance.py`）。夹具覆盖：请求（类型 / base64 / 魔数 / 大小 / sha256 / 幂等键 / 不与 text 同发）、
响应（发前失败码 / `SEND_UNCONFIRMED` / 成功不带码 / `deduped`）、查询结果（四种 state）、能力声明（`dedup` / `idempotency` / `max_runtime_ms`）。

---

## 协作约定

后端 Agent / 工程师遇到不清楚的口径：**提 AMR，AMR 改 spec，后端按新版实现**。不自行解释契约、不硬编码推断口径。AMR 是唯一真相源。

---

*本契约版本：v1.1 / 2026-10-12（§6 发图片 · AMR #287）。v1 / 2026-06-28。*
