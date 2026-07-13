# 数据模型与状态机

## 最小状态集合

```text
NEW
INGESTED
DUPLICATE
UNSUPPORTED
POSE_DONE
SEGMENT_DONE
FACTS_DONE
INTERPRETATION_DONE
PROMPTS_DONE
VALIDATED
NEEDS_REVIEW
APPROVED
EXPORTED
RETRY
FAILED
```

`RUNNING` 不强制作为资产状态。阶段运行状态单独放在 `stage_runs`，避免资产状态与执行锁混淆。

## 允许迁移（概要）

```text
NEW -> INGESTED | DUPLICATE | UNSUPPORTED | FAILED
INGESTED -> POSE_DONE | NEEDS_REVIEW | RETRY | FAILED
POSE_DONE -> SEGMENT_DONE | NEEDS_REVIEW | RETRY | FAILED
SEGMENT_DONE -> FACTS_DONE | NEEDS_REVIEW | RETRY | FAILED
FACTS_DONE -> INTERPRETATION_DONE | NEEDS_REVIEW | RETRY | FAILED
INTERPRETATION_DONE -> PROMPTS_DONE | NEEDS_REVIEW | RETRY | FAILED
PROMPTS_DONE -> VALIDATED | NEEDS_REVIEW | RETRY | FAILED
VALIDATED -> NEEDS_REVIEW | APPROVED
NEEDS_REVIEW -> APPROVED | FAILED | <重新进入明确阶段>
APPROVED -> EXPORTED
RETRY -> <失败阶段的前一稳定状态> | FAILED
```

DUPLICATE 和 UNSUPPORTED 是终止性分类，但可由人工新 run 重新评估；不能修改历史。

## SQLite 骨架

### `assets`

- `asset_id`（稳定、非路径派生）
- `source_sha256`
- `perceptual_hash`
- `perceptual_hash_algorithm`
- `sanitized_source_name`
- `media_type`
- `width`, `height`
- `current_state`
- `retry_count`
- `last_error_code`
- `last_error_redacted`
- `created_at`, `updated_at`
- unique `source_sha256`（重复来源另表记录）

### `asset_sources`

同一内容的多个只读来源记录；路径建议加密或只在本地 runtime 表保存，绝不导出/提交。

### `stage_runs`

- `stage_run_id`
- `asset_id`
- `stage_name`
- `status`: PENDING/RUNNING/SUCCEEDED/FAILED/INTERRUPTED/SKIPPED
- `attempt`
- `started_at`, `finished_at`, `duration_ms`
- `model_id`, `model_revision`
- `prompt_version`, `schema_version`
- `code_commit`
- `config_hash`
- `gpu_peak_vram_mb`
- `error_code`, `error_redacted`
- `output_manifest_hash`
- lease/heartbeat 字段

### `state_transitions`

append-only：from/to、原因、actor、run、timestamp。

### `outputs`

相对 runtime 路径、role、media type、sha256、size、schema version。

### `metadata`

DB schema version、创建版本、migration revision。

## 事务规则

- 资产领取和 lease 在短事务内；
- 模型推理不持有数据库写事务；
- 产物先写临时文件、fsync、Hash，再原子 rename；
- 最后在单事务写 outputs + stage success + state transition；
- 崩溃留下的临时文件不能被视为有效产物；
- 恢复时校验 lease 超时和输出 Hash。

## N0 验证

N0 至少验证：

- SQLite 创建/reopen；
- 有效与无效迁移；
- 事务回滚；
- 模拟 RUNNING 中断后识别为可恢复；
- 幂等 ingest dry-run 不新增记录；
- 固定 fixture 完全重复识别。
