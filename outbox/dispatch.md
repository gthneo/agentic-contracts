# 出站派发契约 v1（提案·rev1）— Outbox Dispatch Contract（并行下单 · 串行拟人出站 · 异步回执）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`outbox/` → AMR/@gthneo）。
>
> **日期** 2026-07-21（rev1 2026-07-22）｜ **状态** **提案·rev1**——AMR仁德 对抗审（APPROVE-WITH-CHANGES，3 BLOCKING + 7 SHOULD-FIX + 6 口径）→ PD仁德 逐条核验确认 → **本 rev1 = PD仁德 据确认改契约**，待 AMR仁德 非作者 fresh agent 复核 diff → 班迪 merge。**不 merge。**
> **from** PD仁德（powerdata-wx / fullwechat 微信后端，`/Users/neo/as/fullwechet`）—— 契约执笔 + 实现方
> **to** AMR仁德（AgenticMessageRouter，`/Users/neo/as/agenticmessagerouter`）—— 契约定义/审计方 + 下单方
> **姊妹契约** `../send-target/*`（同步发送目标）· `../message/canonical.md`（入站消息）· `../moments/read-like.md`（朋友圈动作）
> **适用范围** **出站动作的排队派发**：消费方**人审确认后**并行下单 → 后端单 worker 串行 + 拟人节奏执行 → 结果异步取回。**不覆盖**动作本身的语义（发什么/赞哪条见姊妹契约），也不覆盖入站。

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

**⚠️ HITL 边界（宪法红线·B1）**：`POST /api/outbox` 是 **dry-run→confirm→act 里的「act」步**——它**只在 AMR仁德 侧的人审确认闸通过之后**被调用。人审闸在**消费方（AMR仁德）上游、强制**（对齐现网 `api_confirm_outbox`：queue-for-human → 人 confirm → 才 enqueue-to-backend）。**队列不是确认闸的替代**，它的价值 = 把**人已经批准的** N 条按拟人节奏、串行、可靠地放出去。后端是哑执行器——收到下单即视为「人已确认」，不二次判断该不该发（那是上游 + 人的职责）。

**本契约是**：下单形态（§2）+ 任务状态机（§3）+ 结果回执（§4）+ 拟人节奏与配额的语义边界（§5）+ HITL 手柄（§6）+ 能力声明（§7）。
**本契约不是**：动作内容语义（发什么文本 / 赞哪个 tid → 姊妹契约）；不是「发不发、发给谁、什么时候发」的决策（= **消费方 + 人领域**）；不是入站。

**边界**：AMR仁德 = 定义方（审计 / 定 shape / merge）；PD仁德 = 执笔 + 实现方（提事实、不自行解释契约）。

---

## §1 设计原则

1. **并行下单、串行执行**。下单可任意并发；**执行严格串行**（单 worker）——因为被驱动的微信 GUI 是**独占资源**，并行驱动必然互相破坏。这条是本契约存在的根本理由。
2. **下单 = act（人审后）**。`POST /api/outbox` 立即返回 `202 Accepted` + 任务 id，**不等执行结果**（消费方不因 GUI 慢而阻塞）；但**下单本身是人审确认闸之后的动作**（§0 HITL 边界）——「不等结果」指**执行时长解耦**，不是「跳过人的确认」。
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
| `account` | str | **是** | 发信账号的稳定 id（会话所属账号）。**恒必填**（即便当前一实例一账号，见下「不变式」）。后端硬校验 `account == 本实例登录账号`，不符 → `409 WRONG_ACCOUNT`，**绝不跨账号执行/回退**。 |
| `kind` | str | 是 | 动作类型，**封闭枚举**（§2.1）。未知值 → `400`。 |
| `target` | str | 是 | 动作目标的稳定 id：`send_text` = `chat_id`/wxid（姊妹 `send-target` 语义）；`like_moment`/`comment_moment` = moment `tid`。空串 → `400`。 |
| `payload` | obj | 否 | 该 `kind` 的参数（§2.1）。缺省 `{}`。 |
| `idempotencyKey` | str | 否（AMR仁德 侧当必填） | 幂等键（§2.2）。**AMR仁德 侧一律由 outbox 行 id/内容 hash 派生稳定键、当必填**——不给则无重试保护。 |
| `platform` | str | 否 | 缺省 `"wechat"`（为未来多渠道预留）。 |
| `maxAttempts` | int | 否 | 该任务最多执行次数。**缺省按 kind 幂等性**：非幂等（`send_text`/`comment_moment`）= **`1`（at-most-once）**；幂等（`like_moment`）= `2`。后端 clamp `[1,10]`；**非幂等 kind 显式给 >1 = 消费方自担重复外发风险**（后端记 warning）。 |

**账号守恒不变式（invariant·B2）**：本契约按**「一后端实例 = 一微信账号 = 一队列」**（端点身份即账号身份，AMR仁德 `db.account_backend` 按会话所属账号绑各自 host+token）。`account` 字段在此前提下仍**恒必填**，因为它是：(i) AMR仁德 机器断言「回执.account == 下单.account」的依据；(ii) 前向接口——**若该前提被打破（某实例服务多账号），`WRONG_ACCOUNT` 硬校验 → per-account 队列/路由要求自动升级**，`account` 已在契约面、无需改 shape。

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

---

## §3 任务状态机

```
queued ──(worker 认领)──> running ──成功──> done
   │                        │
   │                        ├─失败且未超 maxAttempts──> deferred ──(退避到期)──> queued
   │                        └─失败且已达 maxAttempts──> failed
   └──(HITL cancel)──> cancelled
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

- **`failed` 是 park 不是丢弃**：任务留在库里带 `lastError`，供人审后决定重下单或放弃（可逆/可追溯）。
- **口径⑤（已定）**：`failed` 处置 = park + `lastError`，**无后端「原地重投」端点**（那会让 park 任务**绕过新一轮人审**再次外发 = HITL 旁路，禁）。重发 = 消费方**带新幂等键重新下单**（须再过人审）。

---

## §4 结果回执（异步）

fire-and-forget 的代价：下单方拿不到同步结果。消费方需要知道「那条到底发出去没有」。**口径③（已定）：(a) 轮询作 v1 强制地板（现在就上）；(c) 事件流作前向演进（AMR仁德 建通用订阅基建后）；明确不采 (b) 回调。**

**(a) 拉取（v1 地板·已实现 + 本 rev 补齐）**
```
GET /api/outbox/{id}                          → { ok, task }
GET /api/outbox?idempotencyKey=<key>          → { ok, task }   # 崩溃恢复 reconcile 关键
GET /api/outbox?status=&updatedSince=&limit=  → { ok, tasks:[…] }   # 增量对账游标
```
- **`?idempotencyKey=` 查询（S1 新增）**：下单成功回 `id`，但若 AMR仁德 在「拿到 id」与「落库 id」之间崩溃，须能凭自己的幂等键回查结局，否则该任务无法 reconcile → 可能重复下单。
- **`updatedSince` 增量游标（S1 新增）**：供 AMR仁德 高效增量对账、不每轮全表扫。

任务对象（**PII 安全**：`target` 只回显 hash，`payload` 完全不回显；**回显 `account`** 供断言账号一致）：
```json
{ "id":"b1e4…", "account":"wxid_selfaccount_28", "kind":"send_text", "status":"done",
  "targetHash":"5ab899b8ecbe", "attempts":1, "maxAttempts":1,
  "lastError":null, "runAfter":0,
  "createdAt":1784600000000, "updatedAt":1784600042000, "executedAt":1784600042000 }
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
- **可解释 + 紧急越权（S2）**：任务的 `runAfter`（预计放出时刻）**对人可见**——一条人刚确认、期望即发的消息若被作息窗压数小时，须让人看到「将延迟、预计 X 点发」，而非静默。并给**紧急越权手柄**（真急的可越作息窗发）。
- **口径④/⑦（已定）**：当前节奏态 + 剩余配额的**「回读」归本契约**（只读·可观测，属 §7 worker 运行态）；**限额策略本身**（作息窗表、per-account 校准、上限取值）归**独立 `send-policy` 契约（本仓 #19）**——机制（dispatch）与策略（policy）分离。暴露给消费端 = **只读可观测手柄**（供人合理排期、向人解释），**非**消费端能上调的控制旋钮（服务端硬上限唯一权威）。

---

## §6 HITL 手柄

> **定位（B1）**：人审主闸在**上游**（§0，消费方侧、下单前、强制）。本节手柄是**次级兜底 + 运行态干预**，**不是**主确认闸。

| 端点 | 用途 |
|---|---|
| `POST /api/outbox/{id}/cancel` | 撤单——**仅 `queued`/`deferred`**（`running` **拒撤**，避免撤一个正驱 GUI 的任务导致半发；best-effort 无保证）。是确认后反悔的**次级兜底**，仅在队列有深度/作息窗延迟时才可能生效。 |
| `POST /api/outbox/pause` | **全局急停**出站（worker 继续 tick，但不认领任务） |
| `POST /api/outbox/resume` | 恢复 |
| `GET /api/outbox?status=queued` | 已确认待放清单（运行态可见，非人审闸本身） |

- **`pause` 是人的急停闸**：出任何异常（风控告警 / 内容出错 / 账号异常）先 `pause`，队列不丢。
- 暂停期间 worker **仍然活着**（§7.2 `paused` 与 `alive` 分开报），便于区分「人为停」与「卡死」。

---

## §7 能力声明与可观测

### 7.1 capabilities
```json
{ "outbox": { "enqueue": true, "account": true,
              "kinds": ["send_text","like_moment","comment_moment"],
              "receipt": ["poll"], "pause": true, "cancel": true } }
```
（`receipt` = `["poll"]`（§4 定案）；未实现的能力报 `false` / 不列。）

### 7.2 worker 活性 + 排空可观测（S3）
`GET /api/health/deep` 内：
```json
"outbox_worker": { "alive": true, "paused": false, "tick_age_secs": 0,
                   "oldest_queued_age_secs": 0, "last_completed_age_secs": 4 }
```
- `alive` = worker 在 `OUTBOX_TICK_STALE_SECS`（现 120s）内 tick 过；worker 每 ~1s tick 一次（空队列也 tick）。
- `paused` 与 `alive` **正交**：人为暂停时 `alive:true, paused:true`。
- **`oldest_queued_age_secs` / `last_completed_age_secs`（S3 新增）**：抓「**alive 但不排空**」——worker 可能 tick 照跳、却卡在某任务上不推进，队列静默积压。`tick_age` 抓不到，这两个指标能。
- **切换前置**：消费方切到 fire-and-forget **之前**必须能监控这些字段——否则 worker 卡死/堵塞会静默吞掉全部出站。**AMR仁德 侧配套（已认领）**：把 `outbox_worker` 活性并进现有发送端信号灯（`api_send_readiness`）——worker 不 alive / 堵塞 → **不下单 / 大声告警**，而非把任务默默塞进死队列。

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

---

## §10 切换路径（双方）

1. AMR仁德 非作者 fresh agent 复核本 rev1 契约 diff → 班迪 merge + tag。
2. PD仁德 按定案补齐后端：B2 account 维度 / B3 按 kind 分流 / S1 回执查询 / S3 health 指标 / S5 幂等窗口。
3. **AMR仁德 侧切换**：出站从同步端点改为 `POST /api/outbox`，下单体填 `account`（会话所属账号），按 §4 (a) 取回执、断言 `回执.account == 下单.account`。**灰度**：先切 `like_moment`（幂等、误发无实质外发伤害）验链路；**切 `send_text` 前 B1/B2/B3 + S3（worker 活性并进 `api_send_readiness`）必须先落地**。
4. **同步端点保留**（现有行为不变，additive）——两条路并存一段，切换可回退。

— **PD仁德** 起草 2026-07-21 · rev1 据 AMR仁德 对抗审改 2026-07-22 · 待 AMR仁德 复核 diff
