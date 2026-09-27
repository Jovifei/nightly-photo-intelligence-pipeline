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

1. Owner 在已配置的 runtime parent 下预置一个专用、Git 外的合成 ACL 探针目录。它与真实执行 ledger、output、cache 和照片源隔离。探针目录的 DACL 策略必须与 ledger 预期策略字节一致；探针位置从可信 runtime 配置推导，不接受任意 CLI 路径。
2. Owner 预置一个独立清理身份，其删除/ACL 权限仅限探针目录。Git 中不存密码、token 或通用命令；runner 不修改 ACL，也不 impersonate 清理身份。
3. 在支持的 Windows worker 上，以实际 Real20 runner token 执行 native preflight。通过 bound handles 绑定 probe 与配置 ledger，核对对象身份及 DACL policy digest；只在 probe 下创建唯一 synthetic claim 和允许的 reservation/terminal 文件名。
4. 对 parent、fresh claim、fresh files 检查有效权限。claim directory 必须拒绝 `DELETE_CHILD`、`DELETE`、`WRITE_DAC`、`WRITE_OWNER`；ledger files 必须拒绝 `FILE_WRITE_DATA`、`DELETE`、`WRITE_DAC`、`WRITE_OWNER`，同时允许 `FILE_APPEND_DATA`。未知 `AccessCheck` 结果失败关闭。
5. runner 关闭全部 handles 后，将仅含 nonce 的 probe 对象交由独立清理身份处理。记录脱敏清理结果；只有确认 probe 对象已移除才报告成功。失败时不做宽泛递归清理或 ACL 修复。
6. 成功结果绑定进 Owner-protected `real20_runtime_identity.json`，并随既有 candidate-bound credential/anchor hash 绑定。结果包含 ledger/probe DACL policy digest、runner-token identity fingerprint、probe result 和 UTC freshness window。`admit()` 在 `_reservation()` 之前重新检查当前 ledger 是否符合绑定策略。DACL 或运行身份改变即要求重新探测并重新签发控制材料。

探针只证明隔离合成 sibling resource 上的继承策略，不在真实 ledger 中创建 claim。真实 ledger 的根目录和父目录有效权限检查继续保留；append-only handles、terminal records、commit markers 和 mutation-denial assertions 均不得删除或放宽。

## 数据流与失败语义

```text
固定 Owner controls + candidate identity
  → 绑定 synthetic probe / ledger identity 和 DACL
  → 实际 runner token 创建 synthetic claim 与 append-only files
  → 检查新对象的有效权限
  → 独立 cleanup identity 仅移除 nonce-scoped probe
  → 验证清理结果并绑定 runtime identity
  → 既有 source/runtime/data admission gates
  → one-shot reservation
  → 仅在 Owner controls 全部有效后进入 Real20 worker
```

探针创建、AccessCheck、DACL 比较、identity、freshness 或清理任一失败，均须在真实 reservation 前停止。探针不消耗真实凭证。一旦真实 reservation 建立，既有一次性语义不变：后续失败仍消耗许可并尝试写入 terminal record；源完整性成功/失败后都要复核。

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

当前控制材料未提供 probe 目录位置或清理身份。Owner 必须预置它们，并将脱敏 identity/policy digest 绑定到新的受保护 runtime-identity record；完成之前不得把 native inheritance 证明记为 PASS。agent 不会创建系统用户、安装 service/scheduled task，或扩大 ACL 来取得该身份。
