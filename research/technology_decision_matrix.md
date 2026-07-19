# 技术决策矩阵

| 能力 | 候选 | 决策 | 理由 |
|---|---|---|---|
| 语言 | Python 3.11/3.12 | 采用其一 | 生态成熟；以机器现状与依赖兼容决定 |
| CLI | Typer | 首选 | typed、命令清晰 |
| 边界模型 | Pydantic | 采用 | JSON/配置校验 |
| 跨语言合同 | JSON Schema 2020-12 | 采用 | Swift/App 可独立验证 |
| 状态 | SQLite | 采用 | 单机、事务、可审计 |
| ORM | SQLAlchemy/stdlib sqlite3 | N0 比较 | 不为简单骨架增加不必要复杂度 |
| migration | 轻量显式 migration/Alembic | N1 决定 | 先看 schema 演进需求 |
| 图像 IO | Pillow | 候选 | 常见格式；需解码安全配置 |
| 视觉计算 | OpenCV | 候选 | 构图/颜色/几何 |
| 精确 Hash | hashlib SHA-256 | 采用 | Python 标准库 |
| 感知 Hash | ImageHash 或自有稳定 wrapper | N1 决定 | 必须固定算法/version |
| logging | stdlib JSON formatter/structlog | N0 比较 | 避免过多依赖 |
| tests | pytest | 采用 |
| lint/format | Ruff | 采用 |
| typecheck | mypy | 采用 |
| packaging | PyPA src layout | 采用 |
| orchestration | explicit stage runner | 采用 | 透明、适合单机 |
| Kedro runtime | Kedro | 不采用 v1 | 借鉴思想即可 |
| distributed queue | Celery/Kafka | 不采用 |
| container | Docker Compose | 后续采用 | 每重阶段独立释放 GPU |
| scheduler | Windows Task Scheduler/fixed CLI | 先采用 |
| agent scheduler | OpenClaw | N8 后可选 | 权限面必须被收窄 |
| pose | MMPose RTMPose/RTMW | N2 Benchmark |
| segmentation | lightweight + escalation | N2 Benchmark |
| fine segmentation | SAM 2 | 延后候选 |
| VLM | local ~2B candidate | N3 Benchmark |
| Embedding | 未定 | N6 |
| training | foundation training | 禁止 v1 |
| review | static HTML | 采用首版 |
| cloud DB/API | 各类 | 禁止首版 |

## SQLite WAL 说明

WAL 不是默认真理。WSL、Docker bind mount 和 Windows 文件系统组合需要实测锁与恢复。N0 记录文件系统；N1 决定 journal mode。
## N2A decision addendum (2026-07-20)

| Capability | Candidate boundary | N2A decision | Rationale |
|---|---|---|---|
| Pose | Typed protocol + deterministic synthetic fake | Adopt interface only | Keeps model execution behind N2B and makes VLM-origin keypoints invalid |
| Segmentation | Metadata-only typed protocol + fake backend | Adopt interface only | No mask bytes, masks, cutouts, or image artifacts in N2A |
| Pose candidates | MMPose/rtmlib | Research only | Official source and license evidence recorded; exact weights/revision pending approval |
| Segmentation candidates | MediaPipe/PaddleSeg | Research only | First-pass candidates; edge and multi-person limits require benchmark |
| Fine segmentation | SAM 2 | Escalation only | Checkpoint and license review must precede any N2B request |
| Benchmark | Fixed 20-case synthetic metadata plan | Adopt plan | Stable scenarios and explicit unknown resource metrics |
| Execution | `npi benchmark run` | Fail closed | Returns `NPI_MODEL_NOT_AUTHORIZED` while N2B is locked |
