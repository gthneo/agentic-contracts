# agentic-contracts — 生态契约真相源

本仓是 **agentic 消息 / 内容路由生态**所有**跨系统契约的唯一真相源**（single source of truth）。
被 AMR（AgenticMessageRouter）、AMP（Agentic Marketing Platform）、fullwechat、PowerData
以及其它后端/通道/开发者与 Agent 共同依赖。

> 一句话：**契约住在这里，实现住在各自的仓。** 任何一方对接口语义有疑义 →
> 不自行解释、不在各自仓硬编码推断口径，而是**回到本仓提 PR 改契约**，再按新版实现。

---

## 0 号契约（根 · 先读）

**[`00-CONSTITUTION.md`](00-CONSTITUTION.md) — 服务于人的 Agent 宪法**，是本仓**最高、统领一切**的契约。
下面所有技术契约（message / send-target / group-metadata / moments / control-and-voice / 版本规范）
都为它服务、可追溯到它：**人在回路、赋能不替代、演进不革命、积德；信息（算料）是 AI 时代的生产资料，
契约是让它标准化、可流通、可增值的方式。** 任何契约/实现**违背 0 号契约，无论多高效，不予采纳**。

> **治理铁律·先读：[`GOVERNANCE.md`](GOVERNANCE.md)** —— 单账号 = 无身份分权 → 必须**机器强制（CI）+
> agent 级分权（作者 agent ≠ 审查 agent）**，让契约/宪法漂移在结构上不可能。改契约前务必读它。

---

## 这仓是什么 / 不是什么

- **是**：通道无关的**接口契约 / 信封 schema / 能力声明 / 错误码 / 版本化规则**。
  纯文档（Markdown spec），是各实现仓的「法律」。
- **不是**：任何一方的实现代码。实现住在 AMR 仓（`src/jl/...`）、fullwechat 仓、
  PowerData 仓等；本仓只定义它们之间**说好的话**。

---

## 谁拥有谁改（ownership model）

**王总钦定：AMR统一拥有所有业务契约**，包括 moments-publish——不按"谁起草谁持有"分散，
而是收归 AMR 一处，保证口径一致、不漂移。唯一例外是 `ops-agent/`（运维契约），它约束的是
"怎么运维 fullwechat 后端自己"，由 **fullwechat 持有**。

| 目录 | 契约 | owner-reviewer |
|---|---|---|
| `message/` | 消息规范化信封（canonical） | AMR / @gthneo |
| `send-target/` | 冷会话自动翻出发送 | AMR / @gthneo |
| `group-metadata/` | 群成员名册 + 群 meta | AMR / @gthneo |
| `moments/` | 朋友圈读+点赞（read-like）+ 发布广播（publish） | AMR / @gthneo |
| `control-and-voice/` | 人机控制权互斥 + 口吻喂养 | AMR / @gthneo |
| `ops-agent/` | fullwechat 后端可观测/运维契约 | **fullwechat 持有** |
| `VERSIONING.md` | 全仓版本化 + 兼容矩阵规则 | AMR / @gthneo |

权威映射以仓根 `CODEOWNERS` 为准（GitHub 会按它自动派 reviewer）。

---

## PR 工作流（契约变更 = PR）

契约**绝不**被某一方在自己仓里悄悄改。任何变更走如下闸：

1. **改契约 = 开 PR**：在本仓改对应 spec，开 PR，写清"改了什么 / 为什么 / 影响哪些消费方"。
2. **owner 批**：CODEOWNERS 指定的 owner（业务契约=AMR，运维契约=fullwechat）review。
3. **CI 跑**（占位，机制 TBD）：
   - lint（spec 格式 / 链接有效性）；
   - **一致性 fixtures**（契约示例信封要能被各消费方的解析器吃下，不破向后兼容）；
   - **兼容闸**（按 `VERSIONING.md`：minor 必须向后兼容，major 必须另开新文件 + bump schema major）。
4. **人 merge = HITL 闸**：CI 绿 + owner 批后，**由人按下 merge**——契约变更是对外承诺，
   不做全自动合并，留人最后一道确认（人在回路最高准则）。

> 演进规则细节（两条版本轴、双向握手、兼容矩阵）见 [`VERSIONING.md`](./VERSIONING.md)。

---

## 被依赖方式（A/A/先A后B）

各消费方（AMR / AMP / fullwechat / PowerData …）这样拿到本仓契约的某个**固定版本**：

1. **工件 = 语言无关的 git tag + GitHub Release tarball**。本仓打 `v*` tag →
   `.github/workflows/release.yml` 自动切一个 Release，附 specs + fixtures 的 tarball。
   tag 就是工件，**不依赖任何语言 / 包管理器**，谁都能拉。
2. **消费方 vendor 一份提交进自己仓的只读副本**（pin 在某个 tag）。不在运行时拉，而是把
   契约树**复制进自己仓 commit**（如 AMR `vendor/contracts/`），→ 构建 / 测试零网络、可复现、可 diff 审。
   升级版本 = 跑同步脚本拉新 tag、人审 diff、commit。
   **参考实现：AMR [`scripts/sync-contracts.sh`](https://github.com/gthneo/agenticmessagerouter/blob/main/scripts/sync-contracts.sh)**
   （`clone --depth 1 --branch <tag>` → 复制 tracked 文件 → pin 在 `CONTRACTS_VERSION`；幂等、public-safe）。
3. **先拉式（pull-based）后推式**。**先 A（拉式）** = 消费方主动拉固定 tag（`sync-contracts.sh <tag>`）。
   **后 B（推式）已落地** = [`.github/workflows/notify-consumers.yml`](.github/workflows/notify-consumers.yml)：
   发新 `v*` tag → 按仓根 [`consumers.json`](consumers.json) 给每个已登记消费方仓**自动开一个 bump PR**
   （改 `CONTRACTS_VERSION` + 同步 vendor），触发该仓自己的 conformance/drift CI。
   **HITL：只开 PR、人审后 merge，绝不自动合**。激活需一次性配 secret `CONTRACTS_SYNC_TOKEN`
   （跨仓写权限的 PAT/App；默认 `GITHUB_TOKEN` 不能跨仓写，长期并入身份分权方案）。
4. **消费方 CI 的两道牙齿**：
   - **一致性 fixtures**：跑 `fixtures/`（vendored 进来的）当 conformance —— 自己的解析器/校验器
     吃下全部合规信封 = 绿，吃不下 = 红（实现与契约漂移了）。
   - **运行时边界校验**：在 ingest 边界做语义校验（`fixtures/conformance.md` 的口径，
     首条 = `msg_id` 必须全局唯一）+ msg_key 碰撞检测，把「schema 过了但语义错」的 bug
     从静默变响亮。参考实现：AMR `src/jl/contract_validate.py` + `db.insert_messages`。

> 演进规则细节（两条版本轴、双向握手、兼容矩阵）见 [`VERSIONING.md`](./VERSIONING.md)。

---

## 公开仓纪律 — 永不入真实数据

本仓是**公开仓**。所有示例信封一律**合成占位**：`张三/李四/王五`、`wxid_test_*`、
`+8613000000000` 段号码。真实联系人 / token / wxid / 凭据**绝不**进本仓。
迁移自 AMR 的 spec 已通过 secrets 扫描（无真实 PII）。

---

## 目录

```
agentic-contracts/
  README.md                          # 本文件
  VERSIONING.md                      # 版本化 + 兼容矩阵（全仓共守）
  CODEOWNERS                         # 每份契约的 owner-reviewer
  message/canonical.md               # 消息规范化信封（通道无关核心 + 微信附录）
  send-target/send-target.md         # 冷会话自动翻出发送
  group-metadata/group-metadata.md   # 群成员名册 + 群 meta
  moments/read-like.md               # 朋友圈：读 + 点赞（v1）
  moments/publish.md                 # 朋友圈：发布 / 广播（v2，AMR 统一持有）
  control-and-voice/control-and-voice.md  # 人机控制权互斥 + 口吻喂养
  ops-agent/ops-agent.md             # fullwechat 后端运维契约（fullwechat 持有）
```
