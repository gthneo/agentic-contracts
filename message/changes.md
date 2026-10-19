# 消息变更流契约 v1（提案·rev0）— Message Change Feed Contract（`message.changes/1`）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`message/` → AMR/@gthneo）。
>
> **日期** 2026-10-19 ｜ **状态** **提案·rev0**（2026-10-19 补实现中查到的事实：§3.3 覆盖、§4.2 换代原因、§5 `NOT_READY` 原因、§9.2 字段定义、§11 存储方式）——PD仁德 起草，待 **AMR仁德**（契约定义/审计方，定稿）与 **Metis仁德**（第二消费方，共同评审）审；班迪 2026-10-19 审定由两个消费方共同评审。**不 merge。**
> **from** PD仁德（powerdata-wx / fullwechat 微信后端，`/Users/neo/as/fullwechet`）—— 契约执笔 + 实现方
> **to** AMR仁德（AgenticMessageRouter，`/Users/neo/as/agenticmessagerouter`）· Metis仁德（Metis，`/Users/neo/as/metis`，微信 Adapter 见 `gthneo/metis#9`）
> **姊妹契约** `canonical.md`（单条消息的信封语义，本契约原样复用）· `../outbox/dispatch.md`（出站；本契约只管入站读）· `../VERSIONING.md`
> **来源** `gthneo/powerdata-wx` Epic #74 Q2（班迪 2026-10-16 审定 Q1 = (c)：正确性状态下沉 backend）；修 `gthneo/powerdata-wx#60`、`#64`。

---

## 术语表（Glossary）

| English name | Definition (canonical) | 中文说明 |
|---|---|---|
| **Change Feed** | An append-only, backend-issued, per-account ordered log of observed message changes, read by cursor. | 消息变更流：后端签发、只追加、按账号排序的日志 |
| **Change** | One entry of the Change Feed: one observation that a message was added or revoked. | 变更条目 |
| **Observation** | The backend poller detecting a new message row, or a mutation of a known row, in the WeChat local database. | 观测：后端轮询器在微信本地库里发现新消息行或已知行被改写 |
| **`seq`** | A strictly increasing integer the backend assigns when it appends a Change, unique within one epoch. | 序列号，后端追加时分配 |
| **Epoch** | An identifier for one continuous lifetime of the feed storage; it changes whenever that storage is recreated. | 日志代次：存储被重建即换代 |
| **Cursor** | An opaque string issued by the backend that encodes (account, epoch, seq); consumers store it and send it back unchanged. | 游标，消费方原样保存、原样回传 |
| **Retention Window** | The minimum time span of Changes the backend guarantees to keep readable. | 保留窗口 |
| **Wake Hint** | A push notification that only tells a consumer to pull; it carries no delivery guarantee. | 唤醒提示，只提示「该拉了」，不保证送达 |
| **Consumer** | Any system that reads the feed with its own cursor. | 消费方（AMR、Metis 微信 Adapter、OpenClaw channel、wechat-mcp） |

---

## §0 这份契约是什么 / 为什么需要它

**问题（现状事实）**：后端 = PWDX（PowerData-WX）主程序 agent-server（Rust HTTP 服务，`gthneo/powerdata-wx` 仓 `packages/agent-server-rust`，现网 0.15.x，一个容器对应一个微信账号）。它的入站推送靠一个内存轮询器（`packages/agent-server-rust/src/tools/wechat_message_poll.rs`）生成 WebSocket（WS）事件 `message:new`。它有四个结构性缺陷：

1. **首见不发（#64，已证实）**：会话第一次进入轮询器的内存基线时只记基线、不发事件。.28 Staging 上（2026-06-28 起统计）：库内消息 124,744 条，无对应事件 10,983 条（8.8%）；**沉寂 ≥ 1 天后的第一条消息约 67–70% 没有事件**。轮询每周期只看排序最新的 200 个会话，其中 123 个是公众号（`gh_`）会话，真实会话只覆盖约最近 21 小时。
2. **游标用 `local_id`（#60）**：`local_id` 在每个 `message_N.db` 分片内各自从 1 计数，同一会话的消息跨 13 个分片；以它为游标会漏发、也会把旧分片的老消息当新消息发。
3. **不可重放（no replay）**：事件只在内存里广播。消费方断线期间的事件直接丢失，所以每个消费方各自补一层轮询加去重（AMR 每 300 s 按会话全量补拉）。
4. **出现第二个消费方**：Metis + OpenClaw 与 AMR 并列读取微信数据（`gthneo/metis#9`），两者相互隔离，需要各自独立推进、互不影响的读取位置。

**本契约的解**：后端维护一条 **Change Feed**——每观测到一条消息新增或撤回，就以单调 `seq` 追加一条 Change（含当时的消息信封快照）；消费方凭自己保存的 **Cursor** 增量拉取；WS 事件降级为 **Wake Hint**。

**可追溯到 0 号宪法**：第九条「接入的算料不得静默丢失；不能接入或者接入不全的，应当如实标明。原件只追加，不改写」——#64 正是静默丢失；本契约把「观测到即入日志」「只追加」「覆盖范围如实声明（§3.3）」写成接口义务。本契约是**只读**接口，不产生对外动作，不涉及授权档位。

**本契约是**：读取接口形态（§2）+ 顺序与送达语义（§3）+ 首读、换代与过期（§4）+ 错误码（§5）+ 唤醒提示（§6）+ 多消费方隔离（§7）+ 账号守恒（§8）+ 能力声明与可观测（§9）。
**本契约不是**：单条消息长什么样（= `canonical.md`，原样复用，不改其语义）；历史回填（沿用现有 `GET /api/messages/{chat_id}`）；出站；推送通道本身的可靠性。

---

## §1 设计原则

1. **顺序由后端在数据所在处签发**（单一本体 One Ontology）：「某条消息排在第几」只有一个来源，不由各消费方各自推断。
2. **`seq` = 观测顺序，不是消息时间**：离线补收、手机同步来的消息，`ts`（`create_time`）可能早于已经处理过的消息，所以 `ts` 不能当游标。
3. **拉取是唯一的正确性路径**：推送只用于唤醒；推送丢了，下一次拉取照样拿全。
4. **至少一次（at-least-once）送达 + 消费方幂等**：同一 Change 可能被读到不止一次（例如消费方从较早的 cursor 重读），消费方按 `(epoch, seq)` 去重；消息级去重仍按 `canonical.md` §2.1 的 `msg_id`。
5. **Cursor 由消费方持有，后端不保存任何消费方的进度**：AMR 与 Metis 的读取位置互不可见、互不影响（§7）。
6. **只读、无副作用**：读 Change Feed 不标已读、不驱动 GUI、不占用 GUI 锁。
7. **账号守恒**：响应恒带 `account`；cursor 绑定账号，拿到别的账号的后端上用即拒（§8）。
8. **快照，不是引用**：Change 携带观测当时的信封快照；之后消息被撤回，记为一条新的 `revoke` Change，旧 Change 不改写。
9. **读空必可区分**（`canonical.md` §6.4）：「确实没有新变更」返回 `200` + 空数组；「现在读不了」必须返回错误，**绝不返回 `200` 空数组**。
10. **覆盖范围如实声明**：哪些情况观测不到，写进契约（§3.3），不让消费方以为「流里没有 = 没发生」。

---

## §2 读取接口

```
GET /api/message-changes?cursor=<opaque>&limit=<N>
GET /api/message-changes?from=now|earliest&limit=<N>      # 首读（还没有 cursor 时）
Authorization: Bearer <token>
X-Consumer: <name>/<version>                               # 建议带，见 §7
```

> **路径说明**：Epic #74 回执里写的是 `/api/messages/changes`。rev0 改为 `/api/message-changes`，因为现有 `GET /api/messages/{chat_id}` 会与之共用前缀：微信老账号的内部 id 可以是用户自定义字符串，若某会话 id 恰为 `changes`，该会话的读取会被新路由遮蔽。换成独立前缀可以排除这种遮蔽。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `cursor` | str | 与 `from` 二选一 | 上一次响应的 `next_cursor`，原样回传。消费方**不得**解析或构造 cursor。 |
| `from` | `now` \| `earliest` | 与 `cursor` 二选一 | 首读起点。`now` = 从当前队头开始，只要之后的新变更（返回空 `changes` + 当前 `next_cursor`）；`earliest` = 从保留窗口内最早的 Change 开始。两者都不给按 `now`（口径 ②）。 |
| `limit` | int | 否 | 单页条数，缺省 `100`，后端 clamp 到 `[1, 500]`。 |

**响应（成功）**：HTTP `200`
```json
{
  "ok": true,
  "schema": "message.changes/1",
  "account": "wxid_selfaccount_28",
  "epoch": "e7c19a0b",
  "changes": [
    {
      "seq": 18233,
      "op": "add",
      "msg_id": "7882440073932743358",
      "chat_id": "5515706095@chatroom",
      "observed_at": 1792900000123,
      "message": { "…": "与 GET /api/messages/{chat_id} 返回数组里的单个元素相同" }
    }
  ],
  "next_cursor": "opaque…",
  "has_more": false,
  "head_seq": 18233,
  "producer": { "backend_version": "0.16.0" }
}
```

| 字段 | 说明 |
|---|---|
| `schema` | 恒为 `message.changes/1`（本契约 major 1）。 |
| `account` | 本实例当前登录账号的 wxid（WeChat 内部账号 ID，即 `/api/health/deep` 的 `wechat.self_id`）。 |
| `epoch` | 当前日志代次（§4.2）。 |
| `changes` | 按 `seq` 升序。可为空。 |
| `next_cursor` | **恒返回**（即使 `changes` 为空，此时等于请求位置），消费方处理完本页后持久化它。 |
| `has_more` | `true` = 队头之前还有未读 Change，应立即再拉一页。 |
| `head_seq` | 本代次当前最大 `seq`，供消费方自算积压（lag）。 |
| `producer.backend_version` | 后端软件版本，供消费方记入血缘（Lineage）。 |

### 2.1 Change 对象

| 字段 | 类型 | 说明 |
|---|---|---|
| `seq` | int | 本代次内严格递增。 |
| `op` | str | `add`（首次观测到这条消息）\| `revoke`（已知消息被撤回）。**消费方遇到不认识的 `op` 必须跳过并记日志，不得报错中断**——后端只以 minor 版本新增 `op`。 |
| `msg_id` | str \| 缺省 | 与 `canonical.md` §2.1 相同：WeChat `serverId` 的字符串形式。后端拿不到全局唯一 id 时**省略**此字段，消费方按 `canonical.md` 的 content-hash 规则去重。 |
| `chat_id` | str | 会话 id（个人 wxid / `…@chatroom` / `gh_…` / `…@openim`）。 |
| `observed_at` | int | 后端观测到此变更的时刻，Unix 毫秒。**不是**消息自身时间（消息时间在 `message.ts`）。 |
| `message` | obj | 观测当时的消息信封快照，**与 `GET /api/messages/{chat_id}` 返回数组里的单个元素是同一个 JSON 形态**（canonical 字段平铺在顶层，没有 `canonical` 包装键）。`op=revoke` 时为撤回后的信封（`kind=system` + `system.event="revoke"`，见 `canonical.md` §4.4）。 |

---

## §3 顺序与送达语义

### 3.1 顺序

- `seq` 在一个代次内**严格递增，但不保证连续**；消费方**不得**根据 `seq` 的间隔推断丢失。
- 顺序是**每账号全序**（跨会话统一排序），按观测先后，不按消息 `ts`。
- 同一代次内，同一条消息的同一个 `op` **至多出现一次**（后端按「消息身份 + `op`」唯一约束追加）。

### 3.2 撤回

- 撤回在微信里是原地改写同一 `serverId` 的行（`canonical.md` §4.4）。后端观测到已知消息行变为撤回形态时，追加一条 `op=revoke` 的 Change，`msg_id` 与原 `add` 相同。
- `revoke` 可能没有对应的 `add`（原消息在本代次开始之前、或首次观测时已被撤回）。消费方按 `canonical.md` §4.4 ① 处理：作为独立的 `system`/`revoke` 事件入库，不报错。

### 3.3 覆盖范围声明（如实标明观测不到的部分）

后端**承诺**：本代次开始之后，轮询器能读到的会话里出现的每条消息，都会以 `add` 进入 Change Feed；**每周期的扫描上限只允许推迟观测，不允许丢弃**（某会话积压超过单周期上限时，下个周期继续，直到追上已入日志的消息）。

后端**观测不到**、因此不会出现在流里的情况：

| 情况 | 说明 |
|---|---|
| 本代次开始之前的历史消息 | 用现有 `GET /api/messages/{chat_id}` 回填（§4.1）。 |
| 被观测之前就在本机删除的消息 | 行已不在库里。 |
| 微信未登录、数据库密钥缺失期间到达、且恢复后已不在本机库里的消息 | 恢复后能读到的会补上；读不到的无从观测。 |
| `canonical.md` §5 列为噪声、后端不 emit 的消息 | 与现有读路径一致。 |
| 公众号（`gh_`）图文 | 不在微信的消息表里（`canonical.md` §6.2 已声明为读路径之外）；公众号会话里普通消息表中的行照常进流。 |
| 消息自身时间早于保留窗口下限的消息 | 例如很久以前的消息在今天才同步到本机。不进流是为了避免「已被 GC 回收的 Change 又以新 `seq` 重复出现」；这类消息用 `GET /api/messages/{chat_id}` 读取。 |

---

## §4 首读、换代与过期

### 4.1 首读（bootstrap）

消费方第一次接入，推荐顺序（保证无缝）：

1. 先调 `from=now`，**持久化**返回的 `next_cursor`；
2. 再用现有 `GET /api/messages/{chat_id}` 回填所需历史；
3. 从第 1 步的 cursor 开始消费 Change Feed。

第 2 步与第 3 步的重叠部分按 `msg_id` 去重。第 1 步必须在第 2 步之前，否则两步之间到达的消息可能两边都拿不到。

### 4.2 换代（epoch）

- Change Feed 的存储被重建时，`epoch` 换成新值，`seq` 从头开始。
- **已知的重建原因**：后端 `agent.db` 用 SQLCipher 加密、密钥即 bearer token；token 与库密钥不一致时，后端会删除并重建 `agent.db`（`gthneo/powerdata-wx` `packages/agent-server-rust/src/db/mod.rs:86-104`，fail-closed 改造见 `#79`）。Change Feed 存于 `agent.db`，所以 token 未先 rekey 就轮换会导致换代。
- **本实例登录的微信账号变了**：后端清空旧账号的 Change 并换代——旧账号的快照绝不能以新账号的身份被读出（§8）。
- 旧代次的 cursor 一律返回 `410 CURSOR_EXPIRED`，`reason="epoch_changed"`。

### 4.3 过期（retention）

- 后端保证保留窗口内的 Change 可读（窗口长度见口径 ①，`capabilities` 中声明）；更早的可被回收。
- cursor 指向已回收的位置 → `410 CURSOR_EXPIRED`，`reason="retention"`。

### 4.4 收到 `410` 后的恢复

```json
{ "ok": false, "code": "CURSOR_EXPIRED", "reason": "retention",
  "oldest_cursor": "opaque…", "head_cursor": "opaque…" }
```

消费方：用 `GET /api/messages/{chat_id}` 按时间范围补拉缺口 → 从 `oldest_cursor`（`retention`）或新代次的 `from=earliest`（`epoch_changed`）继续 → 重叠按 `msg_id` 去重。**补拉是否完整由消费方如实记录**；补不全的时间段应标明，不得当作「没有消息」。

---

## §5 错误码

| HTTP | `code` | 含义 |
|---|---|---|
| `400` | `BAD_CURSOR` | cursor 无法解析或被篡改；同时给 `cursor` 与 `from`。 |
| `401` | — | 鉴权失败（现有行为）。 |
| `409` | `WRONG_ACCOUNT` | cursor 绑定的账号 ≠ 本实例当前登录账号（§8）。 |
| `410` | `CURSOR_EXPIRED` | `reason ∈ {retention, epoch_changed}`，附 `oldest_cursor` / `head_cursor`（§4.4）。 |
| `503` | `NOT_READY` | `reason ∈ {logged_out, not_observing}`：微信未登录；或轮询器超过 300 s 没有完成一整轮观测（如消息库密钥缺失、轮询器停顿）。**这些情况绝不返回 `200` 空数组。** |

错误体统一为 `{ "ok": false, "code": "…", "error": "…人可读说明…" }`，另加各自的附带字段。

---

## §6 唤醒提示（Wake Hint）

- 现有 WS `GET /api/ws/events` 的 `message:new` 事件**新增** `seq`、`epoch` 两个字段；**原有字段不变**（OpenClaw channel 的 `monitor.ts` 正在读它们）。
- `message:new` 只在对应 Change **提交之后**发出，所以消费方收到提示后去拉，一定能拉到这条。
- v1 只对 `add` 发提示；`revoke` 不单独发提示（口径 ④），由消费方的定时拉取取得。
- **消费方必须有定时拉取兜底**（建议间隔 ≤ 60 s）：WS 断线、重连期间的提示会丢，丢了不影响正确性，只影响时延。
- 后续若加 SSE（Server-Sent Events），事件 `id:` 直接用 `seq`，`Last-Event-ID` 可续传；不在 v1 范围。

---

## §7 多消费方隔离

- 每个消费方各自保存自己的 cursor；后端不保存消费方进度（口径 ⑤）。一个消费方的读取、过期、重同步，不影响另一个。
- 消费方**应当**带 `X-Consumer: <name>/<version>` 请求头（例：`amr/<version>`、`metis-wechat-adapter/<version>`）。后端只把它和请求的 `seq` 写入结构化事件日志（无正文、无 PII），用于观测各消费方的积压；**后端不据此改变任何返回内容**。AMR 现有的 `X-AMR-Version` 头（`../VERSIONING.md` §2）不受影响。
- 公众号会话是否进流：见口径 ③。

---

## §8 账号守恒

- `account` = 本实例当前登录账号的 wxid；比对规则同 `../outbox/dispatch.md` §2（字节级精确相等，不做规范化）。
- cursor 内含账号标识；拿到另一个账号的后端上用 → `409 WRONG_ACCOUNT`。
- 消费方**必须**断言 `response.account == 期望账号`，不符即停止消费并告警。同一账号的多条网络路径（局域网 / EasyTier 虚拟 IP / Tailscale）之间切换是安全的；**多个账号 = 多个后端 = 各自独立的 cursor，绝不互为 failover**。

---

## §9 能力声明与可观测

### 9.1 capabilities

```json
{ "message_changes": { "supported": true, "schema": "message.changes/1",
                       "ops": ["add", "revoke"], "retention_days": 7,
                       "max_limit": 500, "wake": ["ws:message:new"] } }
```

没有 `message_changes` 或 `supported:false` 的后端：消费方回退到现有读法（按会话轮询 `GET /api/messages/{chat_id}`）。

### 9.2 `/api/health/deep`

```json
"message_changes": { "epoch": "e7c19a0b", "head_seq": 18233,
                     "last_append_age_secs": 12, "poll_watermark_age_secs": 3,
                     "oldest_retained_age_secs": 604000, "unreadable_chats": 0 }
```

- `poll_watermark_age_secs` = 轮询器上一次**完成一整轮观测**（读到会话库并处理完本轮所有有变化的会话）距今的秒数。它抓「轮询器活着但不推进」——现有 `last_poll_age_secs` 只能证明循环在跑，证明不了在推进。
- `unreadable_chats` = 上一轮有变化、但消息表暂时读不到（某个分片缺密钥）的会话数；它们每轮重试。非 0 表示有消息正在延迟进流。
- `last_append_age_secs` 大，不一定是故障（夜间可能确实没有消息）；`poll_watermark_age_secs` 大才是故障信号。

### 9.3 血缘（Lineage）

消费方记录每条入库消息的来源时，建议一并记 `(account, epoch, seq, producer.backend_version)`。这对应 Metis 接入规范的「版本入血缘」（`/Users/neo/as/metis/specs/07-access-adapters.md` §5）与 0 号宪法第九条的「可追溯至证据与规则版本」。

---

## §10 待定口径（请 AMR仁德 定稿、Metis仁德 共同评审）

| # | 口径 | 选项与代价 | PD仁德 建议（非定案） |
|---|---|---|---|
| ① | 保留窗口 | (a) 7 天；(b) 30 天；(c) 按条数。存储估算：.28 自 2026-06-28 至 2026-10-11 约 124,744 条，约 1,200 条/天；每条快照按约 1 KB 估算，7 天约 8 MB，30 天约 36 MB | (a) 7 天起，可配置；与 outbox 幂等窗口一致 |
| ② | 首读缺省起点 | (a) `now`；(b) `earliest` | (a) `now`：首读走 §4.1 回填历史，`earliest` 需显式指定 |
| ③ | 公众号（`gh_`）会话是否进流 | (a) 全部进流，消费方按 `chat_id` 前缀自行过滤；(b) 缺省排除，`?include=official` 打开 | (a)：Metis 规范要求「读宽」，过滤放在消费方；轮询器的选会话方式改为按 `sort_timestamp` 后不再有名额挤占问题 |
| ④ | `revoke` 是否单独发唤醒提示 | (a) v1 不发，靠定时拉取；(b) 新增 WS 事件 | (a)：撤回量小，定时拉取的时延可接受；需要时以 minor 版本加 |
| ⑤ | 后端是否保存消费方进度 | (a) 不保存，只记 `X-Consumer` 日志；(b) 按名字保存（类似 Kafka consumer group），后端可直接报各消费方积压 | (a)：后端无状态，消费方隔离最彻底；积压用日志里的 `seq` 计算 |
| ⑥ | 没有 `serverId` 的消息行 | (a) 后端用内部替代键保证唯一，Change 省略 `msg_id`；(b) 不进流 | (a)：不进流违反「不得静默丢失」。这类行在库里实际有多少**存疑**，M1 开发时在 Dev `.156` 上实测 |

另请 **AMR仁德** 回复（Epic #74 回执 §5 已问，非本契约口径）：AMR 现有的 `serverId` 去重和 300 s 全量补拉，改接 Change Feed 之后保留还是退役。

---

## §11 PD仁德 实现侧（参考·非契约条款）

| 项 | 计划 |
|---|---|
| 存储 | `agent.db` 表 `message_changes`（`seq INTEGER PRIMARY KEY AUTOINCREMENT`、消息身份键、`op`、`chat_id`、`observed_at`、信封 JSON；唯一约束 `(身份键, op)`，`INSERT OR IGNORE`）+ 键值表 `message_feed_meta`（`epoch`、账号短哈希、`started_at`、观测水位、`gc_floor`）。**运行时 `CREATE TABLE IF NOT EXISTS` 建表，不走 refinery 迁移**：refinery 默认 `abort_missing=true`，旧版二进制打开记录过更新迁移的 `agent.db` 会拒绝启动，带新迁移的版本就无法靠换回旧二进制回滚。 |
| 轮询器 | 改写 `wechat_message_poll.rs`：选会话改为 `sort_timestamp > 上周期水位 − 安全余量`（修 #64 的名额挤占）；删除「首见只记基线」分支（修 #64）；消息身份用 `serverId`（修 #60，与 PR #58 同一原则）；水位落盘，重启后从水位续扫；单会话积压超过单周期上限时下周期继续。 |
| 撤回检测 | 已入日志的 `serverId` 行变为 `local_type=10000` 结构化 `<sysmsg type=revokemsg>` → 追加 `revoke`。选会话用会话指纹（活动时间 + `last_msg_locald_id` + 摘要哈希），撤回会改写会话摘要。**存疑**：撤回后会话行是否一定变化，M1 在 Dev `.156` 上实测。 |
| WS | `message:new` 加 `seq`、`epoch`，在追加提交后发出。 |
| 发布 | PWDX 主程序 agent-server **0.15.x → 0.16.0**（minor，按 7 份发布文档纪律）；PWDX 的 Connector（wechat-mcp，MCP（Model Context Protocol）服务）本里程碑不动。开发与 ≥24 小时观测只在 Dev `.156`（`192.168.31.156`）。回滚 = 换回 0.15.x 二进制；两张新表不经迁移登记，旧二进制直接忽略。实现分支 `gthneo/powerdata-wx` `feat/message-change-feed`，已热更到 Dev `.156` 观测。 |

---

## §12 切换路径

1. AMR仁德（定稿）与 Metis仁德（共同评审）审本提案 → PD仁德 出 rev1 → 非作者 fresh agent 对抗审 → 班迪 merge + tag。
2. PD仁德 按定稿实现（agent-server 0.16.0）。**纯增量**：`GET /api/messages/{chat_id}`、`message:new` 原有字段、AMR 现有读法都不变。
3. 各消费方按自己的节奏改接，互不依赖：OpenClaw channel（Epic #74 M2，PD仁德）· Metis 微信 Adapter（`gthneo/metis#9`，Metis仁德）· AMR（Epic #74 M5，AMR仁德 决定何时改接）。

— **PD仁德** 起草 2026-10-19 · 待 AMR仁德 定稿、Metis仁德 共同评审
