# 通讯录实体名册契约 v1（提案）— Contacts / Entity Roster Contract

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`contacts/` → AMR/@gthneo）。
>
> **日期** 2026-07-21 ｜ **状态** **AMR 对抗审定稿**（read/计数/taxonomy/OpenID 桩定稿；§4 connect 收为占位桩、`connect_supported` 翻真前须再走治理铁律 #5 独立审。§10 六口径已拍 + 独立宪法审并入）
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
6. **HITL + 哑执行(写动作铁律)**。connect/触达是对外写动作 → **AMR 永不自动加人**;AMR **提议候选(评分/时机仅供参考)→ 人逐个 ✓/✕ 决定连谁、说什么 →** AMR 才逐条调;后端哑执行 + 幂等(复用 outbox 引擎)。节奏来自**逐条人审的自然间隔 + 尊重对方(非骚扰)**,**不是绕平台风控的伪装**。connect 翻真的四条不可协商前置见 §4。
7. **能力逐项 gate·不过度声明**。read 现成;connect / counts / 视频号 / friend 细分等未实现前 capabilities 报 `false`,AMR 静默降级(§8)。**契约可定义全实体面,可用性由 capabilities 逐项 gate**。

---

## §2 实体 Canonical（加法式超集 · 老字段【保留】/ 新字段【➕新增·opt-in】）

后端对每个通讯录实体 emit 一个信封。合成占位值(无真实 PII):

```json
{
  "schema": "contact.entity/1",
  "id": "wxid_test_zhangsan",
  "idScheme": "wxid",
  "contactType": "individual",
  "entityKind": "individual",
  "isFriend": true,
  "nickName": "张三",
  "remark": "张三-悠爱金属",
  "alias": "zhangsan_wx",
  "description": "备忘:镍钛材料供应",
  "phone": "13800000000",
  "smallHeadUrl": "https://.../head/abc.jpg",
  "source": { "seenIn": ["contacts"] },
  "capabilities": { "connect": false },
  "direction": "in"
}
```

> **序列化约定(AMR仁德 定稿口径⑦·2026-07-21)= 实体信封字段一律 camelCase**(随现网 `/api/contacts` 既有约定:`nickName`/`smallHeadUrl`/`contactType`)。新字段 = `idScheme`/`entityKind`/`isFriend`/`schema`/`source.seenIn`/`direction`/`capabilities`;好友字段钉 **`isFriend`**(三态 true/false/null,与 PD仁德 现网出线一致,零改)。`/api/capabilities` 的能力键仍 snake_case(随姊妹契约 moments `comment_delete` 惯例,是另一对象另一约定)。`idScheme` 的**取值**(`custom_id` 等)是枚举值非字段名,不受此约束。**本文其余处若见 snake_case 字段名(`id_scheme`/`entity_kind` 等)= 口径⑦ 前的概念指代,一律以本 §2 camelCase 为准**(§11 PD仁德 复审记录保留原文不改)。

### 2.1 字段表

| 字段 | 状态 | 类型 | 说明 |
|---|---|---|---|
| `schema` | 【➕新增·opt-in】 | str | 实体信封契约版本标识,v1 固定 `"contact.entity/1"`(与姊妹契约 `moment.canonical/1` 同族,利日后演进)。 |
| `id` | 【保留·= 原 `username`】 | str | 实体稳定唯一 ID = 微信 `username`。**AMR 定稿(口径①):`id` 为规范名 + `username` 永久保留为 alias 双写**(非「保留一段」——删 `username` 即 breaking、与总纲『一行不改』冲突,故**永久**双写,零强制迁移)。 |
| `username` | 【保留·永久】 | str | 现有字段,= `id`。**永久同时输出**(口径①双写),AMR 现有消费一行不改。 |
| `contactType` | 【保留·**冻结**】 | str | 现有枚举 `individual`/`official`/`openim`/`chatroom`,**冻结不扩值**(AMR 定稿口径②:`system`/`channel` 只进 `entity_kind`,不加进 `contactType`——给 switch on `contactType` 的老消费方塞未知值非纯 additive)。老值语义不变。 |
| `nickName` | 【保留】 | str | 昵称。 |
| `remark` | 【保留】 | str\|null | 备注名。 |
| `alias` | 【保留】 | str\|null | 微信号。 |
| `description` | 【保留】 | str\|null | 备忘。 |
| `phone` | 【保留】 | str\|null | 备注电话(`extra_buffer` field14 解出)。 |
| `smallHeadUrl` | 【保留·camelCase】 | str\|null | 头像 URL(现网既有 camelCase 名,口径⑦)。 |
| `idScheme` | 【➕新增·opt-in】 | str | 实体 ID 的命名空间/类型(**取值**):`wxid`(系统分配个人)/`custom_id`(自定义微信号个人)/`gh`(公众号)/`openim`(企微号)/`chatroom`(群聊号)/`finder`(视频号)。**从 `id` 的前后缀确定性派生**,给消费方一个无需自己解析后缀的类型钥匙。 |
| `entityKind` | 【➕新增·opt-in】 | str | 规范实体类别枚举(§6):`individual`/`official`/`wecom`/`chatroom`/`system`/`channel`。**这是 canonical 干净命名**(`contactType` 是遗留字段,二者并存;`wecom`=企微号避「企业号」歧义)。消费方新逻辑建议读 `entityKind`。 |
| `isFriend` | 【➕新增·opt-in】 | bool\|null | **是否好友**(仅 `individual` 有意义)。`true`=好友、`false`=非好友(群里见过的陌生人等)、`null`=friend-flag delta 未归零前恒值(PD仁德 已实证判定键 `localType==1`,见 §9)。**这是 7,368 好友 vs 46,235 全量的区分键**。名钉 `isFriend`(camelCase,口径⑦)。 |
| `source` | 【➕新增·opt-in·stub】 | obj | 来源/provenance:此实体从哪见到。`{ "seen_in": ["contacts" \| "<群聊号 id>" ...] }`。**群陌生人**用它标「从哪个群捕获」(§4/§9,机制待验证,先打桩)。 |
| `capabilities` | 【➕新增·opt-in·stub】 | obj | 此实体的可写能力开关:`{ "connect": bool }`(能否对其发起连接/触达,§4)。未实现前恒 `false`。 |
| `direction` | 【➕新增·opt-in】 | `"in"` | 与姊妹契约对齐(联系人恒 `in`;保留以备未来)。 |

### 2.2 口径
- **加法式保证**:AMR 现有代码只读【保留】字段 → 行为不变。【➕新增】字段一律可缺省/可忽略。
- **system 账号默认排除(AMR 定稿口径②·守 additive 的关键)**:`entity_kind:system` 的 16 个内置账号(微信团队/文件传输助手等)**默认不进 `/api/contacts` 结果集** —— 保老消费**行集不变**(AMR `fetch_contacts` 只跳 `gh_`、不会把系统账号当人),仅 **opt-in**(`?include=system`,或随 `entity_kind` capability 一起)时才返回;inventory 照计(§3.2 `system:16`)。**system『暴露』= 可查/可计,不等于默认入名册**。
- **`isFriend` 与计数(口径③)**:`isFriend:true`=好友、`false`=非好友(~38k 群成员/陌生人)、`null`=friend delta 未归零前恒值。**准确性铁律:`inventory.friends` 要么精确 = 微信「X 个朋友」(7,368),要么 `null` —— 绝不给近似数**。**friend-flag 判定键 PD仁德 已实证(2026-07-21)= `localType == 1 && entityKind == individual`** —— 原猜「3=好友」**证伪**,方向相反(详见 §9)。⚠️ 实现计得 **7,404** vs 微信 UI **7,368**(**delta +36**,成因见 §9)→ **按本口径「拒近似」,`inventory.friends` 在 delta 归零前恒 `null`、`friend_flag` 保持 `false`**;per-contact `isFriend` 字段照常给真值(三态语义已定,消费侧自行收敛)。

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
- `contactType` 现值 = 老枚举(4 值·冻结,口径②);`entityKind`/`isFriend`/`idScheme` 等 opt-in 字段(camelCase·口径⑦)随 capabilities 上线。**system 账号默认不在结果集**(口径②,`?include=system` opt-in 才返回)。

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
- **准确性铁律(王总)**:`friends` 须**精确**等于微信「X 个朋友」,做不到则报 `null`(不给近似);每项须写死数哪些 `entity_kind`/local_type。
- **计数归属(AMR 定稿口径⑥)**:inventory 只 own **实体计数**(individuals/friends/official/wecom/system);`groups`(群聊号)恒 `null` —— 权威在 `group-metadata`;`channels_subscribed`(视频号)恒 `null` —— 视频号面未通(§5)。**单一真相源**,避免群数被两处各计致漂移。
- **计数↔名册一致性不变式**:inventory 各计数须与 `/api/contacts` **同一分类谓词** —— 如 `contacts_total`(46235)== 默认名册可翻页总行数(**不含 system**,口径②)= individuals(45702)+official(453)+wecom(80);`system`(16)单列;`friends`(7368)⊂ individuals。否则 count≠名册长度 = 漂移。
- capabilities `inventory:true`(未实现前 `false` / 项为 `null`)。

---

## §4 连接 / 触达（connect）—— 精简保留桩·capability=false·翻真前须再走独立审

**动机(王总 2026-07-21)**:通讯录里有大量**非好友**(群里见过、没加的陌生人,§2 `friend:false`)。消费端应能**定向对这些实体发起连接/触达**(加好友 / 首次问候),做关系拓展 —— 实体面的「出站」。

**本版态度(AMR 定稿口径④)= 只声明能力占位,不铺详细语义**。connect 是所有出站里**风险最高**的:对**陌生人**主动触达 = 微信风控最敏感 + **积德红线**(0 号宪法第 4 条:群刷陌生人 = 骚扰/操纵/耗德)。故本版只保留占位端点,**完整语义(端点体/错误码/风控/可逆)= 专门 v.next**,待 PD 风控实证 + AMR 一份 HITL+积德 设计后再定。

```
POST /api/contacts/{id}/connect       # 占位·capabilities.connect_supported=false 前一律 501/降级
```

**⚖️ `connect_supported` 翻真的四条不可协商前置**(写进契约·非「v.next 再议」·独立宪法审 2026-07-21 要求)——**不得从 `false` 翻 `true`,直到四条全部落地**:

1. **逐个人审 + 每条理由**:每个触达目标**独立 ✓/✕**,且每条附「为何加这个人」的理由。**禁一键批量放行**(对陌生人「一键批 500」= 积德所禁的橡皮图章式群发;「批量审」= 逐个过目、非一键盖章)。
2. **硬限速 / 日配额上限**:**后端服务端内建**速率/配额硬顶(纵深防御,不 100% 依赖消费端自律),AMR 侧再叠一层。
3. **可逆 = 一等能力**(非「细节待定」):撤回请求 / 删会话,与正向 connect **同版交付**。
4. **禁模板群发**:不对多目标发同一话术。

**其余口径**:
- **谁触达谁 = 人决定**:AMR **提议候选**(评分/时机仅供参考、排序供人看)→ **人决定连谁、说什么** → AMR 才逐条哑执行调端点。后端只提供哑执行端点 + 上述服务端限速,**不决定加谁**。
- **节奏**:来自**逐条人审的自然间隔 + 尊重对方(非骚扰)**,**不是绕平台风控的伪装**。
- **capabilities**:`connect_supported:false`(**占位,未实现**)。
- **翻真那次 PR 须再走治理铁律 #5 独立宪法审**(对陌生人触达是宪法最敏感面)。

---

## §5 视频号（Channels）占位 —— 第 6 类实体·深读排后

- 视频号 = 微信独立子系统(短视频/直播)。**实体 ID = `finder` 命名空间**(`v2_...@finder` finder 账号 + 用户可见短「视频号ID」;作品 = feedId)。个人/自己均可有视频号 + 订阅他人视频号。
- **⚠️ PD 实证(2026-07-21 .28)**:**视频号数据不在后端可读的 SQLCipher DB 里**(`db_storage` 12 库无 finder 库;finder worker 目录空、按需从服务器拉)。它是 **XWeb/RadiumWMPF 渲染**的子系统(同朋友圈),而 XWeb 的 a11y/CDP introspection 被 Tencent 编译期封(见后端仓 `docs/design/webview-a11y-structural-research-2026-07-20.md`)→ **后端当前够不着视频号数据**(读它 = 驱 XWeb WebView〔被封〕或 finder 协议〔重〕= 所有 surface 里最难)。
- **契约态度**:视频号 = `entity_kind:"channel"` **仅占位**(声明存在)。**capabilities `channels:false`**;订阅名册/feed **深读排后**(对应后端 backlog B7「视频号 T1 取件·较难」)。契约里**不许诺「支持」**,不误导消费方。

---

## §6 微信账号/实体类别 taxonomy（暴露给消费者·王总 2026-07-21）

| `entityKind` | 中文 | `id` 模式 / `idScheme` | 说明 |
|---|---|---|---|
| `individual` | 个人号 | `wxid_*`(wxid)/ 自定义号(custom_id) | 真人。再分 `isFriend:true`(好友·`localType==1`)/`false`(非好友:群陌生人等·`localType==3`) |
| `official` | 公众号 | `gh_*`(gh) | 订阅号 + 服务号(现未细分) |
| `wecom` | **企业微信号(企微号)** | `数字@openim`(openim) | WeCom 用户作外部联系人。**术语:全称「企业微信号」/简写「企微号」,禁用「企业号」(歧义)** |
| `chatroom` | **群聊号** | `*@chatroom`(chatroom) | 群。名册/成员走 group-metadata;`/api/contacts` 排除。**术语:一律「群聊号」加「号」字** |
| `system` | 系统账号 | **≥16(PD仁德 实证列表不完整·待补全)** | 微信内置服务号(非真人)。**⚠️ PD仁德 2026-07-21 实证:现有 16 项 `SYSTEM_USERNAMES` 不全(如 `qqsync`=QQ同步助手 / `weibo`=微博 等服务号漏列 → 被误归 individual 计入好友),是 friends 计数 delta +36 的成因之一 → PD仁德 待补全该列表**。已知 16 项:weixin=微信团队 / filehelper=文件传输助手 / fmessage=新的朋友 / floatbottle=漂流瓶 / medianote=语音记事本 / newsapp=腾讯新闻 / qqmail=QQ邮箱提醒 / weixingongzhong=公众平台助手 / mphelper=公众平台安全助手 / qqsafe=QQ安全中心 / exmail_tool=腾讯企业邮箱 / notifymessage=服务通知 / qmessage=QQ消息 / tmessage·lbsapp·pc_qq(3 个存疑)。**原被后端丢弃 → 现可暴露(标 `entity_kind:system`),但默认排除出名册、`?include=system` opt-in 才返回 + inventory 照计(口径②)** |
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
| `friend_flag` | §2 `isFriend` 好友细分。**判定键已实证(`localType==1 && entityKind==individual`,§9)**;但 `true` 的前置 = **friends 计数 delta 归零**(现 7,404 vs UI 7,368 差 +36),故暂 `false` |
| `entity_kind` | §2/§6 规范实体枚举 + `id_scheme` opt-in 字段 |
| `source_provenance` | §2 `source`(群陌生人来源) |
| `connect_supported` | §4 连接/触达(打桩) |
| `channels` | §5 视频号深读(排后) |

---

## §9 fullwechat 实现侧（PD 提事实·参考·AMR 不 own 此节）

| 项 | 实现参考 / PD 实证 |
|---|---|
| 名册读 | 读 `contact.db contact` 表 `WHERE local_type IN (1,3,5) AND NOT @chatroom`;分页 `LIMIT/OFFSET`。 |
| **分页 bug 已修(2026-07-21)** | 原 `row_to_contact` 在 `LIMIT` **之后**丢系统账号 → 含系统账号的页返回 `limit-1`,消费方短页早停(该号翻页只到 3799/46235)。修:系统账号排除挪进 SQL WHERE(过滤在 LIMIT 前→每页满)+ ORDER BY 加 `id` 唯一 tiebreak。已部署 `.28`,翻页达全量 46235。**system 账号(口径②·默认排除)**:默认仍从结果集排除(保每页满 + 老消费行集不变);仅 opt-in(`?include=system`)时以 `entity_kind:"system"` 返回,inventory 照计 `system:16`。 |
| **friend-flag ✅ 已实证(2026-07-21·原猜测证伪)** | **键 = `local_type`,方向与原猜相反:`1` 标好友、`3` 标非好友**(原文「疑 3=好友」**已证伪**)。真机标定(`.28` 仁兄号 46,235 行):`local_type=1` → **7,404 individual** + 453 公众号 · `local_type=3` → **38,298 individual**(非好友:群成员/陌生人/临时会话)· `local_type=5` → 80 企微号。判定规则 = **`local_type == 1 && entity_kind == individual`**(公众号也在 `1` 但属订阅非好友;企微号/群聊号永不为友)。已实现 + TDD 单测 + 部署 `.28`。 |
| **⚠️ friends 计数暂不精确 → 按口径③ `inventory.friends` 恒 `null`** | 实现后 `friend:true` 计 **7,404**,微信 UI 报 **7,368**,**delta +36**(尚未归零)。已查明部分成因:① **`qqsync`(QQ同步助手)/`weibo`(微博)等服务号不在现有 16 项 `SYSTEM_USERNAMES` 列表** → 被归 individual 计入好友(**该列表不完整,PD 待补全**);② ~10 行**无昵称无备注的 `wxid_` 残留**(疑注销/停用号仍留 `local_type=1`);③ 余量或因 UI 数取自 7-20 截图、与今日实际有增删(需同时刻复核)。**故 `inventory.friends` 在 delta 归零前恒 `null`(拒近似,守口径③)**;per-contact `friend` 字段照常提供,消费侧自行收敛。 |
| **✅ 序列化约定已钉(AMR仁德 口径⑦·2026-07-21)= camelCase** | 后端 `Contact` 带 `#[serde(rename_all = "camelCase")]` → 出线 camelCase(`nickName`/`smallHeadUrl`/`contactType`/`localType`/`isFriend`)。**AMR仁德 采纳 (a):实体信封新字段随现网 camelCase**(`idScheme`/`entityKind`/`isFriend`/`source.seenIn`),**PD仁德 零改**;§2 示例/表已改齐。好友字段钉 **`isFriend`**(非 `friend`/`is_friend`),与 PD仁德 现网出线一致。`/api/capabilities` 能力键仍 snake_case(另一对象·随姊妹契约 moments `comment_delete` 惯例)。 |
| **群陌生人捕获(待验证)** | 群成员 roster 在 `chat_room.ext_buffer` roomdata(非 contact 表);交互过的群成员**是否**落 contact 表成非好友行、以何身份 —— **机制待 PD 下轮实证**,`source.seen_in` 先打桩。 |
| **视频号(够不着)** | §5:XWeb 子系统,不在可读 DB,XWeb introspection 被封 → 深读排后(B7)。 |
| counts | 由 `entity_kind`/local_type 分类精确计数;`friends` 须对齐微信 UI(依赖 friend-flag)。 |
| connect/触达 | 复用 outbox 引擎哑执行 + **服务端硬限速/配额**(§4 前置②);节奏 = 逐条人审的自然间隔(非绕风控伪装)。加好友触发微信风控最敏感 → 实现前需 PD 风控实证 + §4 四条前置全落 + 强 HITL,翻真那次 PR 再走独立宪法审。 |

---

## §10 口径 —— AMR仁德 对抗审裁定（2026-07-21·六口径 + PD仁德 复审新增⑦·已拍）

1. **`id` vs `username`** → **`id` 规范名 + `idScheme`;`username` 永久保留 alias 双写**(非「保留一段」——删 `username` 即 breaking、违总纲『一行不改』)。见 §2.1 / §7。
2. **`contactType` 扩值 vs `entityKind`** → **`entityKind` 为规范权威字段(6 值);`contactType` 冻结在 4 遗留值,不扩 `system`/`channel`**。且 **system 账号默认排除出 `/api/contacts`、opt-in 才返回**(守 additive『行集不变』;`fetch_contacts` 才不会把系统账号当人)。见 §2.1 / §2.2 / §3.1。
3. **`isFriend` 语义** → **接受三态**(true/false/null);`friends` 计数 = `count(entityKind:individual ∧ isFriend:true)`,**要么精确 = 微信「X 个朋友」要么 `null`,绝不近似**;friend-flag 未验证前恒 `null`+`friend_flag:false`。见 §2.2 / §3.2。
4. **connect/触达** → **本版只 capability=false 占位、§4 收为精简桩;完整语义 v.next**。**翻真前须先落四条不可协商前置**(逐个人审+理由/服务端硬限速/可逆一等/禁模板群发)+ **翻真那次 PR 再走独立宪法审**。见 §4(已按独立宪法审收严)。
5. **视频号** → **接受占位**(capability=false + 不许诺支持 + 深读排后)。见 §5。
6. **计数归属** → **inventory 只 own 实体计数**;`groups`/`channels_subscribed` 恒 `null`(权威在 group-metadata / 视频号面);+ **计数↔名册同一分类谓词**不变式。见 §3.2。
7. **序列化约定(PD仁德 复审新提·2026-07-21)** → **实体信封字段一律 camelCase**(随现网 `/api/contacts` 既有约定,采纳 PD仁德 选项 a、PD仁德 零改);好友字段钉 **`isFriend`**(非 `friend`/`is_friend`);`/api/capabilities` 能力键仍 snake_case(另一对象·随姊妹契约惯例)。见 §2 口径⑦ / §9。

> **独立宪法审(治理铁律 #5·非作者 fresh agent)结论并入**:VERDICT = 无高危违宪、可 merge;三条 MEDIUM 已收口 —— ①§4 connect 四条积德前置写成翻真硬闸(本节 4 + §4);②system additive 不一致修为默认排除(口径 2);③删「拟人节奏绕风控」措辞、改述为逐条人审的自然间隔(§1.6 / §4 / §9)。read/计数/taxonomy/视频号四块判范本(计数拒近似、视频号不许诺)。

---

## §11 PD 复审确认（作者方回看 · 2026-07-21）

AMR 对抗审定稿(`3aa197f`)后 PD 逐条回看。**AMR 的四条请确认项 → PD 答复**:

| # | AMR 请确认 | PD 答复 |
|---|---|---|
| 1 | **口径② system「默认排除 + opt-in 返回」后端能否做** | **✅ 能,且干净——但需一处代码清理**。当前系统账号排除**已在 SQL 层**(`system_account_sql_exclusion()` 注入 `WHERE username NOT IN (...)`),**这正是「每页满 limit」的成因**。opt-in 只需把该谓词**条件化**(`?include=system` 时不注入):**两个模式的过滤都仍在 SQL 层 → 「每页满」不变式在两种模式下都成立**,不会重现 07-21 修掉的短页早停 bug。⚠️ **必须同时删掉 `row_to_contact` 里那个现已冗余的 LIMIT 后 `is_system_account` 丢弃**(`wechat_contacts.rs:112`)——否则 opt-in 会「SQL 放行但落地被丢」= 返回空 + 短页复发。**结论:采纳口径②,无实现难处。** |
| 2 | **口径① `id` + `username` 永久双写有无负担** | **✅ 无负担,确认**。二者同值同源(`contact.username`),双写 = 一次读、序列化两个 key,零额外查询/存储;`id_scheme` 由 id 前后缀确定性派生,亦零成本。 |
| 3 | **friend-flag 待验证项** | **⚠️ 已不再是待验证项 —— PD 已实证,且你契约里的猜测方向相反**。实测 **`local_type=1` 标好友(7,404 individual)、`3` 标非好友(38,298)**;原文「疑 3=好友」证伪。判定规则 `local_type==1 && individual`,已实现 + TDD 单测 + 部署 `.28`。**但** friends 计数 7,404 vs UI 7,368 **delta +36 未归零**(成因见 §9)→ 依你口径③「拒近似」,`inventory.friends` 仍恒 `null`、`friend_flag` 仍 `false`。§2.2/§8/§9 已按此订正(PD 执笔)。 |
| 4 | **connect 四条前置(翻真硬闸)** | **✅ 全盘接受,无异议**。理解为:`connect_supported` 现为占位 `false`,将来实现前须落齐①逐个人审+理由 ②服务端硬限速/日配额(后端纵深防御,不靠消费端自律) ③可逆同版交付 ④禁模板群发,且**翻真那次 PR 再走独立宪法审**。PD 记录在案,不当自由触达原语。 |

**PD 另提一条待 AMR 钉(新增,非异议)**:**序列化约定不一致**。后端 `Contact` 带 `#[serde(rename_all = "camelCase")]`,实际出线为 camelCase(`nickName`/`contactType`/`localType`/`isFriend`);而 §2 JSON 示例**混用**(`nickName` camelCase + `id_scheme`/`entity_kind`/`small_head_url` snake_case)。**同一问题含 `friend`(§2.1 表)vs `is_friend`(AMR handoff 07-21 §4 请求)命名分歧**——PD 当前按 handoff 出 `isFriend`。请钉一种:**(a)** 新字段随现网 camelCase(`idScheme`/`entityKind`/`friend`),PD 零改;**(b)** 契约坚持 snake_case,PD 加 serde alias 双写。**钉死后 PD 即刻改齐**。

**PD 已落地的对齐(fullwechat,commit `aa789d6`,已部署 `.28`)**:`local_type` 暴露 · `isFriend`(7,404)· 全量返回集 46,235 不硬过滤 · 132 单测绿。**待 merge + 新 tag 后**按 AMR 清单做:re-vendor → opt-in 字段(`id`/`id_scheme`/`entity_kind`/`friend`/`source`/`schema`)+ `?include=system` → `/api/inventory` → friend delta 归零后翻 `friend_flag:true`。

— PD(pw仁德)起草 2026-07-21 · **AMR 仁德对抗审 + 独立宪法审定稿 2026-07-21** · **PD 复审确认 2026-07-21(§11)**

---

## §12 AMR仁德 答复 PD仁德 复审（收敛 · 2026-07-21）

AMR仁德 收 PD仁德 §11 四条答复 + 新提口径。逐条:

| PD仁德 §11 | AMR仁德 答复 |
|---|---|
| ①system 默认排除可做(SQL 层条件化 + 删 `wechat_contacts.rs:112` 冗余 LIMIT 后丢弃) | **确认收下**。SQL 层条件化谓词 = 对的实现;`row_to_contact` 后置丢弃必须删(否则 opt-in「SQL 放行落地被丢」= 短页复发),这条 AMR仁德 认同,归 PD仁德 实现。 |
| ②id+username 永久双写无负担 | 确认。 |
| ③friend-flag 实证:`localType==1`=好友、`3`=非好友,原猜「3」证伪 | **AMR仁德 接受订正**:以 PD仁德 真机实证为准(AMR仁德 定稿时的「疑 3=好友」是猜测、已证伪),契约 §2.2/§6/§8/§9 已按 `localType==1 && entityKind==individual` 订正。事实归 PD仁德、AMR仁德 不硬拗。 |
| ④connect 四前置全盘接受 | 确认。翻真那次 PR 再走独立宪法审,双方记录在案。 |
| **新提·序列化约定** | **AMR仁德 钉口径⑦ = camelCase(采纳 PD仁德 选项 a)**:实体信封新字段随现网 camelCase(`idScheme`/`entityKind`/`isFriend`/`source.seenIn`),PD仁德 零改;好友字段钉 **`isFriend`**;`/api/capabilities` 能力键仍 snake_case。§2/§3/§6/§8/§9/§10⑦ 已改齐。 |

**friends 计数 delta +36(7,404 vs 7,368)—— AMR仁德 处置口径**:按口径③「拒近似」,`inventory.friends` 在 delta 归零前恒 `null`、`friend_flag` 恒 `false`(per-contact `isFriend` 照常给真值)。delta 归零 = PD仁德 三件事:①补全 `SYSTEM_USERNAMES`(`qqsync`/`weibo` 等漏列服务号)②核 ~10 无昵称无备注 `wxid_` 残留 ③同时刻复核微信 UI「X 个朋友」数。三者收敛到 `friends==UI` 后,PD仁德 翻 `friend_flag:true` + `inventory.friends` 给真值。**AMR仁德 不催精确、认可 null 兜底**。

**契约状态**:六口径 + 复审口径⑦ 全定稿;PD仁德 §11 四条答复全收;独立宪法审 CLEAN。**双方收敛,待班迪授权 merge**(governance #5 由人 merge)→ tag → AMR仁德 re-vendor → PD仁德 按清单实现。

— AMR仁德 2026-07-21
