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


# send-target/send-target.md §6（发图片）：请求 / 响应 / 能力声明三种夹具。
IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/gif"})
IMAGE_MAX_BYTES = 20 * 1024 * 1024        # §6.1-3:班迪 2026-10-12 定 20 MiB
IMAGE_MAGIC = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",),
               "image/gif": (b"GIF87a", b"GIF89a")}
# §6.3：发前失败码（确定没发出）+ 发后未确认。成功响应不带码。
IMAGE_PRESEND_CODES = frozenset({"CONTACT_NOT_FOUND", "AMBIGUOUS", "NOT_LOGGED_IN", "SEND_IN_FLIGHT",
                                 "SEND_BUSY",
                                 "INVALID_IMAGE", "INVALID_REQUEST", "SEND_FAILED_PRESEND"})
IMAGE_FAIL_CODES = IMAGE_PRESEND_CODES | {"SEND_UNCONFIRMED"}


IDEM_KEY_RE = __import__("re").compile(r"^[A-Za-z0-9._:-]{1,64}$")   # §6.1-6
LOOKUP_STATES = frozenset({"in_flight", "sent", "not_sent", "unknown"})   # §6.4-2


def validate_image_send(obj: object) -> list[str]:
    """§6 夹具 → 违规列表（[] = 合规）。夹具形如 {"type": request|response|capability, "body": {...}}。"""
    import base64
    import binascii
    import hashlib
    if not isinstance(obj, dict) or not isinstance(obj.get("body"), dict):
        return ["fixture must be {type, body:{...}}"]
    t, body = obj.get("type"), obj["body"]
    viol: list[str] = []
    if t == "request":
        if not (isinstance(body.get("chatId"), str) and body["chatId"]):
            viol.append("chatId must be a non-empty string (§6.1)")
        if "text" in body or "file" in body:
            viol.append("image must not be combined with text/file → INVALID_REQUEST (§6.1-4)")
        img = body.get("image")
        if not isinstance(img, dict):
            return viol + ["image must be an object (§6.1)"]
        mime = img.get("mimeType")
        if mime not in IMAGE_MIMES:
            viol.append(f"mimeType {mime!r} not in {sorted(IMAGE_MIMES)} (§6.1-1)")
        try:
            data = base64.b64decode(img.get("data") or "", validate=True)
        except (binascii.Error, ValueError, TypeError):
            return viol + ["data is not standard base64 → INVALID_IMAGE (§6.1-2)"]
        if not data:
            viol.append("data decodes to empty (§6.1)")
        if len(data) > IMAGE_MAX_BYTES:
            viol.append(f"decoded size {len(data)} > {IMAGE_MAX_BYTES} (§6.1-3)")
        if mime in IMAGE_MAGIC and not data.startswith(IMAGE_MAGIC[mime]):
            viol.append("magic bytes do not match mimeType → INVALID_IMAGE (§6.1-1)")
        # D1 = b(班迪 2026-10-12):键可选;给了就必须合规
        if "idempotencyKey" in body:
            key = body.get("idempotencyKey")
            if not (isinstance(key, str) and IDEM_KEY_RE.match(key)):
                viol.append("idempotencyKey must be 1-64 chars of [A-Za-z0-9._:-] (§6.1-6)")
        if "sha256" in img and img["sha256"] != hashlib.sha256(data).hexdigest():
            viol.append("sha256 does not match decoded bytes → INVALID_IMAGE (§6.1-5)")
    elif t == "response":
        if not isinstance(body.get("ok"), bool):
            viol.append("ok must be a bool (§2.1)")
        if not (isinstance(body.get("chat_id"), str) and body["chat_id"]):
            viol.append("chat_id must be a non-empty string (§2.1)")
        if body.get("ok") is True and "code" in body:
            viol.append("a successful response carries no code (§2.1)")
        for flag in ("deduped", "idempotent", "opened"):
            if flag in body and not isinstance(body[flag], bool):
                viol.append(f"{flag} must be a bool when present (§6.4)")
        if body.get("ok") is False and body.get("code") not in IMAGE_FAIL_CODES:
            viol.append(f"failure code {body.get('code')!r} must be a pre-send code or "
                        f"SEND_UNCONFIRMED (§6.3)")
    elif t == "lookup":
        st = body.get("state")
        if st not in LOOKUP_STATES:
            viol.append(f"state {st!r} not in {sorted(LOOKUP_STATES)} (§6.4-2)")
        for camel in ("chatId", "receivedAt", "sentAt"):
            if camel in body:
                viol.append(f"{camel} must be snake_case in responses (§2.1-2 · C3)")
        if not (isinstance(body.get("chat_id"), str) and body["chat_id"]):
            viol.append("chat_id must be a non-empty string (§6.4-2)")
        sha = body.get("sha256")
        if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
            viol.append("sha256 must be 64 lowercase hex chars (§6.4-2)")
        if not isinstance(body.get("received_at"), int):
            viol.append("received_at must be Unix seconds (int) (§6.4-2 · C4)")
        if st == "sent" and not isinstance(body.get("sent_at"), int):
            viol.append("a sent record carries sent_at (Unix seconds) (§6.4-2)")
        if st in ("not_sent", "unknown") and body.get("code") not in IMAGE_FAIL_CODES:
            viol.append("a not_sent / unknown record carries its failure code (§6.4-2)")
    elif t == "lookup_miss":
        if body.get("code") != "KEY_NOT_FOUND":
            viol.append('a lookup 404 must carry code "KEY_NOT_FOUND" (§6.4-2 · C2)')
        if not isinstance(body.get("store_since"), int):
            viol.append("a lookup 404 must carry store_since (Unix seconds) (§6.4-2 · C2)")
        if "instance" in body and not isinstance(body["instance"], str):
            viol.append("instance must be a string when present (§6.4-2)")
    elif t == "capability":
        img = ((body.get("send") or {}).get("image")) if isinstance(body.get("send"), dict) else None
        if not isinstance(img, dict):
            return ["send.image must be an object (§6.6)"]
        mimes = img.get("mimes")
        if not (isinstance(mimes, list) and mimes and set(mimes) <= IMAGE_MIMES):
            viol.append("send.image.mimes must be a non-empty subset of the whitelist (§6.6)")
        mb = img.get("max_bytes")
        if not (isinstance(mb, int) and 0 < mb <= IMAGE_MAX_BYTES):
            viol.append("send.image.max_bytes must be an int in (0, 20 MiB] (§6.1-3)")
        if img.get("dedup") != "sha256":
            viol.append('send.image.dedup must be "sha256" (§6.4-1)')
        if img.get("idempotency") is not True:
            viol.append("send.image.idempotency must be true (§6.4-2 / §6.6)")
        if "instance" in img and not (isinstance(img["instance"], str) and img["instance"]):
            viol.append("send.image.instance must be a non-empty string when present (§6.4-2)")
        mr = img.get("max_runtime_ms")
        if not (isinstance(mr, int) and mr > 0):
            viol.append("send.image.max_runtime_ms must be a positive int (§6.2-4)")
    else:
        viol.append(f"unknown fixture type {t!r}")
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

    # send-target §6（发图片）：valid/ 必须全过；invalid/ 每条必须被判出至少一处违规（反向牙齿）。
    img_dir = root / "fixtures" / "send-target-image"
    img_valid = sorted((img_dir / "valid").glob("*.json"))
    img_invalid = sorted((img_dir / "invalid").glob("*.json"))
    for name, lst in (("valid", img_valid), ("invalid", img_invalid)):
        if not lst:                      # §6.8:目录空 = 牙齿没了,fail-closed
            print(f"  [FAIL] fixtures/send-target-image/{name}/ is empty", file=sys.stderr)
            total_viol += 1
    for f, must_pass in [(f, True) for f in img_valid] + [(f, False) for f in img_invalid]:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [FAIL] {f.name}: cannot parse JSON: {e}", file=sys.stderr)
            total_viol += 1
            continue
        viol = validate_image_send(obj)
        if must_pass:
            for v in viol:
                print(f"  [FAIL] {f.name}: {v}", file=sys.stderr)
            total_viol += len(viol)
            if not viol:
                print(f"  [ok]   {f.name} (send-target-image)")
        elif not viol:
            print(f"  [FAIL] invalid/{f.name}: expected a violation, got none (§6 牙齿钝了)",
                  file=sys.stderr)
            total_viol += 1
        else:
            print(f"  [ok]   invalid/{f.name} rejected: {viol[0]}")

    print(f"\nconformance: {len(files)} envelope + {len(read_files)} read-signal "
          f"+ {len(rich_files)} rich-file + {len(img_valid)}/{len(img_invalid)} send-target-image "
          f"(valid/invalid) fixtures, {total_viol} violation(s)")
    if total_viol:
        print("conformance: RED — fixtures drifted from contract", file=sys.stderr)
        return 1
    print("conformance: GREEN — all fixtures conform to message.canonical + rich-file.archive + send-target §6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
