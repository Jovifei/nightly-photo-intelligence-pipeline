# 拍照双项目方案索引 v1（初稿）

> 状态：**初稿，待业主批准**。
> 业主令（2026-11-14 11:02）：**旧方案不删除，标注清楚哪个是旧方案、哪个是现行执行方案。** 本索引只作标注，不删除、不移动任何文档。
> 标注规则：每项标注日期与状态；日期以文件名或文档内记录为准，未逐项核实的标注“日期见仓库内记录”；状态分为：**现行方案**（当前执行口径）、**旧方案**（历史方案，保留备查，执行口径已更新）、**历史记录**（契约/状态/交接记录，保留备查）、**未合并草案**（draft PR，未进入 main）。
> 执行状态 HOLD；N2B1P 门禁保持硬停；本索引本身不授权执行。

## 1. 现行方案（2026-11-14，待业主批准）

本套文档集（初稿，本地 `~/workspace/photo-projects/docs-draft-20261114/`，尚未进入仓库）：

| 文档 | 内容 | 状态 |
|---|---|---|
| `01-requirements.md` | 需求文档：v1 范围、未完成项、诚实边界、10 项待拍板事项 | **现行方案（初稿，待批准）** |
| `02-feasibility-report.md` | 可行性报告：逐组件裁决、许可证登记摘要、性能未知项、关键勘误 | **现行方案（初稿，待批准）** |
| `03-execution-plan.md` | 执行方案：大阶段、小步骤、验收标准、GPU 租约、门禁规则 | **现行方案（初稿，待批准）** |
| `04-license-register.md` | 许可证登记表：逐资产证据形式、来源、状态 | **现行方案（初稿，待批准）** |
| `05-review-record.md` | 评审记录：Muse 调研 + dot 审查 + GPT 两轮审核 + 共识声明 + 门禁状态 | **现行方案（初稿，待批准）** |
| `06-plan-index.md` | 本索引 | **现行方案（初稿，待批准）** |

现行方案的技术共识基础：Muse 调研 + dot 独立调研与审查 + GPT 两轮审核（第一轮 15m36s、终轮约 4m30s）。共识状态 CONFIRMED；业主批准 PENDING；执行 HOLD。终轮原文已由 Muse 逐字核对，见 `05-review-record.md` §6。

**待业主批准后**，本套文档按业主 11:02 令更新进仓库 `docs/` 目录（NPI 仓由 dot 代提交，Muse 无写权限）。

## 2. 未合并草案（draft PR，均未进入 main）

| 草案 | 位置 | 日期 | 状态 |
|---|---|---|---|
| 技术路线卡点与封堵点状态报告 | NPI draft PR #4（分支 `muse/tech-route-blockers-20261114`，tip `6d6d7ad`，新增 `docs/TECHNICAL_ROUTE_BLOCKERS_20261114.md`） | 2026-11-14 凌晨 | **未合并草案**；B4 表述已对齐（见 §6.4）：草案 B4 行的“实现未执行”为旧表述，正确状态以文档 38 + dot 纠正为准 |
| 技术路线与需求 v1 | NPI draft PR #5（分支 `muse/tech-route-requirements-20261114`，tip `595d62d`，新增 `docs/TECHNICAL_ROUTE_AND_REQUIREMENTS_20261114.md`） | 2026-11-14 | **未合并草案**；已被本套文档集吸收并更新（基线栈、勘误、契约、阶段顺序均有更新），定稿后以本套文档集为准 |
| App T3–T17 | App stacked draft PR #7–#21（15 个） | 2026-09–10 | **未合并草案**；与 main 的差异未对账，状态未知，待 Grok 对账 |

## 3. 本地规划稿与调研报告（2026-11-13/14）

| 文档 | 日期 | 状态 |
|---|---|---|
| `~/workspace/photo-projects/plan-20261114.md`（规划稿 v0.2） | 2026-11-14 02:46（v0.1 00:46） | **旧方案**：已被本套文档集吸收并更新；保留备查，不删除 |
| `~/workspace/photo-projects/technical-route-and-requirements-20261114.md`（路线与需求 v1） | 2026-11-14 | **旧方案**：即 PR #5 内容的本地稿；已被本套文档集吸收并更新；保留备查 |
| `~/workspace/photo-projects/technical-route-blockers-20261114.md`（卡点文档本地稿） | 2026-11-14 凌晨 | **历史记录**：即 PR #4 内容的本地稿；卡点状态以最新核实为准 |
| `~/workspace/photo-projects/ai-analysis-prompt-20261114.md`（给 AI 的分析任务简报） | 2026-11-14 | **历史记录**：调研任务简报，保留备查 |
| `~/workspace/research_notes/photo-pose-tech-route-survey-20261113-1655/report.md`（技术路线调研报告） | 2026-11-13/14 | **历史记录**：调研证据来源，保留备查；结论以本套文档集为准 |
| `~/workspace/research_notes/photo-pose-feasibility-20261113-1726/report.md`（可行性调研报告） | 2026-11-13/14 | **历史记录**：调研证据来源，保留备查；结论以本套文档集为准 |

## 4. NPI 仓 `docs/` 现状（2026-11-14 只读核实，main 分支）

以下均为**旧方案 / 历史记录**：保留备查，不删除；执行口径以现行方案（§1）为准。其中契约类文档（导出契约、状态机、门禁）仍为仓库内有效的契约记录，直至业主批准新契约并正式替换。

### 4.1 编号文档 00–40（日期见仓库内记录，未逐项核实）

| 文档 | 性质 | 状态 |
|---|---|---|
| `00_reading_order.md` | 阅读顺序 | 历史记录 |
| `01_two_project_relationship.md` | 双项目关系 | 历史记录 |
| `02_timeline_and_gates.md` | 时间线与门禁 | 历史记录（门禁状态以最新业主决定为准：N2B1P 硬停保持） |
| `03_architecture_and_pipeline.md` | 架构与流水线 | 旧方案 |
| `04_export_contract.md` | 导出契约 | 历史记录（契约类） |
| `05_scope_and_non_goals.md` | 范围与非目标 | 旧方案 |
| `06_product_requirements_prd.md` | 产品需求（旧 PRD） | **旧方案**：需求口径以现行 `01-requirements.md` 为准 |
| `07_user_needs_and_use_cases.md` | 用户需求与用例 | 旧方案 |
| `08_pipeline_stage_design.md` | 流水线阶段设计 | 旧方案 |
| `09_data_model_and_state_machine.md` | 数据模型与状态机 | 历史记录（契约类） |
| `10_photo_intelligence_schema.md` | 照片智能 Schema | 历史记录（契约类） |
| `11_cli_contract.md` | CLI 契约 | 历史记录（契约类） |
| `12_directory_and_repository_layout.md` | 目录与仓库布局 | 历史记录 |
| `13_read_only_source_protection.md` | 只读源保护 | 历史记录 |
| `14_privacy_security_threat_model.md` | 隐私安全威胁模型 | 历史记录 |
| `15_open_source_model_license_policy.md` | 开源模型许可政策 | 历史记录（许可政策类；逐资产登记以现行 `04-license-register.md` 为准） |
| `16_gpu_resource_and_runtime_strategy.md` | GPU 资源与运行时策略 | 旧方案（GPU 租约口径以现行 `03-execution-plan.md` §5 为准） |
| `17_pose_segmentation_vlm_strategy.md` | 姿势/分割/VLM 策略 | 旧方案（模型选型以现行方案为准） |
| `18_prompt_and_hallucination_policy.md` | 提示词与幻觉政策 | 历史记录 |
| `19_human_review_workflow.md` | 人工审核流程 | 历史记录 |
| `20_testing_and_quality_strategy.md` | 测试与质量策略 | 旧方案 |
| `21_observability_resume_and_failure_policy.md` | 可观测/续跑/失败政策 | 历史记录 |
| `22_app_integration_boundary.md` | App 集成边界 | 历史记录 |
| `23_openclaw_future_security_boundary.md` | 未来安全边界 | 历史记录 |
| `24_definition_of_done.md` | 完成定义 | 历史记录 |
| `25_requirements_traceability.md` | 需求追溯 | 旧方案 |
| `26_research_sources_and_decisions.md` | 研究来源与决策 | 历史记录 |
| `27_codex_implementation_plan.md` | Codex 实施计划 | 旧方案 |
| `28_n1_detailed_plan.md` | N1 详细计划 | 旧方案 |
| `29_acceptance_test_catalog.md` | 验收测试目录 | 旧方案（验收口径以现行 `03-execution-plan.md` §4 为准） |
| `30_risk_register.md` | 风险登记 | 历史记录 |
| `31_agent_execution_playbook.md` | Agent 执行手册 | 历史记录 |
| `32_windows_wsl_docker_operating_model.md` | Windows/WSL/Docker 运行模型 | 历史记录 |
| `33_preflight_command_catalog.md` | 预检命令目录 | 历史记录 |
| `34_dependency_and_supply_chain.md` | 依赖与供应链 | 历史记录 |
| `35_data_manifest_contract.md` | 数据清单契约 | 历史记录（契约类） |
| `36_database_backup_and_recovery.md` | 数据库备份与恢复 | 历史记录 |
| `37_schema_business_validation.md` | Schema 业务验证 | 历史记录 |
| `38_n2b2_synthetic_validation_status.md` | N2B2 合成验证状态 | 历史记录（状态类；与 PR #4 的 B4 注记存在表述冲突，定稿前须对齐） |
| `40_engineering_fix_code_only.md` | 工程修复（仅代码） | 历史记录 |

注：编号中无 `39_*` 文档（2026-11-14 核实）。

### 4.2 其他文档与目录

| 文档/目录 | 日期 | 状态 |
|---|---|---|
| `OWNER_PHOTO_DIRECTION_GOAL_20261004.md` | 2026-10-04 | 历史记录（业主目标） |
| `T14_SYNTHETIC_CONTRACT_VALIDATION_HANDOFF.md` | 日期见仓库内记录 | 历史记录（交接） |
| `pose_direction_bundle_v1.md` | 日期见仓库内记录 | 历史记录（bundle v1） |
| `openspec/` 目录 | — | 历史记录 |
| `plan/` 目录 | — | 旧方案 |

## 5. App 仓 `docs/` 现状（2026-11-14 只读核实，main 分支）

以下均为**旧方案 / 历史记录**：保留备查，不删除；执行口径以现行方案（§1）为准。

| 文档 | 日期 | 状态 |
|---|---|---|
| `00_ANDROID_FIRST_EXECUTION_PLAN.md` | 日期见仓库内记录 | 旧方案 |
| `01_CAMERAX_AND_POSE_SPIKE.md` | 日期见仓库内记录 | 旧方案（spike 计划；Stage 0 以现行方案为准） |
| `03_REFERENCE_REPOSITORY_MAP.md` | 日期见仓库内记录 | 历史记录 |
| `04_IOS_SECOND_PLATFORM_GATE.md` | 日期见仓库内记录 | 历史记录 |
| `AA0_P0_CONTRACT.md` | 日期见仓库内记录 | 历史记录（契约类） |
| `AA0_PHASE1_REFERENCE_DIRECTOR_MVP_IMPLEMENTATION_REPORT.md` | 日期见仓库内记录 | 历史记录 |
| `ANDROID_BETA_PHONE_SETUP.md` | 日期见仓库内记录 | 历史记录 |
| `BETA_5_PERSON_TEST_PLAN.md` | 日期见仓库内记录 | 旧方案 |
| `BETA_USER_GUIDE.md` | 日期见仓库内记录 | 历史记录 |
| `CAMERA_DIRECTOR_EVOLUTION_PLAN.md` | 日期见仓库内记录 | 旧方案 |
| `CURRENT_PROGRAM_STATUS.md` | 日期见仓库内记录 | 历史记录（状态类；状态以最新核实为准） |
| `LOCAL_MAINLINE_RECONCILIATION_20261002.md` | 2026-10-02 | 历史记录 |
| `NEXT_GATE_MATRIX.md` | 日期见仓库内记录 | 历史记录 |
| `OWNER_PRODUCT_DECISIONS_2026-07-29.md` | 2026-07-29 | 历史记录（业主产品决策） |
| `P23C_PUBLIC_KNOWLEDGE_PACK_PREPARATION.md` | 日期见仓库内记录 | 历史记录 |
| `P23D_DURABLE_READY_RECOVERY.md` | 日期见仓库内记录 | 历史记录 |
| `P25R_OWNER_FINAL_REVIEW_GUIDE.md` | 日期见仓库内记录 | 历史记录 |
| `P25T_PRODUCT_AND_PIPELINE_ACTION_PLAN_20260921.md` | 2026-09-21 | 旧方案 |
| `P25U_CAPTURE_RESULTS_AND_OPEN_SOURCE_20260923.md` | 2026-09-23 | 历史记录 |
| `P25_REAL_20_CONTENT_REVIEW.md` | 日期见仓库内记录 | 历史记录 |
| `PHASE1_5_VLM_INTEGRATION_PLAN.md` | 日期见仓库内记录 | 旧方案 |
| `PHASE1_PRODUCT_READINESS_REVIEW.md` | 日期见仓库内记录 | 历史记录 |
| `PIPELINE_APP_BUNDLE_CONTRACT.md` | 日期见仓库内记录 | 历史记录（契约类） |
| `PKB1_PRODUCER_GOLDEN_VECTOR_HANDOFF_REQUEST.md` | 日期见仓库内记录 | 历史记录 |
| `POSE_DIRECTION_SCREEN.md` | 日期见仓库内记录 | 历史记录 |
| `PR22_SOURCE_REVIEW_20261002.md` | 2026-10-02 | 历史记录 |
| `PR23_LOCAL_INTAKE_20261002.md` | 2026-10-02 | 历史记录 |
| `PROGRAM_HANDOFF_REFERENCE.md` | 日期见仓库内记录 | 历史记录 |
| `PROGRESS_CONTRACT.md` | 日期见仓库内记录 | 历史记录（契约类） |
| `PROJECT_MASTER_ROADMAP.md` | 日期见仓库内记录 | 旧方案（路线图；执行口径以现行方案为准） |
| `PROJECT_PROGRESS.md` | 日期见仓库内记录 | 历史记录 |
| `PROJECT_RELATIONSHIP.md` | 日期见仓库内记录 | 历史记录 |
| `REMOTE_LOCAL_GITHUB_WORKFLOW.md` | 日期见仓库内记录 | 历史记录 |
| `REMOTE_PR22_REVIEW_HANDOFF_20261002.md` | 2026-10-02 | 历史记录 |
| `T14_INTAKE_PREFLIGHT_HANDOFF.md` | 日期见仓库内记录 | 历史记录 |
| `T4_STAGE_ASSESSMENT_20260927.md` | 2026-09-27 | 历史记录 |
| `UI0_APPLE_GLASS_DESIGN_SPEC.md` | 日期见仓库内记录 | 历史记录（设计规范） |
| `UI1_P1B_ENGINEERING_COMPLETION_PLAN.md` | 日期见仓库内记录 | 旧方案 |
| `current_program_status.v1.json` / `project_progress.json` | 日期见仓库内记录 | 历史记录（状态数据） |
| `privacy-policy.md` | 日期见仓库内记录 | 历史记录 |
| `handoff/`、`phase1_5/`、`reference/`、`references/` 目录 | — | 历史记录 |

## 6. 标注方法说明

1. 本索引标注时**未修改任何仓库文件**；旧文档的“旧方案/历史记录”标注仅存在于本索引中，待业主批准后，随本套文档集一并进入仓库 `docs/`，旧文档本身不删除、不移动。
2. NPI 仓编号文档 00–40 的逐项日期未逐项核实（只读核实了目录清单），标注为“日期见仓库内记录”；如需精确到日，须逐项读取文档内日期或 git 历史后补。
3. 契约类文档（导出契约、状态机、bundle 契约等）在新契约正式批准替换之前，仍为仓库内有效的契约记录；本索引不擅自宣布其失效。
4. PR #4 的 B4 注记与 NPI 文档 38 的表述已对齐（Muse 2026-11-14 核对原文）：文档 38 载明 N2B2 合成栈已在 S3/S20 上执行（峰值 11,338 MiB），生产 N2B2 锁定、Real20 未做；PR #4 草案 B4 行的“合成栈实现未执行”为旧表述，已由 dot 纠正采纳，本套文档采用正确表述。

## 7. 修订记录

- 2026-11-14：初稿。目录清单只读核实于 2026-11-14（NPI main 44 项、App main 44 项，含目录）。状态：待业主批准。
