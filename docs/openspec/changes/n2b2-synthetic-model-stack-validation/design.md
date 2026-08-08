## Context

nightly-photo-intelligence-pipeline 采用不可变基线 + 双门禁（Phase Gate + Data Gate）治理体系。`MASTER_EXECUTION_CONTRACT.md` 为权威来源；comet-classic 是可选开发流程外壳，不覆盖主合同。N2B2 本轮 Owner Choice A 指定本地 `qwen3.5:9b`（Q4_K_M）取代计划的 Qwen3-VL-2B，且仅校验现有 TorchVision 缓存、不下载。

## Goals / Non-Goals

**Goals:**
- 在不越权前提下，落地 N2B2 全部控制面契约文件与第 18 节停止态报告。
- 配置 comet-classic（OpenSpec classic 布局），使后续 N2B2 实现可在该流程外壳下推进。

**Non-Goals:**
- 不运行任何模型推理或视觉前向。
- 不下载 Qwen3-VL-2B、不重新下载 TorchVision 权重。
- 不推进 git 历史（commit 延迟至 N2B1P 批准）。
- 不修改任何锁定/停止边界状态。

## Decisions

- **控制面-only 路径**：因 N2B1P 独立审查未落盘，严格走 Section 2 的「不越权控制面检查 + 停止」分支，停止态 = `N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED`。
- **gitignore 排除 scratch**：将 `.workbuddy/`、`.superpowers/`、`docs/superpowers/` 纳入忽略，消除 sensitive_file_scan 对绝对路径的 2 处误报（均属助手/comet 草稿，非交付物）。
- **skip_specs: true**：本变更无 spec 级能力增量，仅落地控制面文件，避免 OpenSpec 拒绝零 delta 变更。
- **commit 延迟**：提交会推进 git 历史越过仍处 N2B1P 的治理状态，导致 `verify_handoff.py` 与 `tests/test_git.py` 失败（按设计的一致性守卫）。故 commit 与下游实现一并延迟至 N2B1P 批准。

## Risks / Trade-offs

- 工作树保持 dirty 直到 N2B1P 批准；`test_git_worktree_is_clean` 等测试会在批准前持续失败——这是预期且符合治理的。
- comet-classic skill 自带参考文件（classic-layout.md / scripts.md）在包内缺失，已依据 `comet classic root show` 与标准 OpenSpec 约定推断根布局，并在本变更中落地。
