# 流水线阶段设计

## S0 Ingest

输入：批准 manifest 中的只读文件。  
输出：source fingerprint、基础元数据、候选重复关系。  
禁止：修改源、写回 EXIF、移动、重命名。

## S1 Processability

分类候选：

```text
SUPPORTED_SINGLE_PERSON
SUPPORTED_MULTI_PERSON
NO_PERSON
SCREENSHOT
COLLAGE
SEVERE_OCCLUSION
LOW_RESOLUTION
DUPLICATE
MANUAL_REVIEW
UNSUPPORTED_FORMAT
```

模型与规则冲突进入 `NEEDS_REVIEW`。

## S2 Pose

输出关键点、置信度、角度、肩胯线、方向、镜像策略和约束。关键点坐标必须标记模型、坐标系和归一化方式。

## S3 Segmentation

先轻量人物分割。轮廓质量不够且条目价值高时再升级精细分割。所有升级条件可审计。

## S4 Deterministic facts

计算尺寸、主体框比例、亮度/颜色统计、留白、结构线候选等。确定性事实要记录算法版本。

## S5 Visible facts

经批准的本地 VLM 只能提取可见事实，并接受严格 Schema。不能生成 Pose 坐标或受限断言。

## S6 Reconciliation

将 Pose、分割、确定性结果和 VLM 事实对齐。冲突不静默覆盖，写入 `uncertainties`。

## S7 Photographic interpretation

分析背景摄影价值、构图资源、光线用法、空间约束、影调方向。每条解释引用事实证据。

## S8 Story candidates

固定生成：

- `safe`：稳妥且最易执行；
- `narrative`：具有简单故事关系；
- `dynamic`：带动作或瞬间。

不得声称故事是原作者真实意图。

## S9 Director prompts

四通道：

- `standard_guidance`
- `dramatic_guidance`
- `plan_b`
- `photographer_technical`

Plan B 应比原动作更简单，并保留场景/构图意图。

## S10 Validation

JSON Schema、跨字段规则、敏感字段扫描、Hash 和 provenance 完整性。

## S11 Review

人工批准/拒绝/修正；保留原始输出和变更记录。

## S12 Export

仅 APPROVED，生成不可变 Bundle 与校验和。

## 幂等键

每个阶段的逻辑输入键至少包含：

```text
asset_id
source_sha256
stage_name
stage_code_version
model_id + revision (if any)
prompt_version (if any)
schema_version
effective_config_hash
```

相同键且产物 Hash 有效时复用；任一版本变化产生新 stage run。
