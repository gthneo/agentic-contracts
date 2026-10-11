#!/usr/bin/env python3
"""conformance.py — CI 闸的可执行一致性校验（机器，不可绕）。

把 `fixtures/conformance.md` 里**能自动化**的语义口径，变成跑得起来的检查：
对 `fixtures/message-canonical/*.json` 里每条 canonical 信封做**结构 + 语义**校验，
任一条不合规 → 非 0 退出 → PR 的 CI 红 → merge 不了。

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


# outbox/dispatch.md v1.1（rev4）§0 / §2.3 / §3 / §7.1 + control-and-voice.md §8.1：
# 在场并行任务（形态 B）的受理、认领与消费方交出判定。参考实现；漂移先改契约，再改这里。
OUTBOX_AUTHORIZATIONS = frozenset({"human_confirmed", "presence_parallel"})
PRESENCE_TTL_MAX_SECS = 600  # outbox/dispatch.md §2.3：presence_ttl_secs ∈ [1, 600]（W ≤ N ≤ N_max = 10 分钟）
OUTBOX_PRESENCE_CHECKS = frozenset({"enqueue", "claim", "handover"})
CONTROL_STATES = frozenset({"agent", "human"})


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def evaluate_outbox_enqueue(inp: dict) -> tuple[int, str | None]:
    """后端受理判定（dispatch §2.3 表，按序）。返回 (HTTP 状态, code)。WRONG_ACCOUNT 不在此建模。"""
    req = inp["request"]
    auth = req.get("authorization", "human_confirmed")
    if auth not in OUTBOX_AUTHORIZATIONS:
        return 400, "BAD_AUTHORIZATION"
    if auth == "human_confirmed":
        if "presence_session_id" in req or "presence_ttl_secs" in req:
            return 400, "PRESENCE_FIELDS_WITHOUT_AUTHORIZATION"
        return 202, None
    if inp["caps"].get("presence_parallel") is not True:
        return 409, "PRESENCE_PARALLEL_UNSUPPORTED"
    if req.get("kind") != "send_text":
        return 400, "PRESENCE_KIND_NOT_ALLOWED"
    sid = req.get("presence_session_id")
    if not (isinstance(sid, str) and sid):
        return 400, "MISSING_PRESENCE_SESSION"
    ttl = req.get("presence_ttl_secs")
    if not (_is_int(ttl) and 1 <= ttl <= PRESENCE_TTL_MAX_SECS):
        return 400, "BAD_PRESENCE_TTL"
    if inp["control_state"] != "agent":
        return 409, "HUMAN_IN_CONTROL"
    if inp["run_after_beyond_deadline"]:
        return 409, "PRESENCE_WINDOW_EXCEEDED"
    return 202, None


def evaluate_outbox_claim(inp: dict) -> str:
    """worker 对一条 queued 任务的处置（dispatch §3 + control-and-voice §8.1 PP-4）。

    返回 run | hold | expire | cancel。形态 B：HUMAN → cancel；过截止 → expire；pause → hold；否则 run。
    形态 A：pause 或 HUMAN → hold；否则 run（rev3 行为不变）。
    """
    if inp["authorization"] == "presence_parallel":
        if inp["control_state"] == "human":
            return "cancel"
        if inp["secs_since_accept"] > inp["presence_ttl_secs"]:
            return "expire"
        if inp["paused"]:
            return "hold"
        return "run"
    if inp["paused"] or inp["control_state"] == "human":
        return "hold"
    return "run"


def evaluate_outbox_handover(inp: dict) -> str:
    """消费方能否以形态 B 交出这一条（dispatch §0 / §7.1 + control-and-voice §8.1 PP-2…PP-5）。

    返回 presence_parallel | semi（semi = 只能按形态 A 逐条人审确认）。
    constitution_item_parallel = 0 号宪法 v2.1「在场并行」I-3「单条可按 parallel 交出」的判定结果
    （该判定本身的 fixture 在 fixtures/presence-parallel/，随 PR #25）。
    control_state 取 agent | human | unknown（unknown = 拉不到，按 HUMAN 处理）。
    """
    c = inp["outbox_caps"]
    caps_ok = (c.get("presence_parallel") is True and c.get("cancel") is True
               and c.get("pause") is True and c.get("account") is True)
    ok = (caps_ok and inp["control_caps"].get("state") is True
          and inp["control_state"] == "agent"
          and inp["constitution_item_parallel"] and inp["via_outbox"])
    return "presence_parallel" if ok else "semi"


def validate_outbox_presence_case(obj: object) -> list[str]:
    """对单条 outbox-presence fixture 返回违规列表（[] = 合规）。纯函数，永不抛。

    结构闸（字段在、值落枚举）+ 语义闸（expected 必须等于参考实现的判定）。
    """
    if not isinstance(obj, dict):
        return [f"outbox-presence case is not an object (got {type(obj).__name__})"]
    viol: list[str] = []
    if not (isinstance(obj.get("case"), str) and obj.get("case")):
        viol.append("case must be a non-empty string")
    check, inp, exp = obj.get("check"), obj.get("input"), obj.get("expected")
    if check not in OUTBOX_PRESENCE_CHECKS:
        return viol + [f"check {check!r} not in {sorted(OUTBOX_PRESENCE_CHECKS)}"]
    if not isinstance(inp, dict) or not isinstance(exp, dict):
        return viol + ["input and expected must be objects"]
    try:
        if check == "enqueue":
            for fld in ("caps", "request", "control_state", "run_after_beyond_deadline"):
                if fld not in inp:
                    viol.append(f"input missing field: {fld}")
            if viol:
                return viol
            if not isinstance(inp["caps"], dict) or not isinstance(inp["request"], dict):
                return viol + ["input.caps and input.request must be objects"]
            if inp["control_state"] not in CONTROL_STATES:
                viol.append(f"input.control_state {inp['control_state']!r} not in {sorted(CONTROL_STATES)}")
            if not isinstance(inp["run_after_beyond_deadline"], bool):
                viol.append("input.run_after_beyond_deadline must be a bool")
            if not _is_int(exp.get("status")):
                viol.append("expected.status must be an int")
            if viol:
                return viol
            status, code = evaluate_outbox_enqueue(inp)
            if (status, code) != (exp["status"], exp.get("code")):
                viol.append(f"enqueue: expected ({exp['status']}, {exp.get('code')!r}), "
                            f"rule gives ({status}, {code!r}) (outbox/dispatch.md §2.3)")
        elif check == "claim":
            for fld in ("authorization", "control_state", "secs_since_accept", "presence_ttl_secs", "paused"):
                if fld not in inp:
                    viol.append(f"input missing field: {fld}")
            if viol:
                return viol
            if inp["authorization"] not in OUTBOX_AUTHORIZATIONS:
                viol.append(f"input.authorization {inp['authorization']!r} not in enum")
            if inp["control_state"] not in CONTROL_STATES:
                viol.append(f"input.control_state {inp['control_state']!r} not in {sorted(CONTROL_STATES)}")
            if not (_is_int(inp["secs_since_accept"]) and _is_int(inp["presence_ttl_secs"])):
                viol.append("input.secs_since_accept / presence_ttl_secs must be ints")
            if not isinstance(inp["paused"], bool):
                viol.append("input.paused must be a bool")
            if exp.get("action") not in ("run", "hold", "expire", "cancel"):
                viol.append(f"expected.action {exp.get('action')!r} not in run|hold|expire|cancel")
            if viol:
                return viol
            action = evaluate_outbox_claim(inp)
            if action != exp["action"]:
                viol.append(f"claim: expected {exp['action']!r}, rule gives {action!r} "
                            f"(outbox/dispatch.md §3 + control-and-voice.md §8.1 PP-4)")
        else:  # handover
            for fld in ("outbox_caps", "control_caps", "control_state", "constitution_item_parallel", "via_outbox"):
                if fld not in inp:
                    viol.append(f"input missing field: {fld}")
            if viol:
                return viol
            if not isinstance(inp["outbox_caps"], dict) or not isinstance(inp["control_caps"], dict):
                return viol + ["input.outbox_caps and input.control_caps must be objects"]
            if inp["control_state"] not in ("agent", "human", "unknown"):
                viol.append(f"input.control_state {inp['control_state']!r} not in agent|human|unknown")
            for fld in ("constitution_item_parallel", "via_outbox"):
                if not isinstance(inp[fld], bool):
                    viol.append(f"input.{fld} must be a bool")
            if exp.get("form") not in ("presence_parallel", "semi"):
                viol.append(f"expected.form {exp.get('form')!r} not in presence_parallel|semi")
            if viol:
                return viol
            form = evaluate_outbox_handover(inp)
            if form != exp["form"]:
                viol.append(f"handover: expected {exp['form']!r}, rule gives {form!r} "
                            f"(outbox/dispatch.md §0 / §7.1 + control-and-voice.md §8.1)")
    except (KeyError, TypeError, AttributeError) as e:  # 永不抛：结构异常记为违规
        viol.append(f"malformed case: {e!r}")
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

    # outbox/dispatch.md v1.1（rev4）+ control-and-voice.md §8.1：在场并行任务（形态 B）的受理 / 认领 / 交出判定。
    op_dir = root / "fixtures" / "outbox-presence"
    op_files = sorted(op_dir.glob("*.json"))
    seen_op_cases: dict[str, str] = {}
    for f in op_files:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot parse JSON: {e}", file=sys.stderr)
            total_viol += 1
            continue
        viol = validate_outbox_presence_case(obj)
        for v in viol:
            print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
        total_viol += len(viol)
        case = obj.get("case") if isinstance(obj, dict) else None
        if isinstance(case, str) and case:
            if case in seen_op_cases:
                print(f"  [FAIL] {f.name}: case {case!r} collides with {seen_op_cases[case]}", file=sys.stderr)
                total_viol += 1
            else:
                seen_op_cases[case] = f.name
        if not viol:
            print(f"  [ok]   {f.name} (outbox-presence)")
    print(f"  outbox-presence: {len(op_files)} fixtures checked")

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

    print(f"\nconformance: {len(files)} envelope + {len(read_files)} read-signal "
          f"+ {len(rich_files)} rich-file fixtures, {total_viol} violation(s)")
    if total_viol:
        print("conformance: RED — fixtures drifted from contract", file=sys.stderr)
        return 1
    print("conformance: GREEN — all fixtures conform to message.canonical + rich-file.archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
