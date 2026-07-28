# 智能体执行 Playbook

## 开始

```bash
python tools/verify_handoff.py
python tools/print_authorization.py
git status --short  # 若尚未 git init，记录即可
```

## 建立工作记录

在 `reports/` 使用模板，记录：

- 实际命令；
- 只读观察；
- 决策；
- 文件变更；
- 测试；
- 未验证项。

不要把私人路径粘贴进报告。

## 实施

- 先定义域状态和边界；
- 再实现安全 guard；
- 再 persistence；
- 再 CLI；
- 每个行为配测试；
- 不创建后续模型 stub 返回“成功”；
- 对未授权命令返回 gate error。

## 自审

- 对照当前 N2B0.7 YAML 每项；
- 运行统一质量命令；
- `git diff --check`；
- 敏感扫描；
- 检查 `git status --ignored`；
- 确认 fixture 未改；
- 确认 `PROJECT_STATE.json` 未被擅自解锁；
- 检查报告四态。

## Commit

当前阶段候选建议：

```text
docs(n2b): qualify GPU-native artifacts fail-closed
```

一个 commit。不得 merge/push。

## 停止

输出 `N2B0_7_ARTIFACT_QUALIFICATION_BLOCKED` 或等待 Owner artifact decision；不问“要不要顺便做 N2B1”，不执行任何 N2B1 命令。
