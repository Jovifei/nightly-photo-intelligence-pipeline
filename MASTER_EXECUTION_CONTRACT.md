# 主执行合同（所有智能体的唯一规范源）

**Normative status: REQUIRED**  
项目：`nightly-photo-intelligence-pipeline`  
当前授权：`N0 / G0_THREE_SYNTHETIC_FIXTURES`

## 1. 使命

构建一个独立、本地优先、离线、可审计、可断点续传、可重复执行的数据生产工程，把 Owner 本地摄影收藏转化成结构化摄影知识，并只把**人工审核通过且符合 JSON Schema** 的 `Photo Intelligence Bundle v1` 单向交给 `ai-photography-director-app`。

本工程不是 iOS App，不是实时相机后端，不是云端服务，也不是模型训练工程。

## 2. 七问执行规则

### 为什么做

收藏图目前只是文件，不能可靠地被现场摄影产品检索和复用。流水线要把可见事实、摄影解释、故事方案、姿势模板、导演提示、疑点、审核和来源分层沉淀，使知识可追溯而不是由大模型自由发挥。

### 做什么

最终范围包括导入、去重、可处理性分类、离线 Pose、人物分割、构图/光线/影调分析、背景摄影价值、三类故事候选、导演话术、人工审核、Bundle 导出、状态恢复和报告。

### 怎么做

- Python typed package + Typer CLI；
- SQLite 持久任务状态机；
- 原图只读边界；
- 显式阶段，不用隐藏的全能 Agent；
- 确定性计算与模型推理分离；
- Pose 坐标只能来自专业模型或确定性计算；
- JSON Schema、输出 Hash、版本与许可可追溯；
- 12GB VRAM 下每次只常驻一个 GPU 重模型；
- 模型先 Benchmark，后采用；
- 人工批准后才能导出。

### 先做什么

只执行 `tasks/phase_n0_environment_scaffold.yaml`。只用仓库内三张合成 fixture。先验证环境、安全底座、typed package、CLI 骨架、SQLite、Hash、只读保护、幂等、日志、Schema 和重启恢复。

### 不能做什么

当前明确禁止：

- 读取或扫描 Owner 真实摄影收藏；
- 处理 20、100 或全量图片；
- 下载 MMPose、RTMPose、SAM、VLM、Embedding 或其他大型权重；
- 上传图片、缩略图、向量或派生物到云端；
- 修改 NVIDIA 驱动；
- 修改系统级 WSL/Docker 配置；
- 使用 Docker socket 赋予 OpenClaw；
- 接入 OpenClaw；
- 修改 `ai-photography-director-app`；
- 共用数据库或导入另一工程业务源码；
- 训练基础模型；
- push、merge 或创建远端资源，除非 Owner 单独批准；
- 因为“测试通过”自动扩大 Scope。

### 怎样验证

每个阶段必须提交：

- 可复现命令；
- 测试结果；
- 负向安全测试；
- 产物清单与 Hash；
- 环境问题；
- 未解决问题；
- 数据门禁状态；
- 依赖、模型、Prompt、Schema 与代码版本；
- 对应需求 ID。

验证标准以任务合同和 `docs/29_acceptance_test_catalog.md` 为准。智能体不得给自己的摄影质量主观打分代替人工评审。

### 什么时候停止等待批准

N0 所有交付完成、质量命令通过并创建一个独立 commit 后立即停止。输出标准停止消息，不启动 N1，不下载模型，不接触真实照片。任何安全硬约束无法证明时也必须 fail closed 并停止。

## 3. 不可变硬约束

1. 原始照片目录只读；绝不修改、移动、删除或改权限。
2. 本地默认；禁止云端图片处理。
3. 敏感与运行数据全部 Git 忽略。
4. 真实数据放量必须依次通过 3 → 20 → 100 → 全量。
5. 阶段授权和数据授权是两个独立门禁，两者都通过才可执行。
6. VLM 不得伪造 EXIF、版权、精确焦段、真实心理、精确安全距离或原调色参数。
7. Pose 坐标不得由文本 VLM 生成。
8. 所有开源代码、模型、权重和数据记录来源、版本、Hash、许可与使用限制。
9. Bundle 只含 APPROVED 且 Schema 有效的条目。
10. App 不能读取 Pipeline DB；Pipeline 不能导入 App 业务源码。
11. OpenClaw 当前没有实现权限，也没有调度权限。
12. Owner 批准必须是仓库中的显式、范围化批准记录；缺失即未批准。

## 4. 双门禁

执行任一非 N0 工作必须同时满足：

```text
phase_authorized == true
AND data_gate_authorized == true
AND required_model_download_approvals_exist
AND required_owner_inputs_are_present
AND handoff_integrity_passes
```

代码阶段通过不自动推进数据规模。数据门禁通过也不自动授权新阶段。

## 5. 冲突处理

- 适配器与主合同冲突：主合同优先。
- 任务与 `PROJECT_STATE.json` 冲突：选择更严格者并停止报告。
- 文档与安全硬约束冲突：安全硬约束优先。
- 不确定某动作是否扩大 Scope：视为禁止。
- 发现疑似密钥、原图或绝对路径将被提交：停止并隔离，不提交。
- Owner 新指令只有在明确说明范围、阶段、数据门禁和授权动作后才可改变状态。

## 6. 实施纪律

- 修改前先验证交付包；
- 小步、可审查、可回滚；
- 不静默吞错；
- 不篡改测试以制造通过；
- 不用 mock 结果声称真实硬件通过；
- 不把未运行标成通过；
- 不将“未检测到”写成“不存在”；
- 证据中区分 `PASS`、`FAIL`、`SKIPPED`、`NOT_AVAILABLE`；
- 绝对路径在报告中脱敏；
- N0 只建底座，不建立假实现冒充后续模型能力。

## 7. N0 完成消息模板

```text
N0_COMPLETE_AWAITING_OWNER_APPROVAL

Commit: <commit_sha>
Authorized phase executed: N0
Authorized data gate used: G0_THREE_SYNTHETIC_FIXTURES
Quality command: <command>
Test evidence: reports/N0_test_evidence.md
Environment report: reports/N0_environment_report.md
Unresolved issues: reports/N0_unresolved_issues.md
N1 plan: reports/N1_detailed_plan.md
Real photo access: NOT_USED
Model downloads: NONE
Cloud access: NONE
OpenClaw integration: NONE
Next action taken: STOPPED
```
