# Nightly Photo Intelligence Pipeline
## N2B2 Synthetic Model Stack Validation 交付文档

**项目：** `nightly-photo-intelligence-pipeline`  
**中文名称：** 夜间摄影灵感分析流水线  
**交付目的：** 对齐当前工程真实进度，冻结 N2B2 的模型与运行时架构，并为 Codex 提供可执行、可审核、可停止的下一阶段任务合同。  
**Owner 决策：** 采用本机已有 `qwen3.5:9b`，不再下载 Qwen3‑VL‑2B；本阶段不做双模型 A/B。  
**数据门：** `SYNTHETIC_ONLY_DATA_GATE`。  
**App 边界：** 大模型不部署进手机 App；模型运行在本地离线 Pipeline，App 只消费审核通过的 Photo Intelligence Bundle v1。

---

## 1. 为什么需要修订原方案

原 N2B2 草案假设：

- 原生 Windows `Transformers + BF16`
- 下载 `Qwen/Qwen3-VL-2B-Instruct`
- 禁止量化
- 不使用本地模型服务

现在 Owner 机器已经存在：

- `qwen3.5:9b`
- Ollama 本地模型
- Q4_K_M
- 约 6.6 GB
- 支持图像输入、工具与 thinking
- RTX 4070 SUPER 12 GB

因此继续下载 Qwen3‑VL‑2B 会带来：

1. 重复下载与供应链审核；
2. 新增一套 Transformers 依赖；
3. 双 VLM 对照扩大 Scope；
4. 延迟第一版摄影理解闭环。

### 新决策

本轮采用：

```text
TorchVision deterministic models
        +
Ollama local qwen3.5:9b
```

而不是：

```text
TorchVision
        +
Transformers Qwen3-VL-2B
```

这是一个明确的运行时架构变更，不得隐藏成原 BF16 合同的小修改。

---

## 2. 模型定位

### 2.1 确定性视觉层

#### Keypoint R-CNN ResNet-50 FPN COCO V1

角色：

```text
POSE_BASELINE_SMOKE
```

负责：

- 人体框；
- COCO 17 点关键点；
- score；
- Pose 运行链路和 CUDA smoke。

限制：

- 不是最终 WholeBody Pose；
- 不能提供完整手、脸、脚关键点；
- 不能由它直接生成摄影解释。

#### LRASPP MobileNetV3-Large

角色：

```text
SEGMENTATION_PRIMARY
```

负责：

- person 类粗语义分割；
- 人物面积；
- 前景比例；
- 边界接触；
- 粗轮廓事实。

#### DeepLabV3 MobileNetV3-Large

角色：

```text
SEGMENTATION_QUALITY_COMPARATOR
```

负责：

- 与 LRASPP 做固定子集质量对照；
- 不作为 LRASPP OOM/超时自动回退。

### 2.2 摄影理解层

#### qwen3.5:9b

角色：

```text
PHOTOGRAPHY_REASONING_MODEL
```

运行时：

```text
LOCAL_OLLAMA_MULTIMODAL_Q4_K_M
```

负责：

- 场景摄影价值；
- 构图解释；
- 光线与影调的非精确描述；
- 三类故事候选；
- standard / dramatic / plan_b / technical 导演提示；
- uncertainties。

不得负责：

- 关键点；
- bbox；
- mask；
- 精确角度；
- EXIF；
- 精确焦段；
- 人物真实心理；
- 版权判断；
- 修改确定性事实。

---

## 3. 当前阶段选择：A，单 VLM

本阶段选择：

```text
A：qwen3.5:9b 替代原计划的 Qwen3-VL-2B
```

不执行：

```text
B：9B 与 2B 双模型 A/B
```

原因：

- 目标是尽快跑通产品闭环；
- 9B 已存在本机，不需要下载；
- 9B 是原生多模态模型；
- 双模型会扩大下载、缓存、Schema、报告和 GPU 对照范围；
- 当前尚未完成真实照片 Gate，不需要提前做模型选型终局。

原 `Qwen3-VL-2B` 研究记录保留，但状态改为：

```text
SUPERSEDED_FOR_N2B2_SYNTHETIC_VALIDATION
NOT_DOWNLOADED
NOT_EXECUTED
```

---

## 4. 运行时架构

### 4.1 混合运行时

```text
Python / TorchVision
- Keypoint R-CNN
- LRASPP
- DeepLabV3

Local Ollama loopback API
- qwen3.5:9b
```

### 4.2 Ollama 信任边界

只允许：

```text
http://127.0.0.1:11434
```

必须拒绝：

- 非 loopback host；
- Ollama cloud；
- 远程 API；
-代理转发；
-自动 pull；
- `ollama create`；
- `ollama copy`；
- `ollama delete`；
-任何联网模型获取。

图片以当前进程内存中的 Base64 bytes 发送，不传真实绝对路径。

### 4.3 模型身份固定

运行前只读记录：

```text
model_name
local_digest
size
format
family
parameter_size
quantization_level
capabilities
license
ollama_version
```

必须使用本机实际 `/api/tags`、`/api/show` 和 `ollama show` 结果，不得仅抄远程 tag。

最低要求：

```text
model = qwen3.5:9b
vision capability = present
quantization = Q4_K_M
```

本阶段不得把 Ollama Q4_K_M 结果描述成官方 BF16 checkpoint 结果。

---

## 5. 数据 Gate

### 5.1 本轮只允许合成数据

```text
REAL_PHOTO_READ_COUNT = 0
REAL_EXIF_READ_COUNT = 0
G1_SOURCE_ACCESS = 0
SQLITE_WRITE_COUNT = 0
```

禁止：

- G1 Snapshot；
- Billfish；
-用户收藏图；
-任何 EXIF；
-真实照片目录；
-真实 App 数据。

### 5.2 分两级执行

#### Gate S3：3 张 synthetic smoke

至少覆盖：

1. 单人；
2. 多人或遮挡；
3. no-person / unsupported negative control。

只有 S3 全部满足控制面和运行时门，才进入 S20。

#### Gate S20：20 张 synthetic validation

建议 case matrix：

| Case | 主场景 |
|---|---|
| 01–04 | 单人：全身、半身、坐姿、道具 |
| 05–08 | 多人：分离、靠近、遮挡、镜像 |
| 09–11 | 夜景 / 低照度 |
| 12–14 | 复杂背景 |
| 15–16 | 强逆光 / 剪影 |
| 17–18 | 极简构图 / 大留白 |
| 19 | no-person negative control |
| 20 | collage/screenshot unsupported control |

如果没有足够逼真的合成人像 fixture，不能伪造正向 Pose 成功。应返回：

```text
N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT
```

---

## 6. 事实合同

### 6.1 Authoritative Vision Facts

由确定性模型和确定性计算产生：

```text
person_count
person_boxes
pose_keypoints
pose_scores
segmentation_foreground_ratio
subject_centroid
frame_contact_flags
negative_space_metrics
fact_ids
fact_digest
```

### 6.2 Qwen 输入

```text
synthetic image bytes
+
immutable vision fact contract
+
uncertainties
+
forbidden-field rules
```

### 6.3 Qwen 输出

只允许：

```text
input_fact_digest
reasoning_based_on_fact_ids
photographic_interpretation
story_candidates
director_prompts
uncertainties
```

禁止出现或覆盖：

```text
person_count
bbox
keypoints
mask
pose_confidence
segmentation_confidence
EXIF
exact_focal_length
exact_camera_distance
copyright_status
real_mental_state
```

Qwen 输出必须回显相同 `input_fact_digest`，并引用有效 `fact_ids`。

---

## 7. Ollama 请求约束

使用本地原生 API，要求：

```text
stream = false
think = false
format = strict JSON Schema
keep_alive = stage-controlled
```

建议初始选项：

```text
temperature = 0
num_ctx = 8192
num_predict <= 1200
single image
long side <= 1024
```

如 `seed` 在当前 Ollama 版本受支持，固定 seed；若不支持，应记录 `SEED_NOT_AVAILABLE`，不得伪造确定性。

Qwen 阶段：

1. 模型加载；
2. 逐图串行；
3. 阶段结束设置 `keep_alive=0`；
4. 使用 `/api/ps` 确认模型卸载；
5. 再检查 GPU 回落。

---

## 8. GPU 与时延门

### 8.1 同驻限制

任何时刻最多一个重模型占用 GPU：

```text
Pose stage
→ unload
Segmentation stage
→ unload
Qwen stage
→ unload
```

不得让 Ollama Qwen 与 TorchVision 模型同时驻留。

### 8.2 初始阈值

```text
absolute GPU used <= 11,500 MiB
Pose single image <= 60 s
Segmentation single image <= 60 s
Qwen cold load <= 180 s
Qwen steady single image <= 120 s
```

卸载后 60 秒内必须：

- `/api/ps` 不再列出 qwen3.5:9b；
- GPU 回到阶段前 baseline + 1,024 MiB 以内。

任何 OOM、系统内存不足、超时、模型未卸载或 GPU 长时间不回落，立即停止。

---

## 9. 重复性定义

### 确定性视觉层

同一图片、同一权重、同一环境重复两次：

- facts canonical JSON byte-identical；
- `fact_digest` 完全相同。

### Qwen 层

不要求自由文本逐字一致，但必须满足：

- JSON Schema均通过；
- `input_fact_digest` 一致；
- forbidden fields均为 0；
- story type 集合一致；
-引用的 fact IDs 合法；
-关键摄影结论不与 authoritative facts 冲突。

如需要严格文本一致性，不得通过放宽事实约束实现。

---

## 10. 输出与持久化

Git 外 runtime：

```text
synthetic_images/
vision_facts/
qwen_outputs/
bundles/
runtime_metrics/
raw_logs_redacted/
```

每张图输出：

```text
analysis.json
vision_facts.json
director_prompt.json
reference_bundle.json
```

仓库内只允许提交：

-合同；
-Schema；
-adapter；
-tests；
-模型身份登记；
-脱敏阶段报告；
-任务与审批状态。

不得提交：

-模型文件；
-合成图片大批量产物；
-完整 Qwen 原始 thinking；
-Ollama blobs；
-runtime DB；
-绝对路径。

---

## 11. 进入 N2B2 前的状态协调

Codex 必须先确认实际磁盘状态，不能只依据接力摘要。

必须确定：

```text
N2B1P exact HEAD
N2B1P remediation status
N2B1P external review verdict
three TorchVision cache entries
PROJECT_STATE current stage
N2B2 authorization status
```

只有磁盘上存在与精确 SHA 绑定的 N2B1P 通过证据，且三份 cache 均严格为 `CACHE_HIT`，才允许执行真实模型。

若 N2B1P 仍等待外部审核：

```text
N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED
```

此时不得运行模型，只能完成不越权的控制面草案并停止。

---

## 12. 验收条件

N2B2 synthetic validation 通过至少要求：

- 3 张 smoke 完成；
- 20 张 synthetic 执行完成，或因 fixture 能力不足诚实停止；
- TorchVision 权重未重复下载；
- Ollama 模型未 pull；
- Qwen 本地 digest已固定；
-所有输出通过 Schema；
- `fact_digest` 不变；
-Qwen forbidden fields = 0；
-真实照片 / EXIF / G1访问均为 0；
-SQLite 写入为 0；
-GPU阈值通过；
-模型卸载验证通过；
-无模型和 runtime 产物进入 Git；
-全量质量门通过；
-工作树干净；
-未 push、未 merge。

---

## 13. 停止状态

成功候选：

```text
N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW
```

常见阻断：

```text
N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED
N2B2_LOCAL_QWEN_IDENTITY_MISMATCH
N2B2_LOCAL_QWEN_VISION_CAPABILITY_MISSING
N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT
N2B2_GPU_LIMIT_EXCEEDED
N2B2_FACT_IMMUTABILITY_VIOLATION
N2B2_QWEN_SCHEMA_OR_PROVENANCE_FAILED
N2B2_MODEL_UNLOAD_FAILED
N2B2_CHANGES_REQUIRED
```

任何停止状态均不得自动进入：

-真实 20 张；
-G1续签；
-RTMW；
-RTMDet；
-SAM2；
-App部署；
-Obsidian同步；
-G2；
-N3。

---

## 14. 后续路线

```text
N2B2 synthetic validation
→ independent review
→ Owner approval
→ fresh G1 renewal
→ fixed 20 real-photo benchmark
→ human review
→ N3 scene/composition/lighting interpretation
→ Bundle v1
→ App consumes approved bundle
```

最终质量升级候选：

```text
RTMDet
+ RTMW-l
+ LRASPP
+ SAM2.1 Tiny
+ qwen3.5:9b or later reviewed VLM
```

这不属于当前任务。
