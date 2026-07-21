# 通讯录实体名册契约 v1（提案）— Contacts / Entity Roster Contract

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`contacts/` → AMR/@gthneo）。
>
> **日期** 2026-07-21 ｜ **状态** **提案·PD 起草待 AMR 审计**（不 merge，交 AMR 仁德对抗审后定稿）
> **from** fullwechat / PowerData-WX 后端（pw仁德，起草 + 提事实）｜ **to** AgenticMessageRouter（AMR 仁德，定义方·审计/merge）
> **姊妹契约** `../message/canonical.md`（会话消息）· `../moments/read-like.md`（朋友圈）· `../group-metadata/*`（群元数据）
> **适用范围** 微信通讯录里的**实体名册**：读（roster + 计数）+ 连接（connect·打桩）。**不覆盖**会话消息 / 朋友圈 / 群内消息（各有姊妹契约）。

---

## §0 这份契约是什么 / 不是什么 · 起草背景

**背景（PD 实证事实）**：微信把私聊/群聊/朋友圈/公众号/视频号/联系人全锁进一个超级 App。本软件对每个「信息面 surface」做归一,统一暴露 canonical。**联系人此前无正式契约**,AMR 直接 ad-hoc 调 `/api/contacts`。2026-07-21 一次通讯录缺口排查(微信 7368 好友 vs 后端翻页只吐 3799)暴露:后端有分页 bug(已修,见 §9)+ 后端其实持有 46,235 个联系人行(远超好友数,含非好友)。王总由此钦定:**把微信生态里每个「账号/实体」都归一、可进出,做成契约能力,可复制到其他生态**。本契约即通讯录实体面的归一。

**本契约是**:通讯录**实体 canonical**(§2)+ 读名册/计数(§3)+ 连接/触达打桩(§4)+ 视频号占位(§5)+ 账号类别 taxonomy(§6)+ 实体唯一 ID/OpenID 概念(§7)。
**本契约不是**:会话消息 / 朋友圈动作 / 群名册成员(走 `group-metadata`)/ 关系评分·去重·CRM 映射(= **AMR 消费端领域**,本契约不规定)。

**设计总纲(王总 2026-07-21 钦定 · additive)**:一次把**实体模型立对**,但**字段是现有 `/api/contacts` 的加法式超集** —— 老字段全保留、语义不变,新字段一律 opt-in。**目标 = 大模型的长期好处 + 小消费端的迁移成本;AMR 现有消费一行不改就继续跑,新能力按需 opt-in,不需要重构其 persons 关系图。**

**真相源 + 边界**:AMR = 定义方(审计/merge/定 shape);PD = 实现方(提事实/实现/契约提取)。后端有疑义 → 提 AMR,AMR 改本 spec → 后端按新版实现,不自行解释契约。

---

## §1 设计原则

1. **加法式超集(additive)**。本契约响应 = 现有 `/api/contacts` 字段的**超集**:§2「老字段」逐字保留、语义不变;§2「新字段」全部 opt-in(消费方不读也不丢现有可用性)。**改动面一眼可见**(§2 表逐字段标【保留】/【➕新增】)。
2. **实体 = 一等公民**。通讯录里每一行是一个**微信实体**(个人/公众号/企微号/群聊号/系统/视频号),不只是「联系人」。实体有稳定唯一 ID(§7)、类别(§6)、可选来源(§8 provenance)、可选能力(§4 connect)。
3. **ID 即 OpenID**。实体的 `id`(= 微信 `username`)本身就是稳定的 per-entity 唯一标识;`@`/`gh_` 前后缀即其命名空间/类型(§7)。不新造 ID 体系。
4. **进 + 出**。实体面既能**读**(D1 入站:roster + 计数)也能**连接**(D2 出站:对未加陌生人触达/加好友,§4 打桩)。呼应 inbox/outbox「进出」哲学 —— 实体也能进能出。
5. **归一 vs 领域分层**。后端只做「把实体归一成 typed canonical」(定 id/type/来源);**关系评分、去重、CRM 映射、触达谁 = AMR 消费端领域**,本契约不碰。
6. **HITL + 哑执行(写动作铁律)**。connect/触达是对外写动作 → **AMR 永不自动加人**;人批量审后 AMR 才逐条调;后端哑执行,拟人节奏 + 幂等(复用 outbox 引擎)。
7. **能力逐项 gate·不过度声明**。read 现成;connect / counts / 视频号 / friend 细分等未实现前 capabilities 报 `false`,AMR 静默降级(§8)。**契约可定义全实体面,可用性由 capabilities 逐项 gate**。

---

## §2 实体 Canonical（加法式超集 · 老字段【保留】/ 新字段【➕新增·opt-in】）

后端对每个通讯录实体 emit 一个信封。合成占位值(无真实 PII):

```json
{
  "id": "wxid_test_zhangsan",
  "id_scheme": "wxid",
  "contactType": "individual",
  "entity_kind": "individual",
  "friend": true,
  "nickName": "张三",
  "remark": "张三-悠爱金属",
  "alias": "zhangsan_wx",
  "description": "备忘:镍钛材料供应",
  "phone": "13800000000",
  "small_head_url": "https://.../head/abc.jpg",
  "source": { "seen_in": ["contacts"] },
  "capabilities": { "connect": false },
  "direction": "in"
}
```

### 2.1 字段表

| 字段 | 状态 | 类型 | 说明 |
|---|---|---|---|
| `id` | 【保留·= 原 `username`】 | str | 实体稳定唯一 ID = 微信 `username`。**建议以 `id` 为规范名,`username` 作 alias 保留一段(见 §7)**。若 AMR 要求保留 `username` 名不动,PD 照办(additive)。 |
| `username` | 【保留】 | str | 现有字段,= `id`。为不破坏 AMR 现有消费**继续同时输出**(§7 迁移期双写)。 |
| `contactType` | 【保留·扩值】 | str | 现有枚举 `individual`/`official`/`openim`/`chatroom`。**新增值**:`system`(§6,原被丢的系统账号现暴露)。老值语义不变;AMR 对未知值按「其它」处理即可。 |
| `nickName` | 【保留】 | str | 昵称。 |
| `remark` | 【保留】 | str\|null | 备注名。 |
| `alias` | 【保留】 | str\|null | 微信号。 |
| `description` | 【保留】 | str\|null | 备忘。 |
| `phone` | 【保留】 | str\|null | 备注电话(`extra_buffer` field14 解出)。 |
| `small_head_url` | 【保留】 | str\|null | 头像 URL。 |
| `id_scheme` | 【➕新增·opt-in】 | str | 实体 ID 的命名空间/类型:`wxid`(系统分配个人)/`custom_id`(自定义微信号个人)/`gh`(公众号)/`openim`(企微号)/`chatroom`(群聊号)/`finder`(视频号)。**从 `id` 的前后缀确定性派生**,给消费方一个无需自己解析后缀的类型钥匙。 |
| `entity_kind` | 【➕新增·opt-in】 | str | 规范实体类别枚举(§6):`individual`/`official`/`wecom`/`chatroom`/`system`/`channel`。**这是 canonical 干净命名**(`contactType` 是遗留字段,二者并存;`wecom`=企微号避「企业号」歧义)。消费方新逻辑建议读 `entity_kind`。 |
| `friend` | 【➕新增·opt-in】 | bool\|null | **是否好友**(仅 `individual` 有意义)。`true`=好友、`false`=非好友(群里见过的陌生人等)、`null`=未知(friend-flag 待 PD 验证,见 §9)。**这是 7368 好友 vs 46,235 全量的区分键**。 |
| `source` | 【➕新增·opt-in·stub】 | obj | 来源/provenance:此实体从哪见到。`{ "seen_in": ["contacts" \| "<群聊号 id>" ...] }`。**群陌生人**用它标「从哪个群捕获」(§4/§9,机制待验证,先打桩)。 |
| `capabilities` | 【➕新增·opt-in·stub】 | obj | 此实体的可写能力开关:`{ "connect": bool }`(能否对其发起连接/触达,§4)。未实现前恒 `false`。 |
| `direction` | 【➕新增·opt-in】 | `"in"` | 与姊妹契约对齐(联系人恒 `in`;保留以备未来)。 |

### 2.2 口径
- **加法式保证**:AMR 现有代码只读【保留】字段 → 行为不变。【➕新增】字段一律可缺省/可忽略。
- **`friend` 与计数(§3.2)**:`friend:true` 的个人数应 ≈ 微信「X 个朋友」(该号 7368);`friend:false/null` = 非好友(~38k,群成员/陌生人)。**friend-flag 的底层判定 PD 待验证**(疑 `local_type 3=好友 vs 1=非好友`,§9),验证前 `friend` 可先恒 `null` + capabilities `friend_flag:false`。

---

## §3 读接口

### 3.1 名册读（roster）
```
GET /api/contacts?limit=<N>&offset=<M>
GET /api/contacts/find?q=<term>&limit=<N>&offset=<M>
Authorization: Bearer <token>
```
- 返回实体 canonical(§2)数组。`find` 的 `q` 全字段模糊(remark/nickname/description/alias/phone/id)。
- **分页**:`limit/offset`,翻到**空页(0 条)** 为止 = 正确收尾。**⚠️ 消费方勿以「页 < limit」判末页**(2026-07-21 修复前,某页因后置过滤短一行会误判到底,见 §9)。修复后每页满 `limit`(末页除外)。
- 排序确定性(稳定分页,§9)。
- `contactType` 现值 = 老枚举(+新增 `system`);`entity_kind`/`friend`/`id_scheme` 等 opt-in 字段随 capabilities 上线。

### 3.2 计数（inventory / counts）【新能力·opt-in】
```
GET /api/inventory
Authorization: Bearer <token>
```
返回**准确、实时**的清单计数(每项须与微信自身 UI 数字吻合):
```json
{
  "as_of": 1784600000000,
  "contacts_total": 46235,
  "friends": 7368,
  "individuals": 45702,
  "official_accounts": 453,
  "wecom": 80,
  "system": 16,
  "groups": null,
  "channels_subscribed": null
}
```
- **准确性铁律(王总)**:`friends` 须等于微信「X 个朋友」;每项须写死数哪些 `entity_kind`/local_type。`groups`(群聊号)走 group-metadata 侧;`channels_subscribed`(视频号订阅)= 视频号面,未通(§5)故 `null`。
- capabilities `inventory:true`(未实现前 `false` / 项为 `null`)。

---

## §4 连接 / 触达（connect）—— 打桩·后面几轮实现

**动机(王总 2026-07-21)**:通讯录里有大量**非好友**(群里见过、没加的陌生人,§2 `friend:false`)。消费端应能**定向对这些实体发起连接/触达**(加好友 / 首次问候),这是关系拓展/拟人经营的入口 —— 实体面的「出站」。

```
POST /api/contacts/{id}/connect       # 打桩·capabilities.connect_supported=false 前 501/降级
Authorization: Bearer <token>
{ "channel": "add_friend" | "message_first", "note": "<验证语/开场白>", "idempotency_key": "<...>" }
```
- **哑执行 + HITL(铁律)**:对外写动作。**AMR 永不自动加人/触达**;人批量审「连谁、说什么」后,AMR 才逐条调;后端哑执行,拟人节奏 + 幂等(复用 outbox 引擎)+ 可逆退路(撤回请求/删会话,细节待定)。
- **capabilities**:`connect_supported:false`(**打桩,未实现**)。响应形态/错误码/风控约束**待 AMR 定口径 + PD 实证后补**(加好友触发微信风控最敏感,§9 风险)。
- **谁触达谁 = AMR 领域**(关系评分/时机/配额);后端只提供哑执行端点。

---

## §5 视频号（Channels）占位 —— 第 6 类实体·深读排后

- 视频号 = 微信独立子系统(短视频/直播)。**实体 ID = `finder` 命名空间**(`v2_...@finder` finder 账号 + 用户可见短「视频号ID」;作品 = feedId)。个人/自己均可有视频号 + 订阅他人视频号。
- **⚠️ PD 实证(2026-07-21 .28)**:**视频号数据不在后端可读的 SQLCipher DB 里**(`db_storage` 12 库无 finder 库;finder worker 目录空、按需从服务器拉)。它是 **XWeb/RadiumWMPF 渲染**的子系统(同朋友圈),而 XWeb 的 a11y/CDP introspection 被 Tencent 编译期封(见后端仓 `docs/design/webview-a11y-structural-research-2026-07-20.md`)→ **后端当前够不着视频号数据**(读它 = 驱 XWeb WebView〔被封〕或 finder 协议〔重〕= 所有 surface 里最难)。
- **契约态度**:视频号 = `entity_kind:"channel"` **仅占位**(声明存在)。**capabilities `channels:false`**;订阅名册/feed **深读排后**(对应后端 backlog B7「视频号 T1 取件·较难」)。契约里**不许诺「支持」**,不误导消费方。

---

## §6 微信账号/实体类别 taxonomy（暴露给消费者·王总 2026-07-21）

| `entity_kind` | 中文 | `id` 模式 / `id_scheme` | 说明 |
|---|---|---|---|
| `individual` | 个人号 | `wxid_*`(wxid)/ 自定义号(custom_id) | 真人。再分 `friend:true`(好友)/`false`(非好友:群陌生人等) |
| `official` | 公众号 | `gh_*`(gh) | 订阅号 + 服务号(现未细分) |
| `wecom` | **企业微信号(企微号)** | `数字@openim`(openim) | WeCom 用户作外部联系人。**术语:全称「企业微信号」/简写「企微号」,禁用「企业号」(歧义)** |
| `chatroom` | **群聊号** | `*@chatroom`(chatroom) | 群。名册/成员走 group-metadata;`/api/contacts` 排除。**术语:一律「群聊号」加「号」字** |
| `system` | 系统账号 | 固定 16 个 | 微信内置服务号(非真人):weixin=微信团队 / filehelper=文件传输助手 / fmessage=新的朋友 / floatbottle=漂流瓶 / medianote=语音记事本 / newsapp=腾讯新闻 / qqmail=QQ邮箱提醒 / weixingongzhong=公众平台助手 / mphelper=公众平台安全助手 / qqsafe=QQ安全中心 / exmail_tool=腾讯企业邮箱 / notifymessage=服务通知 / qmessage=QQ消息 / tmessage·lbsapp·pc_qq(3 个存疑)。**原被后端丢弃 → 现暴露(标 `system`),让消费端自行处理** |
| `channel` | 视频号 | `*@finder`(finder) | §5 占位·深读排后 |

---

## §7 实体唯一 ID / OpenID 概念（王总 2026-07-21·打桩引入）

- **微信每个实体已有稳定唯一 ID = `username`**:个人=wxid/自定义号、群聊号=`@chatroom`、公众号=`gh_`、企微号=`@openim`、视频号=`@finder`。**后端 `username`/`id` 就是这个 per-entity 「OpenID」**,前后缀即 `id_scheme`(类型命名空间)。
- **本契约引入 `id`(规范名)+ `id_scheme`,把「username 即实体唯一 ID」在契约里点明**;迁移期 `id` 与 `username` **双写**(additive,AMR 不用改)。
- **跨上下文归一同一人**(同一人在不同群/不同渠道被看见 → 归到一个 canonical 实体)= 更大的**身份图**,属 **AMR 消费端领域**(呼应 AMR 身份图);本契约只保证 per-实体 ID 稳定,不做跨上下文合并。**架构改动大 → 先打桩引入概念,后面几轮实现**。

---

## §8 能力声明（capabilities）

`GET /api/capabilities` 增 `contacts` 项(未实现的报 `false`,AMR 逐项降级):
```json
{
  "contacts": {
    "read": true,
    "find": true,
    "inventory": false,
    "friend_flag": false,
    "entity_kind": false,
    "source_provenance": false,
    "connect_supported": false,
    "channels": false
  }
}
```
| 字段 | 含义 |
|---|---|
| `read`/`find` | §3.1 名册读(已上线) |
| `inventory` | §3.2 计数 |
| `friend_flag` | §2 `friend` 好友细分(待 friend-flag 验证) |
| `entity_kind` | §2/§6 规范实体枚举 + `id_scheme` opt-in 字段 |
| `source_provenance` | §2 `source`(群陌生人来源) |
| `connect_supported` | §4 连接/触达(打桩) |
| `channels` | §5 视频号深读(排后) |

---

## §9 fullwechat 实现侧（PD 提事实·参考·AMR 不 own 此节）

| 项 | 实现参考 / PD 实证 |
|---|---|
| 名册读 | 读 `contact.db contact` 表 `WHERE local_type IN (1,3,5) AND NOT @chatroom`;分页 `LIMIT/OFFSET`。 |
| **分页 bug 已修(2026-07-21)** | 原 `row_to_contact` 在 `LIMIT` **之后**丢系统账号 → 含系统账号的页返回 `limit-1`,消费方短页早停(该号翻页只到 3799/46235)。修:系统账号排除挪进 SQL WHERE(过滤在 LIMIT 前→每页满)+ ORDER BY 加 `id` 唯一 tiebreak。已部署 `.28`,翻页达全量 46235。**改暴露 system 后**:不再 SQL 排除,改 `row_to_contact` 标 `entity_kind:"system"` 不丢(仍保每页满)。 |
| **friend-flag(待验证)** | 后端 45,702 个人 >> 微信 7368 好友 → 含 ~38k 非好友。好友/非好友区分键**待 PD 下轮实证**(疑 `local_type 3=好友 vs 1=非好友`,或另有 verify/friend flag);验证前 `friend` 恒 `null`。 |
| **群陌生人捕获(待验证)** | 群成员 roster 在 `chat_room.ext_buffer` roomdata(非 contact 表);交互过的群成员**是否**落 contact 表成非好友行、以何身份 —— **机制待 PD 下轮实证**,`source.seen_in` 先打桩。 |
| **视频号(够不着)** | §5:XWeb 子系统,不在可读 DB,XWeb introspection 被封 → 深读排后(B7)。 |
| counts | 由 `entity_kind`/local_type 分类精确计数;`friends` 须对齐微信 UI(依赖 friend-flag)。 |
| connect/触达 | 复用 outbox 引擎哑执行 + 拟人节奏;加好友触发微信风控最敏感 → 实现前需 PD 风控实证 + 强 HITL(§4)。 |

---

## §10 待 AMR 仁德拍口径（审计要点·有歧义提出别猜）

1. **`id` vs `username`**:规范名用 `id` 还是保留 `username`?(PD 建议双写迁移,你定终态)
2. **`contactType` 扩值 vs `entity_kind` 新字段**:是给 `contactType` 加 `system`/`channel` 值,还是让消费方改读新的 `entity_kind`?(二者并存的加法式,或你定收敛)
3. **`friend` 语义**:`friend` 三态(true/false/null)口径你认可?是否要 `friend:true` 的计数硬等于微信「X 个朋友」?
4. **connect/触达契约**:§4 打桩的端点形态/错误码/可逆退路/风控口径 —— 你定义,PD 实证补。加好友风险最高,是否本版只声明 capability=false 占位、语义 v.next?
5. **视频号**:§5 占位(capability=false)你认可?深读排后?
6. **计数归属**:`groups` 计数归 group-metadata 还是本契约?`channels_subscribed` 视频号未通先 `null`?

— pw仁德(PD)起草 2026-07-21 · 交 AMR 仁德对抗审后定稿
