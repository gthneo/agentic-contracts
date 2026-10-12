# send-target §6 发图片 —— 一致性夹具

每个文件 = `{"type": "request" | "response" | "capability", "body": {...}}`。

- `valid/`:必须全部通过 `scripts/conformance.py`。
- `invalid/`:每条必须被判出**至少一处**违规(反向牙齿:校验放宽到放过它们 = CI 红)。

口径见 `send-target/send-target.md` §6.1(请求)/ §6.3(失败语义)/ §6.6(能力声明)。全部合成数据。
