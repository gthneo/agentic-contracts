# rich-file conformance fixtures

合成占位（张三/李四/王五、`wxid_test_*`、`md5_test_*`）—— 公开仓零真实 PII。
对 `rich-file/archive.md` 的三个 status 态各一条冒烟样例：

- `valid_local.json` — `has_local=true`（本地有），派生 `status=local`；示范「本地有但 CDN 已过期」（丢了不可再抢）+ 绝对 `retrieval_url` 便利字段。
- `valid_recoverable.json` — `has_local=false ∧ cdn=recoverable`，派生 `status=recoverable`；带 `expire_at`（排抢救优先级）+ 只给 `retrieval_path`（后端不知外部 base）。
- `valid_expired.json` — 壳，`has_local=false ∧ cdn=expired`，派生 `status=expired`；只留元数据 + provenance，无 retrieval（诚实告诉消费方「曾有此文件但已丢」）。

v1.5 范围档（§2 `scope_lane` / §4.5 大群周期档）：

- `valid_scope_periodic.json` — 大群里 2.5 MB 的文件，`large_periodic` 开着 → `scope_lane=periodic`。
- `valid_scope_periodic_large_file.json` — 同一大群里 300 MB 的文件 → 仍是 `scope_lane=periodic`（**不设大小上限**，审定「一并接收」）。
- `valid_scope_out_not_allowlisted.json` — 大群、没开周期档、不在白名单 → `scope_lane=out` + `scope_reason=not_allowlisted`。

`scripts/conformance.py` 对每条校验：必填字段 / status 与两轴一致 / provenance.msg_id 非空且全局唯一（归类钩子）。
