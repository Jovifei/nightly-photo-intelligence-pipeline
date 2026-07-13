# 来源登记（官方/一手来源优先）

访问/整理日期：2026-07-12。URL 用于人工核验，不是自动下载授权。

## 智能体入口

| 主题 | 来源 | 用途 |
|---|---|---|
| Codex `AGENTS.md` | https://developers.openai.com/codex/guides/agents-md | 采用分层智能体说明文件的入口模式 |
| OpenAI Codex | https://developers.openai.com/codex/ | 不把适配器当作主需求源 |
| Claude Code | https://github.com/anthropics/claude-code | `CLAUDE.md` 适配与 Reviewer 工作流 |
| Claude Code 文档 | https://docs.anthropic.com/en/docs/claude-code/memory | CLAUDE.md/项目记忆约定；采用时复核最新地址 |
| OpenClaw cron | https://docs.openclaw.ai/automation/cron-jobs | 未来固定调度能力研究 |
| OpenClaw docs | https://docs.openclaw.ai/ | 权限必须由系统边界落实 |

## Python 工程

| 主题 | 来源 | 用途 |
|---|---|---|
| Python Packaging User Guide | https://packaging.python.org/ | 打包与 `pyproject.toml` |
| src layout vs flat | https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ | 采用 `src/` 布局 |
| PyPA Sample Project | https://github.com/pypa/sampleproject | 最小现代 Python 工程参考 |
| Typer | https://github.com/fastapi/typer | 类型提示 CLI |
| Pydantic | https://github.com/pydantic/pydantic | 边界模型/配置 |
| pytest | https://github.com/pytest-dev/pytest | 测试 |
| Ruff | https://github.com/astral-sh/ruff | lint/format |
| mypy | https://github.com/python/mypy | 静态类型检查 |
| Pillow | https://github.com/python-pillow/Pillow | 图像解码候选 |
| OpenCV | https://github.com/opencv/opencv | 确定性视觉计算候选 |
| ImageHash | https://github.com/JohannesBuchner/imagehash | 感知 Hash 参考实现 |

## 数据/流水线模式

| 主题 | 来源 | 用途 |
|---|---|---|
| Cookiecutter Data Science | https://github.com/drivendataorg/cookiecutter-data-science | 数据、模型、报告职责分离 |
| Kedro | https://github.com/kedro-org/kedro | 显式节点、数据集、可重跑阶段思想 |
| SQLite | https://www.sqlite.org/docs.html | 单机事务状态 |
| SQLite WAL | https://www.sqlite.org/wal.html | WAL 候选；必须在 WSL/文件系统实测 |
| JSON Schema 2020-12 | https://json-schema.org/draft/2020-12 | App 跨语言合同 |

## Windows / WSL / GPU

| 主题 | 来源 | 用途 |
|---|---|---|
| Docker Desktop GPU | https://docs.docker.com/desktop/features/gpu/ | Windows WSL2 GPU 支持前置条件 |
| Microsoft WSL 文件系统 | https://learn.microsoft.com/windows/wsl/filesystems | 路径/性能/权限差异研究 |
| NVIDIA Container Toolkit | https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/ | 只读核验，N0 不安装 |
| RTX 4070 Family | https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4070-family/ | 硬件规格来源；实际资源以 preflight 为准 |

## 模型候选

| 主题 | 来源 | 状态 |
|---|---|---|
| MMPose | https://github.com/open-mmlab/mmpose | Research only |
| RTMPose paper | https://arxiv.org/abs/2303.07399 | Research only |
| SAM 2 | https://github.com/facebookresearch/sam2 | Research only；代码/权重分别审查 |
| Qwen3-VL | https://github.com/QwenLM/Qwen3-VL | Research only |
| Qwen3-VL-2B model card | https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct | Research only；exact revision 未批准 |

## 来源规则

- 技术实现优先官方文档和维护者仓库；
- 论文用于能力背景，不能代替工程 Benchmark；
- 社区量化权重不能因可下载而采用；
- URL、license、revision、Hash 和访问日期进入 provenance；
- 若官方页面与仓库冲突，停止并记录，不自行选择更宽松许可。
