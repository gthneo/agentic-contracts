# AMR 关系图谱只读导出契约 v1（消费方草案·rev0）— AMR Graph Export Contract（`amr-graph-export/1`）

> 真相源: `agentic-contracts` 仓 · owner 见 CODEOWNERS（`graph/` 未单列，落默认行 `*` → AMR/@gthneo）。
>
> **日期** 2026-10-27 ｜ **状态** **消费方草案·rev0**——**Metis仁德**（消费方，`/Users/neo/as/metis`，Claude Fable 5.1 起草）代为起草；待 **AMR仁德**（生产方 · 契约定义方，`/Users/neo/as/agenticmessagerouter`）审并定稿，审过后由 AMR仁德 在 AMR 仓实现 `jl graph export`。角色互换依据：班迪 2026-10-27 09:3x 原话「⑨ 批」（`gthneo/metis#64` 最后一条评论；原分工「导出由 AMR仁德 写」因契约 10-23 期限已过改为 Metis 起草消费方草案）。**不 merge。**
> **from** Metis仁德（消费方 · 导入器 `ImportFromSource` 的实现方，`gthneo/metis` PR #380 / #378 条文）
> **to** AMR仁德（生产方 · `jl graph export` 的实现方）· 抄送 EL仁德（`/Users/neo/as/th-admin`，只负责运行与传输）
> **姊妹契约** `../contacts/roster.md`（后端 → AMR 的通讯录实体面；本契约是 AMR → Metis 的下游导出，方向相反、不重叠）· `../VERSIONING.md`（版本轴）· `../fixtures/conformance.md`（语义口径的写法）
> **来源** 作业单 `/Users/neo/as/th-admin/customers/EL-CD/handoff/2026-10-18-EL-to-AMR-graph-export.md`（§1 先契约 · §2 导出内容表 · §3 provenance · §4 PII · §5 验收）· 调研 `/Users/neo/as/th-admin/customers/EL-CD/ops/2026-10-18-amr-relationship-graph-research.md`（A 数据模型 · B.5 置信档 · C 计数 · F.3 映射 · F.4 PII）· 审核清单 `gthneo/metis#64` 六条 · Metis 口径 `gthneo/metis` `docs/requirements/2026-10-21-epic62-kickoff.md` §0 第 1 / 6 条、§3.3 IM-0 / IM-S / IM-2 / IM-3、R2 / R6；PR #380（IM-S 导入条文）· PR #378（RS-0 机构同一性判据）。
> **AMR 数据模型版本** 按 .178 部署版 **v0.90.0 = 提交 `28a33e4`** 的 `src/jl/schema.sql` 与 `src/jl/db.py` 只读核对（§9 来源映射附录）；起草者未触达任何现场主机、未读任何真实业务数据，本文只含计数与化名。

---

## 术语表（Glossary · English is canonical）

| English name | Definition (canonical) | 中文说明 |
|---|---|---|
| **Graph Export** | A read-only, deterministic JSONL dump of AMR's identity layer (persons, contact points, merge records, negative samples, organizations, employments, self identities) produced by `jl graph export` on the AMR host. | 图谱导出：AMR 身份层的只读、确定性 JSONL 转储 |
| **Record** | One JSON object per line; `type` names the record type. | 记录：一行一个 JSON 对象 |
| **Header** | The first record of every export; declares schema, mode, PII policy, source, rules, counts and invariants. | 首行头记录 |
| **Person** | One AMR `persons` row: the owner of a set of contact points. | 人 |
| **Contact Point** | One (kind, normalized identifier) handle owned by exactly one Person; the AMR endpoint. | 联系方式 / 端点（AMR 口径「端点 endpoint」） |
| **Merge Record** | A summary of one AMR person merge (or "this contact is myself" retirement), with undo state. | 合并记录摘要 |
| **Negative Sample** | One AMR `merge_blocks` row: two identifiers the boss or engine ruled are **not** the same person. | 负样本（Metis `not_same_as` 的来源） |
| **Organization** | One AMR `orgs` row. | 机构 |
| **Employment** | One AMR `org_affiliations` version row (append-only chain, including superseded and revoked rows). | 任职（归属）版本行 |
| **Self Identity** | One of the principal's own handles; the consumer never builds a third-party Person from it. | 本人身份 |
| **Identifier-class value** | A value that is, or is derived from, a raw handle or a source-system id (`wxid`, phone, email, `persons.id`); PII (Personally Identifiable Information). | 标识类值 |
| **Display-class value** | A human-readable name (`persons.name`, `orgs.name`, titles). | 显示类值 |
| **Deterministic** | Same database state → byte-identical output except `header.exported_at`. | 确定性 |
| **Redaction** | Replacing identifier-class values with `h:` + first 16 lowercase hex characters of SHA-256 of the UTF-8 value (`--redact`). Pseudonymization, not anonymization. | 脱敏（哈希化名） |
| **Watermark** | `persons.updated_at` max and `events.id` max at export time; incremental cursor. | 水位线 |
| **Producer / Consumer** | Producer = AMR (`jl graph export`); Consumer = Metis importer (`ImportFromSource`, 04 §2.4.1 draft in PR #380) and its `--dry-run`. | 生产方 / 消费方 |

---

## §0 这份契约是什么 / 不是什么 · 为什么需要它

**结论先行**：Metis State Layer 里 Person = 0（EL仁德 2026-10-21 实测），可导入的人全在 AMR（.178 上 8,094 人、16 机构、21 现行任职、4,636 合并记录、22 负样本；EL仁德 2026-10-21 只读计数）。班迪 2026-10-18 已定：全量导入、全部进归一（Resolution）、近 365 天有往来的约 1,200 人优先；`amr:<persons.id>` 原值只进 Metis `aliases`，仓 / issue / 日志只用哈希。导入器（Metis，`ImportFromSource`）与导出器（AMR，`jl graph export`）分属两仓，**先定契约、再写两边**（S1 事务登记导入曾因格式分叉返工）。

**本契约是**：传输形态与退出码（§2）· 头记录（§3）· 七种记录类型的字段表（§4）· PII 别名策略与 `--redact`（§5）· 证据映射到 Metis 三档所需的**事实字段**（§6）· 幂等、增量、删除与拆分的表达（§7）· 消费方校验清单与生产方自核清单（§8）· 来源映射附录（§9）· 待 AMR仁德 定（§10）· 版本（§11）· 宪法对账（§12）。

**本契约不是**：
- **不是归一判断**。契约只传**事实与来源**（`source` / `by` / `confirmed_at` / `evidence_ref` / `rule`），**不传** AMR 的强度分或档位；strong / medium / weak 由 Metis 按其 04 §2.4 判（§6）。
- **不是消息导出**。不含消息正文、聊天名（`conversations.name`、`channels.label`）、附件路径、证据引文、人情报正文、分数、令牌、凭据（§5.3）。
- **不是回写**。AMR → Metis 单向；Metis 对 AMR 不写（Epic #62 本轮「不回写 AMR」，kickoff §2 ⑦）。
- **不是 HTTP API**。走只读 CLI 到标准输出；现有 HTTP 令牌 `JL_WEB_TOKEN` 有全部写权限、端点有 50 / 500 硬上限、返回界面投影（调研 D.1 / F.2），不适合。

**可追溯到 0 号宪法 v3**：第二条第四款「同一个人……全系统只有一个身份（One Ontology）……经本人确认后归于同一个人名下」——本契约把 AMR 已有的人工裁定（合并、负样本）**原样带到 Metis**，不让两边各长一套身份；第九条「接入的算料不得静默丢失；不能接入或者接入不全的，应当如实标明」——`counts` / `invariants` / 退出码 3 让「少了 / 坏了」可判、不得被当成「真空」；第九条第三款「推算得出的判断应当可以追溯至证据、规则版本及作出者」——每条带 `by` / `source` / `rule` / `evidence_ref`，头记录带 `rules` 与 `source.amr_version`。本契约**只读、无对外动作、不涉及授权档位**。

---

## §1 设计原则

1. **事实不判断（facts, not verdicts）**。生产方给「这个号怎么挂到这个人身上的」，不给「挂得对不对」。判断归 Metis（04 §2.4）。
2. **确定性（deterministic）**。同一库状态两次输出，除 `header.exported_at` 外**逐字节相同**：固定记录顺序、固定键序、固定序列化（§2.4）。EL仁德 的台账只记 sha256、行数、水位线。
3. **只读（read-only）**。SQLite 以 `mode=ro` 打开；不写任何表，**不写 `events`**；不调用 LLM（Large Language Model，大语言模型）。
4. **PII 只在标准输出流里**。真实值不进 AMR 仓、测试夹具、日志、issue、交接文档（作业单 §4、调研 F.4）。stderr 只放不含标识的日志。
5. **空值写 `null`，不写 `0` / 空串**。AMR 列里的 `''` 与 `0`（如 `undone_at=0` = 生效中）在导出时转为 `null`；每个字段**恒在场**（缺省也写 `null`），键序因此固定。
6. **English is canonical**。记录 `type`、字段名、枚举值全英文、一词一义；AMR 的中文自由文本（`orgs.kind`、`self_identities.persona`）以 `*_raw` 字段原样透传，不翻译、不归类。
7. **原样不改写**。`aliases`、`quote`、`reason` 原样透传；规范化只发生在 `value_normalized` / `value_e164` 这两个明确标注规则版本的字段上。
8. **向后兼容按 `VERSIONING.md`**：加字段 / 加枚举值 = minor（消费方忽略未知字段、未知 `type` 行跳过并计数）；改语义 / 删字段 = major，另开 `amr-graph-export/2`。

---

## §2 传输形态

### 2.1 命令

```
jl graph export [--since <RFC3339>] [--redact] [--db <path>] > <export_id>.jsonl
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `--since <ts>` | 否 | 增量模式（§7.2）。不给 = 全量（`header.mode="full"`）。**v1 可不实现**（§10 ④）；不实现时给了此参数须以退出码 2 拒绝，不得静默当全量。 |
| `--redact` | 否 | 标识类值哈希化（§5.4），`header.pii_policy="redacted"`。供 dry-run 报告与样例用；**正式导入用 raw**。 |
| `--db <path>` | 否 | 库路径，缺省 AMR 现行库（.178 为 `/home/dbos-user/.config/jl/jl.db`）。以 SQLite URI `mode=ro` 打开。 |

- **stdout** = 契约载荷：UTF-8（无 BOM）JSONL，每行一个 JSON 对象，以 `\n` 结尾（最后一行也有），无空行、无尾随空白。
- **stderr** = 日志（进度、计时、警告），**不得**含任何标识类值；消费方忽略 stderr。
- 不输出任何提示语到 stdout；stdout 若非空则第一行必是 header（§3）。

### 2.2 退出码

| 退出码 | 含义 | stdout |
|---|---|---|
| `0` | 完整成功 | header（`status="ok"`）+ 全部记录；`header.counts` 与各类型实际行数**相等** |
| `2` | 用法错误 / 库打不开 / `--since` 不支持 | **空** |
| `3` | 不变式失败（§2.3），拒绝输出数据 | 仅 header（`status="error"`）+ **一行** `error` 记录（§3.2）；**无**数据记录 |
| 其他非 0 | 未预期错误（含进程中途被杀） | 不可信，消费方**整份丢弃** |

消费方只在 **退出码 0 且 §8.1 全绿** 时把文件交给 dry-run；其余一律丢弃并把退出码、stderr 尾部交 EL仁德。

### 2.3 导出端不变式（exit 3 的触发条件）

| 不变式 | 判法 | 来源 |
|---|---|---|
| `persons_sharing_endpoint == 0` | 同一 `(kind, value_normalized)` 不出现在两个 `person_id` 下 | AMR `db.shared_endpoints`（`db.py:1698`），#158；.178 实测 0 |
| 每个 `contact_point.person_id` 在本次导出的 `person` 里 | 外键完整 | `channels.person_id REFERENCES persons(id)` + `conversations.person_id` |
| 每个 `employment.person_id` / `org_id` 可解 | 外键完整 | `org_affiliations` 无 FK 约束，故导出端须核 |

任一条不满足 → 退出 3，不输出数据记录（宁可不给，不给一份自相矛盾的身份图；0 号宪法第九条「不全如实标明」）。

### 2.4 确定性规则（逐字节相同的构成）

1. **记录顺序**：header 先；随后按类型块固定顺序 `person → contact_point → merge_record → negative_sample → organization → employment → self_identity`；块内排序：

   | type | 排序键（升序） |
   |---|---|
   | `person` | `id` 按 UTF-8 字节序 |
   | `contact_point` | `(person_id 字节序, kind, value_normalized, source)` |
   | `merge_record` · `organization` · `employment` | AMR 整数主键的数值序（`id` 虽为字符串，按整数比较） |
   | `negative_sample` | `(kind ?? "", a_id, b_id)` |
   | `self_identity` | `(kind, value_normalized)` |

2. **键序**：每条记录的键**恒按 §3 / §4 表格行序**出现，所有键恒在场（无值写 `null`）。
3. **序列化**：等价于 Python `json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)`——紧凑分隔符、非 ASCII 原样（不 `\uXXXX`）、不排序键（按插入序）、无 NaN。字符串中的控制字符按 JSON 标准转义。
4. **时间戳**：一律 RFC 3339 UTC 秒级 `YYYY-MM-DDTHH:MM:SSZ` 字符串（AMR 存 Unix 秒整数，导出时转换；`0` / `NULL` → `null`）。字典序 = 时间序。
5. **整数 / 布尔**：AMR `INTEGER` 布尔列（`watch`、`pinned`）输出 JSON `true` / `false`；计数与 `account_id`、`match_digits`、`events_id_max` 为 JSON 整数。
6. **id 的类型**：所有实体 id 及其引用（`person.id`、`*_person_id`、`survivor_id`、`merged_id`、`organization.id`、`parent_id`、`merged_into`、`org_id`、`employment.id`、`superseded_by`、`merge_record.id`）**一律字符串**（AMR 整数主键转十进制字符串）；`account_id` 是 AMR 账号槽位（0–255 整数），**保留整数**。
7. **`header.exported_at` 是唯一允许两次运行不同的字段**；`body_sha256`（若给）= 除 header 外全部行（含每行 `\n`）的 SHA-256，两次运行相同。

> 验法（生产方自核 P1）：对同一份库快照连跑两次，`tail -n +2 a.jsonl | sha256sum` 与 b 相等；或比较两份 `body_sha256`。

---

## §3 头记录（header）

### 3.1 字段（键序即行序）

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `"header"` | 恒定 |
| `schema` | `"amr-graph-export/1"` | 兼容路由前缀 `amr-graph-export/`（同 `fixtures/conformance.md` C5 的思路） |
| `status` | `"ok"` \| `"error"` | `error` 仅与退出码 3 同现 |
| `mode` | `"full"` \| `"incremental"` | §7.2 |
| `since` | ts \| `null` | `incremental` 时回显 `--since`；`full` 为 `null` |
| `pii_policy` | `"raw"` \| `"redacted"` | §5.4 |
| `exported_at` | ts | 导出时刻；**唯一非确定性字段** |
| `source` | obj | `{amr_version: str, amr_commit: str\|null, db_sha256: str\|null}`——`amr_version` = `jl.__version__`（如 `"0.90.0"`）；`amr_commit` = 部署提交短 sha（`DEPLOYED_REF`，拿不到写 `null`）；`db_sha256` 可选（WAL 模式下对 706 MB 库算哈希既慢又随 checkpoint 变，缺省 `null`） |
| `rules` | obj | 规范化规则版本，供消费方入血缘：`{identifier_canon: "amr-canon/1", phone_e164: "cn-mobile-11/1", redaction: "sha256-16/1"}`（§4.2 注、§5.4）。AMR仁德 改规则即 bump 字符串 |
| `watermark` | obj | `{persons_updated_at_max: ts\|null, events_id_max: int\|null}`；给增量与台账用（作业单 §2 header 行） |
| `invariants` | obj | `{persons_sharing_endpoint: int}`；`status="ok"` 时**恒为 0** |
| `counts` | obj | 七个键恒在场：`{person, contact_point, merge_record, negative_sample, organization, employment, self_identity}`，各为本次输出该类型的**实际行数**（不是库内总数；增量时是增量行数） |
| `body_sha256` | str \| `null` | §2.4 第 7 条；可选 |

### 3.2 `error` 记录（仅退出码 3）

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `"error"` | |
| `code` | `"invariant_violation"` | v1 唯一值；minor 可加 |
| `invariant` | str | 失败的不变式名，如 `"persons_sharing_endpoint"` |
| `value` | int | 实测值（如共享端点数） |
| `samples` | array\<str\> | **恒哈希**（`h:` 前缀，§5.4）的样本 id，≤ 5 个；不论 `pii_policy` |
| `message` | str | 人可读说明，不含标识类值 |

---

## §4 记录类型（record types）

通用约定：**每个字段恒在场**；标「必填」= 值不得为 `null`；标「可选」= 允许 `null`；`ts` = §2.4 第 4 条格式。「AMR 来源」给表.列（按 `28a33e4` 的 `src/jl/schema.sql`），供 AMR仁德 核；与 AMR 列名不一致处是有意的（English canonical、一词一义），见 §9。

### 4.1 `person`（AMR `persons`，8,094 行）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"person"` | 必填 | — | |
| `id` | str | 必填 | `persons.id` | **标识类**（由第一个端点派生，`_new_person_id`；.178 上 4,840 / 8,094 以 `wxid_` 或数字开头）。Metis：只进 `aliases` 作 `amr:<id>`（IM-S 第 6 条） |
| `name` | str \| null | 可选 | `persons.name` | 显示类；`''` → `null`。Metis 写 `name` |
| `name_by` | `"user"` \| `"engine"` | 必填 | `persons.name_by` | `'user'` → `user`（人定的显示名，富化不覆盖）；`''` → `engine` |
| `aliases` | array\<str\> | 必填（可空数组） | `persons.aliases`（JSON） | **混合类**：含名字别名，也含形如 wxid / 11 位数字的句柄（调研 F.3「涉及 3,797 人」）。原样透传、不分类；分类归 Metis（IM-S：句柄形态的值作弱档 ContactPoint 候选，其余作名字别名）。`--redact` 下每个值哈希（fail-closed，§5.4） |
| `watch` | bool | 必填 | `persons.watch` | 本人关注标记（事实，Metis 自决用途） |
| `created_at` | ts | 必填 | `persons.created_at` | |
| `updated_at` | ts | 必填 | `persons.updated_at` | 增量水位（§7.2） |
| `last_contact_at` | ts \| null | 可选 | 推荐 `MAX(conversations.last_activity_at)`（该人名下私聊） | 归一队列排序（#64 第 3 条：近 365 天约 1,200 人优先）。来源列**待 AMR仁德 定**（§10 ②）；无会话 → `null` |
| `accounts` | array\<int\> | 必填（可空数组） | `conversations.account_id`（`type='private'` 且 `person_id` = 本人） | 升序去重。与 `self_identity.persona_raw` 合起来是 Metis 推 `domain_hint`（工作 / 生活 / 公共分群）的**事实输入**（#64 第 3 条）；契约不直接给 `domain_hint`（那是判断） |
| `sources` | array\<str\> | 必填（可空数组） | 派生 | = 本人全部 `contact_point.source` 的去重升序集合（便利字段；消费方按 `contact_point` 重算校验，§8.1 C9） |

**不导出**：`company`（投影，由 `employment` 重建）· `category` / `threshold_days`（已退役）· `person_intel:*`（情报正文）· 任何分数 / 热度（调研 F.3「不导入」）。

### 4.2 `contact_point`（AMR `channels` ∪ `conversations(type='private')` 对端，去重后约 8,183）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"contact_point"` | 必填 | — | |
| `person_id` | str | 必填 | `channels.person_id` / `conversations.person_id` | 必须可解到本次导出的 `person`（§2.3） |
| `kind` | enum | 必填 | `channels.kind` / `conversations.platform` | `wechat` \| `phone` \| `email` \| `feishu` \| `imsg` \| `whatsapp` \| `wecom` \| `xhs` \| `unknown`。**AMR 的 `gmail` 映到 `email`**；认不出的落 `unknown`，不得自创 |
| `value_raw` | str \| null | 可选 | `channels.identifier` / `conversations.chat_id` 原文 | 标识类。同一规范值有多个原文时取字节序最小者；`--redact` 下 `null` |
| `value_normalized` | str | 必填 | `db._canon_identifier(kind, identifier)`（`db.py:1272`） | 标识类。微信去 PowerData 设备后缀（`wxid_<base>_<4–12 位>` → `wxid_<base>`）；电话 = `canon_phone`（只留数字、去 `86` 国家码与国内长途 `0`）；邮箱小写（`contacts.canon`）。规则版本 = `header.rules.identifier_canon` |
| `value_e164` | str \| null | 可选 | 派生 | **仅 `kind=phone`**：`value_normalized` 为 **11 位且以 `1` 开头** → `"+86" + 11 位`（规则 `cn-mobile-11/1`，作业单 §2）；否则 `null`。非电话恒 `null` |
| `unparsed` | bool \| null | 可选 | 派生 | `kind=phone`：`value_e164 == null` ⇔ `true`（非中国 / 短号，.178 约 36 个；Metis 定前默认标 `unparsed`、不建 ContactPoint、进确认卡，PR #380 §2.4.4）；非电话恒 `null` |
| `source` | enum | 必填 | 见 §9.2 | `conversation_counterpart`（私聊对端）\| `roster_friend`（通讯录好友）\| `selfstated_capture`（对方自述、引擎捕获）\| `user_link`（人工挂会话 / 加端点）\| `user_merge`（随人工合并搬来）\| `dedup_batch`（规则批次，批次名在 `batch`；= 作业单 §3 的 `batch_158a`）\| `phone_suffix_match`（电话尾号匹配，位数在 `match_digits`）\| `unknown`。**推不出就写 `unknown`，不猜**（§10 ①） |
| `by` | `"user"` \| `"engine"` \| `"unknown"` | 必填 | `channels.meta.by` / 事件 actor | 这条「人 ↔ 句柄」归属是谁断言的 |
| `confirmed_at` | ts \| null | 可选 | `channels.meta.captured_at` / `events(kind='link').ts` / `contact_captures.at` | 人或引擎断言归属的时刻；`channels` 本身**无时间戳列**（调研 A.1），推不出写 `null`（§10 ①） |
| `evidence_ref` | str \| null | 可选 | `channels.meta.evidence_id` | `"amr-evidence:<evidence.id>"` 指针；**不导出引文**（引文含号码，作业单 §2「不导出」） |
| `match_digits` | int \| null | 可选 | `phone.tail_match`（`_MIN_TAIL = 7`） | 仅 `source=phone_suffix_match`：匹配的尾号位数。Metis 按 #64 第 2 条只当**弱**信号 |
| `batch` | str \| null | 可选 | `person_merges.batch` | 仅 `source=dedup_batch`（如 `"158-a"`） |
| `account_id` | int \| null | 可选 | `conversations.account_id` | 仅会话来源：哪个本人账号下的私聊 |
| `pinned` | bool | 必填 | `channels.pinned` | 本人钦点的首选发送端点；会话来源无此列 → `false` |

> **为什么是「`channels` ∪ 私聊会话对端」而不是一张 handles 表**：AMR **没有** `handles` / `endpoints` 表（EL仁德 2026-10-21 Q11 没找到是对的）。端点 = `channels(person_id, kind, identifier)` 行 **∪** `conversations(type='private', person_id, platform, chat_id)` 的对端，去重判据 `db.endpoint_owner_index`（`db.py:1690`，`_endpoint_claims` 把两处按 `(kind, 归一标识)` 合并，`db.py:1650`）。本契约的 `contact_point` 就是这个去重后的并集（.178 去重后 8,183：微信 7,940 / 电话 236 / 邮箱 7）。

### 4.3 `merge_record`（AMR `person_merges`，4,636 行；只要摘要，不要全文日志）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"merge_record"` | 必填 | — | |
| `id` | str | 必填 | `person_merges.id` | 十进制字符串 |
| `action` | `"merge"` \| `"self"` | 必填 | `person_merges.action` | `self` = 「这个联系人其实是本人的号」（#257，`keep_id=''`） |
| `survivor_id` | str \| null | 可选 | `person_merges.keep_id` | 保留方；`action=self` 时 `null`。消费方把 `amr:<merged_id>` 挂到 survivor 的别名上（IM-S / 调研 F.3 第 2 行） |
| `merged_id` | str | 必填 | `person_merges.drop_id` | 被合并方；生效中的合并其 id **不在** `person` 里 |
| `by` | `"user"` \| `"engine"` | 必填 | 派生 | `batch != ''` → `engine`（规则批次，规则经班迪审定仍记 engine，判断归 Metis）；否则 `user`（认人队列 ✓ / CLI `--commit`） |
| `batch` | str \| null | 可选 | `person_merges.batch` | 如 `"158-a"`（4,630 条） |
| `rule` | str \| null | 可选 | `person_merges.evidence.rule` | 如 `"shell_vs_conversation_raw_equal"` |
| `reason` | str \| null | 可选 | `person_merges.reason` | 原样 |
| `evidence` | obj \| null | 可选 | `person_merges.evidence`（JSON） | 判定依据**快照**（如共享的端点），满足 #64 第 4 条「带快照而非引用」；形状由 AMR 定，消费方当不透明对象入血缘；`--redact` 下 `null` |
| `merged_at` | ts | 必填 | `person_merges.merged_at` | |
| `undone_at` | ts \| null | 可选 | `person_merges.undone_at`（`0` → `null`） | 非空 = 已撤销；撤销的合并不约束 `merged_id` 的存在性 |

**不导出**：`drop_row` / `keep_before` / `keep_after` / `moved` / `removed` / `changed` / `settings`（全文日志 3.3 MB，含整行 PII，撤销用，Metis 不需要）· `actor`（运维账号名）。

### 4.4 `negative_sample`（AMR `merge_blocks`，22 行）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"negative_sample"` | 必填 | — | |
| `kind` | str \| null | 可选 | `merge_blocks.kind` | 端点种类；.178 有 2 行 `''` → `null`，交人确认（调研 F.3） |
| `a_id` | str | 必填 | `merge_blocks.id_a` | 规范化标识（小者在前，AMR 已排）；标识类 |
| `b_id` | str | 必填 | `merge_blocks.id_b` | 同上；`a_id != b_id` |
| `a_person_id` | str \| null | 可选 | 导出时按 `endpoint_owner_index` 解 | 便利字段：这个标识**此刻**归谁；解不出 `null`。消费方以自己的 `contact_point` 索引重解为准 |
| `b_person_id` | str \| null | 可选 | 同上 | |
| `reason` | str \| null | 可选 | `merge_blocks.reason` | 原样（如 `"user: 认人队列 ✕"`、detach 写的说明） |
| `created_at` | ts | 必填 | `merge_blocks.created_at` | |

Metis：建 `not_same_as`（`by=user, source=amr`，IM-2），是归一的既有人工裁定（#64 第 3 条）。

### 4.5 `organization`（AMR `orgs`，16 行）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"organization"` | 必填 | — | |
| `id` | str | 必填 | `orgs.id` | 十进制字符串。Metis：**只作幂等键** `amr:org:<id>` 进 `aliases`，不是同一性键（RS-0 §7.1 第 1 条）；`object_key` 为代理键 `org:<uuid4>` |
| `name` | str | 必填 | `orgs.name` | 显示类 |
| `aliases` | array\<str\> | 必填（可空数组） | `orgs.aliases`（JSON） | 全称 / 简称 / 被并进来那家的名字；显示类 |
| `kind_raw` | str \| null | 可选 | `orgs.kind` | AMR 中文自由值（企业 / 政府机关 / 事业单位 / 学校 / 协会 / 非营利 / 其他）原样；`''` → `null`；不翻译 |
| `parent_id` | str \| null | 可选 | `orgs.parent_id` | 上级单位（部门 → 单位）；Metis → `sub_organization_of`（不是同一性证据，RS-0 §2.2） |
| `by` | `"user"` \| `"engine"` | 必填 | `orgs.by` | .178 全部 `user` |
| `created_at` | ts | 必填 | `orgs.created_at` | |
| `merged_into` | str \| null | 可选 | `orgs.merged_into` | 非空 = 已并进另一家（墓碑；可拆回，`org_merges`）。消费方把 `amr:org:<id>` 挂到 `merged_into` 那家的别名 |
| `registration_no` | str \| null | 可选 | **AMR 无此列** → 恒 `null` | 预留位：统一社会信用代码 / 注册号（RS-0 候选键）。「契约没有注册号字段也可导入，全部走 medium / weak」（PR #378 发现分流 1） |
| `jurisdiction` | str \| null | 可选 | **AMR 无此列** → 恒 `null` | 预留位 |
| `domains` | array\<str\> \| null | 可选 | **AMR 无此列** → 恒 `null` | 预留位（邮箱域名候选键）。「未测得」= `null`，与「测得为空」`[]` 区分 |

**不导出**：`org_key`（AMR 的派生核心名，`web_intel.org_key`；Metis 有自己的 `org-name-canon/1`，两套规范化不混）· `org_intel:*` · `web_mentions`。`org_merges`（.178 为 0 行）本版不设类型，若将来非 0 以 minor 加 `org_merge_record`。

### 4.6 `employment`（AMR `org_affiliations`，**全部版本行**，.178 为 22 行 / 现行 21）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"employment"` | 必填 | — | |
| `id` | str | 必填 | `org_affiliations.id` | 十进制字符串 |
| `person_id` | str | 必填 | `org_affiliations.person_id` | 可解（§2.3） |
| `org_id` | str | 必填 | `org_affiliations.org_id` | 可解到 `organization`（含 `merged_into` 非空者） |
| `title` | str \| null | 可选 | `org_affiliations.title` | 显示类；`''` → `null` |
| `dept` | str \| null | 可选 | `org_affiliations.dept` | 部门文本；成体系的部门在 `organization.parent_id` |
| `state` | `"current"` \| `"former"` | 必填 | `org_affiliations.state` | |
| `by` | `"user"` \| `"engine"` | 必填 | `org_affiliations.by` | |
| `source` | str \| null | 可选 | `org_affiliations.source` | AMR 血缘：哪条规则 / 哪个入口写的（`company_field` 19 · `ui` 3），原样 |
| `evidence_ref` | str \| null | 可选 | `org_affiliations.evidence_id` | `"amr-evidence:<id>"`；.178 现行 21 行均为 `null` |
| `quote` | str \| null | 可选 | `org_affiliations.quote` | 原话**快照**（支撑这条任职的证据，#64 第 4 条）；`''` → `null`；`--redact` 下 `null`。是否导出**待 AMR仁德 定**（§10 ⑤） |
| `started_at` | ts \| null | 可选 | **AMR 无起止时间列** → 恒 `null` | 预留位；Metis `employed_by` 自然键 `(Person, Organization, started_at)` 遇 `null` 的处置归 RS-0 §7.2 第 5 条 |
| `ended_at` | ts \| null | 可选 | 同上 → 恒 `null` | 预留位 |
| `recorded_at` | ts | 必填 | `org_affiliations.at` | **这一行被写下的时刻，不是任职开始时刻**（一词一义，故不叫 `started_at`） |
| `superseded_by` | str \| null | 可选 | `org_affiliations.superseded_by` | 版本链：被哪一行取代 |
| `revoked_at` | ts \| null | 可选 | `org_affiliations.revoked_at` | 人 ✕（负样本：引擎不再加回同一对） |
| `revoked_by` | str \| null | 可选 | `org_affiliations.revoked_by` | `''` → `null` |
| `revoke_reason` | str \| null | 可选 | `org_affiliations.revoke_reason` | `''` → `null` |

**现行任职** = 同一 `(person_id, org_id)` 下 `superseded_by == null ∧ revoked_at == null ∧ state == "current"` 的那一行（AMR `schema.sql` 归属注释）。消费方重建只追加版本链（作业单 §2）。

### 4.7 `self_identity`（AMR `self_identities` ⋈ `accounts`，7 行）

| 字段 | 类型 | 必填 | AMR 来源 | 说明 |
|---|---|---|---|---|
| `type` | `"self_identity"` | 必填 | — | |
| `account_id` | int \| null | 可选 | `accounts.account_id`，按 `(platform == kind, canon(self_id) == canon(identifier))` 关联 | 解不到账号 → `null`（如仅登记为本人号、未接入的电话号） |
| `kind` | enum | 必填 | `self_identities.kind` | 同 §4.2 `kind` 枚举 |
| `value_normalized` | str | 必填 | `_canon_identifier(kind, identifier)` | 标识类 |
| `persona_raw` | str \| null | 可选 | `self_identities.persona` | AMR 中文值原样（自我 / AI分身 / 经营 / 工作 / 生活）；Metis 映到域是判断，归 Metis |
| `created_at` | ts | 必填 | `self_identities.created_at` | |

用途：消费方**不为它们建第三方 Person**（它们是本人），并用 `account_id × persona_raw` 推 `person.accounts` 的域提示。**不导出** `accounts.cred_ref` / `host` / `tool` / 任何凭据。

### 4.8 保留扩展位（v1 不输出）

- `knowledge_fact`（`knowledge_facts`，人的已确认事实 18 条）：Epic #62 本轮范围外（kickoff §2 ⑦）；若班迪定做，以 minor 加 `--with-facts` 开关与 `knowledge_fact` 类型，默认不输出（作业单 §2）。
- `org_merge_record`（`org_merges`，现 0 行）：见 §4.5。
- `matter_persons` / AMR 的事：范围外（调研待议 ④）。

---

## §5 PII 别名策略（#64 清单第 1 条）

### 5.1 值的分类

| 类 | 契约里的字段 | Metis 落点 | 可见性 |
|---|---|---|---|
| **标识类（identifier-class）** | `person.id` · `contact_point.value_raw` / `value_normalized` / `value_e164` · `merge_record.survivor_id` / `merged_id` · `negative_sample.a_id` / `b_id` / `*_person_id` · `employment.person_id` · `self_identity.value_normalized` · `contact_point.person_id` | `amr:<id>` 只进 `objects.aliases`（标识类别名 Identifier alias）；句柄经 Metis `handle-canon` 建 ContactPoint | **只对老板会话可见**（04 §2.4.3，PR #380；UI-0a 实现） |
| **显示类（display-class）** | `person.name` · `organization.name` / `aliases` · `employment.title` / `dept` | `name` 属性 / 名字别名 | 按对象的域与读权限（06 §7） |
| **混合类（mixed）** | `person.aliases[]`（名字与句柄形态混在一个数组） | 逐值分类归 Metis（IM-S）；分类前按标识类处理 | fail-closed：未分类即老板可见 |
| **自由文本（free text）** | `merge_record.reason` / `evidence` · `negative_sample.reason` · `employment.quote` / `source` · `*_raw` | 血缘 / 证据快照 | 可能含标识类值，与标识类同待 |

`organization.id` 不含个人信息，但按 RS-0 只作幂等键进 `aliases`（`amr:org:<id>`）。

### 5.2 仓 / issue / 日志的引用形态

- 仓、issue、交接文档、日志里**引用**某个 AMR 记录一律写 `amr:h:<sha256 前 12 位>`（#64 第 1 条，班迪 2026-10-18「Metis 里存原值，其他地方只用哈希」）。
- `--redact` 输出的 `h:<16 位>`（§5.4）与上式取同一 SHA-256 的前缀：前 12 位相同，可互相对照。

### 5.3 永不导出

消息正文 · 聊天名（`conversations.name`、`channels.label`、`channels.meta.remark`）· 附件 / 媒体路径 · 证据引文（`evidence.quote`，只给 `amr-evidence:<id>` 指针）· 人情报正文（`person_intel:*`、`web_mentions`）· 分数 / 热度 / 温度 · 令牌（`tokens`、`JL_WEB_TOKEN`）· 本人账号凭据（`accounts.cred_ref` / `host`）· `person_merges` 全文日志列 · 运维账号名（`actor`）。

### 5.4 `--redact`（规则 `sha256-16/1`）

- 标识类字段的值 → `"h:" + sha256(utf8(value)).hexdigest()[:16]`；`person.aliases[]` 每个值同法；`contact_point.value_raw` → `null`；`merge_record.evidence` / `employment.quote` → `null`；显示类不变。
- 引用字段（`*_person_id`、`survivor_id`、`merged_id`）与 `person.id` 用**同一函数**，哈希后仍可连接（join）。
- `header.pii_policy = "redacted"`；其余规则（排序、键序、计数）不变——排序键用**哈希前**的值还是哈希后的值？**定前默认：排序仍按 raw 值**，这样 redacted 与 raw 两份文件行序一致、可逐行对照（§10 ③ 请 AMR仁德 确认）。
- **诚实声明**：哈希一个低熵标识（手机号 10^11 空间）只是**化名（pseudonymization）**，不是匿名化；握有候选集者可反查。`--redact` 输出仍按「不进 gth 可读目录」处理（kickoff R2），只用于 dry-run 报告与样例。
- `error.samples` 不论 `pii_policy` **恒哈希**（§3.2）。

### 5.5 落盘与传输（给 EL仁德 的约束，非契约载荷）

raw 输出经 SSH 管道直接落到 `metis` 用户所有的 `0700` 目录、文件 `0600`，不经 `/srv/metis-in`（gth 可读）、不在 Mac 落盘（kickoff §3.3 IM-3、R2）；台账只记 `sha256` / 行数 / `watermark`。保留与备份口径按 Metis 04 §2.4.5（PR #380）。

---

## §6 证据映射到 Metis 三档（#64 清单第 2 条）——契约只传事实

契约**不含**任何档位字段。下表是**消费方（Metis 04 §2.4）的判断**，写在这里只为让 AMR仁德 核「这些事实字段够不够判」：

| 契约事实（本文件字段） | AMR 现状（调研 B.5） | Metis 三档输入（判断归 Metis） |
|---|---|---|
| `contact_point` 本身：`(kind, value_normalized)` 归 `person_id` | 唯一判据 `endpoint_owner_index`，不变式 0 | ContactPoint 事实 + `contact_of` 链接；归属可信度看下面各行 |
| `source=selfstated_capture` ∧ `evidence_ref` 非空 ∧ `by=engine` | 引擎按证据（`identity=confirmed`、引文闸核实）直接写 `channels` | **strong**（对话中明确交换过的手机号 / 邮箱 / 微信号）；进班迪每日清单 |
| `source=user_link` / `user_merge` ∧ `by=user` | 人工 ✓ | **strong**（人工裁定） |
| `source=dedup_batch`、`rule=shell_vs_conversation_raw_equal` | 原始标识逐字相等 + 被并方是空壳；班迪 2026-10-09 审定规则 | **strong**（同一个号） |
| `source=conversation_counterpart` / `roster_friend` | 会话对端 / 通讯录好友 | 句柄事实本身；人 ↔ 句柄归属按 `by` |
| `source=phone_suffix_match`，`match_digits ≥ 7` | AMR 自动挂会话（强度 3） | **weak**（#64 第 2 条：尾号相同只算弱；不自动关联，进候选） |
| 同名（`person.name` 相等） | AMR 认人队列 token 分 2 | **weak** |
| 同名 ∧ 同一 `employment.org_id` | AMR 同名 + 公司备注 各 2 | **medium**（「时间对得上」= 证据时间戳落在 Encounter `[started_at, ended_at]` 内，**不以同群代替**；本契约不含群，故不会误用） |
| `negative_sample` | `merge_blocks` | `not_same_as`（阻止规则） |
| `merge_record`（生效中） | `person_merges` | `amr:<merged_id>` 作 survivor 的历史别名；不是新的归一候选 |

AMR 的强度分（`suggest_person_merges` 的 1 / 2 / 3 / 5）**不导出**，避免 Metis 误把来源系统的分当证据。

---

## §7 幂等与增量（#64 清单第 3 条「完整性」· 作业单 §7）

### 7.1 全量为准

- 每次全量导出是**一份快照（snapshot）**。消费方以 `person.id` / `organization.id` / `employment.id` / `merge_record.id` 幂等 upsert；`contact_point` 以 `(person_id, kind, value_normalized, source)` 幂等；`negative_sample` 以 `(kind, a_id, b_id)` 幂等。
- 消费方对两次全量做差：**新增 / 变更 / 消失**三类进 Dry-run Diff Report（04 §2.4.1）。
- 规模：.178 全量约 3–5 MB、秒级到分钟级（调研 F.5）；**每日全量比对成本很低**，是 v1 的推荐节奏（kickoff R6「IM-3 每日全量比对 + 漂移读数」）。

### 7.2 增量（`--since`，可选能力）

- 语义：输出 `person.updated_at >= since` 的人**及其全部** `contact_point` 与 `employment`；`merge_record` 取 `merged_at >= since ∨ undone_at >= since`；`negative_sample` 取 `created_at >= since`；`organization` 与 `self_identity` **恒全量**（行数小）。`header.mode="incremental"`、`since` 回显、`counts` 为增量行数。
- 增量**只作加速**：`channels` 无时间戳、`contact.reject` 物理删 `channels` 行（调研 A.3），增量**看不见删除**；消费方仍须定期全量。
- v1 是否实现待 AMR仁德 定（§10 ④）；不实现则 `--since` → 退出码 2。

### 7.3 删除、拆分、撤销在 AMR 侧的表达（定前默认）

| AMR 事件 | 导出里怎么看见 | 消费方动作 |
|---|---|---|
| 合并（merge） | `merged_id` 从 `person` 消失 + 出现生效中的 `merge_record` | `amr:<merged_id>` 挂到 survivor 别名；不新建 Person |
| 撤销合并（unmerge） | `merge_record.undone_at` 非空；`merged_id` 可能重新出现在 `person` | 按 Metis 04 §2.4 的 Split 路径交老板（合并拆分属 0 号宪法第五条第二款第（二）项第 7 目，**消费方不自动拆**） |
| 拆分 / 脱离（detach / split） | 出现**新** `person.id`（旧 id 不复用）+ 新 `negative_sample` | 新 Person 进归一候选；`not_same_as` 照建 |
| 删联系方式（`contact.reject`） | 该 `contact_point` 从下次全量消失；`contact_captures` 有 `rejected` 行但**本版不导出** | 全量比对「消失」→ 报告给老板，**不自动删**（用户级「只增不删」；Metis 以撤回事件表达） |
| 人物理删除 | AMR 现版本不删 persons（除合并） | 若全量比对发现 id 消失且无对应 `merge_record` → 报告，不自动删 |

**v1 不设墓碑行（tombstone）**：删除 / 消失由消费方全量比对发现并交人；这是定前默认，AMR仁德 若认为应导出 `contact_captures.state=rejected` 作负样本，以 minor 加 `contact_rejection` 类型。

---

## §8 校验清单

### 8.1 消费方校验清单（Metis IM-2 `--dry-run` 第一段；`scripts/conformance.py` 对 `fixtures/amr-graph-export/*.jsonl` 跑同一套）

| # | 校验 | 失败处置 |
|---|---|---|
| C1 | 第一行是 `type="header"`，`schema` 以 `amr-graph-export/` 开头且 major = 1；`status="ok"` | 退出，整份丢弃 |
| C2 | 每行可解析为 JSON 对象；`type` ∈ 七类（未知 `type` 跳过并计数，minor 兼容）；类型块顺序与块内排序符合 §2.4 | 排序不符 = 非确定性输出，丢弃 |
| C3 | 每条记录键序与键集 = §3 / §4 表（所有键在场） | 丢弃 |
| C4 | `header.counts[type]` = 该类型实际行数，七个键齐 | 丢弃（不全如实标明） |
| C5 | `person.id` 唯一；`organization.id` / `employment.id` / `merge_record.id` 各自唯一；`contact_point` 自然键唯一 | 丢弃 |
| C6 | 每个 `contact_point.person_id`、`employment.person_id` 可解到 `person`；`employment.org_id`、`organization.parent_id` / `merged_into`、`employment.superseded_by` 可解 | 丢弃 |
| C7 | **不变式**：同一 `(kind, value_normalized)` 不出现在两个 `person_id` 下；`header.invariants.persons_sharing_endpoint == 0` | 丢弃 |
| C8 | 生效中的 `merge_record`（`undone_at == null`，`action=merge`）：`merged_id` ∉ `person`；`survivor_id` 沿 `merge_record` 链（A→B→C）可解到一个在场的 `person`，链无环 | 丢弃 |
| C9 | `person.sources` = 其 `contact_point.source` 去重升序；`person.accounts` = 其 `contact_point.account_id`（非 null）去重升序 | 丢弃（便利字段与真相不一致） |
| C10 | `kind=phone`：`value_e164` 匹配 `^\+\d{6,15}$` 或 `null`；`unparsed` ⇔ `value_e164 == null`；非电话 `value_e164` 与 `unparsed` 恒 `null`；`match_digits` 仅在 `source=phone_suffix_match` 非空；`negative_sample.a_id != b_id` | 丢弃 |
| C11 | 时间戳匹配 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`；枚举值落封闭集；`by` ∈ 允许集 | 丢弃 |
| C12 | `pii_policy="raw"` 时文件位置符合 §5.5（运维核，非解析器） | EL仁德 停止导入 |

C1–C11 全绿 + 退出码 0 → 进入 Dry-run Diff Report；任何红 → 不写库、把失败项与计数（不含标识值）交 EL仁德 转 AMR仁德。

### 8.2 生产方自核清单（AMR仁德 实现 `jl graph export` 时逐条打勾）

- [ ] P1 **确定性**：同一库快照连跑两次，除 header 外逐字节相同（§2.4 验法）；`body_sha256` 相等。
- [ ] P2 **只读**：`mode=ro` 打开；不写任何表、不写 `events`；不调用 LLM。
- [ ] P3 **退出码**：0 / 2 / 3 按 §2.2；退出 3 只给 header + `error`，无数据行；`--since` 不支持时退出 2。
- [ ] P4 **计数**：`header.counts` 七键 = 实际行数；全量下与调研 C 节 / EL Q11 同口径（person 8,094 · organization 16 · employment 全部版本行 22 · negative_sample 22 · merge_record 4,636 · self_identity 7；允许之后新增的差额）。
- [ ] P5 **不变式**：导出前跑 `shared_endpoints`；非 0 → 退出 3。
- [ ] P6 **PII**：stderr、测试夹具、日志、仓里零真实标识；测试用合成值；`--redact` 按 §5.4；`error.samples` 恒哈希。
- [ ] P7 **不导出项**（§5.3）一项不漏；`channels.label` / `conversations.name` / `meta.remark` 不出现。
- [ ] P8 **空值**：`''` / `0` 按 §1 第 5 条转 `null`；每个键恒在场。
- [ ] P9 **时间戳**：Unix 秒 → RFC 3339 UTC；`undone_at=0` → `null`。
- [ ] P10 **规范化**：`value_normalized` 用 `db._canon_identifier`（与入列 / 去重同一函数，不另写一份）；`gmail` → `email`；`value_e164` 只认 11 位首 `1`。
- [ ] P11 **source 推断**：推不出写 `unknown`，不猜（§10 ①）。
- [ ] P12 **排序与键序**：§2.4；JSON 序列化参数一致。
- [ ] P13 **fixtures**：`fixtures/amr-graph-export/*.jsonl` 能被 AMR 的测试当黄金用例读入；AMR 自己的输出能过 `scripts/conformance.py` 的 `validate_graph_export`。
- [ ] P14 **性能**：.178 线上库（706 MB，WAL）分钟级以内、不影响 `amr-web.service`（作业单 §5 第 4 条）。
- [ ] P15 **发布**：按 AMR 仓发布流程出版本，把版本号 / 提交与调用方式告知 EL仁德（`DEPLOYED_REF` 核对）。

---

## §9 来源映射附录（AMR `28a33e4` · 供 AMR仁德 核）

### 9.1 表 → 记录类型

| 记录类型 | AMR 表（`src/jl/schema.sql` 行号） | 关键列 | 备注 |
|---|---|---|---|
| `person` | `persons`（:7） | `id` TEXT PK · `name` · `name_by` · `aliases` JSON · `watch` · `created_at` · `updated_at` | `category` / `threshold_days` 已退役；`company` 是投影 |
| `contact_point` | `channels`（:20）**∪** `conversations`（:45，`type='private' ∧ person_id IS NOT NULL ∧ chat_id != ''`） | `channels(person_id, kind, identifier, pinned, meta JSON)`，UNIQUE `(person_id, kind, identifier)`；`conversations(account_id, platform, chat_id, person_id, last_activity_at)`，UNIQUE `(account_id, chat_id)` | 去重判据 `db._endpoint_claims` / `endpoint_owner_index`（`db.py:1650–1700`）；归一 `db._canon_identifier`（`db.py:1272`）；电话 `channels/phone.py canon_phone` / `tail_match`（`_MIN_TAIL = 7`）；**无独立 handles / endpoints 表** |
| `merge_record` | `person_merges`（:709） | `id` · `action` · `keep_id` · `drop_id` · `batch` · `actor` · `reason` · `evidence` JSON · `merged_at` · `undone_at`（0 = 生效） | 全文日志列不导出 |
| `negative_sample` | `merge_blocks`（:489） | `kind` · `id_a` · `id_b`（canon，小者在前）· `reason` · `created_at`，UNIQUE `(kind, id_a, id_b)` | 无整数主键 |
| `organization` | `orgs`（:783） | `id` INTEGER PK · `name` · `org_key` · `aliases` JSON · `kind` · `parent_id` · `by` · `created_at` · `merged_into` | 唯一索引 `(org_key, COALESCE(parent_id,0)) WHERE merged_into IS NULL`（:794） |
| `employment` | `org_affiliations`（:801） | `id` · `person_id` · `org_id` · `title` · `dept` · `state` · `by` · `source` · `evidence_id` · `quote` · `at` · `superseded_by` · `revoked_at` · `revoked_by` · `revoke_reason` | 只追加版本链；无 FK |
| `self_identity` | `self_identities`（:332）⋈ `accounts`（:32） | `self_identities(kind, identifier, persona)` UNIQUE `(kind, identifier)`；`accounts(account_id, platform, self_id)` | `cred_ref` / `host` / `tool` 不导出 |
| header `watermark` | `persons.updated_at` max · `events`（:361）`id` max | | `events` 只读取 max，不写 |
| （不导出） | `knowledge_facts`（:556）· `contact_captures`（:736）· `evidence`（:680）· `evidence_sources`（:669）· `org_merges`（:841）· `matter_persons`（:276）· `web_mentions`（:645）· `app_settings` KV `person_intel:*` | | 见 §4.8 / §5.3 |

### 9.2 `contact_point.source` 的推断来源（供 §10 ① 讨论）

| `source` | AMR 里能看到的痕迹 | 推断可靠度 |
|---|---|---|
| `conversation_counterpart` | 行来自 `conversations(type='private')` 对端 | 确定 |
| `selfstated_capture` | `channels.meta = {by:"engine", evidence_id, captured_at}`（`contacts._add_channel`）；`contact_captures.state='captured'` | 确定；`confirmed_at = meta.captured_at`、`evidence_ref = meta.evidence_id` |
| `user_link` | `db.set_conversation_person` 学到的端点（`upsert_channel` 不带 meta）+ `events(kind='link', actor='user', detail.learned = chat_id)` | 可由事件反推（13 条）；`confirmed_at = events.ts` |
| `roster_friend` | `channels/fullwechat.fetch_contacts` 入列的 `channels` 行（meta 含 `remark` / `company` 等通讯录字段或为空） | 中：与 `user_link` 同为「无 by 的 channel 行」，靠 meta 键区分 |
| `user_merge` | `person_merges.moved` 里 `{table:"channels", rowids}` 指向的行 | 可由合并日志反推；`confirmed_at = merged_at` |
| `dedup_batch` | 同上且 `person_merges.batch != ''` | 同上 |
| `phone_suffix_match` | `conversations(platform='phone')` 对端与本人 `channels(kind='phone')` 不逐字相等但 `tail_match` 为真（`db._match_person`） | 导出时可重算；`match_digits` = 公共后缀位数 |
| `unknown` | 以上都推不出 | 兜底，不猜 |

---

## §10 待 AMR仁德 定（≤ 5 条；每条带消费方推荐与定前默认）

| # | 问题 | 消费方推荐 | 定前默认（fail-closed） |
|---|---|---|---|
| ① | **`contact_point.source` / `by` / `confirmed_at` 的推断口径**：按 §9.2 从 `channels.meta`、`events(kind='link')`、`person_merges.moved`、`tail_match` 重算，还是 v1 只分 `conversation_counterpart` / `selfstated_capture` / `unknown` 三档 | 按 §9.2 全推；推不出的写 `unknown` + `confirmed_at=null`，并在 stderr 给各 `source` 的计数 | 三档：`conversation_counterpart`（会话对端）/ `selfstated_capture`（meta.by=engine）/ `unknown`；`by` 除 engine 捕获外写 `unknown` |
| ② | **`person.last_contact_at` 的来源列**：`MAX(conversations.last_activity_at)`（EL Q11 用此口径：近 365 天 1,211 人）还是 `MAX(messages.ts)`（调研 C 用此口径：1,202 人） | `conversations.last_activity_at`（有索引 `idx_conv_activity`，不扫 33 万行消息表；与 EL 基线一致） | 同推荐 |
| ③ | **`--redact` 的排序键**：按 raw 值排（redacted 与 raw 两份行序一致、可逐行对照）还是按哈希值排（redacted 文件自洽、不泄露 raw 顺序） | 按 raw 值排 | 同推荐 |
| ④ | **`--since` 增量是否进 v1** | **v1 不做**：全量 3–5 MB、每日全量比对成本低（§7.1）；header 仍带 `watermark` 供将来；`--since` 给了即退出 2 | 不做 |
| ⑤ | **`employment.quote` 是否导出**（任职原话快照，#64 第 4 条「带快照」 vs 作业单 §2「引文不导出」——后者针对含号码的联系方式引文） | **导出**：它支撑 `employed_by` 链接的证据，.178 现行 21 行里 19 条来自 `company_field`、quote 多为空；`--redact` 下置 `null` | 导出 |

**已由起草者按 schema 核定、不占席位（AMR仁德 只需确认）**：端点 = `channels ∪ conversations(private)`、无 handles 表（§4.2 注）；负样本表 = `merge_blocks`（§4.4）；机构主键 = `orgs.id` INTEGER → 字符串，Metis 只作幂等键（§4.5）；AMR 无 `registration_no` / `started_at` / `ended_at` 列 → 恒 `null`（§4.5 / §4.6）；`undone_at=0` → `null`；`gmail` → `email`。

---

## §11 版本与变更

- **schema** `amr-graph-export/1`，本文件 **v1.0（消费方草案 rev0）**。major（`/2`）= 破坏性，另开文件；minor = 加字段 / 加 `type` / 加枚举值，消费方忽略未知项（§1 第 8 条）。
- **与 `consumers.json` 的关系**：AMR 钉在 `v0.13.0`（契约仓最新 tag `v0.14.0`，含 0 号宪法 v3）；本契约合入后发 tag 会按 `consumers.json` 给 AMR 开 bump PR——**是否借此升级 vendor 副本由 AMR仁德 定**（作业单 §1 第 3 条）。本 PR 不改 `consumers.json`、不改 `CODEOWNERS`。
- **fixtures**：`fixtures/amr-graph-export/sample-small.jsonl`（11 行，覆盖全部七类）· `sample-edge.jsonl`（16 行，边界）· `README.md`；`scripts/conformance.py` 的 `validate_graph_export` 对它们跑 §8.1 C1–C11（CI 闸）。
- **Metis 侧对应**：`ImportFromSource` 五格（04 §2.4.1，PR #380）读本契约；`amr:<id>` 只进 `aliases`、名字写 `name`、`unparsed` 电话、Import Inbox、Dry-run Diff Report；机构按 RS-0（04 §7.1 / §7.2，PR #378）：`amr:org:<id>` 幂等键、同名只到 medium、不自动合并。
- **切换路径**：AMR仁德 审 rev0 → Metis仁德 出 rev1 → 非作者 fresh agent 对抗审（GOVERNANCE §2）→ 班迪 merge + tag → AMR仁德 实现 `jl graph export`（IM-1）∥ Metis仁德 实现导入器（IM-2，按 fixtures 开工）→ EL仁德 现场 IM-3（dry-run → 班迪 Decision → 写入）。

---

## §12 宪法对账（0 号宪法 v3）

- **第二条第四款（One Ontology）**：AMR 的合并、负样本、`self` 退役原样带入 Metis；Metis 不重做 AMR 已有的人工裁定，也不被 AMR 的引擎分左右（§6）。✅
- **第五条第二款第（二）项第 7 目（合并或拆分人与组织由本人逐项放行）**：本契约只**搬运**裁定，不触发任何合并 / 拆分；消费方遇撤销合并、机构同名等情形进确认卡交老板（§7.3、RS-0 定前默认不自动合并）。✅
- **第七条第一款（看得见 / 停得下 / 接得过 / 有记录）**：导出是只读 CLI，无长期进程、无对外动作；每份导出 `header` 自述来源、规则版本、计数、不变式；台账记 sha256 / 行数 / 水位线。✅
- **第八条第四款（校验不能完成视为不允许）**：不变式失败 → 退出 3 不给数据；`source` 推不出写 `unknown` 不猜；消费方 C1–C11 任一红即不写库。✅
- **第九条（算料归人、不静默丢失、推算可溯源、外流以必要为限）**：计数与不变式让「少了」可判；每条带 `by` / `source` / `rule` / `evidence_ref`，头记录带 `rules` / `source.amr_version`；只导出身份层所必要的字段，消息正文、引文、情报、凭据一律不出（§5.3）；raw 输出不离开本人控制的两台主机（§5.5）；不调用 LLM。✅
- **第九条第二款（原件只追加）**：导出不改写 AMR；消费方对「消失」只报告不删（§7.3）。✅
- **档位**：本契约不涉及任何对外动作，不引入档位词汇。✅

---

## 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0 rev0 | 2026-10-27 | 消费方草案：Metis仁德 代起草（班迪「⑨ 批」），待 AMR仁德 审。七类记录 + header / error；退出码 0 / 2 / 3；确定性规则；PII 四类与 `--redact`；三档映射只传事实；全量为准、`--since` 可选；消费方 C1–C12 / 生产方 P1–P15；来源映射附录按 AMR `28a33e4`；待定 5 条。 |

— **Metis仁德**（Claude Fable 5.1）起草 2026-10-27 · 待 **AMR仁德** 审定 · 抄送 **EL仁德**
