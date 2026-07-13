# 系统架构与流水线

## 架构风格

第一版采用单机、显式分阶段、SQLite 协调的批处理架构。复用现有 Python 工程惯例，但不引入分布式编排平台。

```text
READ-ONLY SOURCE
  │
  ▼
Ingest / fingerprint / dedupe
  │
  ▼
Processability classification
  │
  ├─ duplicate / unsupported / review
  ▼
Pose facts  ───────┐
  ▼                │
Segmentation       │
  ▼                │
Deterministic visual facts
  │                │
  ▼                │
VLM visible facts  │  (模型必须先获批准与 Benchmark)
  └──────┬─────────┘
         ▼
Fact reconciliation
         ▼
Photographic interpretation
         ▼
Safe / narrative / dynamic stories
         ▼
Director prompts + Plan B
         ▼
Schema validation
         ▼
Human review
         ▼
Approved-only Bundle v1 export
```

## 逻辑组件

1. `source_guard`：检查源与输出隔离，只读打开，拒绝 symlink escape。
2. `ingest`：枚举白名单文件、流式 SHA-256、感知 Hash、元数据登记。
3. `state_store`：SQLite 资产、阶段运行、状态迁移、输出 Hash 和 lease。
4. `stage_runner`：幂等执行一个明确阶段。
5. `pose_adapter`：专业 Pose 模型接口，不接受 VLM 关键点。
6. `segmentation_adapter`：轻量优先、精细升级。
7. `deterministic_facts`：尺寸、位置、颜色、亮度、结构等可重复计算。
8. `vlm_adapter`：只通过严格 Schema 提取可见事实；研究阶段默认关闭。
9. `interpretation_engine`：基于事实进行摄影解释，保留证据链。
10. `prompt_engine`：生成标准、戏感、Plan B 和技术提示。
11. `validator`：跨层规则与 JSON Schema。
12. `review_renderer`：静态 HTML 卡片。
13. `exporter`：只导出 APPROVED 条目，写相对路径与校验和。
14. `reporter`：状态、失败、性能、版本、许可与审核摘要。

## 首版进程模型

- 单主进程或单 worker；
- SQLite 单写者语义；
- 每次只运行一个 GPU 重阶段；
- 阶段完成后释放模型和 GPU；
- 不使用 Kubernetes、Kafka、分布式 Celery；
- 后续如有必要再增加受控并发，不预先平台化。

## 推荐代码布局（N0 创建）

```text
src/nightly_photo_intelligence_pipeline/
├── __init__.py
├── cli.py
├── config.py
├── logging.py
├── domain/
│   ├── states.py
│   └── models.py
├── persistence/
│   ├── sqlite.py
│   └── migrations.py
├── ingest/
│   ├── hashing.py
│   ├── perceptual_hash.py
│   └── source_guard.py
└── reporting/
    └── status.py
```

后续阶段再增加 `stages/`、`models/`、`review/`、`export/`，N0 不创建空洞的大量假模块。

## 数据目录建议

运行时目录均在 Git 外：

```text
<NPI_RUNTIME_ROOT>/
├── state/
├── work/
├── artifacts/
├── reports/
├── releases/
├── cache/
└── models/
```

原图目录独立，并以只读方式提供：

```text
<READ_ONLY_PHOTO_DIR>/
```

绝不能把 runtime 放在原图目录内，反之亦然。
