# 出站派发契约 v1（提案）— Outbox Dispatch Contract（并行下单 · 串行拟人出站 · 异步回执）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`outbox/` → AMR/@gthneo）。
>
> **日期** 2026-07-21 ｜ **状态** **提案·PD仁德 起草待 AMR仁德 审计**（不 merge）
> **from** PD仁德（powerdata-wx / fullwechat 微信后端，`/Users/neo/as/fullwechet`）—— 契约执笔 + 实现方
> **to** AMR仁德（AgenticMessageRouter，`/Users/neo/as/agenticmessagerouter`）—— 契约定义/审计方 + 下单方
> **姊妹契约** `../send-target/*`（同步发送目标）· `../message/canonical.md`（入站消息）· `../moments/read-like.md`（朋友圈动作）
> **适用范围** **出站动作的排队派发**：消费方并行下单 → 后端单 worker 串行 + 拟人节奏执行 → 结果异步取回。**不覆盖**动作本身的语义（发什么/赞哪条见姊妹契约），也不覆盖入站。

---

## §0 这份契约是什么 / 为什么需要它

**问题（现状事实）**：消费方（AMR仁德 / M2仁德 等）当前调**同步**出站端点（`POST /api/messages` 等）——请求要一直挂到 GUI 驱动完成（发一条消息驱动搜索→打开会话→输入→发送，秒级到数十秒）。这带来三个结构性问题：

1. **并发不安全**：多个消费方/多条消息同时打进来 → 同时驱动同一个微信 GUI → 互相抢焦点、窗口错位、误发。
2. **调用方被阻塞**：并行生成内容的一侧（M2仁德 可并行产出多条）被迫等待串行的 GUI 执行。
3. **无拟人节奏落点**：同步端点「来一条发一条」，没有一个能安放「间隔/作息窗/速率上限」的位置——而这是账号资产保护的刚需（见 §5）。

**本契约的解**：在两侧之间放一个**持久化出站队列（outbox）**：
- **消费方并行下单**（fire-and-forget，立刻拿回 `202` + 任务 id，不等执行）；
- **后端单 worker 串行出队**，按拟人节奏执行（同一时刻只有一个动作在驱 GUI）；
- **结果异步取回**（§4）。

**本契约是**：下单形态（§2）+ 任务状态机（§3）+ 结果回执（§4）+ 拟人节奏与配额的语义边界（§5）+ HITL 手柄（§6）+ 能力声明（§7）。
**本契约不是**：动作内容语义（发什么文本 / 赞哪个 tid → 姊妹契约）；不是「发给谁、什么时候发」的决策（= **消费方领域**）；不是入站。

**边界**：AMR仁德 = 定义方（审计 / 定 shape / merge）；PD仁德 = 执笔 + 实现方（提事实、不自行解释契约）。

---

## §1 设计原则

1. **并行下单、串行执行**。下单可任意并发；**执行严格串行**（单 worker）——因为被驱动的微信 GUI 是**独占资源**，并行驱动必然互相破坏。这条是本契约存在的根本理由。
2. **fire-and-forget**。下单立即返回 `202 Accepted` + 任务 id，**不等执行结果**。消费方不因 GUI 慢而阻塞。
3. **持久化 + 崩溃可恢复**。任务落库（不是内存队列）；进程重启后**回收孤儿 `running` 任务**重新排队，不丢单、不悬挂。
4. **幂等**。`idempotencyKey` 相同 = 同一意图，重复下单**不重复执行**（消费方重试安全）。
5. **拟人节奏由后端承载、由后端硬限**（§5）。节奏 = 尊重对方 + 账号资产保护，**不是绕平台风控的伪装**；服务端**内建硬上限**，不 100% 依赖消费端自律（纵深防御）。
6. **HITL 一等**（§6）。人能随时 `pause` 全局、`cancel` 单条；已下单未执行的任务**可撤**。
7. **哑执行**。后端不决定「发不发、发给谁、发什么」——那是消费方 + 人的决策；后端只负责「按拟人节奏、串行、可靠地执行已下单的意图」。
8. **可观测**。worker 活性必须能被外部看见（§7.2），否则 worker 卡死会静默吞掉**所有**出站。

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
  "kind": "send_text",
  "target": "wxid_test_zhangsan",
  "payload": { "text": "你好" },
  "idempotencyKey": "amr-msg-8f3a1c",
  "platform": "wechat",
  "maxAttempts": 2
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `kind` | str | 是 | 动作类型，**封闭枚举**（§2.1）。未知值 → `400`。 |
| `target` | str | 是 | 动作目标的稳定 id：`send_text` = `chat_id`/wxid（姊妹 `send-target` 语义）；`like_moment`/`comment_moment` = moment `tid`。空串 → `400`。 |
| `payload` | obj | 否 | 该 `kind` 的参数（§2.1）。缺省 `{}`。 |
| `idempotencyKey` | str | 否 | 幂等键（§2.2）。**强烈建议给**——不给则无重试保护。 |
| `platform` | str | 否 | 缺省 `"wechat"`（为未来多渠道预留）。 |
| `maxAttempts` | int | 否 | 该任务最多执行次数，缺省 `2`，**后端 clamp 到 [1,10]**。 |

**响应（成功）**：HTTP **`202 Accepted`**
```json
{ "ok": true, "id": "b1e4…", "status": "queued" }
```
- **`202` 而非 `200`** 是语义核心：**已受理、尚未执行**。消费方拿到 `id` 即可返回，不等结果。
- 参数非法 → `400 {ok:false,error:"…"}`；入队失败 → `500`。

### 2.1 `kind` 枚举与 payload（PD仁德 现实现）

| `kind` | payload | 对应同步端点（语义等价，见姊妹契约） |
|---|---|---|
| `send_text` | `{ "text": "…" }` | `POST /api/messages` |
| `like_moment` | `{}` | `POST /api/moments/{tid}/like` |
| `comment_moment` | `{ "text": "…" }` | `POST /api/moments/{tid}/comment` |

> **扩展留位**：`unlike_moment` / `comment_delete` / `publish_moment` 等可后续纳入（新增走 AMR仁德 改 spec）。**待 AMR仁德 拍**：D 角撤销动作是否也该走队列？（PD仁德 观点见 §8 待议①。）

### 2.2 幂等语义

- 同一 `idempotencyKey` **重复下单 = no-op**，返回**原任务** id 与状态（不新建、不重复执行）。
- 消费方安全重试的前提；**没给 key 的下单无幂等保护**（网络重试可能产生两条真实出站）。
- **待 AMR仁德 拍**：幂等键的**有效窗口**（永久 / N 天）？见 §8 待议②。

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
| `queued` | 已受理，等待 worker | 否 |
| `running` | worker 正在执行（此刻正驱 GUI） | 否 |
| `deferred` | 执行失败，**温和退避**后重排（PD仁德 现实现退避 ~30s） | 否 |
| `done` | 执行成功 | **是** |
| `failed` | 达到 `maxAttempts` 仍失败，**停止重试**（park） | **是** |
| `cancelled` | 人/消费方在执行前撤单 | **是** |

- **崩溃恢复**：进程重启时，卡在 `running` 的孤儿任务被**回收重排**（避免永久悬挂）。
- **`failed` 是 park 不是丢弃**：任务留在库里带 `lastError`，供人审后决定重下单或放弃（可逆/可追溯）。

---

## §4 结果回执（异步）——⚠️ 本契约最需 AMR仁德 定的一节

fire-and-forget 的代价：下单方拿不到同步结果。消费方需要知道「那条到底发出去没有」。**PD仁德 现实现只提供拉取（a）**：

**(a) 拉取（已实现）**
```
GET /api/outbox/{id}     → { ok, task }
GET /api/outbox?status=&limit=   → { ok, tasks:[…] }
```
任务对象（**PII 安全**：`target` 只回显 hash，`payload` 完全不回显）：
```json
{ "id":"b1e4…", "kind":"send_text", "status":"done",
  "targetHash":"5ab899b8ecbe", "attempts":1, "maxAttempts":2,
  "lastError":null, "runAfter":0,
  "createdAt":1784600000000, "updatedAt":1784600042000, "executedAt":1784600042000 }
```

**(b) 回调 webhook（未实现·待 AMR仁德 定）**：终态时后端 `POST` 到 AMR仁德 提供的 URL。
**(c) 事件流（未实现·待 AMR仁德 定）**：复用现有结构化事件面，AMR仁德 订阅。

> **待 AMR仁德 拍（§8 待议③）**：回执走 (a) 轮询 / (b) 回调 / (c) 事件流,还是 (a)+(b)？PD仁德 给事实不预设：(a) 已在线、零新增攻击面，但要求 AMR仁德 轮询；(b) 实时、省轮询,但引入后端主动外呼 + 鉴权/重试/失败堆积问题;(c) 与既有事件面一致,但需 AMR仁德 侧订阅基建。

---

## §5 拟人节奏与配额（后端承载）

后端在**执行侧**（非下单侧）施加节奏，消费方无需也无法绕过：

- **间隔**：相邻出站动作之间的最小间隔 + 抖动。
- **作息窗**：非活跃时段不执行（任务留在 `queued`，到点再发）。
- **速率上限**：单位时间出站条数硬顶。
- **dwell**：动作前后的自然停顿。

**语义定位（宪法要求）**：节奏 = **尊重对方（非骚扰）+ 账号资产保护**；**不是**把自动化伪装成人以躲平台检测。参数由后端按该账号自身历史校准（`agent.db` 行为 profile）。

- **服务端硬限（纵深防御）**：即使消费方疯狂下单，后端也**必须**按上限执行——**不 100% 依赖消费端自律**。
- **超限行为**：超出速率/作息窗的任务**留在队列等待**（不是拒绝、不是丢弃）。
- **待 AMR仁德 拍（§8 待议④）**：后端是否要把当前节奏参数 + 剩余配额**暴露给消费端**（供其自律排期）？这与 roadmap 的 `send-policy` 契约（A2）重叠——是并入本契约还是独立成契约？

---

## §6 HITL 手柄（已实现）

| 端点 | 用途 |
|---|---|
| `POST /api/outbox/{id}/cancel` | 撤单（仅未进终态者）——误下单的退路 |
| `POST /api/outbox/pause` | **全局暂停**出站（worker 继续 tick，但不认领任务） |
| `POST /api/outbox/resume` | 恢复 |
| `GET /api/outbox?status=queued` | 人审待发清单 |

- **`pause` 是人的急停闸**：出任何异常（风控告警 / 内容出错 / 账号异常）先 `pause`，队列不丢。
- 暂停期间 worker **仍然活着**（§7.2 `paused` 与 `alive` 分开报），便于区分「人为停」与「卡死」。

---

## §7 能力声明与可观测

### 7.1 capabilities
```json
{ "outbox": { "enqueue": true, "kinds": ["send_text","like_moment","comment_moment"],
              "receipt": ["poll"], "pause": true, "cancel": true } }
```
（`receipt` 取值随 §4 定案；未实现的能力报 `false` / 不列。）

### 7.2 worker 活性（已实现·切换前置）
`GET /api/health/deep` 内：
```json
"outbox_worker": { "alive": true, "paused": false, "tick_age_secs": 0 }
```
- `alive` = worker 在 `OUTBOX_TICK_STALE_SECS`（现 120s）内 tick 过；worker 每 ~1s tick 一次（空队列也 tick）。
- `paused` 与 `alive` **正交**：人为暂停时 `alive:true, paused:true`。
- **切换前置**：消费方切到 fire-and-forget **之前**必须能监控此字段——否则 worker 卡死会静默吞掉全部出站。

---

## §8 待 AMR仁德 拍的口径（PD仁德 摆决策面，不预设）

| # | 待议 | PD仁德 给的事实 |
|---|---|---|
| ① | **D 角撤销动作是否入队**（`unlike`/`comment_delete`/`delete-moment`） | 事实：撤销通常是**误触后的紧急回收**,排队会延迟回收窗口;但撤销同样驱 GUI、同样需串行。二者张力归 AMR仁德 裁。 |
| ② | **幂等键有效窗口** | 现实现按库内记录判定（无 TTL 清理）。窗口过长 = 库增长;过短 = 迟到重试会重复发。 |
| ③ | **回执机制**（§4） | (a) 轮询已在线;(b) 回调需后端主动外呼(鉴权/重试/堆积);(c) 事件流需消费侧订阅基建。 |
| ④ | **节奏/配额是否暴露给消费端** | 与 roadmap `send-policy`(A2) 重叠;是否并入本契约。 |
| ⑤ | **`failed` 任务的处置** | 现为 park + 留 `lastError`。是否需要「重投」端点,还是由消费方重新下单(新 idempotencyKey)? |
| ⑥ | **多账号** | 现实现单账号单队列。多账号实例各自独立队列,还是契约层要带 `account` 维度? |

---

## §9 PD仁德 实现侧（参考·AMR仁德 不 own 此节）

| 项 | 现状 |
|---|---|
| 存储 | `agent.db` 表 `outbox`（V4 迁移），字段含 `id/kind/platform/target/payload/status/idempotency_key/attempts/max_attempts/last_error/run_after/created_at/updated_at/executed_at/result` |
| worker | 单 worker，1s tick；原子认领（避免双取）；**绝不跨 await 持 DB 锁** |
| 执行 | `RealExecutor` 复用现有同步端点的出站核心（send/like/comment），**DRY，不复制业务逻辑** |
| 重试 | 失败 → `deferred` + ~30s 退避 → 重排；达 `maxAttempts` → `failed`(park) |
| 恢复 | 启动时回收孤儿 `running` |
| 已部署 | `http://192.168.31.28:6174`，worker 实测 `alive:true`；**历史零任务**——消费方尚未切换 |
| 未做 | 回执 (b)/(c)；节奏参数暴露；多账号维度 |

---

## §10 切换路径（双方，供 AMR仁德 参考）

1. AMR仁德 审定本契约 → 班迪 merge + tag。
2. PD仁德 按定案补齐（回执机制 / capabilities `outbox` 块 / 其余口径）。
3. **AMR仁德 侧切换**：出站从同步端点改为 `POST /api/outbox`，按 §4 定案取回执。**建议灰度**：先切一种 `kind`（如 `like_moment`，风险最低）跑通再全切。
4. **同步端点保留**（现有行为不变，additive）——两条路并存一段，切换可回退。

— **PD仁德** 起草 2026-07-21 · 交 **AMR仁德** 对抗审后定稿
