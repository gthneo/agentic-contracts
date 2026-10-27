# fixtures/amr-graph-export — `amr-graph-export/1` 导出流样例（JSONL，非单条信封）

这两份是 `graph/amr-graph-export.md` 的**可执行一致性测试**：每份都是一次完整的 `jl graph export` 标准输出
（首行 header + 记录行），`scripts/conformance.py` 的 `validate_graph_export` 对它们跑契约 §8.1 的
C1–C11（header 先行 / 计数 = 行数 / 键序与排序 / id 唯一 / 外键可解 / 同一端点不跨人 / 合并链可解 /
便利字段与真相一致 / 电话 E.164 与 `unparsed` 互斥 / 时间戳与枚举）。

- **消费方**（Metis `ImportFromSource --dry-run`）：先吃下这两份、退出码 0，再接真实导出。
- **生产方**（AMR `jl graph export`）：把它们当黄金用例读入测试；自己的输出也要能过同一个 `validate_graph_export`。
- **负向样例**由各消费方自带（本目录只放合规样例，与 `../message-canonical/` 同口径）。

| 文件 | 行数 | 覆盖 |
|---|---|---|
| `sample-small.jsonl` | 11 | 全部七类各至少一条：两人（`wxid_` 派生 id 与数字派生 id 各一）· 微信 / 电话（可转 E.164）/ 邮箱（大小写归一）三种端点 · 一条 `158-a` 批次合并 · 一条负样本 · 一个机构 · 一条现行任职 · 一条本人身份 |
| `sample-edge.jsonl` | 16 | 边界：**无名字的人**（`name:null`、`aliases:[]`）· **同一人多句柄**（两个微信号其一带 PowerData 设备后缀、一个非中国电话；见于两个账号）· **非中国号码**与**短号**（`value_e164:null` + `unparsed:true`）· `phone_suffix_match`（`match_digits:7`）· `action="self"` 的合并（`survivor_id:null`）· **已撤销的合并**（`undone_at` 非空）· **`kind` 为空的负样本** · **机构无注册号 + 上下级**（部门 → 单位）· **已结束任职**（版本链 `superseded_by` + `revoked_*`）· 未接入账号的本人电话（`account_id:null`） |

## 公开仓纪律（零真实 PII）

全部**合成化名**：人 = 甲 / 乙 / 丙；机构 = 甲科技 / 乙集团；wxid = `wxid_example*` / `wxid_selfexample*`；
电话 = `+86 138/139 0000 xxxx` 段、`+1 415 555 0100`（北美保留测试段）、`12345`；邮箱 = `example.com`。
`header.source.amr_commit` 用 AMR 公开仓的提交号 `28a33e4`（非敏感）。**真实 wxid / 号码 / 姓名 / 机构名绝不进本目录**；
由真实记录改写的样例须先做本地隐私审计再推（`gthneo/metis#323` 教训）。

> 语义口径（契约 §2.4 确定性、§5 PII、§7 增量）见 `../../graph/amr-graph-export.md`；本目录不另解释。
