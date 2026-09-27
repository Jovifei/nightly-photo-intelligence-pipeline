# Real20 ledger inheritance preflight — design

状态：Jovi 于 2026-09-27 选择“隔离探针目录＋独立清理身份”。本设计定义第一个 code-only 安全加固子项目；它不是 Owner 执行凭证，也不授权读取照片。

## 目标

在任何真实 Real20 reservation 之前，证明新建 ledger claim 及其允许的 append-only 文件会获得所需的 Windows 有效权限。缺少、过期、不匹配或无法清理的探针都必须在消耗一次性凭证之前 fail closed。

## 当前证据

- 候选基线：`71bcd85361da55097a258ff6c6b03c89797ea312`，tree `1bf81584fa12a912648187d798e1e9dc4c480293`。
- 当前 handoff verifier 为 `8 PASS / 0 FAIL`；这是 code-only 证据，不是 Real20 许可。
- `admission.protect_consumption()` 检查配置 ledger 根和它的父目录；`runner._run_real20()` 中真实 claim 由 `_reservation()` 创建，claim 权限检查发生在 reservation 之后。
- 当前原生测试观察到新 claim 初始具有 `WRITE_DAC`，然后手动设置 per-claim ACL；这不能证明新 claim 会从父目录继承正确策略。
- `PROJECT_STATE.authorization.active_execution` 仍仅为 N2B1P cache promotion，`phase_status.N2B2=LOCKED`。九个固定 Real20 Owner 控制文件均不存在，Real20 为 `NOT_RUN`。

## 选定架构

1. Owner 在已配置 runtime parent 下预置专用、Git 外的合成 ACL 探针目录。它与真实执行 ledger、output、cache 和照片源分离；位置从可信 runtime 配置推导，不接受任意 CLI 路径。探针根与 ledger 根的 DACL policy digest 必须一致。
2. Owner 预置独立清理身份，其删除/ACL 权限仅限探针目录。Git 中不存密码或 token；runner 不修改 ACL，也不 impersonate 清理身份。
3. `npi real20 ledger-probe` 在实际 runner identity 下运行：绑定 probe 与配置 ledger 的句柄、核对对象身份和 DACL policy digest，并只在 probe 下创建唯一 synthetic claim 与允许的 reservation/terminal 文件名。该命令不读取照片、不创建真实 ledger reservation，也不需要 Real20 lease。
4. 对 parent、fresh claim、fresh files 检查有效权限。claim directory 必须拒绝 `DELETE_CHILD`、`DELETE`、`WRITE_DAC`、`WRITE_OWNER`；ledger files 必须拒绝 `FILE_WRITE_DATA`、`DELETE`、`WRITE_DAC`、`WRITE_OWNER`，同时允许 `FILE_APPEND_DATA`。未知 `AccessCheck` 结果失败关闭。
5. `npi real20 ledger-probe-clean` 由独立清理身份运行，只接收 probe nonce 与对象 identity，删除对应的 synthetic probe 并返回清理证明；它不能访问真实 ledger、source、output 或 cache。失败时不做宽泛递归清理或 ACL 修复。
6. Owner 将探测与清理证明嵌入现有固定受保护控制 `real20_runtime_identity.json` 的 `ledger_acl_probe` 字段。该字段包含 ledger/probe DACL policy digest、runner/cleanup identity fingerprints、probe result 和 UTC freshness window；现有 runtime-identity SHA 绑定继续把它带入 credential/anchor。Real20 的 pre-reservation gate 校验该证明与实时 ledger DACL/identity；不匹配就不能调用 `_reservation()`。DACL 或运行身份改变后必须重新探测并重新准备 candidate-bound controls。

探针只证明隔离合成 sibling resource 上的继承策略，不在真实 ledger 中创建 claim。探针与 ledger 的策略摘要、文件系统对象身份和 runner token 必须绑定一致。真实 ledger 的根目录和父目录有效权限检查继续保留；append-only handles、terminal records、commit markers 和 mutation-denial assertions 均不得删除或放宽。

## Runtime identity v2 的两个语义域

现有 `real20_runtime_identity.json` 将实时模型/GPU 观察值作为整个对象：credential/anchor 绑定其 canonical SHA-256，runner 又要求 `runtime_probe()` 的 canonical SHA-256 与同一个摘要相等。直接在这个对象上增添 `ledger_acl_probe` 会令实时观察值永远无法相等，因此新执行只接受以下 v2 顶层结构：

- `schema_version`：精确字符串 `2.0`；
- `runtime_observation`：保留现有 `runtime_probe()` 输出的 `models`、`worker`、`vision`、`qwen` 映射及其字段语义，不添加 ACL 元数据；
- `ledger_acl_probe`：本设计第 6 点规定的 Owner 绑定探针及独立清理证明，包含版本、策略与对象摘要、runner/cleanup 身份、结果及 UTC freshness window。

正式 Schema 必须严格定义这三个顶层成员和每个子对象，拒绝额外字段。credential/anchor 继续绑定**整个 v2 控制对象**的 canonical SHA-256，包含 `ledger_acl_probe`；实时 `runtime_probe()` 只与 `runtime_observation` 子对象的 canonical SHA-256 比较。`ledger_acl_probe` 由 admission 独立检查。v1 可用于解释历史证据，但不能满足新的 Real20 admission；未知版本、额外字段、缺失子对象或类型错误都失败关闭。不得把 ACL 字段塞进实时 GPU/模型探针，也不得降级整体凭证绑定。

执行顺序是：严格读取并验证完整 v2 与 credential/anchor → 从 live attestation 获取并匹配 runner identity、ledger policy digest 和 ledger object identity，再验证 `ledger_acl_probe` 的版本、结果、身份、策略、对象和 freshness → 验证实时 `runtime_observation` → 在已绑定**真实 ledger** 句柄上，仅以非变更方式重检 ledger 根和父目录的有效权限、runner identity、对象/策略绑定及其他 admission 门 → `_reservation()`。缺少 live attestation 也必须失败关闭；不得退回结构字段自洽即通过。不得在真实 ledger 创建、重放或清理 synthetic probe，也不得修复或修改 ACL。上述四层任一失败时，`_reservation()` 调用次数必须为零。静态控制检查应先于可能较重的运行时探针；准确位置可由实现保持上述先后约束。

`ledger-probe` 只生成 Git 外、脱敏的候选证明；`ledger-probe-clean` 由独立清理身份生成清理证明。继承观察可以独立记录为 `PROBE_PASS`，但只有清理证明存在且有效，整份证明才能成为 `ADMISSION_ELIGIBLE`；清理失败时保留真实的观察结果，同时拒绝准入。两份证明完成且被 Owner 审核后，才组装并封存 v2 `real20_runtime_identity.json`，之后再创建绑定其整体摘要的 credential/anchor。探针命令不得原地改写已封存或已绑定凭证的控制文件；否则整体摘要变化会使凭证失效。

`ledger_acl_probe` 必须分别记录 `probe_object_sha256`（隔离 synthetic sibling）和 `ledger_object_sha256`（真实 ledger 对象上下文）；两者不能混用。回归测试必须至少证明：仅改变 `ledger_acl_probe` 时整体控制摘要改变而 `runtime_observation` 摘要不变；改变 `runtime_observation` 时两种摘要均改变；实时探针只比较观察子对象；修改已绑定 proof 使 credential/anchor 失效；缺失/过期/清理失败/身份、策略或真实 ledger 对象不匹配时都在 reservation 前拒绝。

## 数据流与失败语义

```text
固定 Owner controls + candidate identity
  → `ledger-probe` 在实际 runner token 下创建 synthetic claim/files
  → 检查新对象的有效权限并生成 nonce-bound probe 结果
  → `ledger-probe-clean` 由独立 cleanup identity 清理并返回证明
  → Owner 将 probe/cleanup 证明嵌入 runtime identity
  → pre-reservation gate 重检 ledger DACL/identity、worker/native operators、source/data/phase gates
  → one-shot reservation
  → 仅在 Owner controls 全部有效后进入 Real20 worker
```

探针创建、AccessCheck、DACL 比较、identity、freshness 或清理任一失败，均须在真实 reservation 前停止。探针不消耗真实凭证。`ledger_acl_probe` 是现有 Owner-protected runtime identity 的组成部分，不是 lease，也不能单独授权照片读取。一旦真实 reservation 建立，既有一次性语义不变：后续失败仍消耗许可并尝试写入 terminal record；源完整性成功/失败后都要复核。

## 范围与不变量

- 本子项目不枚举/读取照片，不读 EXIF，不加载/推理模型，不运行 CUDA operator，不写 SQLite，不做 App/Bundle 工作，不修改源数据，也不创建/消费真实 lease/anchor。
- 不改正式 ledger、照片源或系统 ACL。原生测试只使用 Owner 预置的 synthetic probe policy。
- 保持生产 `N2B2=LOCKED`；不改 `PROJECT_STATE.json`、历史 approvals、H3 evidence、tags 或 `main`。
- 保持 bound-handle、只读源、20 项 / 19 次唯一推理、既有模型、v1.2 facts、EXIF 白名单和失败消耗规则。
- R2 工作单中缺失的 source-root 路径、冻结 manifest 文件路径和空 output 路径仍是独立 Owner 输入；本设计不推测它们。

## 实现验收条件

1. RED 测试证明缺失、过期、不匹配或失败的 ACL probe 会在 `_reservation()`、backend 构造和任一 source-image open 之前被拒绝。
2. Windows 原生测试在继承的 synthetic policy 下创建全新的 claim 与文件，并验证所需 allow/deny 矩阵；不得在 claim 创建后补设 per-claim ACL。
3. 测试只通过独立 cleanup identity 清理专用 probe，验证无残留。身份或安全清理路径不可用时，原生继承证明必须标为 `NOT_AVAILABLE`，不能用 skip 或 mock ACL 结果替代。
4. 正向默认 CLI 测试使用 synthetic 图片与 fake model backend 覆盖真实 admission/reservation/ledger 调用链；负向测试证明 ACL gate 拒绝时既没有 reservation，也没有打开图片。
5. 保留现有 append-only profile、N2B1P bound-handle、源完整性、one-shot ledger 测试及所有阶段/数据门。
6. 最终候选须独立审查；从 Git index 重建根 MANIFEST；在精确最终 SHA 上完成受支持的 Python 3.12 全量质量矩阵、handoff 和 preflight。

## 尚缺的 Owner runtime setup

当前控制材料未提供 probe 目录或 cleanup identity。Owner 必须预置 probe/cleanup identities，并将脱敏 identity、policy digest、清理结果和 freshness window 写入现有受保护 runtime identity；完成之前不得把 native inheritance 证明记为 PASS。agent 不会创建系统用户、安装 service/scheduled task，或扩大 ACL 来取得该身份。
