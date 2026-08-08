# Nightly Photo Intelligence Pipeline

> 夜间摄影灵感分析流水线 · 本地优先 / 离线的摄影知识生产管线
> Local-first, offline photography knowledge-production pipeline.

[![schema](https://img.shields.io/badge/schema-v1.7-blue)](PROJECT_STATE.json)
[![stage](https://img.shields.io/badge/stage-N2B1P%20%7C%20N2B2%20LOCKED-orange)](PROJECT_STATE.json)

---

## 这是什么

把本地摄影收藏（目标 500–600 张照片）转化为**可审计、可搜索、可供摄影导演 App 消费**
的结构化知识的离线数据生产流水线。

设计原则：

- **本地优先 / 离线**：不依赖云端处理图片，SQLite 持久状态。
- **可断点续传、可重复执行**：显式 Python 阶段 + SQLite 状态机。
- **严格契约**：逐阶段 YAML 合同 + JSON Schema 校验 + 独立外部审查门禁。
- **人工审核后导出**：任何阶段完成都**不会**自动扩大到推理或真实照片处理。

> ⚠️ **当前真实状态（2026-08）**：本仓库是**工程交接 / 治理包**，不是已上线的产品。
> N2B1P 阶段 remediation 已完成，N2B2 合成模型栈实现已落地但被治理门禁锁定、尚未真正执行推理。
> 详见下方「当前进度」。

---

## 当前进度（如实）

| 阶段 | 状态 | 说明 |
|------|------|------|
| N0 | ✅ APPROVED_COMPLETE | 最小 typed Python 包 + 环境与测试证据 |
| N1 – N2B1R | ✅ APPROVED_COMPLETE | 各基线阶段完成 |
| N2B1P | 🟡 AUTHORIZED / 待外部审查签字 | 本地研究 cache promotion remediation 完成，卡在独立外部审查 |
| N2B2 | 🔒 LOCKED / 被 N2B1P 门阻挡 | 合成模型栈实现已就位（TorchVision + Ollama `qwen3.5:9b`），但执行被门禁阻塞、未跑过推理 |
| N3 / N4 / N5 / G2 / G3 / 主 App | ⛔ 未授权 | 等待各自硬门 |

- `schema_version`: **1.7**；`required_stop_after`: 硬停在 **N2B1P 外部审查**
- `active_execution.phase`: **None**（尚无任何模型执行发生）
- 截至本仓库状态：**从未读取真实照片、从未加载/推理模型**（受双门禁治理约束）

---

## 架构（简要）

```text
src/nightly_photo_intelligence_pipeline/
  n2b2_synthetic/   # N2B2 合成模型栈
                    #   orchestrator / torchvision_loader / ollama_client /
                    #   qwen_reasoning / vision_facts / metrics / config
  ...               # 各阶段 typed 模块
tools/              # verify_handoff.py, run_quality.py, sensitive_file_scan.py
tasks/              # 阶段 YAML 合同
schemas/            # JSON Schema（v1_5 ↔ v1_7 契约链）
reports/            # 阶段报告与证据
fixtures/           # 三张合成测试图（仅用于 N0，不代表模型质量）
```

---

## 快速开始

```bash
# 1. 创建并激活虚拟环境（依赖见 pyproject.toml）
python -m venv .venv
.venv/Scripts/activate          # Windows
source .venv/bin/activate        # macOS / Linux
pip install -e ".[dev]"

# 注意：PyTorch / TorchVision 不在默认依赖内。
# 要跑 N2B2 推理需另行安装，见 https://pytorch.org

# 2. 校验交接（必须先过；不过不允许实施）
python tools/verify_handoff.py

# 3. 质量门（7 门：pytest / contract_integrity / schema_validation /
#             sensitive_scan / ruff_check / ruff_format / mypy）
python tools/run_quality.py
```

> 本仓库的工具**必须用项目 `.venv` 的解释器**运行（需要 pyyaml / jsonschema / pytest / ruff / mypy）。
> 裸 `python` 或系统运行时缺依赖会假报 `ModuleNotFoundError`。

---

## 治理：双门禁执行契约

本项目采用 `MASTER_EXECUTION_CONTRACT.md` + `PROJECT_STATE.json` 双门禁：

- 每个阶段有独立 YAML 合同、JSON Schema 校验、独立外部审查门
- 只读源保护、SQLite 持久状态、typed Python 包
- 报告与停止条件由合同强制
- 详见 `docs/00_reading_order.md` 与 `HANDOFF_INDEX.md`

---

## 隐私与合规

- **不含真实照片**：所有真实照片目录（`photos/`、`library/`、`raw/` 等）均被 `.gitignore` 忽略，绝不入库。
- **模型权重不入库**：`.pt / .pth / .safetensors` 等被忽略。
- **仅合成 fixture**：`fixtures/` 三张为程序生成的几何测试图，非真实照片，不代表模型质量。
- **无密钥**：仓库内无任何 API key / token / 密码。
- **权重商业权利**：`UNKNOWN_NOT_COMMERCIAL_CLEARANCE`，仅限 Owner 机器本地研究 / 评估，不得分发或声明商用。

---

## 文档导航

- **人类 Owner 先读**：`HANDOFF_INDEX.md`、`OWNER_INPUTS_REQUIRED.md`
- **实现智能体先读**：`MASTER_EXECUTION_CONTRACT.md`、`AGENTS.md`(Codex)、`CLAUDE.md`(Claude Code)
- **合同链与状态机**：`PROJECT_STATE.json`、`schemas/`、`tasks/`

---

## License

见 `LICENSE_STATUS.md` 与 `NOTICE.md`。当前为本地研究 / 评估许可，非商用授权。
