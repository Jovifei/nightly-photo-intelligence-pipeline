# 研究来源与决策摘要

详细登记见 `research/source_register.md` 与 `research/github_reference_projects.md`。

## 采用的工程模式

- PyPA `src/` layout：降低从仓库根目录误导入未安装包的风险；
- PyPA Sample Project：借鉴 `pyproject.toml`、测试与打包基本结构；
- Cookiecutter Data Science：借鉴 raw/interim/processed/outputs 的职责分层，但原图保持仓库外只读；
- Kedro：借鉴显式阶段、输入输出和可重跑节点思想，不采用其运行时；
- Typer：类型提示驱动 CLI；
- Pydantic：边界模型和配置校验；
- SQLite：单机持久状态、事务与恢复；
- JSON Schema 2020-12：跨语言 App 合同；
- pytest/Ruff/mypy：测试、lint/format、类型检查。

## 研究候选，不是采用决策

- MMPose/RTMPose/RTMW；
- 轻量人物分割；
- SAM 2 精细分割；
- Qwen3-VL 2B 级本地 VLM；
- 图像 Embedding 模型。

## 明确不采用第一版

- Kubernetes；
- Kafka；
- 分布式 Celery；
- Airflow/Dagster/Prefect 常驻编排；
- 公共云数据库；
- MLflow 服务；
- 多用户权限；
- 基础模型训练。

原因不是这些项目质量低，而是对 500–600 张、本地单机、强隐私、单 GPU 的首版问题增加了不必要的权限、部署和运维面。

## 研究纪律

所有外部结论在采用时重新核验 exact version/revision/许可。此交付包中的 URL 是来源索引，不是自动下载脚本。
