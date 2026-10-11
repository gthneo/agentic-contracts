# 出站派发契约 v1.1（rev4）— Outbox Dispatch Contract（并行下单 · 串行拟人出站 · 异步回执）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`outbox/` → AMR/@gthneo）。
>
> **日期** 2026-07-21（rev1/rev2 2026-07-22 · rev3 2026-07-23 · rev4 2026-10-11）｜ **状态** rev1–rev3 已随 PR #21 合入（v1）。**rev4（v1.1）= AMR仁德 据 0 号宪法 v2.1「在场并行」节（PR #25）补第二种合法确认形态，提案中**：待 PD仁德 确认 → 非作者 fresh agent 对抗审 → 班迪 merge。**rev3 时的状态记录**：**提案·rev3**——AMR仁德 对抗审 → PD仁德 确认 → rev1 → AMR仁德 rev1 复核（3 BLOCKING 真落实、宪法无 FAIL，卡 5 个单行口子）→ **rev2 = PD仁德 补 R1–R5 + 5 建议** → **rev3 = PD仁德 据班迪 SF1 拍板补 `pause` 硬化（`cancel` 明确不硬化）**，待 AMR仁德 非作者 fresh agent 复核 rev3 delta → 班迪 merge。**不 merge。**
> **from** PD仁德（powerdata-wx / fullwechat 微信后端，`/Users/neo/as/fullwechet`）—— 契约执笔 + 实现方
> **to** AMR仁德（AgenticMessageRouter，`/Users/neo/as/agenticmessagerouter`）—— 契约定义/审计方 + 下单方
> **姊妹契约** `../send-target/*`（同步发送目标）· `../message/canonical.md`（入站消息）· `../moments/read-like.md`（朋友圈动作）
> **适用范围** **出站动作的排队派发**：消费方**人审确认后**并行下单 → 后端单 worker 串行 + 拟人节奏执行 → 结果异步取回。**不覆盖**动作本身的语义（发什么/赞哪条见姊妹契约），也不覆盖入站。

### rev4 变更摘要（v1.1 · 在场并行 · 2026-10-11 · 依赖 PR #25）
- **§0 第二种合法确认形态**：「人审确认闸」从一种扩为两种 —— **形态 A** 逐条人审确认（现行，缺省）；**形态 B**
  「在场并行生效、且审计关联到在场会话 id」（0 号宪法 v2.1「在场并行」节 I-3 判定该条「可按 `parallel` 交出」）。
  形态 B 的任务 MUST 带 `authorization: "presence_parallel"` + `presence_session_id` + `presence_ttl_secs`。
- **§2 / §2.3 新字段与受理规则**：`authorization` 封闭枚举（缺省 = `"human_confirmed"`，旧消费方零改动）；
  形态 B 只允许 `send_text`；后端未 opt-in → `409 PRESENCE_PARALLEL_UNSUPPORTED`；HUMAN 态 → `409 HUMAN_IN_CONTROL`；
  预计放出时刻超出有效期 → `409 PRESENCE_WINDOW_EXCEEDED`。
- **§3 两条新转移**：形态 B 任务过有效期未开始执行 → `failed`（`PRESENCE_EXPIRED`）；渠道接管（HUMAN 态）→
  后端立即把形态 B 的 `queued`/`deferred` 任务转 `cancelled`（`HUMAN_TAKEOVER`）。
- **§7.1 新能力位 `presence_parallel`（opt-in）**：声明为 `true` 的后端，`cancel` 由可选能力位升为 **MUST**（rev3 的
  「`cancel` 不硬化」对它不适用），且承诺 §7.1 所列四项（对应 `control-and-voice.md §8.1` PP-2…PP-5）。未声明的后端：本契约行为一字不变。
- **严格增量**：不带 `authorization` 的下单 = 形态 A，与 rev3 完全相同；不声明 `presence_parallel` 的后端无需改动。

### rev3 变更摘要（SF1·班迪 2026-07-23 拍板）
- **SF1（HITL 护盾·硬化）** §7.1/§6：`pause`（全局急停闸）升格为**强制不变式（MUST）**，与 `account` 同列——`"pause"` **恒为 `true`**、不可声明 `false`；若某实现报 `pause:false` 或不提供可用的全局急停，即为**违约**，消费方 **MUST 拒绝对其下单**（一个「停不下来」的出站后端不得被允许对外发送）。堵「一句 `pause:false` 让人失去急停刹车」。
- **`cancel` 明确不硬化（SF1 反面）** §6/§7.1：`cancel` 是**次级兜底、非主 HITL 闸**（主闸在上游人审，§0/§1.8）+ R5 已约束其语义（`running` 不可撤），故**保留普通能力位**（可声明 `false`，消费方优雅降级：隐藏撤单入口、靠上游人审 + `pause` 兜底），**不升格 MUST**，避免过度约束未来实现。

### rev2 变更摘要（对 AMR仁德 rev1 复核·2026-07-22）
- **R1（merge前必改·红线）** §0：强制人审闸主语从「AMR仁德」→ **全体消费方 MUST** + 新消费方准入前置（声明其闸位置/形态,未声明不得下单）—— 堵「非 AMR 消费方无闸直调」。
- **R4（merge前必改·铁律）** §7.1：`account` = **强制不变式（MUST）,不受 capabilities 声明影响**;报 `account:false` = 违约,消费方 MUST 拒绝下单 —— 堵「一句 account:false 合法降级掉账号守恒」。
- **R2** §5：紧急越权手柄上锁（仅人手逐条·必留痕·只越作息窗不越速率硬顶）。
- **R3** §2：`account` 取值域钉死 = wxid(`self_id`,后端可自证)+ 字节级精确比对。
- **R5** §6：cancel 拆两句消歧义（`queued`/`deferred` MUST 可撤 / `running` MUST NOT 撤,不做 best-effort）。
- **建议 1-5**：非幂等 `maxAttempts>1`→`400` 拒绝 / §6 后端侧留痕交叉引用 / §2.2 去重窗 vs 恢复幂等区分 / §3 状态机图同步 B3+S4 / 扫净 `fire-and-forget` 残留。

### rev1 变更摘要（对 2026-07-22 对抗审）
- **B1（红线·HITL）** §0/§1/§6：显式声明 `POST /api/outbox` = 「act」步，**只在 AMR仁德 侧人审确认闸通过后**调用；队列 = 节奏/串行化机制，**非**确认闸替代；`cancel` = 次级兜底，非主 HITL 手柄。
- **B2（铁律·账号守恒）** §2：下单体 + 回执**恒带 `account`（必填）**；后端硬校验 `account == 本实例登录账号`、不符即 `WRONG_ACCOUNT` 拒；「一后端实例一账号」写成显式**不变式**（打破即自动升级 per-account 队列/路由要求）；幂等键 per-account 作用域。
- **B3（对外不可逆·at-most-once）** §2/§3：恢复策略**按 kind 幂等性分档**——幂等 kind 自动重排/重试；非幂等 kind 缺省 `maxAttempts=1`、孤儿 `running` → `failed`(park) 交人，不无脑重驱 GUI。
- **S1–S7**：§4 加 `?idempotencyKey=`/`updatedSince` + 否决回调；§5 绑宪法第 4 条 + `runAfter` 暴露 + 紧急越权；§7 health 加 `oldest_queued_age_secs`/`last_completed_age_secs`；§6 cancel 收紧 `queued`/`deferred`；§8 六口径定案。

---

## §0 这份契约是什么 / 为什么需要它

**问题（现状事实）**：消费方（AMR仁德 / M2仁德 等）当前调**同步**出站端点（`POST /api/messages` 等）——请求要一直挂到 GUI 驱动完成（发一条消息驱动搜索→打开会话→输入→发送，秒级到数十秒）。这带来三个结构性问题：

1. **并发不安全**：多个消费方/多条消息同时打进来 → 同时驱动同一个微信 GUI → 互相抢焦点、窗口错位、误发。
2. **调用方被阻塞**：并行生成内容的一侧（M2仁德 可并行产出多条）被迫等待串行的 GUI 执行。
3. **无拟人节奏落点**：同步端点「来一条发一条」，没有一个能安放「间隔/作息窗/速率上限」的位置——而这是账号资产保护的刚需（见 §5）。

**本契约的解**：在两侧之间放一个**持久化出站队列（outbox）**：
- **消费方在人审确认后并行下单**（拿回 `202` + 任务 id，不等执行）；
- **后端单 worker 串行出队**，按拟人节奏执行（同一时刻只有一个动作在驱 GUI）；
- **结果异步取回**（§4）。

**⚠️ HITL 边界（宪法红线·B1，rev2·R1 收口）**：`POST /api/outbox` 是 **dry-run→confirm→act 里的「act」步**。因后端是哑执行器——收到下单即视为「人已确认」、不二次判断该不该发——**人审确认闸的强制力必须落在每一个消费方身上，而非只绑 AMR仁德**：

- **全体消费方 MUST 前置人审闸**：**任何消费方**（AMR仁德 / M2仁德 / 及未来任何接入方）在调用 `POST /api/outbox` **之前 MUST 已通过其自身侧的人审确认闸**。下单 = 人已批准的「act」，**不存在**「无闸消费方直调后端」这一路径——否则一条对外消息可在无人确认下发出（踩红线 1「不得旁路人」+ 第 2 条「系统永不替你发」）。
- **新消费方准入前置**：任何新接入方在首次下单前 **MUST 书面声明其人审闸的位置与形态**（在契约/接入登记里）；**未声明者不得下单**。
- **队列不是确认闸的替代**：它的价值 = 把**人已经批准的** N 条按拟人节奏、串行、可靠地放出去。参照实现：AMR仁德 现网 `api_confirm_outbox`（queue-for-human → 人 confirm → 才 enqueue-to-backend）。

**合法的确认形态有且只有两种（rev4）** —— 上面「人审确认闸」指下列二者之一；二者之外的任何下单都不合法：

| 形态 | 名称 | 什么构成「人已确认」 | 下单体标记 | 适用 |
|---|---|---|---|---|
| **A** | 逐条人审确认（缺省） | 人对**这一条**逐条确认（含人在消费方界面亲手按下发送） | `authorization` 缺省或 `"human_confirmed"` | 一切 `kind`；rev3 及以前的全部行为 |
| **B** | 在场并行 | **在场并行生效、且审计关联到在场会话 id**：消费方按 0 号宪法 v2.1「在场并行」节 I-3 判定该条「可按 `parallel` 交出」（人显式开启的策略 + 人此刻界面在场 + 全部前置条件），并把这一条关联到该次在场的审计记录（I-6） | `authorization: "presence_parallel"` + `presence_session_id` + `presence_ttl_secs`（§2.3） | 仅 `send_text`（会话内发消息）；仅限后端已声明 `presence_parallel: true` 的账号（§7.1） |

- **形态 B 的判定责任在消费方**：后端是哑执行器，**不判断、也无从验证**人是否在场。`authorization` 是消费方的声明，
  后端用它做三件事：**留痕**（落 `outbox` 行并在回执回显，§4）、**拒绝**（未 opt-in / 字段不全 / HUMAN 态，§2.3）、
  **执行有效期与渠道接管撤单**（§3）。在场判定本身的正确性由消费方的实现与审计负责（0 号宪法 I-1 / I-6）。
- **形态 B 的消费方准入前置**：消费方首次以形态 B 下单前，**MUST 书面声明**（接入登记里）其在场判定实现：直接输入事件的
  区分方法、`N`、状态上报周期 `L`、有效期 `W` 的取值（0 号宪法 I-1 / I-3）。未声明者不得以形态 B 下单（形态 A 不受影响）。
- **形态 B 的消费方侧闸是第一道**：旧后端（rev3 及以前）不认识 `authorization` 字段，会把形态 B 任务**当作普通任务执行**
  （既不拒绝，也不执行有效期与渠道接管撤单）。故消费方 **MUST 只对已声明 `presence_parallel: true` 且 `cancel: true`
  的后端**以形态 B 下单（§7.1）；后端侧拒绝是第二道。
- **在场一结束，消费方 MUST 立即撤下**以形态 B 交出、尚未执行的任务（`cancel`，§6；0 号宪法 I-3）；有效期（§2.3）是
  消费方异常退出、撤单未发出时的后端侧兜底，不替代消费方撤单。

**本契约是**：下单形态（§2）+ 任务状态机（§3）+ 结果回执（§4）+ 拟人节奏与配额的语义边界（§5）+ HITL 手柄（§6）+ 能力声明（§7）。
**本契约不是**：动作内容语义（发什么文本 / 赞哪个 tid → 姊妹契约）；不是「发不发、发给谁、什么时候发」的决策（= **消费方 + 人领域**）；不是入站。

**边界**：AMR仁德 = 定义方（审计 / 定 shape / merge）；PD仁德 = 执笔 + 实现方（提事实、不自行解释契约）。

---

## §1 设计原则

1. **并行下单、串行执行**。下单可任意并发；**执行严格串行**（单 worker）——因为被驱动的微信 GUI 是**独占资源**，并行驱动必然互相破坏。这条是本契约存在的根本理由。
2. **下单 = act（人审后）**。`POST /api/outbox` 立即返回 `202 Accepted` + 任务 id，**不等执行结果**（消费方不因 GUI 慢而阻塞）；但**下单本身是人审确认闸之后的动作**（§0 HITL 边界；确认形态 A / B 见 §0）——「不等结果」指**执行时长解耦**，不是「跳过人的确认」。
3. **持久化 + 崩溃可恢复（按 kind 分档）**。任务落库（不是内存队列）；进程重启后回收孤儿 `running` 任务——**幂等 kind 重排、非幂等 kind park 交人**（§3，B3）。不丢单、不悬挂、不重复外发。
4. **幂等**。`idempotencyKey` 相同 = 同一意图，重复下单**不重复执行**（消费方重试安全）；键 **per-account 作用域**（§2.2）。
5. **账号守恒（铁律·B2）**。下单体 + 回执**恒带 `account`**；后端**只在下单账号 == 本实例登录账号时执行**，不符即拒，**永不跨账号执行、无跨账号回退**。
6. **拟人节奏由后端承载、由后端硬限**（§5）。节奏 = 尊重对方 + 账号资产保护，**不是绕平台风控的伪装**；服务端硬上限 = **天花板（发得更少），非目标值/地板**（宪法第 4 条）；不 100% 依赖消费端自律（纵深防御）。
7. **对外不可逆保守（at-most-once·B3）**。对非幂等 kind（`send_text`/`comment_moment`），恢复/重试**宁可漏掉有意重复，也不对外重投**——多一条不可逆外发 = 骚扰、耗德。
8. **HITL 一等**（§6）。人审闸在上游（§0）；`pause` 全局急停 / `cancel` 撤未执行队列任务 = **次级兜底**，非主确认闸。
9. **哑执行**。后端不决定「发不发、发给谁、发什么」——那是消费方 + 人的决策；后端只负责「按拟人节奏、串行、可靠地执行已确认下单的意图」。
10. **可观测**。worker 活性 + **是否在排空**必须能被外部看见（§7.2），否则 worker「活着但不干活」会静默吞掉出站。

---

## §2 下单（enqueue）

```
POST /api/outbox
Authorization: Bearer <token>
Content-Type: application/json
```

**请求**
```json
{
  "account": "wxid_selfaccount_28",
  "kind": "send_text",
  "target": "wxid_test_zhangsan",
  "payload": { "text": "你好" },
  "idempotencyKey": "amr-msg-8f3a1c",
  "platform": "wechat",
  "maxAttempts": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `account` | str | **是** | 发信账号的 **wxid（`self_id`）**——取值域钉死为**后端可自证的那个 id**（实例当前登录账号的 wxid），**不是** AMR仁德 内部的整数 `account_id`（R3）。**恒必填**（即便当前一实例一账号，见下「不变式」）。后端硬校验 `account == 本实例登录账号 wxid`，不符 → `409 WRONG_ACCOUNT`，**绝不跨账号执行/回退**。 |
| `kind` | str | 是 | 动作类型，**封闭枚举**（§2.1）。未知值 → `400`。 |
| `target` | str | 是 | 动作目标的稳定 id：`send_text` = `chat_id`/wxid（姊妹 `send-target` 语义）；`like_moment`/`comment_moment` = moment `tid`。空串 → `400`。 |
| `payload` | obj | 否 | 该 `kind` 的参数（§2.1）。缺省 `{}`。 |
| `idempotencyKey` | str | 否（AMR仁德 侧当必填） | 幂等键（§2.2）。**AMR仁德 侧一律由 outbox 行 id/内容 hash 派生稳定键、当必填**——不给则无重试保护。 |
| `platform` | str | 否 | 缺省 `"wechat"`（为未来多渠道预留）。 |
| `authorization` | str | 否 | **确认形态（rev4）**，封闭枚举：`"human_confirmed"`（形态 A，**缺省**）\| `"presence_parallel"`（形态 B，§0 / §2.3）。未知值 → `400 BAD_AUTHORIZATION`。 |
| `presence_session_id` | str | 形态 B 必填 | 消费方侧该次**界面在场**的审计记录 id（0 号宪法 I-6）。非空字符串，对后端不透明（后端不解析、只留痕与回显）。形态 A 下 MUST 不出现（出现 → `400`）。 |
| `presence_ttl_secs` | int | 形态 B 必填 | 有效期（秒），`1 ≤ presence_ttl_secs ≤ 600`；消费方取其 `W`（0 号宪法 I-3，`W ≤ N ≤ 10 分钟`）。后端以**自己的受理时刻**起算截止时刻（不用消费方时间戳，免跨机时钟偏差）。形态 A 下 MUST 不出现。 |
| `maxAttempts` | int | 否 | 该任务最多执行次数。**缺省按 kind 幂等性**：非幂等（`send_text`/`comment_moment`）= **`1`（at-most-once）**；幂等（`like_moment`）= `2`。后端 clamp `[1,10]`；**非幂等 kind 显式给 `>1` → `400` 拒绝**（建议1·收口）——不给「配置即违约」留模糊空间,at-most-once 是非幂等 kind 的**硬约束**,唯一安全重试路径是未来的 pre-send marker（§3）。 |

**账号守恒不变式（invariant·B2）**：本契约按**「一后端实例 = 一微信账号 = 一队列」**（端点身份即账号身份，AMR仁德 `db.account_backend` 按会话所属账号绑各自 host+token）。`account` 字段在此前提下仍**恒必填**，因为它是：(i) AMR仁德 机器断言「回执.account == 下单.account」的依据；(ii) 前向接口——**若该前提被打破（某实例服务多账号），`WRONG_ACCOUNT` 硬校验 → per-account 队列/路由要求自动升级**，`account` 已在契约面、无需改 shape。

**取值域 + 比对规则（R3·机器可执行性）**：`account` = wxid（`self_id`），因为后端只能**自证**自己登录账号的 wxid（读不到 AMR仁德 内部整数 `account_id`）；AMR仁德 下单时把 `account_id → self_id` 映射后填入。比对为 **精确、大小写敏感、无前后缀/无规范化的字节级相等**（wxid 本就是稳定不可变 id，不做 trim/lower/normalize，避免「宽松比对」削弱守恒）。不符即 `WRONG_ACCOUNT`，fail-closed。

**响应（成功）**：HTTP **`202 Accepted`**
```json
{ "ok": true, "id": "b1e4…", "account": "wxid_selfaccount_28", "status": "queued" }
```
- **`202` 而非 `200`** 是语义核心：**已受理（人已确认）、尚未执行**。消费方拿到 `id` 即可返回，不等结果。
- 账号不符 → `409 {ok:false,code:"WRONG_ACCOUNT",error:"…"}`；参数非法 → `400`；入队失败 → `500`。

### 2.1 `kind` 枚举与 payload（PD仁德 现实现）

| `kind` | 幂等性 | payload | 对应同步端点（语义等价，见姊妹契约） |
|---|---|---|---|
| `send_text` | **非幂等**（产生真实可见重复） | `{ "text": "…" }` | `POST /api/messages` |
| `like_moment` | **幂等**（微信层再赞 = no-op，见 `moments/read-like.md` §1.4） | `{}` | `POST /api/moments/{tid}/like` |
| `comment_moment` | **非幂等** | `{ "text": "…" }` | `POST /api/moments/{tid}/comment` |

> **口径①（已定）**：D 角撤销/逆动作（`unlike`/`comment_delete`/`delete-moment`）**入队走串行**（同样驱独占 GUI），但走**独立高优先车道 + 豁免 §5 拟人节奏节流**——撤销是误触后的紧急回收（CRUD 并↔拆的「拆」向），不能沉在出站队列尾被作息窗/速率压住。与 §6 `cancel` 区分：`cancel` 撤**未执行的队列任务**（无 GUI 动作）；`unlike` 是**已发生动作的逆 GUI 动作**。新增走 AMR仁德 改 spec。

### 2.2 幂等语义

- 同一 `(account, idempotencyKey)` **重复下单 = no-op**，返回**原任务** id 与状态（不新建、不重复执行）。键 **per-account 作用域**——防 A 账号的键误抑制 B 账号的正当发送。
- **口径②（已定）**：幂等键**有效窗口缺省 ≥ 7 天（可配），到期 GC**。非对称取舍：一条迟到的重复外发是**不可逆对外伤害**，库里几行是廉价的 → 偏长窗口。终态任务保留 ≥7d 供 reconcile（见 §4 `?idempotencyKey=` 查询），过期再 GC。
- **两个「防重」是两件事,别混（建议3）**：(i) **恢复期幂等** = 本节的 `idempotencyKey` + `maxAttempts`（跨下单/重试/崩溃回收,防**同一意图**被执行两遍,窗口 ≥7d）;(ii) 同步端点里 `send_text` 的**去重窗**（`SEND_DEDUP`,姊妹 `send-target` 契约,秒级,挡「调用方超时后重试→重复投递」的在飞窗口）。前者是 outbox 层的意图幂等,后者是执行层的在飞防抖——**机制、时间尺度、作用层都不同**,不可互相替代。

### 2.3 在场并行任务（形态 B）的受理规则（rev4）

实现了 rev4 的后端（**无论是否声明** `presence_parallel`）按下列顺序判定（`WRONG_ACCOUNT` 校验照旧最先）。rev3 及以前的后端不认识这些字段、不会走这张表 —— 那一侧由消费方侧闸挡住（§0）：

| # | 条件 | 结果 |
|---|---|---|
| 1 | `authorization` 不在枚举内 | `400 BAD_AUTHORIZATION` |
| 2 | 形态 A（`authorization` 缺省或 `"human_confirmed"`）而带了 `presence_session_id` / `presence_ttl_secs` | `400 PRESENCE_FIELDS_WITHOUT_AUTHORIZATION`（半填的下单体 fail-closed） |
| 3 | 形态 A，其余合法 | `202`，与 rev3 完全相同 |
| 4 | 形态 B，而本后端未声明 `presence_parallel: true`（含按配置对该账号关闭） | `409 PRESENCE_PARALLEL_UNSUPPORTED` |
| 5 | 形态 B，`kind` ≠ `send_text` | `400 PRESENCE_KIND_NOT_ALLOWED`（在场并行只作用于会话内发消息，0 号宪法 I-3） |
| 6 | 形态 B，`presence_session_id` 缺失 / 空 / 非字符串 | `400 MISSING_PRESENCE_SESSION` |
| 7 | 形态 B，`presence_ttl_secs` 缺失 / 非整数 / 越界 `[1,600]` | `400 BAD_PRESENCE_TTL` |
| 8 | 形态 B，该账号当前处于 HUMAN 态（`control-and-voice.md §1`） | `409 HUMAN_IN_CONTROL` |
| 9 | 形态 B，受理时已能确定预计放出时刻（`runAfter`，§5 作息窗 / 速率）晚于截止时刻 | `409 PRESENCE_WINDOW_EXCEEDED`（不入队；0 号宪法 I-3「不得交出要等很久才放出的任务」） |
| 10 | 形态 B，其余合法 | `202`；`authorization` / `presence_session_id` / `presence_ttl_secs` 与截止时刻落 `outbox` 行 |

- **形态 B 不豁免 §5 节奏**：间隔 / 作息窗 / 速率硬顶照常适用（与撤销车道不同）。节奏把任务推过截止时刻的，按 §3 过期，
  不放宽有效期。
- **幂等（§2.2）照旧**：同一 `(account, idempotencyKey)` 重复下单返回原任务；不得用重复下单改写原任务的 `authorization`
  或续期有效期（返回原任务即可，不新建、不改写）。
- 拒绝时的响应体同 §2：`{ok:false, code:"<上表 code>", error:"…"}`。

---

## §3 任务状态机

```
queued ──(worker 认领)──> running ──成功──> done
   │                        │
   │                        ├─失败且未超 maxAttempts──> deferred ──(退避到期)──> queued
   │                        └─失败且已达 maxAttempts──> failed
   │
   │        ┌─ 崩溃回收孤儿 running（B3·按 kind 分流）:
   │        │    幂等 kind (like_moment)      → queued  （自动重排,安全）
   │        │    非幂等 (send_text/comment)   → failed  （park 交人,不重驱 GUI）
   │
   └──(HITL cancel)──> cancelled       ⚠️ cancel 仅 queued/deferred;running MUST NOT 撤（S4·R5）

   形态 B（authorization="presence_parallel"，rev4）另有两条，均只作用于 queued/deferred:
     过截止时刻仍未开始执行        → failed     （lastError="PRESENCE_EXPIRED"，不重试）
     账号进入 HUMAN 态（渠道接管）  → cancelled  （lastError="HUMAN_TAKEOVER"，后端自行完成）
```

| 状态 | 含义 | 终态 |
|---|---|---|
| `queued` | 已受理（人已确认），等待 worker | 否 |
| `running` | worker 正在执行（此刻正驱 GUI） | 否 |
| `deferred` | 执行失败，**温和退避**后重排（PD仁德 现实现退避 ~30s） | 否 |
| `done` | 执行成功 | **是** |
| `failed` | 达到 `maxAttempts` 仍失败，或非幂等孤儿回收，**停止重试**（park） | **是** |
| `cancelled` | 人/消费方在执行前撤单 | **是** |

**崩溃恢复：按 kind 幂等性分档（B3）**。进程重启时，卡在 `running` 的孤儿任务这样处理：
- **幂等 kind**（`like_moment`）→ 回 `queued` **自动重排**（再执行安全，微信层再赞 = no-op）。
- **非幂等 kind**（`send_text`/`comment_moment`）→ **`failed`(park) 交人复核，不无脑重驱 GUI**。理由：孤儿可能是「GUI 已按下发送、标 done 前崩溃」→ 消息其实**已发出**，盲目重排 = 客户收两遍。v1 **保守**：一律 park，宁漏勿重。
  - （后续优化留位：若后端能**证明** attempt 未真正发出——如失败发生在 GUI 发送键按下之前、有 pre-send intent marker 可判——才允许自动重试。**v1 不做此优化、不赌**。）
- **`deferred → queued` 的 `maxAttempts` 内自动重试**是**同一已确认意图**的瞬时故障重试，性质不同、可接受；但非幂等 kind 缺省 `maxAttempts=1` 使其 at-most-once。

- **形态 B 的两条转移（rev4）**：
  - **有效期**：截止时刻 = 后端受理时刻 + `presence_ttl_secs`（§2.3）。worker **MUST NOT 在截止时刻之后开始执行**形态 B 任务
    （认领前判定）；过期的 `queued`/`deferred` 任务转 `failed`、`lastError: "PRESENCE_EXPIRED"`，不重试、不自动转回形态 A。
    要发，消费方带新幂等键按形态 A 重新下单（过逐条人审，同口径⑤）。`pause` 期间时钟照走：暂停跨过截止时刻的形态 B 任务，
    `resume` 后不执行。
  - **渠道接管**：账号进入 HUMAN 态（`control-and-voice.md §1`）时，后端 **MUST 立即**把该账号全部 `queued`/`deferred` 的
    形态 B 任务转 `cancelled`、`lastError: "HUMAN_TAKEOVER"`（`control-and-voice.md §8.1` PP-4）。形态 A 任务照 §5 / 控制态
    既有行为挂起、人走后继续，不受影响。`running` 的那一条照 R5 不可撤。
  - 两条都是**朝不发的方向**收：形态 B 的任务只会被执行、过期或撤下，最迟在截止时刻之后不再执行。
    **诚实记账**：「离场时刻」到「截止时刻」之间（至多 `presence_ttl_secs` ≤ `W`）仍有残余窗口，后端无从知道人已离场；这段窗口只能由消费方在离场时立即撤单（§0、§6）关闭。后端有效期是消费方撤单失灵时的上界，不是离场判定。
- **`failed` 是 park 不是丢弃**：任务留在库里带 `lastError`，供人审后决定重下单或放弃（可逆/可追溯）。
- **口径⑤（已定）**：`failed` 处置 = park + `lastError`，**无后端「原地重投」端点**（那会让 park 任务**绕过新一轮人审**再次外发 = HITL 旁路，禁）。重发 = 消费方**带新幂等键重新下单**（须再过人审）。

---

## §4 结果回执（异步）

异步派发（下单不阻塞执行,§1.2）的代价：下单方拿不到同步结果。消费方需要知道「那条到底发出去没有」。**口径③（已定）：(a) 轮询作 v1 强制地板（现在就上）；(c) 事件流作前向演进（AMR仁德 建通用订阅基建后）；明确不采 (b) 回调。**

**(a) 拉取（v1 地板·已实现 + 本 rev 补齐）**
```
GET /api/outbox/{id}                          → { ok, task }
GET /api/outbox?idempotencyKey=<key>          → { ok, task }   # 崩溃恢复 reconcile 关键
GET /api/outbox?status=&updatedSince=&limit=  → { ok, tasks:[…] }   # 增量对账游标
```
- **`?idempotencyKey=` 查询（S1 新增）**：下单成功回 `id`，但若 AMR仁德 在「拿到 id」与「落库 id」之间崩溃，须能凭自己的幂等键回查结局，否则该任务无法 reconcile → 可能重复下单。
- **`updatedSince` 增量游标（S1 新增）**：供 AMR仁德 高效增量对账、不每轮全表扫。

任务对象（**PII 安全**：`target` 只回显 hash，`payload` 完全不回显；**回显 `account`** 供断言账号一致；
**rev4：回显 `authorization`**（缺省任务回 `"human_confirmed"`），形态 B 另回显 `presence_session_id` 与 `presenceDeadline`
（后端截止时刻，毫秒，后端时钟），供消费方把执行结果关联回在场审计记录）：
```json
{ "id":"b1e4…", "account":"wxid_selfaccount_28", "kind":"send_text", "status":"done",
  "targetHash":"5ab899b8ecbe", "attempts":1, "maxAttempts":1,
  "lastError":null, "runAfter":0, "authorization":"human_confirmed",
  "createdAt":1784600000000, "updatedAt":1784600042000, "executedAt":1784600042000 }
```
形态 B 的任务对象（rev4）：
```json
{ "id":"c7d2…", "account":"wxid_selfaccount_28", "kind":"send_text", "status":"queued",
  "targetHash":"5ab899b8ecbe", "attempts":0, "maxAttempts":1,
  "lastError":null, "runAfter":0,
  "authorization":"presence_parallel", "presence_session_id":"ps_test_0001",
  "presenceDeadline":1784600300000,
  "createdAt":1784600000000, "updatedAt":1784600000000, "executedAt":null }
```

**(b) 回调 webhook —— 否决（不做）**：反转依赖（后端主动外呼 AMR仁德）引入鉴权/重试/失败堆积 + 耦合 AMR仁德 可达性；HITL 系统里人本在看，(b) 省下的亚-poll 时延不抵新增攻击面。且状态可经 (a) 查询，(b) 永远只可能是 (a) 之上的优化、非替代。
**(c) 事件流（后续演进）**：复用既有结构化事件面，AMR仁德 订阅，免 N 个轮询环——等 AMR仁德 侧持久订阅基建因其他需求落地后再上。此前用 (a)。

---

## §5 拟人节奏与配额（后端承载）

后端在**执行侧**（非下单侧）施加节奏，消费方无需也无法绕过：

- **间隔**：相邻出站动作之间的最小间隔 + 抖动（jitter）。
- **作息窗**：非活跃时段不执行（任务留在 `queued`，到点再发）。
- **速率上限**：单位时间出站条数硬顶。
- **dwell**：动作前后的自然停顿。

**语义定位（宪法第 4 条·钉死·S2）**：
- 节奏目的 = **降低**总外发量、尊重收件人 + 保护账号资产；服务端硬限是**天花板（更少发），绝非目标值/地板（发到雷达下最多）**。
- 作息窗 = **尊重对方作息**，句号。
- **反漂移护栏**：任何把 `jitter`/`dwell`/作息窗**重构为「模仿人以躲平台检测、从而发更多」的措辞或调参 = 红线违背**。节奏**不是**把自动化伪装成人。参数由后端按该账号自身历史校准（`agent.db` 行为 profile）。

- **服务端硬限（纵深防御）**：即使消费方疯狂下单，后端也**必须**按上限执行——**不 100% 依赖消费端自律**。
- **超限行为**：超出速率/作息窗的任务**留在队列等待**（不是拒绝、不是丢弃）。
- **可解释（S2）**：任务的 `runAfter`（预计放出时刻）**对人可见**——一条人刚确认、期望即发的消息若被作息窗压数小时，须让人看到「将延迟、预计 X 点发」，而非静默。
- **紧急越权手柄（S2·R2 上锁）**：真急的可越**作息窗**发,但该手柄**有约束、非漏口**：
  1. **仅限人手动逐条触发**——**禁程序化 / 批量越权**（否则等于给自动化开一条绕节奏的后门）。
  2. **必留痕**（谁 / 何时 / 为何越权），显式 gate、可审计。
  3. **只越作息窗、不越速率硬顶**——速率上限是**天花板**，**任何情形（含紧急越权）不得突破**；越权只把「现在不是活跃时段」这一条放行,不放开「单位时间发多少」的硬顶。
- **口径④/⑦（已定）**：当前节奏态 + 剩余配额的**「回读」归本契约**（只读·可观测，属 §7 worker 运行态）；**限额策略本身**（作息窗表、per-account 校准、上限取值）归**独立 `send-policy` 契约（本仓 #19）**——机制（dispatch）与策略（policy）分离。暴露给消费端 = **只读可观测手柄**（供人合理排期、向人解释），**非**消费端能上调的控制旋钮（服务端硬上限唯一权威）。

---

## §6 HITL 手柄

> **定位（B1）**：人审主闸在**上游**（§0，消费方侧、下单前、强制）。本节手柄是**次级兜底 + 运行态干预**，**不是**主确认闸。

| 端点 | 用途 |
|---|---|
| `POST /api/outbox/{id}/cancel` | 撤单（次级兜底，非主闸）。**语义无歧义（R5）**：`queued`/`deferred` **MUST 可撤**；`running` **MUST NOT 撤**——明确拒绝（返错），**不做 best-effort 尝试**（撤一个正驱 GUI 的任务 = 半发风险）。仅在队列有深度/作息窗延迟时,`cancel` 才有机会赶在 `running` 之前生效。**rev4：对声明 `presence_parallel: true` 的后端，本端点为 MUST（§7.1）**——形态 B 依赖它在离场时撤下未执行的任务（0 号宪法 I-3 / I-6）。 |
| `POST /api/outbox/pause` | **全局急停**出站（worker 继续 tick，但不认领任务） |
| `POST /api/outbox/resume` | 恢复 |
| `GET /api/outbox?status=queued` | 已确认待放清单（运行态可见，非人审闸本身） |

- **`pause` 是人的急停闸**：出任何异常（风控告警 / 内容出错 / 账号异常）先 `pause`，队列不丢。**（rev3·SF1：`pause` 硬化为 MUST 不变式，见 §7.1——任何实现都 MUST 给人可用的全局急停，不得报 `pause:false`；与 `cancel` 不同,`cancel` 保留可降级。）**
- **形态 B 的撤单是主路径之一（rev4）**：对形态 A，`cancel` 是次级兜底；对形态 B，「在场一结束即撤下未执行的任务」是 0 号宪法
  I-3 的 MUST，`cancel` 是它的执行手段，后端的有效期（§3）与渠道接管撤单（§3）是它的后端侧兜底。
- 暂停期间 worker **仍然活着**（§7.2 `paused` 与 `alive` 分开报），便于区分「人为停」与「卡死」。
- **留痕交叉引用（建议2）**：端到端可追溯 = **人审决策留痕在消费方侧**（AMR仁德 `log_event`，谁/何时确认）+ **后端执行留痕**（每次 GUI 动作的执行结果/时刻/`lastError` 落 `outbox` 行,`pause`/`cancel`/紧急越权亦留痕）。两段拼起来才是完整的「谁批的 → 何时发的 → 结果如何」链条。

---

## §7 能力声明与可观测

### 7.1 capabilities
```json
{ "outbox": { "enqueue": true, "account": true,
              "kinds": ["send_text","like_moment","comment_moment"],
              "receipt": ["poll"], "pause": true, "cancel": true } }
```
（`receipt` = `["poll"]`（§4 定案）；未实现的能力报 `false` / 不列。）

rev4 起可多一项（opt-in，缺省 = 不列 = `false`）：
```json
{ "outbox": { "...": "同上", "cancel": true, "presence_parallel": true } }
```

**`presence_parallel`（rev4 · opt-in 能力位）**：声明 `true` = 本后端承诺对本账号：
1. 按 §2.3 受理 / 拒绝形态 B 下单，并把 `authorization` / `presence_session_id` / `presence_ttl_secs` / 截止时刻落 `outbox` 行、在回执回显（§4）；
2. 执行形态 B 的有效期与渠道接管撤单（§3）；
3. **`cancel` 为 MUST**：声明 `presence_parallel: true` 而 `cancel` 不为 `true` = **违约**，消费方 **MUST 不以形态 B 下单**（形态 A 不受影响）；
4. 满足 `control-and-voice.md §8.1` PP-2（该账号全部驱动 GUI 的写动作由同一互斥锁串行化）与 PP-3（`control.state: true`）。

未声明（或声明 `false`）的后端：本契约对它的要求与 rev3 **一字不变**，消费方对它只用形态 A。能力位按账号读（一实例一账号，§2）。


**⚠️ `account` 不是可选能力位（rev2·R4 收口）**：`account` 维度 + `WRONG_ACCOUNT` 硬校验是**强制不变式（MUST）**，账号守恒是 0 号宪法铁律 5，**不受 capabilities 声明影响**——`"account"` 在此**恒为 `true`**，仅作可发现性回显，**不是一个可被降级的开关**。若某实现**报 `account:false` 或不做 `WRONG_ACCOUNT` 校验**，即为**违约**，消费方 **MUST 拒绝对其下单**（不得靠字符串巧合放行）。这条堵死「用一句 `account:false` 合法降级掉账号守恒」的口子。

**⚠️ `pause` 是不可降级的急停闸（rev3·SF1 收口）**：`pause`（全局急停，§6）与 `account` 同列**强制不变式（MUST）**——它是人的**紧急刹车**，HITL 一等（§1.8/§8）+ 0 号宪法「人在回路」的落点。`"pause"` 在此**恒为 `true`**，仅作可发现性回显，**不是一个可被降级的开关**。若某实现**报 `pause:false` 或不提供可用的全局急停**，即为**违约**，消费方 **MUST 拒绝对其下单**——一个「停不下来」的出站后端不得被允许对外发送。这条堵死「一句 `pause:false` 让人失去急停闸」的口子。

**↔ 对比 `cancel`（rev3·SF1 明确不硬化；rev4 例外见上方 `presence_parallel` 第 3 条）**：`cancel`（§6·撤单）是**次级兜底、非主 HITL 闸**（主闸在上游人审确认，§0/§1.8），且 R5 已约束其语义（`running` 不可撤）。故 `cancel` **保留为普通能力位**（可声明 `false`）——实现未提供撤单时消费方**优雅降级**（隐藏撤单入口，靠上游人审 + `pause` 兜底），**不升格 MUST**，避免过度约束未来实现。二者的区分标准 = **「缺了它人是否失去安全底线」**:缺 `pause` = 人没了急停刹车(致命)→ MUST;缺 `cancel` = 还有上游人审 + pause(可接受)→ 可选。

### 7.2 worker 活性 + 排空可观测（S3）
`GET /api/health/deep` 内：
```json
"outbox_worker": { "alive": true, "paused": false, "tick_age_secs": 0,
                   "oldest_queued_age_secs": 0, "last_completed_age_secs": 4 }
```
- `alive` = worker 在 `OUTBOX_TICK_STALE_SECS`（现 120s）内 tick 过；worker 每 ~1s tick 一次（空队列也 tick）。
- `paused` 与 `alive` **正交**：人为暂停时 `alive:true, paused:true`。
- **`oldest_queued_age_secs` / `last_completed_age_secs`（S3 新增）**：抓「**alive 但不排空**」——worker 可能 tick 照跳、却卡在某任务上不推进，队列静默积压。`tick_age` 抓不到，这两个指标能。
- **切换前置**：消费方切到**异步派发（`202` 下单）之前**必须能监控这些字段——否则 worker 卡死/堵塞会静默吞掉全部出站。**AMR仁德 侧配套（已认领）**：把 `outbox_worker` 活性并进现有发送端信号灯（`api_send_readiness`）——worker 不 alive / 堵塞 → **不下单 / 大声告警**，而非把任务默默塞进死队列。

---

## §8 口径定案（AMR仁德 对抗审 2026-07-22）

> 原为「待 AMR仁德 拍」，本 rev 记入 AMR仁德 对抗审给的口径（详见 PR#17 对抗审全文 + PD仁德 确认）。

| # | 口径 | 定案 | 落点 |
|---|---|---|---|
| ① | D 角撤销动作是否入队 | **入队 + 独立高优先车道 + 豁免节流**（与 `cancel` 区分） | §2.1 尾注 |
| ② | 幂等键有效窗口 | **≥ 7 天（可配）+ per-account 作用域**；到期 GC | §2.2 |
| ③ | 回执机制 | **(a) 轮询地板 + (c) 事件流演进；否决 (b) 回调** | §4 |
| ④ | 节奏/配额是否暴露消费端 | **暴露只读可观测；硬限留服务端；策略另立 `send-policy` #19** | §5 |
| ⑤ | `failed` 处置 | **park + lastError；无后端重投端点；重发 = 新幂等键重新下单（过人审）** | §3 |
| ⑥ | 多账号 | **per-account + `account` 字段（回执回显）+ 硬校验无跨账号 + 一实例一账号不变式** | §2 |
| ⑦ | 在场并行的确认形态（rev4） | **形态 B 合法，但仅限：`send_text` + 后端已 opt-in `presence_parallel` + `cancel` 为 MUST + 每条带 `presence_session_id` 与 `presence_ttl_secs`；判定责任在消费方，后端留痕 / 拒绝 / 执行有效期与渠道接管撤单** —— 待 PD仁德 确认 | §0 / §2.3 / §3 / §7.1 |

---

## §9 PD仁德 实现侧（参考·AMR仁德 不 own 此节）

| 项 | 现状 / rev1 待补 |
|---|---|
| 存储 | `agent.db` 表 `outbox`（V4 迁移）。**rev1 待加 `account` 列** + 幂等键 per-account + 终态保留 ≥7d GC |
| worker | 单 worker，1s tick（`worker.rs:12`）；原子认领（避免双取）；**绝不跨 await 持 DB 锁** |
| 执行 | `RealExecutor` 复用现有同步端点的出站核心（send/like/comment），**DRY，不复制业务逻辑** |
| 重试 | 失败 → `deferred` + ~30s 退避 → 重排；达 `maxAttempts` → `failed`(park) |
| 恢复 | **rev1 待改**：`reclaim_orphaned_running`（`repo.rs:121`）现无脑重排 → 改**按 kind 分流**（幂等→queued / 非幂等→failed·park）（B3） |
| account | **rev1 待做**：下单体 + 校验 `== 本实例账号` + `WRONG_ACCOUNT` 拒 + 回执回显（B2） |
| health | **rev1 待做**：加 `oldest_queued_age_secs` / `last_completed_age_secs`（S3） |
| 回执 | **rev1 待做**：`?idempotencyKey=` + `updatedSince`（S1） |
| 已部署 | `http://192.168.31.28:6174`，worker 实测 `alive:true`；**历史零任务**——消费方尚未切换 |
| presence_parallel | **rev4 待做（opt-in，不做即维持现状）**：`outbox` 行加 `authorization` / `presence_session_id` / `presence_ttl_secs` / 截止时刻列 · §2.3 受理判定 · 认领前截止判定 + 过期转 `failed` · HUMAN 态立即撤形态 B 任务 · `cancel` 端点就绪 · 同步端点与 worker 共用同一 GUI 互斥锁（`control-and-voice.md §8.1` PP-2）· 全部就绪后才在 capabilities 报 `presence_parallel: true` |

---

## §10 切换路径（双方）

1. AMR仁德 非作者 fresh agent 复核本 rev1 契约 diff → 班迪 merge + tag。
2. PD仁德 按定案补齐后端：B2 account 维度 / B3 按 kind 分流 / S1 回执查询 / S3 health 指标 / S5 幂等窗口。
3. **AMR仁德 侧切换**：出站从同步端点改为 `POST /api/outbox`，下单体填 `account`（会话所属账号），按 §4 (a) 取回执、断言 `回执.account == 下单.account`。**灰度**：先切 `like_moment`（幂等、误发无实质外发伤害）验链路；**切 `send_text` 前 B1/B2/B3 + S3（worker 活性并进 `api_send_readiness`）必须先落地**。
4. **同步端点保留**（现有行为不变，additive）——两条路并存一段，切换可回退。
5. **在场并行（rev4，可选）**：前置 = 第 3 步的 `send_text` 已切到 outbox 并稳定。PD仁德 完成 §9 `presence_parallel` 一行并真机验
   （HUMAN 态撤单、过期不执行、同步端点与 worker 互斥）后才报能力位；AMR仁德 按 0 号宪法 I-1…I-6 实现在场判定并按 §0 完成
   形态 B 准入声明后，才以形态 B 下单。任一侧撤回，回到形态 A，不影响既有发送。

— **PD仁德** 起草 2026-07-21 · rev1 据 AMR仁德 对抗审改 2026-07-22 · 待 AMR仁德 复核 diff
— **AMR仁德** rev4（v1.1）据 0 号宪法 v2.1「在场并行」节起草 2026-10-11 · **待 PD仁德 确认**（本 rev 新增的后端义务全部在 §2.3 / §3 / §7.1 / §9）
