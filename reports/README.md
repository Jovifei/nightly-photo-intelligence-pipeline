# Reports

交付包本身不包含伪造的 N0 执行结果。实现智能体必须从 `templates/` 复制并根据真实命令填写：

- `N0_environment_report.md`
- `N0_test_evidence.md`
- `N0_unresolved_issues.md`
- `N1_detailed_plan.md`

`PASS` 只能用于真实运行且证据存在；否则使用 `FAIL`、`SKIPPED` 或 `NOT_AVAILABLE`。
