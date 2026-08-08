# 可直接发送给 Codex 的长任务 Prompt

我是 `nightly-photo-intelligence-pipeline` 项目的 Owner：Jovi。

我授权执行一个新的、条件式阶段任务：

```text
N2B2_SYNTHETIC_MODEL_STACK_VALIDATION
```

本轮采用 Owner 选择 **A**：

```text
本机已有 qwen3.5:9b
正式替代原 N2B2 计划中的 Qwen3-VL-2B
不保留双模型 A/B
不下载 Qwen3-VL-2B
```

该替代只适用于本轮 N2B2 synthetic validation，不等于最终生产模型永久定型。

---

## 一、项目和范围锁定

唯一项目：

```text
nightly-photo-intelligence-pipeline
夜间摄影灵感分析流水线
```

不得处理：

- jovi-automation；
- Tesla MateLink；
- Android 代码；
-其他仓库；
-其他聊天中混入的治理链。

App 边界：

> 模型运行在 Windows 本地离线 Pipeline，不部署到手机 App。  
> App 未来只消费经审核的 Photo Intelligence Bundle v1。

---

## 二、开始前必须从磁盘对齐真实状态

先阅读：

```text
README_FIRST.md
MASTER_EXECUTION_CONTRACT.md
PROJECT_STATE.json
tasks/todo.md
tasks/lessons.md
tasks/phase_n2b1p_local_research_cache_promotion.yaml
approvals/owner_n2b1p_cache_promotion.yaml
research/N2B1P_cache_promotion_evidence.json
reports/N2B1P_cache_promotion_report.md
```

并查找：

- N2B1P remediation 的精确 commit；
- N2B1P 独立 Reviewer 的精确结论；
- 当前阶段 task contract；
- N2B2 是否仍 LOCKED；
- 三份 TorchVision cache manifest；
-任何已经存在的 N2B2 草稿或未提交改动。

执行：

```powershell
git rev-parse HEAD
git rev-parse HEAD^
git branch --show-current
git status --short
git diff --name-status
git diff --cached --name-status
git log --oneline --decorate --graph -30
git log --merges --oneline
git diff --check
```

不得清理、reset、覆盖或丢弃已有改动。

输出内部状态判断：

```text
ACTUAL_HEAD
ACTUAL_CURRENT_STAGE
N2B1P_EXACT_SHA
N2B1P_REVIEW_VERDICT
N2B1P_APPROVED
N2B2_AUTHORIZED
```

### 执行前置

只有在磁盘证据证明：

```text
N2B1P exact SHA 已通过所需独立审查
三份 TorchVision cache 均严格 CACHE_HIT
N2B2 本 Prompt 被记录为 Owner 授权
```

时，才允许运行真实模型。

否则只允许完成不越权的控制面检查，并停止：

```text
N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED
```

不得为了推进而自行把 N2B1P 标记为通过。

---

## 三、Owner 架构决策

### 3.1 确定性视觉层

继续使用已 promotion 的三份 TorchVision 权重：

```text
Keypoint R-CNN ResNet-50 FPN COCO V1
role = POSE_BASELINE_SMOKE

LRASPP MobileNetV3-Large
role = SEGMENTATION_PRIMARY

DeepLabV3 MobileNetV3-Large
role = SEGMENTATION_QUALITY_COMPARATOR
```

规则：

- 只验证既有 cache；
- 禁止重新下载；
- 禁止自动 TorchVision 下载；
- Keypoint R-CNN 不是最终 WholeBody Pose；
- DeepLab不是 LRASPP OOM fallback。

### 3.2 摄影理解层

本轮使用本机已有：

```text
qwen3.5:9b
role = PHOTOGRAPHY_REASONING_MODEL
runtime = LOCAL_OLLAMA_MULTIMODAL_Q4_K_M
```

原计划：

```text
Qwen/Qwen3-VL-2B-Instruct
```

本轮状态改为：

```text
SUPERSEDED_FOR_N2B2_SYNTHETIC_VALIDATION
NOT_DOWNLOADED
NOT_EXECUTED
```

禁止：

- `ollama pull`；
-下载任何 Qwen 模型；
- `ollama create`；
-复制、删除或修改本地 Ollama 模型；
-双模型 A/B；
-将 Q4_K_M 描述为 BF16。

---

## 四、Ollama 本地运行时 Gate

只允许访问：

```text
http://127.0.0.1:11434
```

禁止：

- Ollama cloud；
-远程 host；
-proxy；
-其他端口；
-任何外网模型请求。

只读执行并记录：

```powershell
ollama --version
ollama list
ollama show qwen3.5:9b
```

以及本地 API：

```text
GET  /api/version
GET  /api/tags
POST /api/show
GET  /api/ps
```

必须记录本机实际：

```text
model_name
full_local_digest
size_bytes
format
family
parameter_size
quantization_level
capabilities
license
modified_at
ollama_version
```

要求：

```text
model_name = qwen3.5:9b
vision capability present
quantization_level = Q4_K_M
```

如模型不存在、digest 异常、无 vision capability 或 API 不是 loopback：

```text
N2B2_LOCAL_QWEN_IDENTITY_MISMATCH
```

立即停止，禁止 pull。

---

## 五、创建独立 N2B2 控制面

如仓库尚无等价合同，创建：

```text
tasks/phase_n2b2_synthetic_model_stack_validation.yaml
schemas/n2b2_synthetic_model_stack.schema.json
schemas/n2b2_vision_fact_contract.schema.json
schemas/n2b2_photography_reasoning.schema.json
schemas/reference_bundle_v1_synthetic.schema.json
reports/N2B2_synthetic_validation_plan.md
reports/N2B2_owner_inputs_and_limits.md
```

更新：

```text
PROJECT_STATE.json
tasks/index.json
tasks/todo.md
model registry / runtime registry
error taxonomy
preflight
```

状态必须清楚表达：

```text
N2B1P = approved prerequisite（仅在真实证据支持时）
N2B2_SYNTHETIC_MODEL_STACK_VALIDATION = AUTHORIZED
N2B2_REAL_PHOTO_BENCHMARK = LOCKED
G1 real-photo access = not used
G2/G3 = LOCKED
N3-N8 = LOCKED
```

不得自行续签 G1。

---

## 六、数据 Gate

本阶段：

```text
SYNTHETIC_ONLY_DATA_GATE
```

最终硬计数：

```text
REAL_PHOTO_READ_COUNT = 0
REAL_EXIF_READ_COUNT = 0
G1_SOURCE_ACCESS = 0
SQLITE_WRITE_COUNT = 0
APP_WRITE_COUNT = 0
OBSIDIAN_WRITE_COUNT = 0
```

禁止读取：

- G1 Snapshot；
- Billfish；
-真实收藏图；
-用户照片；
-EXIF；
-SQLite中的真实任务数据。

所有 synthetic 图像和详细输出必须位于 Git 外受控 runtime。

---

## 七、Synthetic Fixture Gate

### 7.1 先运行 3 张 smoke

必须至少覆盖：

1. 单人；
2. 多人或遮挡；
3. no-person / unsupported negative control。

不得直接运行 20 张。

### 7.2 通过后运行 20 张

建议固定 case matrix：

```text
01–04 单人：全身、半身、坐姿、道具
05–08 多人：分离、靠近、遮挡、镜像
09–11 夜景或低照度
12–14 复杂背景
15–16 强逆光或剪影
17–18 极简构图或大留白
19 no-person negative control
20 collage/screenshot unsupported control
```

必须冻结：

```text
case_id
generator_version
seed
image_sha256
width
height
expected_processability
tags
```

如果当前没有足以让 Keypoint R-CNN 产生至少一个正向人物检测的非敏感 synthetic fixture：

```text
N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT
```

停止。

不得伪造 Pose 成功，也不得改用真实照片补足。

---

## 八、Vision Fact Contract

建立 canonical authoritative fact contract。

至少包含：

```text
case_id
image_sha256
person_count
person_boxes
pose_keypoints
pose_scores
segmentation_foreground_ratio
subject_centroids
frame_contact_flags
negative_space_metrics
fact_ids
uncertainties
fact_digest
provenance
```

规则：

- 所有 facts 来自确定性模型或确定性计算；
- canonical JSON；
- strict JSON；
-禁止 NaN/Infinity；
- `fact_digest` 为 canonical payload SHA-256；
- Qwen 不能修改这些字段；
- Qwen 不生成关键点；
- Qwen 不生成精确角度。

同一图片重复执行两次：

```text
canonical facts bytes 必须相同
fact_digest 必须相同
```

---

## 九、Qwen Reasoning Contract

Qwen 输入：

```text
synthetic image bytes
+
immutable vision facts
+
fact_digest
+
uncertainty list
+
forbidden-field contract
```

图片必须以内存 Base64 bytes发送给 loopback API，禁止传绝对路径。

Qwen 只允许输出：

```text
input_fact_digest
reasoning_based_on_fact_ids
photographic_interpretation
story_candidates
director_prompts
uncertainties
```

`story_candidates` 固定包含：

```text
safe
narrative
dynamic
```

`director_prompts` 固定包含：

```text
standard
dramatic
plan_b
technical
```

禁止字段至少包括：

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

必须验证：

```text
output.input_fact_digest == input fact_digest
all referenced fact_ids exist
forbidden field count == 0
```

冲突必须进入 `uncertainties`，不能覆盖 facts。

---

## 十、Ollama 请求规范

使用 Ollama 本地原生 API。

请求至少要求：

```text
stream = false
think = false
format = strict JSON Schema
single image
```

初始资源参数：

```text
num_ctx = 8192
num_predict <= 1200
temperature = 0
image long side <= 1024
```

如果当前版本支持 seed：

```text
seed = fixed stage seed
```

如果不支持：

```text
SEED_NOT_AVAILABLE
```

如实记录，不得伪造。

### 模型驻留

Qwen 阶段可在 3/20 张串行任务期间保持加载，以避免每图冷启动。

阶段结束必须：

```text
keep_alive = 0
```

随后：

-轮询 `/api/ps`；
-确认 `qwen3.5:9b` 已卸载；
-确认 GPU回落。

不得让 TorchVision 模型与 Qwen同时驻留。

---

## 十一、阶段执行顺序

严格顺序：

```text
1. state reconciliation
2. TorchVision cache read-only verification
3. Ollama model identity verification
4. synthetic fixture generation/freeze
5. S3 Pose stage
6. unload Pose
7. S3 LRASPP stage
8. unload LRASPP
9. S3 DeepLab comparator
10. unload DeepLab
11. build fact contracts
12. S3 Qwen stage
13. unload Qwen
14. S3 strict validation
15. only if S3 passes, repeat for S20
```

DeepLab只作为比较器。可以使用固定 5-case comparator subset，但必须预先写入合同，不得按结果临时挑选。

---

## 十二、GPU、内存和时延门

记录：

```text
GPU baseline used MiB
GPU peak MiB
Ollama size_vram
CPU RSS peak
cold load duration
per-image duration
unload duration
```

硬阈值：

```text
absolute GPU used <= 11,500 MiB
Pose single image <= 60 s
Segmentation single image <= 60 s
Qwen cold load <= 180 s
Qwen steady single image <= 120 s
```

Qwen卸载后 60 秒内：

```text
/api/ps 不再列出模型
GPU used <= pre-Qwen baseline + 1024 MiB
```

任一：

- OOM；
-超时；
-系统内存不足；
-模型无法卸载；
-GPU不回落；
-Ollama排队/503；
-事实不一致；

立即停止。

---

## 十三、Qwen 重复性

选择固定 2 个 synthetic cases，使用相同：

```text
image
facts
fact_digest
prompt
options
model digest
```

各运行两次。

不要求 Director Prompt 逐字一致，但必须满足：

- Schema均通过；
- fact digest一致；
- forbidden fields为0；
-story type集合一致；
-引用 fact IDs合法；
-不与 authoritative facts冲突。

不得用降低事实约束换取文本一致。

---

## 十四、输出

Git 外每个 case：

```text
analysis.json
vision_facts.json
director_prompt.json
reference_bundle.json
runtime_metrics.json
```

Git 外阶段汇总：

```text
model_identity_attestation.json
synthetic_fixture_manifest.json
gpu_metrics.json
validation_summary.json
CHECKSUMS.sha256
```

仓库内只提交：

-代码；
-Schema；
-tests；
-控制合同；
-脱敏报告；
-任务状态。

禁止提交：

-模型；
-Ollama blobs；
-图片批量产物；
-原始 thinking；
-绝对路径；
-runtime DB；
-真实照片。

---

## 十五、测试要求

至少覆盖：

- 非 loopback Ollama拒绝；
-模型名不匹配；
-digest不匹配；
-vision capability缺失；
-quantization记录；
-禁止 pull；
-禁止 cloud；
-图片路径不得泄漏；
-fact digest mismatch；
-未知 fact ID；
-Qwen forbidden fields；
-Qwen覆盖事实；
-Schema失败；
-thinking字段不持久化；
-keep_alive=0卸载；
-/api/ps卸载验证；
-GPU阈值；
-模型同时驻留拒绝；
-synthetic-only路径；
-G1访问拒绝；
-EXIF拒绝；
-SQLite写入拒绝；
-真实照片计数保持0；
-Keypoint/LRASPP/DeepLab cache不重复下载；
-ReferenceBundle checksum；
-N0→N2B1P全部回归。

使用 mock测试 Ollama错误路径；另用本地真实 Ollama执行受控 S3/S20。

---

## 十六、质量门

完成后执行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy src/nightly_photo_intelligence_pipeline
.venv\Scripts\python.exe tools/run_quality.py
.venv\Scripts\python.exe tools/sensitive_file_scan.py
.venv\Scripts\npi.exe preflight
.venv\Scripts\python.exe tools/verify_handoff.py
git diff --check
```

要求：

```text
pytest 0 failed
Ruff/format/mypy exit 0
quality 7 PASS
sensitive scan 0 violations
preflight 0 FAIL
handoff 0 FAIL
no NOT_AVAILABLE
no false PASS for SKIPPED
```

---

## 十七、Git规则

N2B1P批准基线不得改写。

N2B2完成后：

-创建一个且仅一个 N2B2 commit；
-无 merge；
-工作树干净；
-不 push；
-不 merge；
-不得混入 docs/02、docs/24、docs/31、Obsidian 或 print_authorization漂移。

建议 commit：

```text
feat(n2b2): validate synthetic photography model stack
```

如存在 N2B2 开始前的未提交候选改动，应先只读归属审计，不得覆盖。

---

## 十八、停止与输出

成功停止：

```text
N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW
```

输出必须包含：

- 起始和最终 HEAD；
- N2B1P精确基线；
- N2B2 commit；
-模型列表；
-三份 TorchVision CACHE_HIT证据；
-qwen3.5:9b本地完整 digest；
-Ollama版本；
-quantization；
-capabilities；
-license记录；
-是否发生任何网络/pull；
-S3结果；
-S20结果；
-20张 fixture manifest；
-fact immutability；
-Qwen schema/provenance；
-重复性结果；
-GPU峰值；
-CPU峰值；
-每模型耗时；
-卸载结果；
-ReferenceBundle校验；
-全部质量命令；
-REAL_PHOTO_READ_COUNT；
-REAL_EXIF_READ_COUNT；
-G1_SOURCE_ACCESS；
-SQLITE_WRITE_COUNT；
-APP_WRITE_COUNT；
-OBSIDIAN_WRITE_COUNT；
-模型下载字节数；
-未进入真实照片阶段；
-N2B2 real benchmark仍锁定；
-未 push/merge；
-给独立 Reviewer的精确 SHA。

阻断状态按实际使用：

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

完成后停止。

不得进入：

- G1续签；
-真实20张；
-RTMW；
-RTMDet；
-SAM2；
-App部署；
-Obsidian同步；
-G2；
-N3。
