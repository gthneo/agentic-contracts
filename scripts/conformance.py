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
import re
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


def _constitution_parse(path: pathlib.Path, mode: str):
    """Split a constitution text into sections and footers (fail-closed: unrecognized lines are kept as stray).

    mode: zh (00-CONSTITUTION.md) | en (00-CONSTITUTION.en.md) | zh-en (00-CONSTITUTION.zh-en.md).
    Returns (sections, footers); each section is (heading, zh_units, en_units, stray_lines).
    """
    sections: list[tuple[str, list[str], list[str], list[str]]] = []
    footers: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            sections.append((line[3:].strip(), [], [], []))
            continue
        if not sections:
            continue  # title and header notes before the first section
        text = line.strip()
        if not text or text == "---":
            continue
        if line.startswith("*"):
            footers.append(text)
            continue
        _heading, zh_units, en_units, stray = sections[-1]
        if mode in ("zh", "zh-en") and line.startswith("\u3000\u3000"):
            zh_units.append(text)
        elif mode == "zh-en" and line.startswith("> "):
            en_units.append(text[2:].strip())
        elif mode == "en" and not line.startswith((">", "#", "\u3000")):
            en_units.append(text)
        else:
            stray.append(text)
    return sections, footers


def check_constitution_sync(root: pathlib.Path) -> int:
    """GOVERNANCE §3 (b)：三份宪法文本逐单元、逐节标题与尾注一致；节内不能识别的行一律判失败。"""
    zh_p, en_p, zhen_p = (root / "00-CONSTITUTION.md", root / "00-CONSTITUTION.en.md",
                          root / "00-CONSTITUTION.zh-en.md")
    if not (en_p.exists() and zhen_p.exists()):
        print("  [FAIL] constitution: 00-CONSTITUTION.en.md / .zh-en.md missing", file=sys.stderr)
        return 1
    zh, zh_f = _constitution_parse(zh_p, "zh")
    en, en_f = _constitution_parse(en_p, "en")
    bi, bi_f = _constitution_parse(zhen_p, "zh-en")
    problems: list[str] = []
    for name, secs in ((zh_p.name, zh), (en_p.name, en), (zhen_p.name, bi)):
        for heading, _zu, _eu, stray in secs:
            problems += [f"{name} · {heading}: unrecognized line {s[:48]!r}" for s in stray]
    if not len(zh) == len(en) == len(bi):
        problems.append(f"section count zh={len(zh)} en={len(en)} zh-en={len(bi)}")
    for (zh_h, zu, _a, _b), (en_h, _c, eu, _d), (bi_h, bz, be, _e) in zip(zh, en, bi):
        if bi_h != f"{zh_h} · {en_h}":
            problems.append(f"zh-en heading {bi_h!r} is not {zh_h!r} · {en_h!r}")
        if len(zu) != len(eu):
            problems.append(f"{zh_h}: {len(zu)} zh units vs {len(eu)} en units")
        if bz != zu:
            problems.append(f"{zh_h}: zh-en Chinese text differs from {zh_p.name}")
        if be != eu:
            problems.append(f"{en_h}: zh-en English text differs from {en_p.name}")
    if bi_f != zh_f + en_f:
        problems.append("zh-en footer differs from the two single-language footers")
    for p in problems:
        print(f"  [FAIL] constitution: {p}", file=sys.stderr)
    if not problems:
        print(f"  [ok]   constitution texts in sync ({sum(len(s[1]) for s in zh)} units, headings and footers)")
    return len(problems)


# --- graph/amr-graph-export.md（AMR → Metis 只读导出流，JSONL；一份文件 = 一次导出）---------------
# 消费方校验清单 §8.1 C1–C11 里能在一份流上自动化的部分。与 Metis 导入器 `--dry-run` 第一段同口径；
# AMR `jl graph export` 的输出也应能过这一套（生产方自核 P13）。

GRAPH_SCHEMA_PREFIX = "amr-graph-export/"
GRAPH_TYPES = ("person", "contact_point", "merge_record", "negative_sample",
               "organization", "employment", "self_identity")
# 键序 = 契约 §3 / §4 表格行序；所有键恒在场（无值写 null）—— 这是确定性输出的构成（§2.4 第 2 条）。
GRAPH_FIELDS = {
    "header": ("type", "schema", "status", "mode", "since", "pii_policy", "exported_at", "source",
               "rules", "watermark", "invariants", "counts", "body_sha256"),
    "person": ("type", "id", "name", "name_by", "aliases", "watch", "created_at", "updated_at",
               "last_contact_at", "accounts", "sources"),
    "contact_point": ("type", "person_id", "kind", "value_raw", "value_normalized", "value_e164",
                      "unparsed", "source", "by", "confirmed_at", "evidence_ref", "match_digits",
                      "batch", "account_id", "pinned"),
    "merge_record": ("type", "id", "action", "survivor_id", "merged_id", "by", "batch", "rule",
                     "reason", "evidence", "merged_at", "undone_at"),
    "negative_sample": ("type", "kind", "a_id", "b_id", "a_person_id", "b_person_id", "reason",
                        "created_at"),
    "organization": ("type", "id", "name", "aliases", "kind_raw", "parent_id", "by", "created_at",
                     "merged_into", "registration_no", "jurisdiction", "domains"),
    "employment": ("type", "id", "person_id", "org_id", "title", "dept", "state", "by", "source",
                   "evidence_ref", "quote", "started_at", "ended_at", "recorded_at",
                   "superseded_by", "revoked_at", "revoked_by", "revoke_reason"),
    "self_identity": ("type", "account_id", "kind", "value_normalized", "persona_raw", "created_at"),
}
GRAPH_CP_KINDS = frozenset({"wechat", "phone", "email", "feishu", "imsg", "whatsapp", "wecom",
                            "xhs", "unknown"})
GRAPH_CP_SOURCES = frozenset({"conversation_counterpart", "roster_friend", "selfstated_capture",
                              "user_link", "user_merge", "dedup_batch", "phone_suffix_match",
                              "unknown"})
GRAPH_BY = frozenset({"user", "engine"})
GRAPH_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")      # §2.4 第 4 条
GRAPH_E164 = re.compile(r"^\+\d{6,15}$")                              # C10
GRAPH_EVIDENCE_REF = "amr-evidence:"


def _g_ts(v: object) -> bool:
    return isinstance(v, str) and bool(GRAPH_TS.match(v))


def _g_opt_ts(v: object) -> bool:
    return v is None or _g_ts(v)


def _g_str(v: object) -> bool:
    return isinstance(v, str) and bool(v)


def _g_opt_str(v: object) -> bool:          # §1 第 5 条：空串不合法，缺省写 null
    return v is None or _g_str(v)


def _g_str_list(v: object) -> bool:
    return isinstance(v, list) and all(_g_str(x) for x in v)


def _g_digits(v: object) -> bool:           # AMR 整数主键 → 十进制字符串（§2.4 第 6 条）
    return isinstance(v, str) and v.isdigit()


def _g_opt_int(v: object) -> bool:
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


def validate_graph_export(lines: list[str]) -> list[str]:
    """对一份 amr-graph-export/1 流（已按 \\n 切开、不含末尾空元素）返回违规列表（[] = 合规）。
    纯函数，永不抛。覆盖 graph/amr-graph-export.md §8.1 C1–C11。"""
    viol: list[str] = []
    recs: list[tuple[int, dict]] = []
    for i, line in enumerate(lines, 1):
        if line == "" or line != line.strip():
            viol.append(f"line {i}: empty line or surrounding whitespace (§2.1)")
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            viol.append(f"line {i}: cannot parse JSON: {e}")
            continue
        if not isinstance(obj, dict):
            viol.append(f"line {i}: record is not an object")
            continue
        recs.append((i, obj))
    if not recs:
        return viol + ["empty stream: header missing (C1)"]

    # ---- C1 / C3 header --------------------------------------------------------------------
    _hi, h = recs[0]
    if h.get("type") != "header":
        return viol + ["C1: first record must be type=header"]
    if list(h.keys()) != list(GRAPH_FIELDS["header"]):
        viol.append(f"header: keys/order {list(h.keys())} != {list(GRAPH_FIELDS['header'])} (C3)")
    schema = h.get("schema")
    if not (isinstance(schema, str) and schema.startswith(GRAPH_SCHEMA_PREFIX)
            and schema[len(GRAPH_SCHEMA_PREFIX):].split(".")[0] == "1"):
        viol.append(f"header.schema {schema!r} must be {GRAPH_SCHEMA_PREFIX}1[.x] (C1)")
    if h.get("status") != "ok":
        viol.append(f"header.status {h.get('status')!r} != 'ok' (C1：error 流不进 dry-run)")
    mode = h.get("mode")
    if mode not in ("full", "incremental"):
        viol.append(f"header.mode {mode!r} not in {{full, incremental}} (§3.1)")
    elif mode == "full" and h.get("since") is not None:
        viol.append("header.since must be null in full mode (§3.1)")
    elif mode == "incremental" and not _g_ts(h.get("since")):
        viol.append("header.since must be a timestamp in incremental mode (§3.1)")
    if h.get("pii_policy") not in ("raw", "redacted"):
        viol.append(f"header.pii_policy {h.get('pii_policy')!r} not in {{raw, redacted}} (§5.4)")
    if not _g_ts(h.get("exported_at")):
        viol.append("header.exported_at must be RFC 3339 UTC seconds (§2.4)")
    src = h.get("source")
    if not (isinstance(src, dict) and list(src.keys()) == ["amr_version", "amr_commit", "db_sha256"]
            and _g_str(src.get("amr_version")) and _g_opt_str(src.get("amr_commit"))
            and _g_opt_str(src.get("db_sha256"))):
        viol.append("header.source must be {amr_version, amr_commit?, db_sha256?} (§3.1)")
    rules = h.get("rules")
    if not (isinstance(rules, dict)
            and list(rules.keys()) == ["identifier_canon", "phone_e164", "redaction"]
            and all(_g_str(v) for v in rules.values())):
        viol.append("header.rules must be {identifier_canon, phone_e164, redaction} (§3.1)")
    wm = h.get("watermark")
    if not (isinstance(wm, dict) and list(wm.keys()) == ["persons_updated_at_max", "events_id_max"]
            and _g_opt_ts(wm.get("persons_updated_at_max")) and _g_opt_int(wm.get("events_id_max"))):
        viol.append("header.watermark must be {persons_updated_at_max?, events_id_max?} (§3.1)")
    inv = h.get("invariants")
    if not (isinstance(inv, dict) and list(inv.keys()) == ["persons_sharing_endpoint"]):
        viol.append("header.invariants must be {persons_sharing_endpoint} (§3.1)")
    elif inv.get("persons_sharing_endpoint") != 0:
        viol.append(f"header.invariants.persons_sharing_endpoint "
                    f"{inv.get('persons_sharing_endpoint')!r} != 0 (C7)")
    counts = h.get("counts")
    if not (isinstance(counts, dict) and list(counts.keys()) == list(GRAPH_TYPES)
            and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                    for v in counts.values())):
        viol.append(f"header.counts must have exactly {list(GRAPH_TYPES)} as non-negative ints (C4)")
        counts = {}
    bs = h.get("body_sha256")
    if not (bs is None or (isinstance(bs, str) and re.fullmatch(r"[0-9a-f]{64}", bs))):
        viol.append("header.body_sha256 must be null or 64 lowercase hex (§2.4)")

    # ---- C2 / C3 body: type blocks, key order ---------------------------------------------
    by_type: dict[str, list[tuple[int, dict]]] = {t: [] for t in GRAPH_TYPES}
    last_rank = -1
    for i, r in recs[1:]:
        t = r.get("type")
        if t == "header":
            viol.append(f"line {i}: second header (C1)")
            continue
        if t not in GRAPH_TYPES:
            continue                          # C2：未知 type 跳过并计数（minor 兼容）
        rank = GRAPH_TYPES.index(t)
        if rank < last_rank:
            viol.append(f"line {i}: {t} after a later type block — type block order (§2.4 第 1 条)")
        last_rank = max(last_rank, rank)
        if list(r.keys()) != list(GRAPH_FIELDS[t]):
            viol.append(f"line {i}: {t} keys/order {list(r.keys())} != {list(GRAPH_FIELDS[t])} (C3)")
        by_type[t].append((i, r))

    # ---- C4 counts == rows ---------------------------------------------------------------
    for t in GRAPH_TYPES:
        if counts and counts.get(t) != len(by_type[t]):
            viol.append(f"header.counts.{t}={counts.get(t)!r} but {len(by_type[t])} rows (C4)")

    def sorted_check(t: str, key) -> None:
        rows = [r for _i, r in by_type[t]]
        try:
            if rows != sorted(rows, key=key):
                viol.append(f"{t}: rows not in contract sort order (§2.4 第 1 条)")
        except (TypeError, ValueError, AttributeError):
            viol.append(f"{t}: sort key not computable (field type error)")

    # ---- person ----------------------------------------------------------------------------
    persons: dict[str, dict] = {}
    for i, r in by_type["person"]:
        pid = r.get("id")
        if not _g_str(pid):
            viol.append(f"line {i}: person.id must be a non-empty string")
        elif pid in persons:
            viol.append(f"line {i}: duplicate person.id (C5)")
        else:
            persons[pid] = r
        if not _g_opt_str(r.get("name")):
            viol.append(f"line {i}: person.name must be null or non-empty string")
        if r.get("name_by") not in GRAPH_BY:
            viol.append(f"line {i}: person.name_by {r.get('name_by')!r} not in {{user, engine}}")
        if not _g_str_list(r.get("aliases")):
            viol.append(f"line {i}: person.aliases must be a list of non-empty strings")
        if not isinstance(r.get("watch"), bool):
            viol.append(f"line {i}: person.watch must be bool")
        for f in ("created_at", "updated_at"):
            if not _g_ts(r.get(f)):
                viol.append(f"line {i}: person.{f} must be RFC 3339 UTC (C11)")
        if not _g_opt_ts(r.get("last_contact_at")):
            viol.append(f"line {i}: person.last_contact_at must be null or RFC 3339 UTC (C11)")
        acc = r.get("accounts")
        if not (isinstance(acc, list) and all(_g_opt_int(a) and a is not None for a in acc)
                and acc == sorted(set(acc))):
            viol.append(f"line {i}: person.accounts must be a sorted unique list of ints")
        srcs = r.get("sources")
        if not (isinstance(srcs, list) and all(s in GRAPH_CP_SOURCES for s in srcs)
                and srcs == sorted(set(srcs))):
            viol.append(f"line {i}: person.sources must be a sorted unique list of source enum values")
    sorted_check("person", lambda r: str(r.get("id")).encode("utf-8"))

    # ---- contact_point ---------------------------------------------------------------------
    cp_keys: set[tuple] = set()
    endpoint_owner: dict[tuple, str] = {}
    derived_sources: dict[str, set] = {pid: set() for pid in persons}
    derived_accounts: dict[str, set] = {pid: set() for pid in persons}
    for i, r in by_type["contact_point"]:
        pid, kind = r.get("person_id"), r.get("kind")
        if pid not in persons:
            viol.append(f"line {i}: contact_point.person_id does not resolve to a person (C6)")
        if kind not in GRAPH_CP_KINDS:
            viol.append(f"line {i}: contact_point.kind {kind!r} not in enum (C11)")
        if not _g_opt_str(r.get("value_raw")):
            viol.append(f"line {i}: contact_point.value_raw must be null or non-empty string")
        vn = r.get("value_normalized")
        if not _g_str(vn):
            viol.append(f"line {i}: contact_point.value_normalized must be a non-empty string")
        e164, unparsed = r.get("value_e164"), r.get("unparsed")
        if kind == "phone":
            if not (e164 is None or (isinstance(e164, str) and GRAPH_E164.match(e164))):
                viol.append(f"line {i}: contact_point.value_e164 must be null or E.164 (C10)")
            if not isinstance(unparsed, bool) or unparsed != (e164 is None):
                viol.append(f"line {i}: phone: unparsed must be bool and == (value_e164 is null) (C10)")
        elif e164 is not None or unparsed is not None:
            viol.append(f"line {i}: non-phone: value_e164 and unparsed must be null (C10)")
        source = r.get("source")
        if source not in GRAPH_CP_SOURCES:
            viol.append(f"line {i}: contact_point.source {source!r} not in enum (C11)")
        if r.get("by") not in GRAPH_BY | {"unknown"}:
            viol.append(f"line {i}: contact_point.by {r.get('by')!r} not in {{user, engine, unknown}}")
        if not _g_opt_ts(r.get("confirmed_at")):
            viol.append(f"line {i}: contact_point.confirmed_at must be null or RFC 3339 UTC (C11)")
        ev = r.get("evidence_ref")
        if not (ev is None or (_g_str(ev) and ev.startswith(GRAPH_EVIDENCE_REF))):
            viol.append(f"line {i}: contact_point.evidence_ref must be null or '{GRAPH_EVIDENCE_REF}<id>'")
        md = r.get("match_digits")
        if not _g_opt_int(md) or (md is not None and source != "phone_suffix_match") \
                or (md is None and source == "phone_suffix_match"):
            viol.append(f"line {i}: match_digits must be an int iff source=phone_suffix_match (C10)")
        if not _g_opt_str(r.get("batch")) or (r.get("batch") is None and source == "dedup_batch"):
            viol.append(f"line {i}: contact_point.batch must be non-empty when source=dedup_batch")
        if not _g_opt_int(r.get("account_id")):
            viol.append(f"line {i}: contact_point.account_id must be null or int")
        if not isinstance(r.get("pinned"), bool):
            viol.append(f"line {i}: contact_point.pinned must be bool")
        nk = (pid, kind, vn, source)
        if nk in cp_keys:
            viol.append(f"line {i}: duplicate contact_point natural key (C5)")
        cp_keys.add(nk)
        ep = (kind, vn)
        if ep in endpoint_owner and endpoint_owner[ep] != pid:
            viol.append(f"line {i}: endpoint ({kind}, …) owned by two persons — persons_sharing_endpoint (C7)")
        endpoint_owner.setdefault(ep, pid)
        if pid in persons:
            derived_sources[pid].add(source)
            if r.get("account_id") is not None:
                derived_accounts[pid].add(r["account_id"])
    sorted_check("contact_point", lambda r: (str(r.get("person_id")).encode("utf-8"), str(r.get("kind")),
                                             str(r.get("value_normalized")), str(r.get("source"))))
    for pid, p in persons.items():            # C9 便利字段与真相一致
        if p.get("sources") != sorted(derived_sources[pid]):
            viol.append(f"person {pid[:4]}…: sources {p.get('sources')} != derived from contact_points (C9)")
        if p.get("accounts") != sorted(derived_accounts[pid]):
            viol.append(f"person {pid[:4]}…: accounts {p.get('accounts')} != derived from contact_points (C9)")

    # ---- merge_record ----------------------------------------------------------------------
    mr_ids: set[str] = set()
    survivor_of: dict[str, str] = {}
    for i, r in by_type["merge_record"]:
        mid = r.get("id")
        if not _g_digits(mid):
            viol.append(f"line {i}: merge_record.id must be a decimal string")
        elif mid in mr_ids:
            viol.append(f"line {i}: duplicate merge_record.id (C5)")
        mr_ids.add(str(mid))
        action, surv, merged = r.get("action"), r.get("survivor_id"), r.get("merged_id")
        if action not in ("merge", "self"):
            viol.append(f"line {i}: merge_record.action {action!r} not in {{merge, self}}")
        if action == "self" and surv is not None:
            viol.append(f"line {i}: action=self requires survivor_id=null")
        if action == "merge" and not _g_str(surv):
            viol.append(f"line {i}: action=merge requires survivor_id")
        if not _g_str(merged):
            viol.append(f"line {i}: merge_record.merged_id must be a non-empty string")
        if r.get("by") not in GRAPH_BY:
            viol.append(f"line {i}: merge_record.by {r.get('by')!r} not in {{user, engine}}")
        for f in ("batch", "rule", "reason"):
            if not _g_opt_str(r.get(f)):
                viol.append(f"line {i}: merge_record.{f} must be null or non-empty string")
        if not (r.get("evidence") is None or isinstance(r.get("evidence"), dict)):
            viol.append(f"line {i}: merge_record.evidence must be null or object")
        if not _g_ts(r.get("merged_at")):
            viol.append(f"line {i}: merge_record.merged_at must be RFC 3339 UTC (C11)")
        if not _g_opt_ts(r.get("undone_at")):
            viol.append(f"line {i}: merge_record.undone_at must be null or RFC 3339 UTC (C11)")
        if action == "merge" and r.get("undone_at") is None and _g_str(merged) and _g_str(surv):
            if merged in persons:
                viol.append(f"line {i}: active merge but merged_id still present as a person (C8)")
            survivor_of[merged] = surv
    sorted_check("merge_record", lambda r: int(r.get("id")))
    for merged, surv in survivor_of.items():   # C8 链可解、无环
        seen, cur, ok = set(), surv, False
        while True:
            if cur in persons:
                ok = True
                break
            if cur in seen or cur not in survivor_of:
                break
            seen.add(cur)
            cur = survivor_of[cur]
        if not ok:
            viol.append(f"merge_record: survivor chain of merged {merged[:4]}… does not resolve to a person (C8)")

    # ---- negative_sample -------------------------------------------------------------------
    ns_keys: set[tuple] = set()
    for i, r in by_type["negative_sample"]:
        kind, a, b = r.get("kind"), r.get("a_id"), r.get("b_id")
        if not _g_opt_str(kind):
            viol.append(f"line {i}: negative_sample.kind must be null or non-empty string")
        if not (_g_str(a) and _g_str(b)):
            viol.append(f"line {i}: negative_sample.a_id / b_id must be non-empty strings")
        elif a == b:
            viol.append(f"line {i}: negative_sample.a_id == b_id (C10)")
        for f in ("a_person_id", "b_person_id"):
            v = r.get(f)
            if not _g_opt_str(v):
                viol.append(f"line {i}: negative_sample.{f} must be null or non-empty string")
            elif v is not None and v not in persons:
                viol.append(f"line {i}: negative_sample.{f} does not resolve to a person (C6)")
        if not _g_opt_str(r.get("reason")):
            viol.append(f"line {i}: negative_sample.reason must be null or non-empty string")
        if not _g_ts(r.get("created_at")):
            viol.append(f"line {i}: negative_sample.created_at must be RFC 3339 UTC (C11)")
        nk = (kind, a, b)
        if nk in ns_keys:
            viol.append(f"line {i}: duplicate negative_sample (C5)")
        ns_keys.add(nk)
    sorted_check("negative_sample", lambda r: (r.get("kind") or "", str(r.get("a_id")), str(r.get("b_id"))))

    # ---- organization ----------------------------------------------------------------------
    orgs: dict[str, dict] = {}
    for i, r in by_type["organization"]:
        oid = r.get("id")
        if not _g_digits(oid):
            viol.append(f"line {i}: organization.id must be a decimal string")
        elif oid in orgs:
            viol.append(f"line {i}: duplicate organization.id (C5)")
        else:
            orgs[oid] = r
        if not _g_str(r.get("name")):
            viol.append(f"line {i}: organization.name must be a non-empty string")
        if not _g_str_list(r.get("aliases")):
            viol.append(f"line {i}: organization.aliases must be a list of non-empty strings")
        for f in ("kind_raw", "parent_id", "merged_into", "registration_no", "jurisdiction"):
            if not _g_opt_str(r.get(f)):
                viol.append(f"line {i}: organization.{f} must be null or non-empty string")
        if r.get("by") not in GRAPH_BY:
            viol.append(f"line {i}: organization.by {r.get('by')!r} not in {{user, engine}}")
        if not _g_ts(r.get("created_at")):
            viol.append(f"line {i}: organization.created_at must be RFC 3339 UTC (C11)")
        if not (r.get("domains") is None or _g_str_list(r.get("domains"))):
            viol.append(f"line {i}: organization.domains must be null or a list of non-empty strings")
    for i, r in by_type["organization"]:
        for f in ("parent_id", "merged_into"):
            v = r.get(f)
            if v is not None and v not in orgs:
                viol.append(f"line {i}: organization.{f} does not resolve to an organization (C6)")
    sorted_check("organization", lambda r: int(r.get("id")))

    # ---- employment ------------------------------------------------------------------------
    emp_ids: set[str] = set()
    for i, r in by_type["employment"]:
        eid = r.get("id")
        if not _g_digits(eid):
            viol.append(f"line {i}: employment.id must be a decimal string")
        elif eid in emp_ids:
            viol.append(f"line {i}: duplicate employment.id (C5)")
        emp_ids.add(str(eid))
        if r.get("person_id") not in persons:
            viol.append(f"line {i}: employment.person_id does not resolve to a person (C6)")
        if r.get("org_id") not in orgs:
            viol.append(f"line {i}: employment.org_id does not resolve to an organization (C6)")
        for f in ("title", "dept", "source", "quote", "superseded_by", "revoked_by", "revoke_reason"):
            if not _g_opt_str(r.get(f)):
                viol.append(f"line {i}: employment.{f} must be null or non-empty string")
        if r.get("state") not in ("current", "former"):
            viol.append(f"line {i}: employment.state {r.get('state')!r} not in {{current, former}}")
        if r.get("by") not in GRAPH_BY:
            viol.append(f"line {i}: employment.by {r.get('by')!r} not in {{user, engine}}")
        ev = r.get("evidence_ref")
        if not (ev is None or (_g_str(ev) and ev.startswith(GRAPH_EVIDENCE_REF))):
            viol.append(f"line {i}: employment.evidence_ref must be null or '{GRAPH_EVIDENCE_REF}<id>'")
        for f in ("started_at", "ended_at", "revoked_at"):
            if not _g_opt_ts(r.get(f)):
                viol.append(f"line {i}: employment.{f} must be null or RFC 3339 UTC (C11)")
        if not _g_ts(r.get("recorded_at")):
            viol.append(f"line {i}: employment.recorded_at must be RFC 3339 UTC (C11)")
    for i, r in by_type["employment"]:
        sb = r.get("superseded_by")
        if sb is not None and sb not in emp_ids:
            viol.append(f"line {i}: employment.superseded_by does not resolve to an employment (C6)")
    sorted_check("employment", lambda r: int(r.get("id")))

    # ---- self_identity ---------------------------------------------------------------------
    for i, r in by_type["self_identity"]:
        if not _g_opt_int(r.get("account_id")):
            viol.append(f"line {i}: self_identity.account_id must be null or int")
        if r.get("kind") not in GRAPH_CP_KINDS:
            viol.append(f"line {i}: self_identity.kind {r.get('kind')!r} not in enum (C11)")
        if not _g_str(r.get("value_normalized")):
            viol.append(f"line {i}: self_identity.value_normalized must be a non-empty string")
        if not _g_opt_str(r.get("persona_raw")):
            viol.append(f"line {i}: self_identity.persona_raw must be null or non-empty string")
        if not _g_ts(r.get("created_at")):
            viol.append(f"line {i}: self_identity.created_at must be RFC 3339 UTC (C11)")
    sorted_check("self_identity", lambda r: (str(r.get("kind")), str(r.get("value_normalized"))))

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

    # graph/amr-graph-export.md §8.1：AMR → Metis 导出流（JSONL；一份文件 = 一次导出；另一套校验，单独目录）。
    graph_dir = root / "fixtures" / "amr-graph-export"
    graph_files = sorted(graph_dir.glob("*.jsonl"))
    for f in graph_files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot read as UTF-8: {e}", file=sys.stderr)
            total_viol += 1
            continue
        viol = []
        if "\r" in text:
            viol.append("stream contains CR — lines must end with \\n only (§2.1)")
        if not text.endswith("\n"):
            viol.append("stream must end with \\n (§2.1)")
        viol += validate_graph_export(text.split("\n")[:-1] if text.endswith("\n") else text.split("\n"))
        for v in viol:
            print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
        total_viol += len(viol)
        if not viol:
            print(f"  [ok]   {f.name} (amr-graph-export, {text.count(chr(10))} lines)")

    total_viol += check_constitution_sync(root)

    print(f"\nconformance: {len(files)} envelope + {len(read_files)} read-signal "
          f"+ {len(rich_files)} rich-file + {len(graph_files)} amr-graph-export fixtures, "
          f"{total_viol} violation(s)")
    if total_viol:
        print("conformance: RED — fixtures drifted from contract", file=sys.stderr)
        return 1
    print("conformance: GREEN — all fixtures conform to message.canonical + rich-file.archive "
          "+ amr-graph-export; constitution texts in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
