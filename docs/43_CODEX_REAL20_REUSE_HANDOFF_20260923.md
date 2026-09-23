# Real20 本地接收与产品闭环任务 — 2026-09-23

这是新任务，不是 R0 接收记录或旧 R2 Prompt 的重复。仓库：
`Jovifei/nightly-photo-intelligence-pipeline`；分支：
`gpt/real20-transition-20260921`。本轮远端提交是
`0eb61780418474ca2acbe8f84961d55820dae484` 的普通后继，具体新 SHA 请 fetch 后读取。
main 基线仍为 `ffc4130823c1308f089b835c766e341ec2173e82`。

## 0. 范围与保护

Jovi 已请求审计、最小修复、开源复用和本分支普通提交。不要再询问是否允许写代码，
不要把历史 R0 ZIP 覆盖 R1，不重复跑 H3。使用新干净普通用户 worktree。
主工作树 AGENTS.md 原记录 2638 bytes、SHA
`b07a0460c28c74388b4d83500b128aa59fc8af1af9a753e97e1a5f8bdea70048`；
开始/结束复算，保留用户较新的真实修改，不能强制恢复成旧 Hash。
不 reset、不 force-push、不改 main、不改原图/ACL/系统策略。

本提交直接修改 src/real20 源码，没有待应用 payload。不要运行旧 apply 脚本。
阅读 docs/42_real20_review_and_reuse_20260923.md 与 integrations/label_studio/。
云端没有完整仓库可运行环境；开发定向测试使用明确隔离依赖的 harness，
它没有提交为 tests/conftest.py。本机必须用完整真实包执行新回归和原有测试。

## 1. 先确认修复和剩余阻塞，不能直接消费 R2 许可

核对：
A1 完整 admit 在默认 backend/runtime probe 与照片能力检查之前。
A2 ledger_root 始终是配置 Path，bound_ledger 单独是已持有句柄，二者对象身份比较。
A3 ExitStack 覆盖 output/ledger/reservation，reservation 记录写失败也尝试 FAILED；
任一 integrity/unload/evidence check 抛 OSError/TypeError/KeyboardInterrupt，
其他清理和 terminal 尝试仍执行；多个错误保留在异常组，不能伪造 persisted。

运行 tests/test_real20_review_lifecycle.py。保留原始默认 CLI、admission、数据门、
source guard/native 测试；新单元测试不能替代真实 Windows 验收。

**额外必须闭合的原生权限问题：**
`protect_consumption` 要求 DELETE_CHILD/DELETE/WRITE_DAC/WRITE_OWNER 被拒绝；
`windows_bound_promotion._directory_access(writable=True)` 同时申请 DELETE_CHILD/DELETE。
请先在已允许的 Git 外临时 synthetic 目录复现实际所需权限矩阵：
ledger 打开 -> 子 claim 创建 -> reservation 写入 -> FAILED/COMPLETE 发布。
如果代码访问掩码与保护策略矛盾，做最小的 append-only ledger 访问模式和出版权限分离，
不删除 protect_consumption，不把 bound 操作退回普通路径写，不全局放开删除/改 ACL。
继承权限、当前句柄权限、创建新目录的权限分别解释，验证实际 worker 的操作。
需要具体 Owner 文件系统决策时，只报那个决策和测试证据，不能用“权限 skip”掩盖失败。
若还存在任何真实安全断言失败，停止实际数据执行，先修代码。

## 2. 一次完成候选登记、支持环境验收和普通提交

本快照根 MANIFEST 已按原 Git 清单与新文件字节计算更新，但旧固定祖先数量的
preflight/test_git/verify_handoff 尚未登记本次候选。不得把这些失败声称为 PASS。
按实际最终源码登记一个明确、正常 code-only 后继，保留所有旧 tag、phase/data 锁、
no-merge、完整清单和授权校验。不重写 HEAD、不减少检查、不把新 SHA 冒充旧 SHA。
对 native 修复也在本批完成后统一冻结，不为每个格式化步骤制造新的运行许可。

使用已有 Python 3.12 CUDA/项目环境的绝对解释器路径，非 editable checkout
显式记录 PYTHONPATH=src。不开启新模型、不为代码测试下载安装库。
执行并记录真实完整矩阵：pytest、run_quality、verify_handoff、CLI preflight、
Ruff check/format、mypy、Schema、敏感扫描、git diff --check。
同时运行 tests/test_real20_label_studio.py。测试数记录实际值，不套旧 759。
只将真实 winerror=1314 的 symlink 创建缺口标 skip，其他错误真实失败。

支持环境中可能还需小范围格式/typing 修正；云端 Ruff/mypy 未运行，不能拿开发
42 项通过替代本机结果。全部修改后从 Git index 自动重建 MANIFEST，再普通 commit/push
同一分支并读回远端。main 不自动合并。代码最终 Review 与数据权限分开记录。

## 3. 开源复用是真实接口，不是要求重写审核 App

已接入：
- Label Studio 原生 review_config.xml；
- 完整 Real20 JSON -> tasks/data/predictions 的 export；
- annotations -> 绑定原输入的人工审查记录 import；
- jsonschema/referencing 固定本地 schema 校验（禁止远程 ref）。

这些不是伪称复制了上游源码；是使用其公开协议复用完整人工审核界面。
不要自己再做一个同功能前端。Label Studio server 未安装/未启动，UI roundtrip 未测试。
不得把完整服务器装进 ML venv、把它数据库混入 Pipeline，或自动打开云存储/模型后端。
其本地服务与数据库是独立部署步骤，按 Owner 的现有部署许可处理。
先用纯 synthetic JSON/预览进行服务器导入/导出兼容验证；最新版本与安全信息以官方为准。
保留 metadata-only adapter，不因为服务不可用而阻塞修复和代码送审。

工具：
`python tools/real20_review_exchange.py export --help`
`python tools/real20_review_exchange.py import --help`

生成原 tasks 文件后保存原字节与完整 SHA；导入时传 --original-tasks-sha256。
预览只允许显式 19 个 canonical ID，对应 1 个重复引用；照片原根仅做排除边界，
不得扫描、递归挂载整个图库。工具不会制作预览或验证其像素，实际审核前需要
在已授权同一资产范围内单独制作/校验 EXIF-free preview 映射。
不要让 ACCEPT 自动成为 Owner APPROVED；取消、缺失、多份冲突 annotation 都应保留。

## 4. 代码通过后落实 R2，而不是再发一段状态复述

Jovi 已多次表达 Real20 推进授权。完成互不依赖的代码和环境工作后，一次整理：
最终 candidate/tree/full-source/quality/review；固定 20 项清单（19+1）；
真实 source fingerprint/read-only；模型/cache/runtime/operator；新输出与时间窗。
从已知控制文件定位原 manifest 和 source 配置，不扫描照片。
原 G1 manifest SHA：
`29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47`。
原 G1 可能是历史文本清单，应使用实际 g1_contract 的解析，不按旧 R0 假设改造成假源。
若两个绝对路径确实没有配置/记录，在完成其他工作后只集中询问这两个输入。
不能编造路径，也不能反复询问笼统“授权吗”。

新批准的 Real20 credential/anchor 要绑定最终代码、真实数据和具体 UTC 窗口；
已有明确的、仍有效的 Owner 物料化指令可按其范围执行，不能把本提交或 DRAFT 当许可。
过期/已消费许可不能复用。新代码 Review 和所有必需本机条件通过前，不读取照片。
若后续操作中出现真实失败，一次许可按合同消耗，保存失败证据，不自动换目录重跑。

R2 成功后保留 Pending Human Review，使用本集成开展逐张人数/姿态/分割/构图/建议审核。
记录人工修改时间、无依据解释、ACCEPT/EDIT/REJECT，不替用户决定。
之后才是 APPROVED-only Bundle、独立 App 导入/显示/拒绝错误/回滚。
不在本批开始全量、替换模型、向量数据库或 OpenClaw。

## 5. 最终一次性汇报

报告必须区分：
1. actual runtime bug 修复与测试；
2. native 权限/竞态已测、缺口与失败；
3. 最终支持环境矩阵与新远端 SHA；
4. Label Studio JSON 兼容已测、server/UI 未测或实际通过；
5. R2 是否真正执行，未执行的具体剩余条件；
6. 原 AGENTS/state/源/H3 证据未改，完整日志与报告 SHA。

不要回复“本轮是重复接力所以没做事”。这是有明确新代码和真实待验证问题的新任务。
不要把 cloud development tests、旧质量报告、metadata 一致性或 code-only Review
混合成生产可执行 PASS。不要向用户提供虚构完成比例。
