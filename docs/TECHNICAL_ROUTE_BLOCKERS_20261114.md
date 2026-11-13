# 技术路线卡点与封堵点状态报告（2026-11-14）

> 核实日期：2026-11-14 凌晨。核实方法：仓库全文阅读（README、PROJECT_STATE.json、契约、ADRs、后端代码、PR 状态）+ 主机 SSH 只读实测。
> 本文档只记录状态，不修改任何门禁、不执行任何推理。业主已于 2026-11-14 00:57 明确：**暂不解封门禁**。技术路线研究报告完成、业主拍板之前，不跑模型、不改门禁。

## 1. 卡点清单

| 编号 | 卡点 | 证据 | 影响 | 解封/推进条件 | 当前状态 |
|---|---|---|---|---|---|
| B1 | N2B1P 外部审查硬停 | `PROJECT_STATE.json` 的 `required_stop_after` 硬停在 N2B1P 外部审查；`approvals/REVIEWER_N2B1P_INDEPENDENT_REVIEW_PROMPT.md` 存在但审查员角色从未有人担任（2026-08-08 立规至今） | N2B2 及之后阶段按合同不得执行 | 业主决定是否改简化执行契约 | **暂不解封（业主 00:57 明确）** |
| B2 | 业主输入未齐 | `OWNER_INPUTS_REQUIRED.md` 所列：真实照片根目录授权、20 张校准清单、EXIF 读取许可、模型下载批准、放量批准，至今未齐 | 任何真实照片处理与模型下载都不得开始 | 业主逐项提供/批准 | 待业主 |
| B3 | 姿势模型缺口 | N2B2 规划的 TorchVision Keypoint R-CNN 只有 COCO 17 点，无手、无脸；`pose/contracts.py` 已预留 HAND/FACE 分区但无模型 | 做不出“手弯多少、眼睛看哪” | 技术路线研究选型（进行中，见 §3） | 研究中 |
| B4 | 真实后端未接入 | `pose/`、`segmentation/` 只有 Protocol + fake 后端；N2B2 合成栈实现未执行；README 自述从未读真实照片、从未跑推理 | 流水线产不出真实姿势事实 | B1/B2/B3 解决后接入 | 未开始 |
| B5 | App 侧对账未完成 | ai-photography-director-app 的 T3–T17 仍是 15 个 stacked draft PR（#7–#21），与 main 的差异未对账；真实姿势估计为 `FakePoseEstimator` | 消费端能力边界不清 | Grok 对账（已派活，待回） | 待回 |
| B6 | LAN 服务未验证 | 主机侧 FastAPI 服务代码 + Qwen3-VL-2B 权重 4.26GB + manifest 均已就位（2026-11-14 实测），但从未观测到运行，配对/HTTPS 未实测 | 手机经局域网调主机分析的链路未经证实 | 主机冒烟（合成图先行）+ 真机配对实测 | 未开始 |
| B7 | GPU 窗口排班 | 空闲窗口：每天 02:00–10:00，工作日另加 14:00–19:00；2026-11-14 凌晨窗口已有 ComfyUI 任务 | 姿势实验须排队，不可抢卡 | Grok 排班后定 | 待排班 |
| B8 | 诚实边界未进产品 | 单图距离只能估计、视线给落区、光向给扇区——均须带置信度/不确定性标注，现有 schema 与文案未覆盖 | 若不处理，产品会把估计报成实测 | 随 Schema v1 落地（方案阶段） | 设计债 |

## 2. 已确认可用的基础（2026-11-14 主机实测）

- Tailscale 通，SSH 正常；主机 RTX 4070 SUPER 12GB。
- Ollama 在跑：`qwen3.5:4b` / `qwen3.5:9b`，两者 capabilities 均含 vision（未实测过图像输入）。
- `E:\AI_Tools\Other\LocalLLM\Qwen3-VL-2B-Instruct<revision>\` 内有 `model.safetensors` 4.26GB + config + preprocessor_config + `photoai-model-manifest.json`，与 `local_analysis_service/service.py` 默认 MODEL_ROOT 一致。
- `photoai-service-venv` 有 python；`npi-n2b2-synthetic-runtime\venv` 存在。
- 契约资产齐全：pose/segmentation Protocol、vision-facts 契约、pose-direction bundle v1、benchmark harness、PKB1 工具链。

## 3. 研究中的技术方向（路线研究报告覆盖范围）

每个候选须给出：仓库链接、论文/报告出处、代码许可证与权重许可证（分开）、能否商用、12GB 显存能否跑、成熟度。

1. 全身姿势（含手、脸）——单张照片出全身关键点与关节角。
2. 手部姿态——手指弯曲程度。
3. 视线估计——眼睛看向哪里（落区 + 置信度）。
4. 单图深度——辅助估计拍摄距离（估计 + 不确定性）。
5. 光向估计——光从哪个方向来（扇区 + 置信度）。
6. 端侧实时姿势——手机上实时跑的方案（与现有 `PoseKeypoint33` 33 点 schema 对齐）。
7. VLM 图像解读——风格、构图、情绪（只做解读，不生产姿势坐标）。

研究分工：Muse（深度调研）+ dot（开源模型评估）+ Grok Bot（主机与 App 侧可行性）。结论汇总后形成《技术方向报告》，报业主拍板。

## 4. 下一步顺序

1. 团队审查与深度研究（本阶段）→ 2. 技术方向报告 → 3. 业主拍板技术路线 → 4. 设定方案 → 5. 执行。
2. 报告完成前：不跑模型、不改门禁、不合并不部署。

## 5. 修订记录

- 2026-11-14：初版（Muse 核实，业主令：先定技术路线）。