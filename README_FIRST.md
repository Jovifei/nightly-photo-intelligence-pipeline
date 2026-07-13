# Nightly Photo Intelligence Pipeline — 智能体交付包

项目名：`nightly-photo-intelligence-pipeline`  
中文名：**夜间摄影灵感分析流水线**  
交付包版本：`1.0.0`  
交付日期：`2026-07-12`

## 这是什么

这是一套面向实现智能体的、可直接放入独立 Git 仓库根目录的工程交接包。它不是完整实现，也不是允许一次性执行全部路线图的授权书。

它回答七个必须一致的问题：

1. **为什么做**：把本地摄影收藏转化成可审计、可搜索、可供摄影导演 App 消费的结构化知识。
2. **做什么**：建设本地优先、可断点续传、可重复执行、人工审核后导出的离线数据生产流水线。
3. **怎么做**：显式 Python 阶段、SQLite 状态机、严格 JSON Schema、只读源保护、逐阶段模型 Benchmark。
4. **先做什么**：当前只允许执行 N0 环境与脚手架，且只使用三张合成 fixture。
5. **不能做什么**：不能扫描真实收藏、不能下载大模型、不能改驱动/WSL/Docker 系统配置、不能连接云端、不能接入 OpenClaw、不能修改主 App。
6. **怎样验证**：每个需求、阶段和数据放量都有可执行验收、证据文件和负向测试。
7. **什么时候停止**：N0 完成一个独立 commit 后必须停止，等待 Owner 明确批准 N1；任何通过都不会自动扩大数据量。

## 智能体入口

- 任意实现智能体：先读 [`MASTER_EXECUTION_CONTRACT.md`](MASTER_EXECUTION_CONTRACT.md)
- Codex / 支持 `AGENTS.md` 的工具：再读 [`AGENTS.md`](AGENTS.md)
- Claude Code：再读 [`CLAUDE.md`](CLAUDE.md)
- OpenClaw：只能读 [`OPENCLAW.md`](OPENCLAW.md)，当前不得执行实现或调度
- 人类 Owner：先读 [`HANDOFF_INDEX.md`](HANDOFF_INDEX.md) 和 [`OWNER_INPUTS_REQUIRED.md`](OWNER_INPUTS_REQUIRED.md)

适配器文件不能改变主合同。发生冲突时，主合同与 `PROJECT_STATE.json` 优先。

## 当前授权

| 项目 | 当前值 |
|---|---|
| 阶段 | `N0` |
| 阶段状态 | `AUTHORIZED` |
| 数据门禁 | `G0_THREE_SYNTHETIC_FIXTURES` |
| 真实图片目录 | `NOT_AUTHORIZED` |
| 模型下载 | `NOT_AUTHORIZED` |
| 网络访问 | 默认拒绝 |
| OpenClaw 激活 | `NOT_AUTHORIZED` |
| 下一阶段 | `N1_LOCKED` |

唯一可执行任务合同：

```text
tasks/phase_n0_environment_scaffold.yaml
```

## 第一次操作

```bash
python tools/verify_handoff.py
```

校验失败时不得实施。校验通过后，按 `docs/00_reading_order.md` 阅读并执行 N0。

## 交付包与目标仓库

本 ZIP 可解压为目标独立仓库的初始内容。N0 实现智能体负责在该目录初始化 Git、创建最小 typed Python package、产生环境与测试证据，并提交一个独立 commit。不要把该目录放进 `ai-photography-director-app` 仓库。

## 重要说明

- 文档中的模型名称是**研究候选**，不是下载授权。
- 示例路径都是占位符，不能改成个人绝对路径并提交。
- 三张 fixture 是合成图片，只用于 N0；它们不代表模型质量基准。
- OpenClaw 的限制必须由操作系统权限、只读挂载和窄命令包装器落实，不能只靠提示词。
