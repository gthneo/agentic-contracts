# 富文件归档契约 v2 — Rich-File Archive Contract（Inbox 方向·常态下载归档）

> schema 标识：`rich-file.archive/1` ｜ 状态：定稿 v1.3（2026-07-04，download 机制纠偏为 GUI-drive + 保留窗校准；接口/schema 不变·向后兼容）
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
| `file_id` | str | 是 | 稳定 id = **微信消息库里那条记录自带的文件 md5**（壳也有）。**严禁** md5(本地字节)。 |
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
| `POST /api/files/download {chat, msg_id?}` | **主动下载（常态·写侧）** | **单件**（给 `msg_id`）或**会话级批量**（只给 `chat` → 下该会话所有 `cdn=recoverable`）。对 `recoverable` 件后端**驱动微信自身的下载器**（a11y 打开会话→定位该消息→触发下载，微信客户端自己完成取件+落盘）→ 读 `<账号>/msg/file/年-月/` 明文 → `has_local` 转 true。⚠️ **碰 GUI·单 GUI 串行·仅对 ~5–7 天保留窗内的件有效**（窗外微信自身也报「文件已过期」→ 返 typed `expired`）。**不可**用存的 cdnurl+aeskey 在 GUI 外裸取——见文末「机制现实」。**批量走异步**：立即返回 `{accepted}`（本次入队件数，**必给**）；**进度真相源 = `GET /api/files` 的 status 迁移（`recoverable→local`）轮询**，后端**不持有 job 状态机、不另立 job 查询端点**（守无状态）。`job` 字段**可选·纯 informational**（后端要给个计数/批次号可给，但消费方不得依赖它回查进度）。单件小文件可同步返回归档后 item。失败给 typed error（§5）。 |
| `GET /api/media/{chat}/{msg_id}` | **取件（保持纯净）** | 只服务**已落盘（has_local）**字节（**不做同步 lazy CDN 下载**，避免击穿消费方 GET 超时）。未落盘按 cdn 态分**两种终码**：`cdn=recoverable`（能下但还没下）→ **`404 {code:"not_local"}`**（消费方 `POST download` 预热再 GET）；`cdn=expired`（CDN 已删·下不回来）→ **`410 {code:"expired"}`**（终态「没了」，消费方**别再试预热**）。两码分开,免消费方对 expired 件白试一轮预热。 |
| `POST /api/files/delete-local {chat, msg_id}` | **删本地副本 / 复位** | 删**本地下载的那份** → `has_local` 转 false（**不删微信原件**）。下载可逆的操作化落点（CRUD 铁律：Delete 一等、并↔拆可逆）。删前后端留痕；**清盘必 HITL，后端绝不自动删**。 |
| `GET /api/capabilities` → `rich_files` | **能力声明** | `{ list, download, delete_local, auto_download_mb, base_url, local_bytes }`。`download`=写侧就绪位；`auto_download_mb`=微信**被动**下载阈值（实测 .28 = **100**，主动 download **不受此限**）；**`local_bytes`（`download:true` 时必填）**=**整账号**归档目录（`<账号>/msg/file/`）本地占用字节**合计**（不按会话细分——保留策略要的是「看得见盘增长」，整账号一个数最省且够用）。盘增长可见是「主动下载可被接受」的安全前提，也是清盘 HITL 的地基，故**不可选**（download 关时可省）。缺 `rich_files` 键 = 不支持，消费方优雅降级。 |

> **lazy-GET（可选·默认关）**：若后端要做「GET 未落盘时当场拉」，须做**显式 opt-in**（如 `GET …?lazy=1` 返回 `202 + Retry-After` 有界，消费方轮询），**不得**让默认 GET 同步阻塞下载。

> **机制现实（v1.3 · 2026-07-04 逆向调研校准）**：早前设想的「用 XML `cdnurl+aeskey` 在 GUI 外 CDN 直取·不碰 GUI」**不可行**,故 download 落为 **GUI-drive**（驱动微信自身下载器）。两条独立死因:
> 1. `cdnattachurl` **不是 URL**,是会话门控的 ASN.1/DER token;裸取需 **live 登录会话**的 `dns_authkey`（微信私有 `getcdndns` over MMTLS）+ CDN frontip,存的 `aeskey` 只做最后一步 AES-128-ECB 解密（非卡点）。该会话密钥无法干净获取（本 build `7b3f07cc` 的 frida 抠取 `build_unsupported`）。
> 2. **~86% 的历史文件已过 CDN ~5–7 天保留期、永久湮灭**——无字节可取。
>
> **对契约消费方无接口影响**（端点/错误码/capabilities 不变）,但两条现实约束需知晓:①download **碰 GUI、单 GUI 串行**（吞吐/时延受限,批量务必异步）;②可归档的只有**滚动的最近 ~5–7 天新增**,存量绝大多数是 `expired` 死壳。后端**继续持久化** `cdnattachurl/aeskey/md5/encryver`(便宜),留作将来若 frida 支持本 build 走「wcferry 式内部下载器调用」的选项。

## 4. 选择策略（住 AMR，不进后端）

- **后端 = 哑字节抓取器**：只 list + 按 `POST download` 下、按 `POST delete-local` 删、按 GET 取；**不内置「下谁 / 订阅谁」**。
- **策略住 AMR + 人**（宪法「人拿扳手」+「归类归 AMR」）：业务/小群 → AMR 可 `POST download {chat}` 会话级全下（确定性规则）；大群 → 人/规则筛，只下选中的。触发逐消息 / 会话订阅式由 AMR 定。
  - **「按会话自动下载」本身是人可开关 / 可编辑的 gate，非 AMR 默认全开**（守宪法「不得设计甩手全自动、人被旁路」）——默认关或按人设的白名单会话开，人决定哪些会话值得常态落盘。
- **被动兜底**：微信桌面「自动下载 ≤N MB」（实测 .28 N=**100**、ON）继续生效——桌面客户端既有行为、非本系统自动决策；调 N **仍须人手拨挡**，非后端自调。

## 5. 时效 / 分页 / 错误 / 优雅降级

- **时效**：按 `expire_at` 升序，快到期先 `POST download`。
- **`expired` 件**：`GET /api/files` **仍返回**（`status:"expired"`，只元数据 + provenance，无字节），不静默吞（对齐 message §6.4）。
- **typed error（不裸 500）**：取不回 / 下不动时返回可区分错误码——`expired`（CDN 已删）/ `cdn_timeout`（窗口内但超时）/ `not_recoverable`（无 cdnurl/key）/ `too_large`（超后端上限）/ `not_local`（GET 未落盘·recoverable）。结构 `{error:{code, retryable, msg?, chat_id?, msg_id?}}`，对齐 message §6.4 read_unavailable。**`retryable`（bool·后端给·单一真相）**：可否重试由**后端**在 error 里显式标（如 `cdn_timeout`→`true`、`expired`/`not_recoverable`→`false`），**消费方直接读 `retryable`、不按 code 维护白名单**——以后加可重试码不用改消费方。
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

## 8. 版本化 + 能力声明

- schema：`rich-file.archive/1`（承接 `rich-file.rescue/1`，因 rescue 从未实现故一次改名到位）。major（`/2`）= 破坏性另开；minor（doc `vX.Y`）= 向后兼容加字段。
- 能力位：`GET /api/capabilities.rich_files.{list,download,delete_local,...}`。消费方按能力位优雅降级。

## 关联
- 母契约：`message/canonical.md`。根契约：`00-CONSTITUTION.md`（§7 逐条对账）。
- fixtures：`fixtures/rich-file/`。
