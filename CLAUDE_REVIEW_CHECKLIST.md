# Claude Code N0 独立审查清单

默认只审查，不实现、不批准。

## Scope

- [ ] 只有 N0 变更；
- [ ] 无模型/云/OpenClaw/App；
- [ ] `PROJECT_STATE` 未解锁；
- [ ] 一个 commit。

## Source safety

- [ ] 无 write/move/delete/chmod API；
- [ ] source/runtime overlap；
- [ ] symlink escape；
- [ ] pre/post integrity；
- [ ] path redaction。

## State and recovery

- [ ] 状态 enum/迁移守卫；
- [ ] SQLite transaction；
- [ ] interrupted run；
- [ ] dry-run no DB asset mutation；
- [ ] idempotency。

## Quality/evidence

- [ ] pytest/lint/typecheck；
- [ ] valid/invalid Schema；
- [ ] stable exit codes；
- [ ] Git sensitive scan；
- [ ] reports truthful；
- [ ] skips are not passes。

## 结论

`PASS / PASS_WITH_FINDINGS / FAIL`，并明确 `NOT_VERIFIED`。
Reviewer 结论不等于 Owner 进入 N1 批准。
