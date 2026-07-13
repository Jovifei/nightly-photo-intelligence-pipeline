# Photo Intelligence Item v1 分层语义

权威结构见 `schemas/photo_intelligence_item_v1.schema.json`。

## `observed_facts`

只能包含画面可见、模型或确定性计算有证据的事实。每条事实应有：

- `fact_id`
- `kind`
- `value`
- `confidence`
- `evidence_refs`
- `producer`

禁止加入故事、心理、原作者意图或精确相机推断。

## `photographic_interpretation`

包含背景摄影价值、构图资源、光线用法、空间限制和影调方向。每条必须引用一个或多个 `fact_id`，并使用建议/可能/画面表现等措辞。

## `story_candidates`

固定对象键：

- `safe`
- `narrative`
- `dynamic`

每个候选包含 title、scenario、feasibility、constraints、evidence_refs。它是可执行创意，不是真实事件陈述。

## `pose_template`

包含专业 Pose 模型关键点、角度、身体方向、镜像策略、难度和约束。坐标必须声明：

- 原图坐标或归一化坐标；
- origin；
- x/y 方向；
- 是否镜像；
- 模型和 revision；
- 每点置信度。

## `director_prompts`

包含标准引导、戏感、Plan B 和摄影师技术提示。提示应短、可说出口、动作顺序明确。Plan B 有 `simplification_reason`。

## `uncertainties`

记录低置信度、模型冲突、遮挡、无法判断、权限/许可未知。不能通过删除 uncertainty 来让条目通过。

## `review`

状态、Reviewer、时间、修改 patch、理由。自动系统不能把状态设为 APPROVED。

## `provenance`

代码、模型、权重、算法、Prompt、Schema、许可、配置和输入 Hash。模型代码许可与权重许可分开记录。

## 受限字段

Schema 不提供下列“事实字段”：

- `copyright_status`
- `exact_focal_length`
- `exact_camera_distance`
- `real_subject_emotion`
- `original_photographer_intent`
- `exact_lightroom_settings`
- 推测 EXIF

真实 EXIF 只有在文件实际存在且读取成功时才能放在明确的 `source_metadata.exif_observed` 中，并保留原值与存在证据。
