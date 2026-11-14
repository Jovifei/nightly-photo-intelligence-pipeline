# 拍照双项目许可证登记表 v1（初稿）

> 状态：**初稿，待业主批准**。登记只记录许可证据状态，不授权下载与执行。
> 原则：**代码许可 ≠ 权重许可 ≠ 人体参数模型许可 ≠ 数据集许可**，分层登记；结论只落到已选资产，不写成“今后所有同类模型天然都一样”；**许可通过≠进入默认栈**；每个部署资产须记录下载 URL、版本、SHA-256、对应模型卡与许可快照。
> 证据形式说明：`模型卡原文` = 模型托管页/模型卡页面原文；`仓库 LICENSE` = 代码仓库 LICENSE 文件；`条款原文` = 许可条款页面原文；`维护者答复` = 维护者在 issue 中的答复（适用范围以答复原文为准）；`未找到` = 检索后未找到明确证据，标注未核实。
> 适用前提：业主绝对个人自用，不商用（2026-11-14 01:22 拍板）。核心栈仍保持许可证干净（零成本留后路）；3D 模块为 experiment-only 实验隔离。

## 1. v1 默认栈（许可已核实通过）

| 资产 | 层 | 许可 | 证据形式 | 状态 | 备注 |
|---|---|---|---|---|---|
| MediaPipe Pose Landmarker 任务权重（Full / Lite / Heavy） | 权重 | Apache-2.0 | 模型卡（BlazePose GHUM 3D 模型卡） | ✅ 通过 | 须逐资产登记具体 .task 文件；Muse 已独立复核模型卡原文 |
| MediaPipe Hand Landmarker 任务权重 | 权重 | Apache-2.0 | 模型卡 | ✅ 通过 | 同上，逐资产登记 |
| MediaPipe Face Landmarker 任务权重 | 权重 | Apache-2.0 | 模型卡 | ✅ 通过 | 同上，逐资产登记 |
| MediaPipe 代码（Solutions / Tasks） | 代码 | Apache-2.0 | 仓库 LICENSE | ✅ 通过 | — |
| Qwen3-VL-2B 权重 | 权重 | Apache-2.0 | 官方模型页 | ✅ 通过 | 须逐项核对具体 revision；量化版与原版许可须分别核对 |
| OpenVINO gaze-estimation-adas-0002 权重 | 权重 | Apache-2.0 | Open Model Zoo 许可（模型库 Apache-2.0） | ✅ 通过（有条件） | **模型库已弃用/维护模式，须冻结资产本地存档**；默认关闭的可选增强 |
| OpenVINO 运行时 | 代码 | Apache-2.0 | 仓库 LICENSE | ✅ 通过 | — |
| PyTorch / ONNX Runtime / 部署依赖 | 代码 | 各自开源许可 | 各仓库 LICENSE | ✅ 通过 | 以实际选用版本为准 |

## 2. 升级项与候选项（许可已核实，但不进入默认栈）

| 资产 | 层 | 许可 | 证据形式 | 状态 | 备注 |
|---|---|---|---|---|---|
| Depth Anything V3 **Metric-Large** 权重 | 权重 | Apache-2.0 | 官方模型卡 | ✅ 通过（锁定资产） | **须锁定具体资产**：DA3-Large / DA3-Nested 为 CC BY-NC，不可混同；换算公式见可行性报告 |
| TinyCLIP 指定官方权重 `wkcn/TinyCLIP-ViT-8M-16-Text-3M-YFCC15M` | 权重 | MIT | 指定官方权重页模型卡 `license: mit` + 所链接 MIT 正文 | ✅ 通过（候选） | 未找到另外点名该 checkpoint 的权重专用许可文件；低频场景候选分类，后续验证；v1 不含自动场景识别 |
| GeoCalib 权重 `geocalib-pinhole` / `geocalib-distorted` | 权重 | CC BY 4.0 | 独立 LICENSE-WEIGHTS 正文（README License 段区分代码与权重） | ✅ 通过（候选） | 未知内参标定候选；结果只能作有来源的估计 |
| GeoCalib 代码 | 代码 | Apache-2.0 | 仓库 LICENSE | ✅ 通过（候选） | — |
| MoGe-2 指定官方权重 `Ruicheng/moge-2-vits-normal` | 权重 | MIT | 指定官方权重页模型卡元数据 `license: mit` | ✅ 通过（候选） | 未找到独立权重专用许可正文；不外推至其他 MoGe 版本；未知内参标定候选 |
| SMPL-X 本体许可 | 人体参数模型 | 含非商业艺术项目条款 | 条款原文（SMPL-X 许可页） | ✅ 通过（单用户、禁分发） | 许可原文含“non-commercial artistic projects”；Body License 为 CC BY 4.0（不含 shape blendshapes）；Muse 已独立复核条款原文 |
| MANO 资产 | 人体参数模型 | 含非商业艺术用途、不得打包分享 | MANO 许可 | ✅ 通过（单层） | 只解决 MANO 一层；须单独取得；不解决 HaMeR checkpoint 层 |
| HaMeR 代码 | 代码 | MIT | 仓库 LICENSE | ✅ 通过（代码层） | 代码层通过不代表 checkpoint 层通过 |
| Qwen3-VL-8B-Instruct-GGUF（官方量化） | 权重 | 待逐项核对 | 官方 GGUF 仓库 | ⚠️ 待核对 | 不假称量化权重与原版同许可；须核对官方 GGUF 仓库许可声明后登记 |

## 3. 未闭合缺口（升级被门控）

| 资产 | 层 | 证据形式 | 状态 | 影响 |
|---|---|---|---|---|
| RTMW 权重（rtmlib / RTMPose 133 点 checkpoint） | 权重 | rtmlib README 文末 Commercial Use Statement（**维护者使用提醒，不是许可证**）：“For model weights trained on non-commercial datasets (e.g. COCO-WholeBody), please refer to this.”（this 指向 issue #65）；MMPose issue #3062 维护者答复（只针对特定使用） | ❌ **未闭合** | RTMW 133 点升级被门控；须权重许可闭合 + A/B 增益确认 |
| HaMeR 官方 checkpoint | 权重 | 未找到点名官方训练 checkpoint 的作者原文 | ❌ **未核实** | 3D 实验模块 HaMeR 层被门控；代码 MIT 不替代 checkpoint 许可 |
| Gaze-LLE decoder checkpoint | 权重 | 官方 README 与 v1.0.0 release 提供 checkpoint，但无明确权重许可句 | ❌ **未核实** | 视线增强候选被门控；代码 MIT 与标准 DINOv2 骨干 Apache-2.0 已核实，均不覆盖 decoder |
| SMPLer-X checkpoint | 权重 | 作者权重页未找到清晰独立权重许可 | ❌ **未核实** | 3D 实验模块 SMPLer-X 层被门控；SMPL-X 条款不推导整个 checkpoint 链 |
| SMPLer-X 代码 | 代码 | S-Lab License 1.0（非商业） | ⚠️ 非商业许可 | 仅 experiment-only 实验隔离；须业主知情 |

## 4. 排除项（不引入）

| 资产 | 许可/依据 | 证据形式 | 排除理由 |
|---|---|---|---|
| DSINE | 帝国理工自定义非商业许可 | 官方 LICENSE（verified live 一手读到） | 限定用途；权重独立许可未核清；法线 ≠ 光源方向；光向改 VLM 解读 + 不确定性标注 |
| MobileCLIP2 | Research Purposes（非商业科学研究及学术开发） | 官方许可声明 | 不把“个人摄影爱好”自动解释为符合其授权；与 SMPL-X 明确包含艺术项目的条款不同 |
| YOLO-pose | AGPL-3.0 | 仓库 LICENSE | 政策上排除：与“许可证干净”目标冲突，污染未来分享 |
| L2CS-Net | 未核实；Gaze360 训练权重非商业 | — | 许可未核实，不进栈 |
| Sapiens / Sapiens2 | 非商业/专有许可 | — | 不进栈 |
| OpenPose / AlphaPose | 非商业许可；OpenPose 已停滞 | — | 不进栈 |

## 5. 规则

1. **分层登记**：代码、权重、人体参数模型、数据集四层分别登记，任何一层未闭合即该资产未闭合。
2. **逐资产登记**：每个部署资产记录下载 URL、版本/revision、SHA-256、对应模型卡与许可快照；不写成“同类模型天然都一样”。
3. **许可通过≠进入默认栈**：升级项须再凭实测 + 增益确认 + 业主批准方可接入（见 `03-execution-plan.md` §3）。
4. **下载逐项批准**：精确 revision、大小、SHA-256、许可证、删除方式，沿用 `OWNER_INPUTS_REQUIRED.md` 批准表格式。
5. **冻结存档**：OpenVINO Model Zoo 等已弃用/维护模式资产，须冻结资产本地存档（版本号 + SHA-256 + 许可快照），防止上游下架。
6. **措辞**：3D 模块统一称 **experiment-only** 实验隔离；不使用 research-only 措辞（与 MobileCLIP2 的 Research Purposes 许可措辞区分，避免混淆）。
7. **未核实标注**：检索后未找到明确证据的，一律标注“未核实/待确认”，不得以“仅本机、不赚钱”替代缺失的授权证据。

## 6. 核实记录

| 日期 | 核实内容 | 方法 | 结果 |
|---|---|---|---|
| 2026-11-13/14 | DSINE LICENSE | verified live 一手读到官方 LICENSE | 自定义非商业许可，排除 |
| 2026-11-13/14 | MediaPipe 模型卡、OpenVINO 许可、DA3 模型卡、Qwen3-VL 许可、SMPL-X 条款 | 调研报告一手来源核查 | 见上表 |
| 2026-11-14 | MediaPipe BlazePose GHUM 3D 模型卡 Apache-2.0 | Muse 独立复核 | 通过 |
| 2026-11-14 | SMPL-X 许可页条款原文 | Muse 独立复核 | 含非商业艺术项目条款，单用户、禁分发 |
| 2026-11-14 | Qwen3-VL-8B-Instruct-GGUF 官方存在 | Muse 独立复核 | 官方 GGUF 存在（Q4_K_M 约 5GB 估计值）；许可须逐项核对 |
| 2026-11-14 | RTMW 权重缺口 | GPT 第一轮审核 + Muse 复核 | 仍未闭合 |
| 2026-11-14 | GPT 终轮审核登记内容（TinyCLIP / GeoCalib / MoGe-2 / Gaze-LLE） | Muse 已逐字核对终轮原文 | 登记内容与原文一致；引用链接未随转录交付，见 `05-review-record.md` §6 |

## 7. 修订记录

- 2026-11-14：初稿。状态：待业主批准；批准前不下载、不执行。
