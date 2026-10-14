# 图片档位与按人查看契约 v1 — Image Variant & Human-View Contract

> schema 标识：`media.image-variant/1` ｜ 状态：提案 v1.0（2026-10-15）
> **from** AgenticMessageRouter（AMR，定义方 / 消费方）｜ **for** PowerData-WX（PD，fullwechat 微信后端，实现方）
> **真相源** 本仓（`agentic-contracts`）。0 号宪法统领。
> **姊妹契约** `message/canonical.md`（图片消息本体）· `rich-file/archive.md`（文件归档）。
> **来源** AMR #272（图片档位）· AMR #301（人在 AMR 点开图片即取原图 + 看过即标已读）；
> 实现：`gthneo/powerdata-wx` PR #58（`eb338f7`）、PR #65（`3e5040e`）；AMR 分支 `feat-301-image-on-view`，Dev 真机验收 2026-10-14。
> 本文**按 PD 已上线的字段登记**，不另起名字。

## 0. 这份契约管什么

1. 后端在取图响应里说明**这一份是哪一档**（缩略图 / 中图 / 原图）。
2. **人的查看动作**可以让后端操作微信界面取一张图的原图、或把一个会话标为已读 —— 以及谁能触发、怎么调用、怎么回执。

## 1. 档位：`X-Media-Variant`

`GET /api/media/{chat_id}/{server_id}` 的响应头 `X-Media-Variant` ∈ `hd`（原图）· `mid`（中图）· `thumb`（缩略图）。
缺失或其他值 = **未知**；消费方不得把未知读成任何一档。

## 2. 能力位（`GET /api/capabilities`）

| 键 | 类型 | 含义 |
|---|---|---|
| `media.image_on_view` | bool | 支持 §4 单张取图（= 当前微信 build 在白名单内） |
| `media.image_key` | bool | 本机有图片解密密钥。`false` 时 `/api/media` 出不了任何一档图片 |
| `media.image_on_view_suggested_timeout_ms` | int | 单张取图建议等待上限（毫秒） |
| `chats.mark_read` | bool | 支持 §5 标为已读 |

消费方 MUST 以**显式为 `true`** 判定支持；缺失 = 不支持，不得「试一下」。取原图要求 `image_on_view` 与 `image_key` 同时为 `true`。

## 3. D4：谁能触发界面操作（规范性）

- **MUST**：消费方只在**本人的查看动作**（在消费方界面里点开一张图片 / 打开会话并看到最新消息）之后，才可以调用 §4、§5。引擎、定时任务、只持共享令牌的 Agent 一律不得调用。
- **MUST**：只调用该图片 / 会话**所属账号**的后端（渠道 / 账号守恒），不得改用别的账号的后端。
- **MUST**：每次触发留痕（谁 / 何时 / 结果）；留痕不含会话 ID 明文与人名。
- **MUST**：同一账号同一时刻至多一单界面操作（消费方排队或拒绝，不并发）。
- 后端凭 `human_view: true` 区分来源。`human_view` 请求放行未读、允许名单（`chat_allow`）、无进展退避这三项为自动轮次设的限制，**只作用于本次请求**；拒绝名单（`chat_deny`）与系统会话照常拒绝。
- 打开会话会清掉该会话的微信未读（§4、§5 都如此）；这与本人已在消费方看过一致。

## 4. 单张取图

`POST /api/image-prefetch/run`

```json
{ "human_view": true, "chat_id": "<会话 id>", "server_id": "<canonical msg_id，数字或数字字符串>", "dry_run": false }
```

消费方 MUST 显式给出 `dry_run`（后端在 `human_view` 下缺省为 `false`，消费方不得依赖缺省）。请求是同步的，耗时可达分钟级（实测 39–135 秒）；消费方不得让终端用户的浏览器挂着同一个 HTTP 请求等待（反向代理读超时常见 60 秒）。

**200 响应**

| 字段 | 含义 |
|---|---|
| `variant` | 本机现有最好一档：`hd` / `mid` / `thumb` / `null`（同 §1） |
| `has_hd` | 发送方发了原图 |
| `complete` | 已拿到最好一档（`has_hd` 时指原图，否则中图）——**消费方以此判断成败** |
| `ok` | 界面操作本身执行成功（无崩溃）；不表示拿到了最好一档 |
| `newer` · `views` · `gui` · `elapsed_ms` | 之后还有几张图 / 翻页次数 / 是否动了界面 / 耗时 |
| `note`（可选） | `complete:false` 的原因：`expired`（微信 CDN 已清，取不回）· `yielded_to_waiting_action`（为排队的发送让路，可再试）· `not_downloaded` · `oldest_reached_before_target` · `view_budget_exhausted` · `no_visible_image` · `viewer_not_opened` |
| `error`（可选） | `wechat_restarted`（微信进程变了，已熔断） |

消费方判读：`complete:true` 且 `has_hd:false` = 对方没发原图；`complete:false` 按 `note` / `error` 分类；未登记的 `note` 一律按「没取到」处理，新增取值须先在本契约登记。

**错误**（HTTP 状态 + 响应体 `{"ok":false,"error":"<码>","message":"<文字>"}`）

| 状态 | `error` | 含义 |
|---|---|---|
| 400 | `chat_id_required` / `bad_server_id` / `server_id_requires_human_view` | 请求不完整 |
| 404 | `image_not_found` | 该会话里没有这个 `server_id` 的图片消息 |
| 409 | `image_too_far_back` | 目标之后还有 ≥ 20 张图片或视频，不翻 |
| 409 | `denied` / `system_chat` | 拒绝名单 / 系统会话 |
| 409 | `build_not_allowed` / `busy_or_breaker_open` / `not_logged_in` | build 不在白名单 / 已有一单在跑或熔断中 / 未登录 |

后端事件：`image_prefetch_human_view`（开始）· `image_prefetch_human_view_done`（结束；会话 ID 哈希）。

## 5. 标为已读

`POST /api/chats/{chat_id}/read`（无请求体）。未读本就为 0 → 不动界面（`gui:false`）。

**响应** `{ ok, chat_id, unread_before, unread_after, gui, restored, elapsed_ms }`；失败 `{ "ok": false, "error": "<码>" }`，码：`unread_not_cleared` · `chat_not_found` · `unsupported_chat`。
`restore_note`（可选）：`prev_chat_unresolved`（原会话名不唯一，不回）· `yielded_to_waiting_action`。不回原会话不算失败。
后端事件：`chat_mark_read`。

## 6. 版本

本契约为新增，向后兼容；不改动 `message.canonical/1`。字段变更走本仓 PR。
