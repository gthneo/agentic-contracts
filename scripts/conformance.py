#!/usr/bin/env python3
"""conformance.py — CI 闸的可执行一致性校验（机器，不可绕）。

把 `fixtures/conformance.md` 里**能自动化**的语义口径，变成跑得起来的检查：
对 `fixtures/message-canonical/*.json` 里每条 canonical 信封做**结构 + 语义**校验，
任一条不合规 → 非 0 退出 → PR 的 CI 红 → merge 不了。
另对 `fixtures/presence-parallel/*.json` 按 0 号宪法 v2.1「在场并行」节 I-3 校验生效档判定
（`evaluate_presence_parallel` 为参考实现）。

这是单账号生态下的**机器闸**：实现/契约示例一旦漂离 canonical 契约（缺必填 / kind 不在
枚举 / direction 非 in|out / msg_id 空或非字符串 / msg_id 跨 fixtures 撞车），CI 立刻变红，
不靠人眼、不可绕。与 AMR 消费方侧 `tests/test_conformance_fixtures.py` 同口径（双向自检）。

无第三方依赖（纯 stdlib），public-safe（只读合成 fixtures）。

退出码：0 = 全合规；1 = 有违规（细节打到 stderr）。
"""
from __future__ import annotations

import json
import pathlib
import sys

# --- canonical 口径（与 message/canonical.md §2.1 + §3 一致；漂移先改契约）-----------

# kind 封闭枚举 —— message/canonical.md §3（18 个值，conformance.md C4）。
# 2026-07-03 王总钦定 +3：channels(视频号) / friend_verify(好友验证) / call(通话)。
CANONICAL_KINDS = frozenset({
    "text", "image", "voice", "video", "file", "link", "quote", "miniprogram",
    "chat_history", "location", "sticker", "transfer", "red_packet", "system", "unknown",
    "channels", "friend_verify", "call",
})

# 每条信封必填的顶层字段（§2.1）。
REQUIRED_FIELDS = ("schema", "channel", "kind", "text", "ts", "direction")

DIRECTIONS = frozenset({"in", "out"})

SCHEMA_PREFIX = "message.canonical/"  # conformance.md C5：schema 前缀决定兼容路由。


def validate_envelope(env: object) -> list[str]:
    """对单条 canonical 信封返回违规字符串列表（[] = 合规）。纯函数，永不抛。

    覆盖 conformance.md 里能在**单条**上自动化的口径：
      C3 text 非空 / C4 kind 落枚举 / C5 schema 前缀 / direction ∈ {in,out} /
      C1 的结构地板（msg_id 若存在则为非空字符串）。
    """
    if not isinstance(env, dict):
        return [f"envelope is not an object (got {type(env).__name__})"]

    viol: list[str] = []

    # 必填字段（含 C3 text 非空：值为 None/"" 也算缺）。
    for f in REQUIRED_FIELDS:
        if f not in env or env[f] in (None, ""):
            viol.append(f"missing required field: {f}")

    schema = env.get("schema")
    if isinstance(schema, str) and not schema.startswith(SCHEMA_PREFIX):
        viol.append(f"schema {schema!r} must start with {SCHEMA_PREFIX!r} (C5)")

    kind = env.get("kind")
    if kind is not None and kind not in CANONICAL_KINDS:
        viol.append(f"kind {kind!r} not in canonical enum (C4)")

    direction = env.get("direction")
    if direction is not None and direction not in DIRECTIONS:
        viol.append(f"direction {direction!r} not in {{in,out}}")

    # C1 的结构地板：msg_id 可选，但存在即必须是非空字符串（数值/空 = localId-as-id 嫌疑）。
    if "msg_id" in env:
        mid = env["msg_id"]
        if not isinstance(mid, str) or not mid:
            viol.append(f"msg_id must be a non-empty string (got {mid!r}) (C1)")

    return viol


# C6（conformance.md）：读不可用信号体的结构闸。读调用读不到时不得回空数组，要回
# {error:{code:"read_unavailable", reason, chatId, ...}}（REST 409 / MCP 工具错误的 body）。
READ_REASONS = frozenset({"key_unavailable", "table_unavailable", "unknown"})


def validate_read_signal(obj: object) -> list[str]:
    """对单个「读不可用」信号体返回违规列表（[] = 合规）。纯函数，永不抛。

    口径见 message/canonical.md §6.4 + conformance.md C6：必须有 error.code=="read_unavailable"
    + reason 落 READ_REASONS + 非空 chatId。coverage 可选。
    """
    if not isinstance(obj, dict):
        return [f"read-signal is not an object (got {type(obj).__name__})"]
    err = obj.get("error")
    if not isinstance(err, dict):
        return ["read-signal missing object field: error (C6)"]
    viol: list[str] = []
    if err.get("code") != "read_unavailable":
        viol.append(f'error.code must be "read_unavailable" (got {err.get("code")!r}) (C6)')
    if err.get("reason") not in READ_REASONS:
        viol.append(f"error.reason {err.get('reason')!r} not in {sorted(READ_REASONS)} (C6)")
    if not (isinstance(err.get("chatId"), str) and err.get("chatId")):
        viol.append("error.chatId must be a non-empty string (C6)")
    return viol


RICH_FILE_CDN = frozenset({"recoverable", "expired", "unknown"})
RICH_FILE_STATUS = frozenset({"local", "recoverable", "expired"})
RICH_FILE_REQUIRED = ("file_id", "name", "provenance", "has_local", "cdn", "status", "retrieval_path")


def validate_rich_file(obj: object) -> list[str]:
    """对单个 rich_file item 返回违规列表（[] = 合规）。纯函数，永不抛。

    口径见 rich-file/archive.md §2：必填字段 / cdn·status 落枚举 /
    status 是 has_local+cdn 的纯派生（local 优先，须一致）/ provenance.msg_id 非空（归类钩子）。
    """
    if not isinstance(obj, dict):
        return [f"rich_file is not an object (got {type(obj).__name__})"]
    viol: list[str] = []
    for fld in RICH_FILE_REQUIRED:
        if fld not in obj:
            viol.append(f"rich_file missing required field: {fld} (§2)")
    if obj.get("cdn") not in RICH_FILE_CDN:
        viol.append(f"cdn {obj.get('cdn')!r} not in {sorted(RICH_FILE_CDN)} (§2)")
    if obj.get("status") not in RICH_FILE_STATUS:
        viol.append(f"status {obj.get('status')!r} not in {sorted(RICH_FILE_STATUS)} (§2)")
    hl, cdn, st = obj.get("has_local"), obj.get("cdn"), obj.get("status")
    if isinstance(hl, bool):
        derived = "local" if hl else ("recoverable" if cdn == "recoverable"
                                      else "expired" if cdn == "expired" else None)
        if derived is not None and st != derived:
            viol.append(f"status {st!r} 与 has_local={hl}/cdn={cdn!r} 不一致（应派生为 {derived!r}，§2 local 优先）")
    else:
        viol.append("has_local must be a bool (§2)")
    prov = obj.get("provenance")
    if not isinstance(prov, dict):
        viol.append("provenance must be an object (§2.1)")
    else:
        mid = prov.get("msg_id")
        if not (isinstance(mid, str) and mid):
            viol.append("provenance.msg_id must be a non-empty string (§2.1 归类钩子 = message msg_id)")
        if not (isinstance(prov.get("chat_id"), str) and prov.get("chat_id")):
            viol.append("provenance.chat_id must be a non-empty string (§2.1)")
    return viol


# 0 号宪法 v2.1「在场并行」节 I-1 / I-2 / I-3 / I-6：生效档判定的参考实现。漂移先改宪法，再改这里。
RUNGS = ("off", "draft", "semi", "parallel", "audit", "auto")
PRESENCE_STATES = frozenset({"present", "absent", "unknown"})
ACTIONS = frozenset({"conversation_send", "broadcast", "destructive_write", "first_contact"})
N_MAX_MINUTES = 10  # 0 号宪法「在场并行」宪法参数 N_max（2026-10-11 已审定；改宪法时同步改这里）
# 0 号宪法「在场并行」宪法参数 R_max（班迪 2026-10-12 审定；原拟 15 秒 / 20 条；改宪法时同步改这里）：
#   间隔 ≥ R_MAX_MIN_GAP_SECONDS 不超出（恰好 30 秒允许）；本次在场以 parallel 交出的条数（含本条）
#   ≤ R_MAX_SENDS_PER_PRESENCE 不超出（第 7 条允许、第 8 条起按 semi）。
R_MAX_MIN_GAP_SECONDS = 30
R_MAX_SENDS_PER_PRESENCE = 7
# 0 号宪法「在场并行」宪法参数 T_first（班迪 2026-10-12 审定；原拟 10 秒；改宪法时同步改这里）：
#   距在场开始 ≥ T_FIRST_SECONDS 时就绪的那一条才算已过 T_first（恰好 30 秒允许）；不足 30 秒时就绪的那一条
#   按 semi、不排队延后 —— 之后即使已过 T_first，它也不会再被自动按 parallel 交出。
T_FIRST_SECONDS = 30
# 读不到 / 不可信的状态在 fixture 里写成 null（I-1 fail-closed）：sticky / 作用域读不到 = 不生效，
# 群成员数判不出 = 按超过 G 处理，N 读不到 = 配置不合法。
NULLABLE_BOOL_FIELDS = frozenset({"in_policy_scope", "is_large_group", "sticky_exit"})
PRESENCE_BOOL_FIELDS = ("policy_enabled", "in_policy_scope", "is_large_group", "explicitly_listed",
                        "sticky_exit", "anomaly_downgraded", "handles_ready", "backend_cancel")
PRESENCE_INPUT_FIELDS = ("account_cap", "group_rungs", "session_rung", "presence", "n_minutes",
                         *PRESENCE_BOOL_FIELDS, "item")
ITEM_BOOL_FIELDS = ("draft_predates_presence", "trigger_predates_presence", "indicator_rendered",
                    "t_first_elapsed", "within_rate_cap", "run_after_within_window")
# 离场期间到达的消息、在场开始后重新生成的回复（宪法「在场并行」I-3，待班迪审定）：
#   "B" = 可按 parallel 交出（受 T_first 与频次上限约束）；"A" = 一律按 semi 逐条放行。
N4_POLICY = "B"


def rate_within_r_max(rate: dict) -> bool:
    """按宪法上限 R_max 判本条是否不超出频次上限（消费方取值恰等于 R_max 时的判定）。

    rate = {"send_ordinal": 本次在场以 parallel 交出的第几条（含本条，≥ 1）,
            "gap_seconds": 与该会话上一条 Agent 发出的间隔（秒，≥ 0）}
    """
    return (rate["send_ordinal"] <= R_MAX_SENDS_PER_PRESENCE
            and rate["gap_seconds"] >= R_MAX_MIN_GAP_SECONDS)


def t_first_elapsed_at_ready(tf: dict) -> bool:
    """按宪法 T_first 判本条是否已过 T_first。

    tf = {"ready_s": 该条就绪待交出时距在场开始的秒数,
          "at_s": 判定这一刻距在场开始的秒数（≥ ready_s）}
    只看就绪时刻：不足 T_first 时就绪的那一条按 semi、不排队延后，at_s 晚于 T_first 也不改判。
    """
    return tf["ready_s"] >= T_FIRST_SECONDS


def _validate_t_first(tf: object, elapsed: object) -> list[str]:
    """item.t_first（可选）的结构闸 + 与 item.t_first_elapsed 的一致性闸。"""
    if not isinstance(tf, dict):
        return ["input.item.t_first must be an object {ready_s, at_s}"]
    viol: list[str] = []
    for k in ("ready_s", "at_s"):
        v = tf.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            viol.append(f"input.item.t_first.{k} {v!r} must be a number ≥ 0")
    if viol:
        return viol
    if tf["at_s"] < tf["ready_s"]:
        return [f"input.item.t_first.at_s {tf['at_s']!r} must be ≥ ready_s {tf['ready_s']!r}"]
    computed = t_first_elapsed_at_ready(tf)
    if elapsed is not computed:
        viol.append(f"input.item.t_first_elapsed {elapsed!r} disagrees with T_first "
                    f"(就绪时刻 ≥ {T_FIRST_SECONDS} 秒，不排队延后) on t_first {tf!r}: rule gives {computed}")
    return viol


def _validate_rate(rate: object, within: object) -> list[str]:
    """item.rate（可选）的结构闸 + 与 item.within_rate_cap 的一致性闸。"""
    if not isinstance(rate, dict):
        return ["input.item.rate must be an object {send_ordinal, gap_seconds}"]
    viol: list[str] = []
    k = rate.get("send_ordinal")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        viol.append(f"input.item.rate.send_ordinal {k!r} must be an integer ≥ 1")
    g = rate.get("gap_seconds")
    if isinstance(g, bool) or not isinstance(g, (int, float)) or g < 0:
        viol.append(f"input.item.rate.gap_seconds {g!r} must be a number ≥ 0")
    if viol:
        return viol
    computed = rate_within_r_max(rate)
    if within is not computed:
        viol.append(f"input.item.within_rate_cap {within!r} disagrees with R_max "
                    f"(≤ {R_MAX_SENDS_PER_PRESENCE} 条 / ≥ {R_MAX_MIN_GAP_SECONDS} 秒) on rate {rate!r}: "
                    f"rule gives {computed}")
    return viol


def _rank(rung: str) -> int:
    return RUNGS.index(rung)


def _min_rung(*rungs: str) -> str:
    return min(rungs, key=_rank)


def evaluate_presence_parallel(inp: dict) -> tuple[bool, str]:
    """返回 (在场并行是否生效, 该条的生效档)。输入须已通过 validate_presence_case 的结构闸。

    在场并行生效 ⇔ 在场（unknown 按不在场，I-1 fail-closed）∧ 0 < N ≤ N_max（N 读不到 = 不合法）
                 ∧ 策略已开启 ∧ 在作用域（读不到 = 不在；超过 G 人的群须显式列入，成员数判不出按超过）
                 ∧ 会话档 ≥ semi ∧ 无未恢复的 sticky 结束（读不到 = 视为有）∧ 本次在场未异常自降
                 ∧ I-6 手柄齐（含频次上限不宽于 R_max）∧ 后端已声明 cancel
    单条可按 parallel 交出 ⇔ 生效 ∧ 会话内发消息 ∧ 稿在本次在场开始之后才拟出
                 ∧ 标识已呈现 ∧ 距在场开始已过 T_first ∧ 本条不超出频次上限
                 ∧ 放出时刻回告存在且不晚于 交出时刻 + W
                 ∧ （口径 A 时）触发消息不早于在场开始
                 ∧ 以上单条项读得到（任一 item 字段为 null = 该条按 semi）
    会话项 = 生效 ? max(会话档, parallel) : 会话档
    生效档 = min(账号封顶档, 各授权组档（无组 → 账号封顶档）, 会话项, 该条的封顶档)
    该条的封顶档 = 单条可按 parallel 交出 ? parallel : semi
    异常自降：收缩到 draft（不变式 4）。
    """
    item = inp["item"]
    n = inp["n_minutes"]
    n_ok = n is not None and 0 < n <= N_MAX_MINUTES
    large = inp["is_large_group"] is not False  # None（判不出）按超过 G 处理
    scope_ok = inp["in_policy_scope"] is True and (not large or inp["explicitly_listed"])
    no_sticky = inp["sticky_exit"] is False  # None（读不到）视为有 sticky
    active = (inp["presence"] == "present" and n_ok and inp["policy_enabled"] and scope_ok
              and _rank(inp["session_rung"]) >= _rank("semi")
              and no_sticky and not inp["anomaly_downgraded"]
              and inp["handles_ready"] and inp["backend_cancel"])
    item_readable = all(item[f] is not None for f in ITEM_BOOL_FIELDS)
    item_parallel = (active and item_readable and item["action"] == "conversation_send"
                     and item["draft_predates_presence"] is False
                     and item["indicator_rendered"] is True and item["t_first_elapsed"] is True
                     and item["within_rate_cap"] is True and item["run_after_within_window"] is True
                     and (N4_POLICY == "B" or item["trigger_predates_presence"] is False))
    session_term = (RUNGS[max(_rank(inp["session_rung"]), _rank("parallel"))]
                    if active else inp["session_rung"])
    groups = inp["group_rungs"] or [inp["account_cap"]]
    item_cap = "parallel" if item_parallel else "semi"
    rung = _min_rung(inp["account_cap"], *groups, session_term, item_cap)
    if inp["anomaly_downgraded"]:
        rung = _min_rung(rung, "draft")
    return active, rung


def validate_presence_case(obj: object) -> list[str]:
    """对单条在场并行 fixture 返回违规列表（[] = 合规）。纯函数，永不抛。

    结构闸（字段在、值落枚举）+ 语义闸（expected 必须等于参考实现的判定）。
    """
    if not isinstance(obj, dict):
        return [f"presence case is not an object (got {type(obj).__name__})"]
    viol: list[str] = []
    if not (isinstance(obj.get("case"), str) and obj.get("case")):
        viol.append("case must be a non-empty string")
    inp, exp = obj.get("input"), obj.get("expected")
    if not isinstance(inp, dict):
        return viol + ["input must be an object"]
    if not isinstance(exp, dict):
        return viol + ["expected must be an object"]
    for fld in PRESENCE_INPUT_FIELDS:
        if fld not in inp:
            viol.append(f"input missing field: {fld}")
    if viol:
        return viol
    for fld in ("account_cap", "session_rung"):
        if inp[fld] not in RUNGS:
            viol.append(f"input.{fld} {inp[fld]!r} not in ladder {RUNGS}")
    groups = inp["group_rungs"]
    if not isinstance(groups, list) or any(g not in RUNGS for g in groups):
        viol.append(f"input.group_rungs {groups!r} must be a list of ladder rungs (empty = no group)")
    if inp["presence"] not in PRESENCE_STATES:
        viol.append(f"input.presence {inp['presence']!r} not in {sorted(PRESENCE_STATES)}")
    n = inp["n_minutes"]
    if n is not None and (isinstance(n, bool) or not isinstance(n, (int, float))):
        viol.append(f"input.n_minutes {n!r} must be a number or null (null = 读不到)")
    for fld in PRESENCE_BOOL_FIELDS:
        v = inp[fld]
        if not (isinstance(v, bool) or (v is None and fld in NULLABLE_BOOL_FIELDS)):
            viol.append(f"input.{fld} must be a bool" + (" or null" if fld in NULLABLE_BOOL_FIELDS else ""))
    item = inp["item"]
    if not isinstance(item, dict):
        viol.append("input.item must be an object")
    else:
        if item.get("action") not in ACTIONS:
            viol.append(f"input.item.action {item.get('action')!r} not in {sorted(ACTIONS)}")
        for fld in ITEM_BOOL_FIELDS:
            if fld not in item:
                viol.append(f"input.item missing field: {fld}")
            elif not (item[fld] is None or isinstance(item[fld], bool)):
                viol.append(f"input.item.{fld} must be a bool or null (null = 读不到)")
        if "rate" in item:
            viol.extend(_validate_rate(item["rate"], item.get("within_rate_cap")))
        if "t_first" in item:
            viol.extend(_validate_t_first(item["t_first"], item.get("t_first_elapsed")))
    if exp.get("effective_rung") not in RUNGS:
        viol.append(f"expected.effective_rung {exp.get('effective_rung')!r} not in ladder")
    if not isinstance(exp.get("presence_parallel_active"), bool):
        viol.append("expected.presence_parallel_active must be a bool")
    if viol:
        return viol
    active, rung = evaluate_presence_parallel(inp)
    if active != exp["presence_parallel_active"]:
        viol.append(f"presence_parallel_active: expected {exp['presence_parallel_active']}, "
                    f"rule gives {active} (0 号宪法 在场并行 I-3)")
    if rung != exp["effective_rung"]:
        viol.append(f"effective_rung: expected {exp['effective_rung']!r}, rule gives {rung!r} "
                    f"(0 号宪法 在场并行 I-3 + 封顶表)")
    return viol


def main(argv: list[str]) -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    fixtures_dir = root / "fixtures" / "message-canonical"
    files = sorted(fixtures_dir.glob("*.json"))

    if not files:
        print(f"conformance: NO fixtures found under {fixtures_dir} — fail-closed", file=sys.stderr)
        return 1

    total_viol = 0
    seen_msg_ids: dict[str, str] = {}  # C1：fixtures 自洽 —— msg_id 跨文件全局唯一。

    for f in files:
        try:
            env = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot parse JSON: {e}", file=sys.stderr)
            total_viol += 1
            continue

        viol = validate_envelope(env)
        for v in viol:
            print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
        total_viol += len(viol)

        mid = env.get("msg_id") if isinstance(env, dict) else None
        if isinstance(mid, str) and mid:
            if mid in seen_msg_ids:
                print(f"  [FAIL] {f.name}: msg_id {mid!r} collides with {seen_msg_ids[mid]} "
                      f"(C1: msg_id 必须全局唯一)", file=sys.stderr)
                total_viol += 1
            else:
                seen_msg_ids[mid] = f.name

        if not viol:
            print(f"  [ok]   {f.name}")

    # C6：读不可用信号体（另一套校验，单独目录，不与信封混淆）。
    read_dir = root / "fixtures" / "read-contract"
    read_files = sorted(read_dir.glob("*.json"))
    for f in read_files:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot parse JSON: {e}", file=sys.stderr)
            total_viol += 1
            continue
        viol = validate_read_signal(obj)
        for v in viol:
            print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
        total_viol += len(viol)
        if not viol:
            print(f"  [ok]   {f.name} (read-signal)")

    # rich-file/archive.md §2：富文件 item（另一套校验，单独目录）。
    rich_dir = root / "fixtures" / "rich-file"
    rich_files = sorted(rich_dir.glob("*.json"))
    seen_prov_ids: dict[str, str] = {}
    for f in rich_files:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot parse JSON: {e}", file=sys.stderr)
            total_viol += 1
            continue
        viol = validate_rich_file(obj)
        for v in viol:
            print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
        total_viol += len(viol)
        prov = obj.get("provenance") if isinstance(obj, dict) else None
        pid = prov.get("msg_id") if isinstance(prov, dict) else None
        if isinstance(pid, str) and pid:
            if pid in seen_prov_ids:
                print(f"  [FAIL] {f.name}: provenance.msg_id {pid!r} collides with "
                      f"{seen_prov_ids[pid]} (归类钩子须唯一)", file=sys.stderr)
                total_viol += 1
            else:
                seen_prov_ids[pid] = f.name
        if not viol:
            print(f"  [ok]   {f.name} (rich-file)")

    # 0 号宪法 v2.1「在场并行」：生效档判定（另一套校验，单独目录）。
    presence_dir = root / "fixtures" / "presence-parallel"
    presence_files = sorted(presence_dir.glob("*.json"))
    seen_cases: dict[str, str] = {}
    for f in presence_files:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot parse JSON: {e}", file=sys.stderr)
            total_viol += 1
            continue
        viol = validate_presence_case(obj)
        for v in viol:
            print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
        total_viol += len(viol)
        case = obj.get("case") if isinstance(obj, dict) else None
        if isinstance(case, str) and case:
            if case in seen_cases:
                print(f"  [FAIL] {f.name}: case {case!r} collides with {seen_cases[case]}", file=sys.stderr)
                total_viol += 1
            else:
                seen_cases[case] = f.name
        if not viol:
            print(f"  [ok]   {f.name} (presence-parallel)")

    print(f"\nconformance: {len(files)} envelope + {len(read_files)} read-signal "
          f"+ {len(rich_files)} rich-file + {len(presence_files)} presence-parallel fixtures, "
          f"{total_viol} violation(s)")
    if total_viol:
        print("conformance: RED — fixtures drifted from contract", file=sys.stderr)
        return 1
    print("conformance: GREEN — all fixtures conform to message.canonical + rich-file.archive "
          "+ constitution presence-parallel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
