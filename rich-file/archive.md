# 富文件归档契约 v2 — Rich-File Archive Contract（Inbox 方向·常态下载归档）

> schema 标识：`rich-file.archive/1` ｜ 状态：定稿 v1.4（2026-07-08，§4.5 范围策略裁定 Route A + §3 主动下载禁用机制勘误并入正文 + §5 补 `active_download_disabled` + §7 补对账；接口/schema 不变·向后兼容）
> **from** AgenticMessageRouter (AMR，定义方 / 消费方) ｜ **for** fullwechat / PowerData-WX（实现方）
> **真相源** 本仓（`agentic-contracts`）。0 号宪法统领。
> **姊妹契约** `message/canonical.md`（本契约是其 `file`-kind 的归档扩展，不另起数据模型）。
> **沿革** Phase 1 = `rich-file.rescue/1`（列举 + 两轴 status + 取件对齐，tag v0.4.0）。Phase 2 把
> 语义从「抢救(rescue)」**重定位为「常态下载(download)」** 并补齐写侧。因 rescue 端点从未实现
> （501 stub、无 live 消费方），趁现在无破坏一次改到位：schema id `rich-file.rescue/1`→`rich-file.archive/1`。

## 0. 这份契约是什么 / 不是什么

**是什么**：微信里的业务文档（PDF/DOC/PPT/表格/附件）是**易失资产**。**关键架构事实**：PowerData-WX
**读走 SQLCipher DB、从不渲染微信 GUI** → 微信「消息进视野就被动落盘」的机制**永不触发** → 库里绝大多数
文件是 `recoverable`（只在 CDN、本地没有）。所以主动下载**不是应急抢救，是常态的「该留就留」**——把该看的
业务文档在 CDN 保留窗（**~5–7 天**，逆向调研校准，非早前的 7~14 天）内**下载到本地 + 带 provenance 暴露**，让 AMR / 任何 Agent 干净
消费、归到人/事。这是 **Inbox 方向**（读入）的算料归档。

**不是什么**：
- **不是新数据模型**。rich_file **是 `message/canonical.md` 里 `file`-kind 消息的归档扩展**——同一个文件，
  消息流里是一条 `kind:"file"` canonical message，这里是一条带归档元数据的 rich_file item，**靠 `msg_id`
  同一把钥匙关联**（见 §2）。不得漂移出两套真相。
- **不做归类决策**。fullwechat 只**下字节 + 给结构化 provenance**；「归哪个人 / 哪件事 / 下不下」由
  **AMR（有人/事模型）+ 人**判（选择策略见 §4）。
- **不删微信原件**。归档 = 本地存一份，原件留在微信。

## 1. 设计原则

1. **让一切 agent 好消费**：字段语义拍死、状态可判、取件端点可达、错误可区分（typed）。
2. **真相 + 便利双给**：状态给「两轴真相 + 派生便利」，取件给「稳定 path + 绝对 url 便利」（见 §2）。
3. **常态下载 · 时效为下限**：该留的就下；按到期戳排，快到期的别拖。`expired` 壳只留元数据（诚实告知「曾有已丢」）。
4. **后端哑、AMR 掌舵**：后端无状态（list + 按请求 download / delete-local / 取件），**下谁、订阅谁的策略住 AMR + 人**（守宪法「人拿扳手」）。

## 2. rich_file item 形态（Phase 1 两态模型，不变）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_id` | str | 是 | 稳定 id = **微信消息库里那条记录自带的文件 md5**（壳也有）。**身份不得用本地字节重派**——`file_id` 永远取消息库自带 md5，即便本地没落盘也有此 id。（**辨析**：*校验/匹配* 一个已落盘文件是不是某 item，按 `md5(盘上字节)==file_id` 认是**允许且推荐**的——微信落盘用内部序号名而非原始标题，只能靠内容哈希认件，见 §3 机制勘误。「严禁 md5(本地字节)」指的是**不得据此重新赋予/覆盖 file_id 身份**，不是禁止内容哈希校验。） |
| `name` / `ext` / `size` / `mime` | | name 必填 | 文件名 / 扩展名（小写无点）/ 字节数 / MIME。 |
| `provenance` | obj | 是 | 来源履历，见 §2.1。 |
| `has_local` | bool | 是 | **真相轴①**：现在本地磁盘上有可取的字节吗。 |
| `cdn` | enum | 是 | **真相轴②**：`recoverable`（本地无/有、CDN 窗口内仍可下载）/ `expired`（CDN 已删，不可再取）/ `unknown`。 |
| `status` | enum | 是 | **派生便利**（由两轴算、读时实时算不缓存）：`local`（has_local）/ `recoverable` / `expired`。local 优先。 |
| `expire_at` | int | 否 | CDN 到期 unix 秒。`cdn=recoverable` 时**应给**（排下载优先级）。 |
| `retrieval_path` | str | 是 | 取件真相：相对路径 `/api/media/{chat}/{msg_id}`，拼 `capabilities.rich_files.base_url`。 |
| `retrieval_url` | str | 否 | 取件便利：绝对 URL。后端知道自己外部 base 时填，否则省。 |

### 2.1 provenance

`{ chat_id(必), chat_name?, sender_id?, sender_name?, sent_at(必), is_read?, msg_id(必) }`。
`msg_id` **必须等于** message envelope 的 `msg_id`（全局唯一稳定 server_id，归类唯一钩子，**严禁 localId**）。

## 3. 端点（fullwechat 实现）

| 端点 | 作用 | 说明 |
|---|---|---|
| `GET /api/files?chat=&since=&status=` | **列举** | rich_file item 列表。**分页必做**（`limit`/`offset` 或 cursor，capabilities 声明），不一次拉全。 |
| `POST /api/files/download {chat, msg_id?}` | **主动下载（常态·写侧）** | **单件**（给 `msg_id`）或**会话级批量**（只给 `chat` → 下该会话所有 `cdn=recoverable`）。对 `recoverable` 件后端**驱动微信自身的下载器**（a11y 打开会话→定位该消息→触发下载，微信客户端自己完成取件+落盘）→ 读 `<账号>/msg/file/年-月/` 明文 → `has_local` 转 true。⚠️ **碰 GUI·单 GUI 串行·仅对 ~5–7 天保留窗内的件有效**（窗外微信自身也报「文件已过期」→ 返 typed `expired`）。**不可**用存的 cdnurl+aeskey 在 GUI 外裸取——见文末「机制现实」。**批量走异步**：立即返回 `{accepted}`（本次入队件数，**必给**）；**进度真相源 = `GET /api/files` 的 status 迁移（`recoverable→local`）轮询**，后端**不持有 job 状态机、不另立 job 查询端点**（守无状态）。`job` 字段**可选·纯 informational**（后端要给个计数/批次号可给，但消费方不得依赖它回查进度）。单件小文件可同步返回归档后 item。失败给 typed error（§5）。**GUI-drive 自动化严格限定于 inbound 取件交互（开会话 / 定位消息 / 触发下载 / 读盘），绝不触达任何 send / forward / compose / publish 控件。**依据 0 号宪法红线「对外动作·系统永不替发」——取件是读入，不得因驱动 live GUI 而越界到任何对外可见/发送动作。 |
| `GET /api/media/{chat}/{msg_id}` | **取件（保持纯净）** | 只服务**已落盘（has_local）**字节（**不做同步 lazy CDN 下载**，避免击穿消费方 GET 超时）。未落盘按 cdn 态分**两种终码**：`cdn=recoverable`（能下但还没下）→ **`404 {code:"not_local"}`**（消费方 `POST download` 预热再 GET）；`cdn=expired`（CDN 已删·下不回来）→ **`410 {code:"expired"}`**（终态「没了」，消费方**别再试预热**）。两码分开,免消费方对 expired 件白试一轮预热。 |
| `POST /api/files/delete-local {chat, msg_id}` | **删本地副本 / 复位** | 删**本地下载的那份** → `has_local` 转 false（**不删微信原件**）。下载可逆的操作化落点（CRUD 铁律：Delete 一等、并↔拆可逆）。删前后端留痕；**清盘必 HITL，后端绝不自动删**。 |
| `GET /api/capabilities` → `rich_files` | **能力声明** | `{ list, download, delete_local, auto_download_mb, base_url, local_bytes }`。`download`=写侧就绪位；`auto_download_mb`=微信**被动**下载阈值（实测 .28 = **100**，主动 download **不受此限**）；**`local_bytes`（`download:true` 时必填）**=**整账号**归档目录（`<账号>/msg/file/`）本地占用字节**合计**（不按会话细分——保留策略要的是「看得见盘增长」，整账号一个数最省且够用）。盘增长可见是「主动下载可被接受」的安全前提，也是清盘 HITL 的地基，故**不可选**（download 关时可省）。缺 `rich_files` 键 = 不支持，消费方优雅降级。 |

> **⚠️ 主动 GUI-drive download 在本 build 已禁用（2026-07-05 .28 真机纠偏）**：上表 `POST /api/files/download` 描述的「后端驱动微信自身下载器」在当前 build（`7b3f07cc`）**不可用、已禁**——右键→原生「Save as…」Qt 对话框被执行循环的 AT-SPI a11y-dump 撞上会**崩微信/掉登录**。故对 `recoverable`-未落盘件，`POST download` 返 typed **`active_download_disabled`**（见 §5），**不真触发 GUI 下载**。**当前现实取件路径 = 被动：微信自身/人/将来安全轻量触发「浏览即下载」落盘 → 后端按内容哈希（`md5+size`）认出 → `GET /api/media` 出件**。§3 的 GUI-drive 主动下载语义**留作契约、待安全触发方案就绪再启用**（届时 §7「GUI-drive 越界护栏」重新生效）。

> **lazy-GET（可选·默认关）**：若后端要做「GET 未落盘时当场拉」，须做**显式 opt-in**（如 `GET …?lazy=1` 返回 `202 + Retry-After` 有界，消费方轮询），**不得**让默认 GET 同步阻塞下载。

> **机制现实（v1.3 · 2026-07-04 逆向调研校准）**：早前设想的「用 XML `cdnurl+aeskey` 在 GUI 外 CDN 直取·不碰 GUI」**不可行**,故 download 落为 **GUI-drive**（驱动微信自身下载器）。两条独立死因:
> 1. `cdnattachurl` **不是 URL**,是会话门控的 ASN.1/DER token;裸取需 **live 登录会话**的 `dns_authkey`（微信私有 `getcdndns` over MMTLS）+ CDN frontip,存的 `aeskey` 只做最后一步 AES-128-ECB 解密（非卡点）。该会话密钥无法干净获取（本 build `7b3f07cc` 的 frida 抠取 `build_unsupported`）。
> 2. **~86% 的历史文件已过 CDN ~5–7 天保留期、永久湮灭**——无字节可取。（**~86% 为单账号（.28）某时点 backlog 实测快照，非契约保证的普适可归档率**。）
>
> **对契约消费方无接口影响**（端点/错误码/capabilities 不变）,但两条现实约束需知晓:①download **碰 GUI、单 GUI 串行**（吞吐/时延受限,批量务必异步）;②可归档的只有**滚动的最近 ~5–7 天新增**,存量绝大多数是 `expired` 死壳。后端**继续持久化** `cdnattachurl/aeskey/md5/encryver`(便宜),留作将来若 frida 支持本 build 走「wcferry 式内部下载器调用」的选项。**消费方（AMR）运维应按串行吞吐重设批量 ETA/超时，勿沿用并行直取的时延预期。**

## 4. 选择策略（住 AMR，不进后端）

- **后端 = 哑字节抓取器**：只 list + 按 `POST download` 下、按 `POST delete-local` 删、按 GET 取；**不内置「下谁 / 订阅谁」**。
- **策略住 AMR + 人**（宪法「人拿扳手」+「归类归 AMR」）：业务/小群 → AMR 可 `POST download {chat}` 会话级全下（确定性规则）；大群 → 人/规则筛，只下选中的。触发逐消息 / 会话订阅式由 AMR 定。
  - **「按会话自动下载」本身是人可开关 / 可编辑的 gate，非 AMR 默认全开**（守宪法「不得设计甩手全自动、人被旁路」）——默认关或按人设的白名单会话开，人决定哪些会话值得常态落盘。
- **被动兜底**：微信桌面「自动下载 ≤N MB」（实测 .28 N=**100**、ON）继续生效——桌面客户端既有行为、非本系统自动决策；调 N **仍须人手拨挡**，非后端自调。

> **§4.5 对本节的细化（Route A）**：本节「策略住 AMR」的原则，经 §4.5 裁定细化为——**范围订阅策略对象（阈值+白名单）的数据落点住 PD**（单一真相源，`GET/PUT /api/files/policy`），但**人仍在 AMR 前端编辑该策略**（`PUT` 写回 PD）。即「扳手在人手上」不变（值是人配），放松的只是「策略数据的存储位」从 AMR 挪到 PD。**download 执行侧**仍是「后端哑抓取器、不越人所设策略自决下谁」。

## 4.5 范围配置策略（§policy · AMR 定稿 · Route A）

> **AMR 定稿**（王丁焱 2026-07-05 裁定 **Route A**；PD 已实现 + 真机 .28 往返验证）。此前 PD 起草、列 A/B 请 AMR 定夺，现**裁定 Route A** 并收敛为规范；`in_scope` 过滤位与 `capabilities.rich_files.policy` 随本节定稿生效。

**为什么**：哪些聊天的媒体值得长期留档 = 业务策略，应由**人在前端配置**（宪法「人拿扳手」），不硬编码、不每次现算。故把"下哪些群"的**默认订阅规则**固化成一份**可配置对象**，沿两轴：空间（小群≤阈值自动 + 私聊含内；大群白名单）× 类型（`documents` / `audio_video` 各自配）。

**裁定 · Route A（配置住 PD，AMR 前端编辑，双方读同一份）**：策略对象（阈值 + 白名单）**单一真相源住 PD**（`GET/PUT /api/files/policy`）；PD 自身的 `in_scope` 过滤读它；**AMR 前端提供人工编辑 UI**，人在前端 `PUT` 写回 PD（**扳手仍在人手上**——值是人配、非后端自决）；AMR 与 PD 读同一份。这**放松了 §4「后端不持有策略数据」**（见 §4 桥接注），但**守住「人拿扳手」**：后端不越过人所设策略去自决「订阅谁」。
> 记录留痕：本裁定否决了「配置住 AMR」的 Route B。独立对抗审曾建议 B（担心策略真相源挪出 AMR 信息中枢），最终裁定权在人，王总选 A。

**配置对象 schema**（住 PD，AMR 前端编辑）：
```jsonc
{
  "small_group_max": 20,          // 成员数 ≤ 此 ⇒ 小群 ⇒ 落"小群"档。私聊(1–2人)天然落此档。
  "dm_auto": false,               // 私聊(1:1)自动在册开关,【默认关·opt-in】,人在前端显式开。
  "documents":   { "auto_small": false, "large_allow": ["<chatId>@chatroom", …] },  // 默认关
  "audio_video": { "auto_small": false, "large_allow": [] }   // 下一轮启用,默认全关
}
```
> **默认 opt-in（守 §4 line 75 + 宪法「不得甩手全自动、人被旁路」）**：所有 `auto_*` **出厂默认关**，**人在 AMR 前端显式开启某档才自动归档**——不得在人未配置前静默把每个私聊/小群的文件自动归档。这是自动归档 PII 的安全地基。

**分类判定**（纯函数，两侧应一致）：私聊 → `dm_auto && <type>.auto_small`；群 `n≤max` → `<type>.auto_small`；群 `n>max` **或成员数未知** → `chat_id ∈ <type>.large_allow`（**未知按大群**，保守不静默归档无界大群）。成员数取 `group-metadata` 的 `member_count`。
> **member_count 是近似值（`group-metadata` 声明 best-effort，`roster:false` 下不精确）**——本判定拿它当小/大群闸，**误分类只会向保守侧降级**（把小群误判成大群 → 需白名单 → 不会静默归档），**绝不向"静默归档无界大群"降级**。故近似可接受。

**端点（Route A · 落 PD）**：`GET /api/files/policy`（前端读，未配过返上述 opt-in 默认）、`PUT /api/files/policy`（前端整对象替换、人在环路写）、`GET /api/files?in_scope=true`（只返在册件，省略=全返·向后兼容）、`capabilities.rich_files.policy:bool`（就绪位）。

**边界重申**：策略只决定"**什么在册**"，**不亲自抓字节**——文件靠微信原生「浏览即下载」落盘、后端按内容哈希（`md5+size`）认出（见 §3「机制现实」+ §3 主动下载禁用注）。在册但未落盘的真缺件，**主动抓取待安全触发**（§3 已禁 GUI-drive 主动下载，返 `active_download_disabled`）。**配置先行、引擎后补，不冲突。**

## 5. 时效 / 分页 / 错误 / 优雅降级

- **时效**：按 `expire_at` 升序，快到期先 `POST download`。
- **`expired` 件**：`GET /api/files` **仍返回**（`status:"expired"`，只元数据 + provenance，无字节），不静默吞（对齐 message §6.4）。
- **typed error（不裸 500）**：取不回 / 下不动时返回可区分错误码——`expired`（CDN 已删；触发来源现含「GUI-drive 窗外微信自身报文件过期」）/ `cdn_timeout`（窗口内但超时）/ `not_recoverable`（无 cdnurl/key）/ `too_large`（超后端上限）/ `not_local`（GET 未落盘·recoverable）/ **`active_download_disabled`**（`POST download` 主动 GUI 下载在本 build 已禁用·见 §3 主动下载禁用注；`retryable:false`——非瞬时，待安全触发方案就绪后本码语义再议）。结构 `{error:{code, retryable, msg?, chat_id?, msg_id?}}`，对齐 message §6.4 read_unavailable。**`retryable`（bool·后端给·单一真相）**：可否重试由**后端**在 error 里显式标（如 `cdn_timeout`→`true`、`expired`/`not_recoverable`/`active_download_disabled`→`false`），**消费方直接读 `retryable`、不按 code 维护白名单**——以后加可重试码不用改消费方。
- **分页**：大会话必分页，不一次拉全（对齐「大号慢后端有界」纪律）。
- **降级**：后端无 `rich_files` 或 `download=false` → 消费方退回纯 `GET /api/media`（仅本地）+ message 流 `file`-kind 元数据，功能不缺、只是无主动下载。

## 6. 与 message/canonical.md 的关系（一把钥匙钉死）

```
一个文件消息
  ├─ 消息流:  message/canonical.md  kind:"file"  file{name,ext,size}  msg_id=<K>
  └─ 归档层:  rich-file.archive/1   rich_file  provenance.msg_id=<K> + status两轴 + retrieval
                                                     ▲ 同一把钥匙 msg_id=<K>，不漂移
```
AMR：ingest 拿到 `kind:"file"` → 需要字节时 `POST download` 预热 → `GET /api/media` 取 → 靠 `provenance.msg_id` 归到人/事。

## 7. 宪法对账（0 号宪法红线自检）

- **人拿扳手**：下谁的选择策略住 AMR + 人，后端不自动决策「下谁」；被动 auto-download 是微信桌面原生行为、调阈值仍须人手拨。✅
- **不可逆决策**：下载 = 可逆地多存一份本地副本（不删原件、`delete-local` 可撤），**护住人的未来选择权**，非替人做不可逆决策。✅
- **清盘 HITL**：主动下载会长盘 → 契约要求后端 `download:true` 时**必报** `local_bytes`（人/Agent 看得见增长，非可选）；**删除/清盘必人审，后端绝不自动清**。✅
- **赋能不替代 · 算料是生产资料**：把易失的微信文档封装进契约（可判状态 + 可达取件 + 可区分错误），让它可流通、可归类、可增值。✅
- **GUI-drive 越界护栏**：GUI-drive 只在 inbound 取件控件上操作（开会话 / 定位消息 / 触发下载 / 读盘），有越界护栏（见 §3 confinement clause），**绝不触达发送 / 转发 / 合成 / 发布控件**。✅（**注**：本 build 主动 GUI-drive download 已禁用〔§3〕，此护栏对该路径当前 moot；待主动下载以安全触发方案重启用时**重新生效**。）
- **范围策略数据落点（Route A · §4.5）**：策略对象单一真相源住 PD（`GET/PUT /api/files/policy`），**后端不自决订阅谁**（只按人所设策略过滤 `in_scope`）；扳手在人——**策略写 = 人在 AMR 前端整对象替换**（`PUT`，human-in-loop write），非 Agent 自动改；`auto_*` 出厂默认关（opt-in），人未开则不自动归档。✅
- **主动抓取现状**：本 build 主动 GUI download 已禁（返 `active_download_disabled`）；重启用须人审 + 维持 §3 confinement。当前取件走被动「浏览即下载 → 内容哈希认件 → GET /api/media」，无主动越界面。✅
- **不泄露对外可见信号（断言）**：a11y 打开会话会翻本地 `is_read`；微信个人聊 / 群聊**无对外已读回执**，故此操作**不泄露任何对外可见信号**——**此为断言（经核实无对外回执），非默认假设**。✅
- **anti-automation 风险自担**：GUI 自动化存在平台 anti-automation（风控）风险，**实现方须知晓并自担节流 / 退避**，不属本契约保证范围。✅

## 8. 版本化 + 能力声明

- schema：`rich-file.archive/1`（承接 `rich-file.rescue/1`，因 rescue 从未实现故一次改名到位）。major（`/2`）= 破坏性另开；minor（doc `vX.Y`）= 向后兼容加字段。
- 能力位：`GET /api/capabilities.rich_files.{list,download,delete_local,...}`。消费方按能力位优雅降级。

## 关联
- 母契约：`message/canonical.md`。根契约：`00-CONSTITUTION.md`（§7 逐条对账）。
- fixtures：`fixtures/rich-file/`。
