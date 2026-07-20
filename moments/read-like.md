# 朋友圈动作契约 v1.2 — Moments Action Contract（读 + 赞/评 + 可逆撤销 CRUD）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`moments/` → AMR/@gthneo）。

> **日期** 2026-06-28 ｜ **状态** 提案（待 fullwechat 后端评估实现）
> **from** AgenticMessageRouter (AMR) ｜ **to** fullwechat 后端
> **真相源** `agentic-contracts` 仓（本文件）—— AMR 定义契约，fullwechat 实现。
> **姊妹契约** `../message/canonical.md`（会话消息通道）/ 发布广播见同目录 `publish.md`
> **适用范围** 微信朋友圈（Moments）：动态读取 + 赞/评写动作 + 取消赞/删评论可逆撤销 + person-scoped warm。**不适用于会话消息**（见 §0）。

---

## §0 这份契约是什么 / 不是什么

微信的数据面分两块：

- **消息通道（Message Channel）**：会话消息，存 `message.db`，姊妹契约已覆盖。
- **社交动态面（Moments / 朋友圈）**：一对多广播 feed，存 `sns.db SnsTimeLine`（独立 WebView），**本契约覆盖**。

两者是**平行层**，技术来源不同、消费语义不同，不能混用一份契约。

**本契约是**：朋友圈 read（读动态信封）+ 赞/评（写动作）+ 取消赞/删评论（可逆撤销动作）的 AMR↔fullwechat 接口约束；含 person-scoped 寻址 warm（§3.4）。  
**本契约不是**：会话消息（见姊妹契约）；不是广泛的 Moments 社区运营规则。删**自己动态**（delete-moment）见姊妹 `publish.md` §7.5（= 发布的逆动作，归发布契约）。评论**读向**（列评论）仍 v.next YAGNI。

**真相源**：AMR 仓。后端有疑义 → 提 AMR，AMR 改本 spec → 后端按新版实现。**后端不自行解释契约**。

---

## §1 设计原则

1. **`text` 永远在场**。每条 moment 无论是纯图/纯视频还是分享链接，都带一个人类可读的 `text`（正文文字；无文字时给占位 `[图片]` / `[视频]` / `[链接]`）。这是展示地板，任何消费方只读 `text` 也不丢可用性。
2. **媒体 `ref` = fullwechat 取件端点绝对 URL，非 cdnurl**。微信 cdnurl 加密、AMR 端拿到也无法解密；`ref` 必须指向 fullwechat 已上线的 `/api/media/{chat_id}/{msg_id}` 端点（或同等，返回解密后字节），AMR GET 时带 bearer auth。与姊妹契约 `media.ref` 语义完全一致。
3. **能力声明 + 优雅降级**。后端暴露 capabilities；每项能力（read / like）独立声明；能力不可用时 AMR 侧静默降级（见 §6）。
4. **写动作幂等**。点赞端点对已赞动态再赞 = no-op，正常返回 `"liked":true`。AMR 可安全重试。
5. **HITL 最高准则（王总钦定）**。点赞是写操作、对外动作。**AMR 永不自动赞**。排期/候选由 AMR 决定，人批量审一次后，AMR 才逐条调点赞端点。后端 like 端点是"哑执行"——只管执行，不决定赞不赞。
6. **LLM 无关**。朋友圈面是纯结构化读取 + 确定性写动作，零 LLM 参与。不因模型不可用而降级功能。
7. **可逆（CRUD 并↔拆双向）**。凡「加」类写动作（赞 §4 / 评 §4.6）都配「撤」类逆动作（取消赞 §4.4 / 删评论 §4.7 / 删自己动态 publish.md §7.5）——误触 / 审后反悔时人能 HITL 撤销，不留不可回收的对外痕迹。这是账号资产保护 + 人在回路的必要退路，非可选（王总钦定 user-level CRUD 铁律）。

---

## §2 Moment Envelope（规范化读形态）

后端对每条 moment emit 一个信封。JSON 形态（合成占位值，无真实 PII）：

```json
{
  "schema": "moment.canonical/1",
  "channel": "wechat",
  "tid": "snsTimeLine_wxid_test_zhangsan_1750000001",
  "author": {
    "name": "张三",
    "wxid": "wxid_test_zhangsan"
  },
  "create_time": 1750000001,
  "text": "今天天气不错，出去走走",
  "media": [
    {
      "kind": "image",
      "placeholder": "[图片]",
      "ref": "https://fullwechat.host/api/media/moments/snsTimeLine_wxid_test_zhangsan_1750000001/0",
      "mime": "image/jpeg"
    }
  ],
  "link": null,
  "liked": false,
  "direction": "in"
}
```

分享链接类 moment（纯分享、无正文）：

```json
{
  "schema": "moment.canonical/1",
  "channel": "wechat",
  "tid": "snsTimeLine_wxid_test_lisi_1750000099",
  "author": { "name": "李四", "wxid": "wxid_test_lisi" },
  "create_time": 1750000099,
  "text": "[链接] 2026年中国制造业白皮书",
  "media": [],
  "link": {
    "title": "2026年中国制造业白皮书",
    "url": "https://example.com/whitepaper",
    "source": "行业观察"
  },
  "liked": true,
  "direction": "in"
}
```

### 2.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema` | str | 是 | 契约版本标识，v1 固定 `"moment.canonical/1"`。 |
| `channel` | str | 是 | 固定 `"wechat"`（v1 仅微信朋友圈）。 |
| `tid` | str | 是 | 动态稳定 id，来自 `sns.db SnsTimeLine` 主键或等效稳定标识。**点赞端点用此字段**，必须在同一后端实例内唯一且稳定（不随登录失效/重新抓取变化）。 |
| `author` | obj | 是 | 发布人。`name`=显示名，`wxid`=稳定 wxid（供 AMR 关系账户归一）。 |
| `create_time` | int | 是 | unix 秒（发布时间）。 |
| `text` | str | 是 | 正文文字，**永远非空**。纯图动态给 `[图片]`；纯视频给 `[视频]`；分享无正文给 `[链接] <链接标题>`。 |
| `media` | arr | 是 | 图片/视频列表，无则空数组 `[]`。字段见 §2.2。 |
| `link` | obj \| null | 是 | 分享链接，仅分享类动态有；纯图文给 `null`。字段见 §2.3。 |
| `liked` | bool | 是 | **我（self）是否已赞**此条动态。AMR 点赞前先读此字段做幂等判断：`liked:true` → 跳过调用（本地幂等）；`liked:false` → 才调端点。后端从 `sns.db` 的赞记录里查。 |
| `direction` | `"in"` \| `"out"` | 是 | `"out"` = 自己发布的动态（self 是 author）；`"in"` = 别人发的动态。判不准时默认 `"in"`（保守）。 |

### 2.2 `media` 元素字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `kind` | `"image"` \| `"video"` | 是 | 媒体类型。 |
| `placeholder` | str | 是 | 文字占位：图片给 `"[图片]"`，视频给 `"[视频]"`。AMR 无法渲染媒体时回退显示此字符串。 |
| `ref` | str | 是 | 取件端点绝对 URL（fullwechat 已上线的解密字节端点）。**非微信 cdnurl**。AMR GET 时带 bearer auth（`Authorization: Bearer <token>`）。路径格式建议 `/api/media/moments/{tid}/{index}`（与消息通道 `/api/media/{chat_id}/{msg_id}` 同族）。 |
| `mime` | str | 否 | MIME 类型，如 `"image/jpeg"` / `"video/mp4"`；给得出就给。 |
| `duration` | int | 否 | 视频时长（秒），仅 `kind="video"` 时有意义；给得出就给。 |

### 2.3 `link` 对象字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | str | 是 | 链接标题（分享文章/网页的标题）。 |
| `url` | str | 否 | 链接 URL；给得出就给（部分分享类 sns 条目可能无 url）。 |
| `source` | str | 否 | 来源名称（公众号名 / 站点名等）；给得出就给。 |

### 2.4 口径说明

- **`text` 地板**：结构化字段（`media` / `link`）给得出就给；给不出时，AMR 凭 `text` 也能正常展示动态摘要。`text` 和 `media`/`link` 不互斥——有文字 + 有图 = `text` 给正文文字，`media` 给图片列表。
- **`tid` 稳定性**：`tid` 必须在后端稳定（不随抓取批次变化）；AMR 用它做幂等判断 + 点赞调用。后端若 `tid` 不稳定，点赞端点无法幂等。
- **`liked` 精度**：从 `sns.db` 现有赞记录查，精度取决于本地 DB 同步状态；已知偏差 → 在 capabilities 里标注（见 §6）；AMR 按 `liked` 做本地幂等，但最终幂等由点赞端点保证（§4）。

---

## §3 读接口契约

### 3.1 按人读

```
GET /api/moments?person=<wxid>&limit=<N>
Authorization: Bearer <token>
```

- 返回指定 `wxid` 的人最近 N 条 moment envelopes（按 `create_time` 倒序）。
- AMR 读某人动态、选出候选 `tid` 去赞时走此接口。
- `person` 参数值 = `author.wxid`。
- `limit` 默认 20，上限后端自定（建议 ≤100）。

### 3.2 全 feed 读（可选）

```
GET /api/moments?limit=<N>
Authorization: Bearer <token>
```

- 不带 `person` 参数 → 返回整个朋友圈 feed（所有联系人）近 N 条，按 `create_time` 倒序。
- 此接口是**可选能力**；capabilities 里标 `"feed_all": true/false`（见 §6）。
- 后端若暂不实现，返回 HTTP 400 / capabilities 声明 `feed_all:false`，AMR 静默隐藏。

### 3.3 公共约束

- **只读**，bearer auth，HTTPS（对齐 §14 TLS 方案）。
- 响应体：JSON 数组 `[<moment envelope>, ...]`（空则 `[]`）。
- 后端**按 `create_time` 倒序**返回（最新在前）。
- 无分页 cursor（v1 YAGNI；AMR 按 limit 截取够用）。

### 3.4 person-scoped warm / sync（cold-start 寻址前置）

**背景（PD 实证事实，非 AMR 预设）**：目标人的**新帖常不在**本地 `sns.db` → `GET /api/moments?person=X` 返 `[]` → 无 `tid` → 后续赞/评端点 `MOMENT_NOT_FOUND` 够不着。实测（#12）：**导航某人相册会把其帖写入 `sns.db` 并拿到稳定、持久的 `tid`**（long-lived view cache，实测 2525 帖 / 1051 作者 / 2+ 年无驱逐）。故 cold 人需要一个显式「warm」动作先填库，寻址模型（`tid`）本身不变。

**端点**
```
POST /api/moments/sync?person=<wxid>
Authorization: Bearer <token>
```
- 后端驱 person-scoped 导航到 X 的相册（**不进单帖、不做任何写动作**）→ X 的帖进 `sns.db`。
- 成功返回 warm 后可寻址的 moments：`{ "ok": true, "count": N, "moments": [ {tid,text,liked,create_time,...}, ... ] }`。
- 失败：`{ "ok": false, "error": "SYNC_FAILED" | "PERSON_NOT_FOUND" }`。

**口径事实（PD 给，编排/触发归 AMR）**：
- **cold-start 依赖**：对某人**首次**赞/评/撤销前须先 `sync` 该人（否则 `MOMENT_NOT_FOUND`）。warm 后 `tid` 长寿命持久 → 同人后续动作**无需重 sync**。
- **驱 GUI 有代价**：warm 驱动微信 GUI（搜人→相册），有**秒级延迟**；相册图片密集时曾有 `msg.db-repair` 风险（后端已缓解：只点文字区、不开全屏看图、快进快出）。故 warm 是**显式、可 HITL gate 的一等动作**，不藏在读接口的惰性副作用里（读写分离）。
- **谁触发 sync、如何编排**（频次 / 时机 / 批量）= **AMR 决策面**，后端只提供哑执行的 warm 端点（守 contract-collaboration-boundary，PD 给事实不预设）。
- **capabilities**：`"sync": true`（未实现前 `false`）。

---

## §4 点赞动作契约

### 4.1 端点

```
POST /api/moments/{tid}/like
Authorization: Bearer <token>
Content-Type: application/json
```

- `{tid}` = moment envelope 里的 `tid` 字段（URL encode 如含特殊字符）。
- 请求体可为空（`{}`）；v1 无额外参数。

### 4.2 响应

**成功（含已赞幂等）**：

```json
{ "ok": true, "tid": "snsTimeLine_wxid_test_zhangsan_1750000001", "liked": true }
```

**失败**：

```json
{ "ok": false, "tid": "snsTimeLine_wxid_test_zhangsan_1750000001", "error": "moment not found" }
```

- HTTP 状态码：成功 `200`；`tid` 不存在 `404`；token 无效 `401`；后端未实现 `501`（AMR 按 capability 声明判断，不依赖 501 才知道）。

### 4.3 幂等语义

- **已赞再赞 = no-op**，返回 `"ok":true, "liked":true`，不报错、不重复发送点赞动作到微信。
- 后端在执行前先查本地赞记录（`sns.db`）；若已赞，直接返回，不触发 a11y 点击。
- AMR 侧也做本地幂等（读 `liked` 字段跳过），但**最终幂等由后端保证**（网络重试场景）。

### 4.4 取消赞 unlike（可逆撤销·v1.2 纳入）

**修订 v1.2（班迪 2026-07-20 钦定）**：原 v1「不做取消赞」已废。理由：拟人引擎 / AMR 一旦规模化点赞，**误触 / 审后反悔是必然**；没有 unlike 就没有 HITL 撤销退路，违「可逆 = CRUD 并↔拆双向」+「账号资产保护」两条铁律。取消赞不是「反悔正向社交表态」，而是**误动作的对外痕迹回收**——这是 safety 刚需。

**端点**
```
DELETE /api/moments/{tid}/like
Authorization: Bearer <token>
```
- `{tid}` = moment envelope 的 `tid`。请求体可空（`{}`）。
- **响应**：成功 `{ "ok": true, "tid": "...", "liked": false }`；失败 `{ "ok": false, "tid": "...", "error": "UNLIKE_FAILED" | "MOMENT_NOT_FOUND" }`。HTTP 同 §4.2（200 / 404 / 401 / 501）。
- **幂等**：已取消（未赞）再取消 = no-op，返回 `"ok": true, "liked": false`，不报错、不触发 GUI。
- **校验**：撤销后回读 `sns.db.liked`（应转 `false`）；person-scoped 帖若 `sns.db` 不更新，退**视觉 likers 行**（Details 下方 likers 行不再含 self 头像）。
- **GUI 原语**：Details 里 ⋯ → 已赞时首项 toggle 为 Cancel（= `more_button_coords` 同源几何，label 随赞态变）。
- **HITL**：同 §4.5——哑执行端点，撤谁 / 何时由 AMR / 人决定（误触清单人审 → 逐条撤）。

**capabilities**：`"unlike": true`（未实现前 `false`）。

### 4.5 HITL 铁律（再次申明）

后端 `/api/moments/{tid}/like` 是**哑执行端点**：收到调用就赞，不做策略判断。  
策略（赞谁 / 何时赞 / 候选优先级）完全在 AMR 侧：

```
AMR 读 feed → 生成候选列表（谁的哪条 tid）
           → 展示给人批量审核
           → 人一次性批准（选 + 确认）
           → AMR 逐条调 POST /api/moments/{tid}/like
```

**系统永不跳过人的批准直接赞**（不管候选看起来多明显）。

### 4.6 评论动作契约（v1.1·MVP 顶层评论·填 §7 留位）

评论 = 逐条对外互动（同 like 由 `tid` 寻址），比 like 多「内容」维度；比 publish（广播）轻。

**端点**
```
POST /api/moments/{tid}/comment
body: { "text": "评论内容", "idempotency_key": "amr-...(可选)" }
```
- `{tid}` = moment envelope 的 `tid`（URL encode 如含特殊字符）。
- `text`（必填）= 评论正文。
- `idempotency_key`（可选，推荐 AMR 给，进它的 outbox 审计/重试）。
- **MVP 顶层评论 only**：不含 `reply_to`（回复某条评论）—— 扩展位留 v.next。

**响应**：成功 `{ "ok": true }`；失败 `{ "ok": false, "error": "COMMENT_FAILED" }`。HTTP：成功 200、`tid` 不存在 404、token 无效 401、未实现 501（AMR 按 capability 判，不依赖 501）。错误码：`COMMENT_FAILED`（GUI/selector 异常，后端保留可重试）、`MOMENT_NOT_FOUND`。

**幂等**：`idempotency_key` 给了 → 后端按 key 去重（窗口 ~10min，扛重试/poll 周期）；没给 → 后端 `(tid, text)` 短窗 backstop（~12s，对齐消息 send，防双击/网络重投）；失败清去重记录、不挡人为重试。

**HITL 铁律（对外动作·王总钦定）**：后端 `/api/moments/{tid}/comment` 是**哑执行端点**——收到调用就评，不做策略判断（评什么/评谁/何时）。**必须继承 outbox→confirm 人审窗**：AMR/AMP 生成候选评论 → 人批量审 → 通过后才逐条调端点。**系统永不自动评论、不进任何自动闸、不替人补内容**（与 §4.5 点赞、publish §7/8 同款）。**LLM 无关**：内容起草可 LLM assist（消费端），gate 是人。

**capabilities**：后端在 `/api/capabilities.moments` 增 `"comment": true`（未实现前 `false`，AMR 按此降级）。

### 4.7 删评论 delete-comment（可逆撤销·v1.2 纳入）

评论的逆动作（呼应 §1.7 可逆）。删的是**自己发的评论**（微信只允许删自己评论）；误评 / 审后反悔时回收对外痕迹。

**端点**
```
DELETE /api/moments/{tid}/comment
body: { "text": "要删除的评论正文" }
```
- `{tid}` = 该评论所在动态的 `tid`。
- `text`（必填）= 要删除的评论正文——后端在该帖下匹配 self 发的、正文 == `text` 的评论删之。
  - ⚖️ **寻址口径（PD 提案·待 AMR 定）**：用 `text` 精确匹配 self 评论——AMR 的 outbox 记得自己评了什么、天然有 `text`，无需后端另暴露评论读接口 / comment-id。备选 = 删 self 在该帖**最近一条**评论（无 `text` 参数）。PD 倾向 **by-text**（多条评论时可精确定位目标、避免误删）。
- **响应**：成功 `{ "ok": true }`；失败 `{ "ok": false, "error": "COMMENT_DELETE_FAILED" | "COMMENT_NOT_FOUND" | "MOMENT_NOT_FOUND" }`。HTTP 同族（200/404/401/501）。
- **幂等**：目标评论已不存在 = no-op，返回 `"ok": true`（视作已达期望态）。
- **GUI 原语**：Details 里定位 self 的评论 list-item → 右键 / 长按 → Delete（**无二次确认**，真机实测）。
- **HITL**：哑执行端点，删哪条由 AMR / 人决定（误评清单人审 → 逐条撤）。

**capabilities**：`"comment_delete": true`（未实现前 `false`）。

---

## §5 AMR 侧「事」模型——点赞 = 一次交互（AMR 消费语义，fullwechat 不实现）

本节是 AMR 内部模型，**fullwechat 后端无需实现**；记录在此是为了让后端理解 AMR 为何这样设计接口。

### 5.1 点赞 = 「维护某人」事下的一次交互

对齐 AMR 仓设计文档 `2026-06-28-supervised-agentic-router-design.md` §2 的事模型：

- **事（matter）**：per-person 的长期维护关系（`type: "关系维护"`，与落地业务事同级别头等对象）。
- **一次点赞 = 该「维护某人」事下的一条 interaction 记录**（commitment event / 互动轨迹）。
- 归一路径：`moment.author.wxid` → 关系账户（person）→ 该 person 的「维护」matter（无则候选新建、人确认）→ 挂 interaction 记录。

### 5.2 点赞把「广播动态」转成「对某人的定向交互」

朋友圈动态本质是广播（一对多）；AMR 点赞后，它在 Router 里变成：  
**「我 → 张三」的一次互动信号**，喂关系账户染色（加权），推高张三的关系温度。

这是 §1.5（群 = 场）逻辑在社交动态面的对称体现——广播面里的信号被 AMR 转换成一对一关系账户的定向交互记录。

### 5.3 HITL = 批量审一次（不逐条、不全自动）

人的介入形态：  
AMR 按染色/关系温度/上次互动时间排出候选列表（"该点赞的人 × 动态"）→ **人在一个 review 界面批量看、打勾或去掉** → 一次确认 → AMR 执行。  
不逐条弹 confirm（太烦），不全自动（违反 HITL）。

### 5.4 排期归 AMR，不归后端

「今天赞哪几个人」的排期策略（频次 / 时间窗 / 关系档位 / 上次点赞距今）完全在 AMR 内部决定，后端只提供读接口和哑执行接口。

---

## §6 能力声明 + 优雅降级

### 6.1 capabilities 声明

后端在 `/api/capabilities`（已上线，姊妹契约）中增加 `moments` 项：

```json
{
  "schema": "message.canonical/1",
  "channel": "wechat",
  "moments": {
    "read": true,
    "feed_all": false,
    "sync": true,
    "like": true,
    "unlike": true,
    "comment": true,
    "comment_delete": true,
    "publish": { "text": true, "image": false, "link": false, "video": false, "delete": true }
  }
}
```

| 字段 | 含义 |
|---|---|
| `read` | 是否支持 `GET /api/moments?person=<wxid>` |
| `feed_all` | 是否支持 `GET /api/moments`（不带 person 的全 feed）|
| `sync` | 是否支持 `POST /api/moments/sync?person=<wxid>`（§3.4 warm）|
| `like` | 是否支持 `POST /api/moments/{tid}/like` |
| `unlike` | 是否支持 `DELETE /api/moments/{tid}/like`（§4.4 可逆撤销）|
| `comment` | 是否支持 `POST /api/moments/{tid}/comment`（§4.6）|
| `comment_delete` | 是否支持 `DELETE /api/moments/{tid}/comment`（§4.7 可逆撤销）|
| `publish` | 发布能力（**对象**）：子字段 `text`/`image`/`link`/`video`/`delete`，语义见 `publish.md`（§9 能力 + §7.5 delete）。**删自己动态 = `publish.delete`**（`publish.md` §7.5）|

> `unlike` / `comment_delete` / `publish.delete` 未实现前报 `false`，AMR 据此隐藏对应撤销/删除入口（降级非报错）。**契约定义全 CRUD 面，实际可用性由 capabilities 逐项 gate**——不过度声明（同 §4.4/§4.6 旧法）。

若后端尚未实现 moments 任何能力，`"moments"` 项可整体缺失，AMR 按「全部 false」处理。

### 6.2 降级矩阵

| 后端能力 | AMR 行为 |
|---|---|
| `read:false` 或 moments 整体未实现 | AMR 朋友圈面不显示（静默隐藏，非报错）；其他功能不受影响 |
| `read:true, like:false` | AMR 展示动态但不提供点赞动作（人仍可手动去原生微信赞）；`like` 入口灰掉 |
| `read:true, like:true` | 完整功能：读 feed + 批量候选 + 人确认 + 点赞执行 |
| `feed_all:false` | AMR 只支持 per-person 读，不提供全 feed 浏览（功能收敛，非降级） |
| like 端点调用失败（网络/超时） | AMR 标记该 `tid` 失败、保留在待处理队列、人下次可重试；不静默丢弃 |

### 6.3 LLM 无关（再申明）

朋友圈面：读动态 = 纯结构化解析；点赞 = 确定性写动作。**零 LLM**。  
即使所有模型不可用，朋友圈 read + like 正常运行（完美满足 LLM-optional 铁律）。

---

## §7 口径与边界

| 事项 | 口径 |
|---|---|
| `media.ref` 路径 | 复用已上线 `/api/media` 端点族，路径建议 `/api/media/moments/{tid}/{index}`；与消息通道 `/api/media/{chat_id}/{msg_id}` 同族，同一 bearer auth。 |
| `tid` 来源 | `sns.db SnsTimeLine` 的稳定主键或等效稳定字段；具体列名后端确认（AMR 不依赖具体列名，只要求 tid 稳定）。 |
| `direction` 判断 | 后端对照 self wxid 与 `author.wxid` 判定；同一 wxid 设备后缀问题（姊妹契约 §9.8 冲突）同样适用。判不准 → 默认 `"in"`，不阻塞。 |
| `liked` 精度 | 依赖 `sns.db` 本地赞记录同步状态；若后端确认无法可靠读取，声明 `"liked_reliable": false`（扩展字段），AMR 跳过本地幂等、仅依赖端点幂等。 |
| 评论（comments） | **v1.1 纳入写向 `POST /api/moments/{tid}/comment`（顶层评论·见 §4.6）**；`GET /api/moments/{tid}/comments`（读评论）仍 v.next YAGNI；capabilities `"comment":true`。 |
| 多媒体 moment（9 图）| `media` 数组按序列出所有图片（index 0–N），每项各自有 `ref`。AMR v1 只展示第一张缩略 + 总数（UI 细节，不影响本契约）。 |
| 自己的 moment（`direction:"out"`）| AMR 读取展示、不对自己的动态执行点赞动作（前端屏蔽）。`liked` 字段对 `"out"` 动态意义不大，后端可给 `null`。 |

---

## §8 fullwechat 实现侧（参考，不占 AMR 契约决策）

本节是 AMR 对后端实现路径的了解，记录在此帮助后端定向；**AMR 不 own 此节，后端实现方式可自行调整**，只要暴露 §2–§6 定义的接口形态。

| 项 | 实现参考 |
|---|---|
| 动态读取 | 读 `sns.db SnsTimeLine`；`GET /api/moments?person=<wxid>` 后端已有初始实现，加 `person` 过滤 + `liked` 字段 + 信封格式对齐本契约。 |
| 点赞执行 | 走 a11y（朋友圈 WebView，`--force-renderer-accessibility` spike 进行中）。**a11y spike 未完成 → 声明 `like:false`；AMR 读-only 先上，不因点赞阻塞读端上线**。 |
| 媒体 `ref` | 复用已上线 `/api/media` 端点；朋友圈图片/视频的解密 + 取件逻辑与消息通道同族，统一 bearer auth。 |
| `tid` 稳定性 | 建议使用 `SnsTimeLine.id` 或 `SnsTimeLine.FeedId`（后端核实哪个稳定）；不用 `create_time` 做 tid（时间戳不唯一）。 |
| `liked` 查询 | 从 `sns.db` 赞相关表查 self 是否已赞；若表结构不确定，提 AMR 澄清。 |

---

## 协作约定

后端 Agent / 工程师遇到任何不清楚的口径：**提 AMR，AMR 改 spec，后端按新版实现**。  
不要自行解释契约、不要在后端硬编码推断出来的口径——有疑义的地方对 AMR 提问，让 AMR 写进 spec，再实现。这保证 AMR 是唯一真相源，不让后端各自猜、日后行为漂移。

---

*本契约版本：v1.2 / 2026-07-20（可逆 CRUD：§3.4 person-scoped sync + §4.4 取消赞 unlike〔修订原「v1 不做取消赞」〕+ §4.7 删评论 delete-comment + §6 capabilities 全 CRUD gate；删自己动态见 publish.md §7.5。v1.1 / 2026-07-16 = +§4.6 评论；v1 / 2026-06-28 = 读+点赞）。major 改动另开新文件。*
