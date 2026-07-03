# 富文件抢救归档契约 v1 — Rich-File Rescue-Archive Contract（Inbox 方向·算料抢救）

> schema 标识：`rich-file.rescue/1` ｜ 状态：定稿 v1.0（2026-07-03）
> **from** AgenticMessageRouter (AMR，定义方) ｜ **for** fullwechat / PowerData-WX（实现方）
> **真相源** 本仓（`agentic-contracts`）。0 号宪法统领；本契约为其服务（§见「宪法对账」）。
> **姊妹契约** `message/canonical.md`（本契约是其 `file`-kind 的 rescue 扩展，不另起数据模型）。

---

## 0. 这份契约是什么 / 不是什么

**是什么**：微信里的业务文档（PDF/DOC/PPT/表格/附件）是**易失资产**——微信 CDN 只临时中转、到期删，不主动抢救就永久丢（实测 .28 历史 38923 条文件消息，本地仅存 ~13.5%，86% 已过期只剩壳）。本契约把这些文档**在过期前抢救到本地 + 带 provenance（来源履历）元数据暴露出去**，让 AMR / 任何 MCP / 任何 Agent 能干净消费、归到人/事。这是 **Inbox 方向**（读入）的算料抢救（对齐 AMR Inbox/Outbox 中枢哲学）。

**不是什么**：
- **不是新数据模型**。rich_file **是 `message/canonical.md` 里 `file`-kind 消息的 rescue 扩展**——同一个文件，在消息流里是一条 `kind:"file"` 的 canonical message，在这里是一条带抢救元数据的 rich_file item，**二者靠 `msg_id` 同一把钥匙关联**（见 §2）。不得让同一文件在两处漂移出两套真相。
- **不做归类决策**。fullwechat 只**抢字节 + 给结构化 provenance**；「这个文件归哪个人 / 哪件事 / 存不存进关系图谱」由 **AMR（有人/事模型）+ 人**判（选择策略见 §4）。
- **不删微信原件**。归档 = 抢救到本地一份，保留时间点风貌；原件留在微信。

## 1. 设计原则

1. **让一切 agent 好消费**：字段语义拍死、状态可判、取件端点可达。
2. **真相 + 便利双给**：状态给「两轴真相 + 派生便利」，取件给「稳定 path 真相 + 绝对 url 便利」（见 §2）——精确消费方读真相，图省事的消费方读便利。
3. **时效优先**：按到期戳排，快到期先抢；壳（已丢）只留元数据，诚实告诉消费方「曾有此文件但已丢」。
4. **后端哑、AMR 掌舵**：后端是无状态字节抓取器（list + 按需 rescue）；选择/归类的舵在 AMR + 人（守宪法「人拿扳手」）。

## 2. rich_file item 形态

一条 rich_file 描述一个文件资产。字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_id` | str | 是 | 稳定 id = **微信消息库里那条记录自带的文件 md5**（壳也有，因为 md5 存在 DB 里，不依赖本地字节）。**严禁**用 md5(本地字节)——那样 `expired` 壳算不出 id。 |
| `name` | str | 是 | 文件名（含或不含扩展名，见 `ext`）。 |
| `ext` | str | 否 | 扩展名（`pdf`/`docx`/`xlsx`/`zip`…），小写不带点。 |
| `size` | int | 否 | 字节数。 |
| `mime` | str | 否 | MIME 类型，给得出就给。 |
| `provenance` | obj | 是 | 来源履历，见 §2.1。 |
| `has_local` | bool | 是 | **真相轴①**：现在本地磁盘上有可取的字节吗。 |
| `cdn` | enum | 是 | **真相轴②**：CDN 侧还能不能抢。`recoverable`（本地无/有，CDN 窗口内仍可下载）/ `expired`（CDN 已删，丢了就再也抢不回）/ `unknown`（后端判不了 CDN 状态）。 |
| `status` | enum | 是 | **派生便利字段**（由两轴算出，供图省事的消费方）：`local`（`has_local=true`）/ `recoverable`（`has_local=false ∧ cdn=recoverable`）/ `expired`（`has_local=false ∧ cdn=expired`）。**local 优先**。⚠️ 派生字段会丢细节（「本地有 + CDN 已没」在 status 里显示 `local`，细节在两轴）——精确消费方读两轴。 |
| `expire_at` | int | 否 | CDN 到期 unix 秒（来自文件消息 XML `media_expire_at`）。**排抢救优先级用**：快到期先抢。`cdn=recoverable` 时**应给**（否则消费方无法排优先级）；`expired`/`local`-only 可省。 |
| `retrieval_path` | str | 是 | **取件真相**：相对路径，如 `/api/media/{chat}/{msg_id}`。消费方拼 `capabilities.rich_files.base_url` + 本路径。不焊死 host（IP/隧道变了只改 base 一处）。 |
| `retrieval_url` | str | 否 | **取件便利**：绝对 URL。后端**知道自己外部可达 base** 时填（= base_url + retrieval_path）；不知道则**省略**，消费方回退 `retrieval_path` + `base_url`。 |

> **精确判定口径**：`status` 是 `has_local`/`cdn` 的**纯派生**，实现方**读时实时计算**（不缓存旧值——一个 `recoverable` 会随窗口关闭变 `expired`，缓存会骗人）。

### 2.1 provenance（来源履历）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chat_id` | str | 是 | 会话 id。 |
| `chat_name` | str | 否 | 会话显示名。 |
| `sender_id` | str | 否 | 发送人稳定 id（wxid）。 |
| `sender_name` | str | 否 | 发送人显示名。 |
| `sent_at` | int | 是 | 发送 unix 秒。 |
| `is_read` | bool | 否 | 本条是否已读（保留时间点风貌）。 |
| `msg_id` | str | 是 | **归类唯一钩子**：**必须等于** `message/canonical.md` 信封的 `msg_id`（= 全局唯一稳定 msg_key，见 message 契约 §2.1）。AMR 靠它把 file JOIN 回消息流 → 落到人/事。**严禁**用会话内 localId。 |

## 3. 端点（fullwechat 实现）

| 端点 | 作用 | 说明 |
|---|---|---|
| `GET /api/files?chat=&since=&status=` | **列举** | 返回 rich_file item 列表。`chat` 按会话过滤；`since` unix 秒起点；`status` 按派生 status 过滤（`local`/`recoverable`/`expired`）。分页见 §5。 |
| `GET /api/media/{chat}/{msg_id}` | **取件**（已有） | 返回明文/解密后字节。= `retrieval_path` 指向的端点。带该通道 bearer auth。 |
| `POST /api/files/rescue {chat, msg_id}` | **主动抢救** | 对 `cdn=recoverable` 件，用 XML 的 cdnurl+key 趁窗口回 CDN 下载落盘 → `has_local` 转 true。返回抢救后的 rich_file item（或 error）。对 `expired` 件返回明确失败（不静默）。 |
| `GET /api/capabilities` → `rich_files` | **能力声明** | `rich_files: {list: bool, rescue: bool, auto_download_mb: int, base_url: str}`。`base_url` = 取件绝对 base（拼 retrieval_path 用）；`auto_download_mb` = 桌面被动 auto-download 阈值（实测 .28 = 20）。缺 `rich_files` 键 = 后端不支持富文件，消费方优雅降级。 |

## 4. 选择策略（住 AMR，不进后端）

- **后端 = 哑字节抓取器**：只 `list` + 按 `POST /rescue` 抢；**不内置「抢谁」的选择策略**。
- **策略住 AMR + 人**（宪法「人拿扳手」+「归类归 AMR」）：
  - **业务 / 小群 → 全量抢救**：AMR 自动对该会话的 `recoverable` 件逐条 `POST /rescue`（全量是确定性规则，非黑箱决策）。
  - **大群 → 只抢「客户认同」的**：人工 / 规则筛，AMR 只对选中的 `POST /rescue`。
- **被动兜底保留**：桌面「文件自动下载 ≤N MB」（实测 .28 ON, N=20）继续生效——这是**桌面客户端**的既有行为、非 AMR/后端自动决策，低风险，保留；N 可调高多救大文件。
- **不删原件**：抢救 = 多存一份本地副本，可逆（后续可删），**保留人的未来选择权**，不做不可逆决策。

## 5. 时效 / 分页 / 优雅降级

- **时效排序**：消费方按 `expire_at` 升序排 `recoverable` 件，快到期先 `POST /rescue`。
- **`expired` 件**：`GET /api/files` **仍返回**（`status:"expired"`，只有元数据 + provenance，无 `retrieval_url`/字节），诚实告诉消费方「曾有此文件但已丢」——**不静默吞掉**（对齐 message 契约 §6.4「读空必可区分」精神）。
- **分页**：`GET /api/files` 大会话必分页（`limit`/`offset` 或 cursor，实现方定，capabilities 声明）；**不得一次拉全**（对齐「大号慢后端有界」纪律）。
- **降级**：后端无 `rich_files` 能力 → 消费方退回纯 `GET /api/media` 单条取件 + message 流的 `file`-kind 元数据，功能不缺、只是无主动抢救。

## 6. 与 message/canonical.md 的关系（一图钉死）

```
一个文件消息
  ├─ 在消息流:  message/canonical.md  kind:"file"  file{name,ext,size}  msg_id=<K>
  └─ 在抢救层:  rich-file.rescue/1   rich_file  provenance.msg_id=<K>  + status两轴 + retrieval
                                                     ▲ 同一把钥匙 msg_id=<K> 关联，不漂移
```
- `file`-kind 消息 = 「有这么条文件消息」（Inbox 读入的一条）；rich_file = 「这个文件的字节可不可取、怎么取、来自哪」（抢救 + 消费视角）。
- AMR：ingest 消息流拿到 `kind:"file"` → 需要字节/抢救时查 `GET /api/files`（或按 msg_id 定位）→ `POST /rescue` / `GET /api/media` 取件 → 靠 `provenance.msg_id` 归到人/事。

## 7. 宪法对账（0 号宪法红线自检）

- **人拿扳手**：抢谁的选择策略住 AMR + 人，后端不自动决策「存谁」——不踩「甩手全自动、人被旁路」。✅
- **不可逆决策**：抢救 = 可逆地多存一份本地副本（不删原件、后续可删），**护住人的未来选择权**，非替人做不可逆决策。✅
- **赋能不替代**：把「文件会过期丢失」这件苦活交给数字员工盯 + 抢，人只做「这份值不值得留 / 归哪」的判断。✅
- **算料是生产资料**：把易失的微信文档**封装进契约**（结构化 provenance + 可判状态 + 可达取件），让它可流通、可归类、可增值——正是 0 号宪法第 5 条。✅

## 8. 版本化 + 能力声明

- schema：`rich-file.rescue/1`。major（`/2`）= 破坏性另开；minor（doc `vX.Y`）= 向后兼容加字段。
- 能力位：`GET /api/capabilities.rich_files`（见 §3）。消费方按能力位优雅降级。

## 关联
- 母契约：`message/canonical.md`（`file`-kind、`msg_id` 口径、§6.4 读可区分）。
- 根契约：`00-CONSTITUTION.md`（本契约 §7 逐条对账）。
- fixtures：`fixtures/rich-file/`（conformance 冒烟）。
