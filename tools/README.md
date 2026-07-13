# Handoff Tools

这些工具只验证交付包，不实现生产流水线。

```bash
python tools/verify_handoff.py
python tools/print_authorization.py
```

验证器只读运行，不联网、不安装依赖。若环境已有 `jsonschema`，会执行完整 Draft 2020-12 示例验证；否则执行内置核心规则并清楚标记可选验证器缺失。
