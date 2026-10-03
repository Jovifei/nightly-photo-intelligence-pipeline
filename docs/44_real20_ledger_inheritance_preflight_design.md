# Real20 ledger inheritance preflight — current design

状态：R1 code-only architecture，2026-10-03。本文取代 2026-09-27 版本中“第二个 Windows cleanup account / 独立清理账户”的要求。当前设计使用 **cleanup capability + restricted pre-opened-handle helper**；不要求第二个 Windows 账户。

本文不授权 bootstrap/native probe/helper machine execution，不授权 Real20 reservation，不授权照片/EXIF、模型/CUDA、SQLite 或 production N2B2 解锁。

## 1. 目标

在任何真实 Real20 reservation 之前，用隔离 synthetic sibling resource 证明：

- production ledger 根对象身份稳定；
- synthetic probe 根与 ledger 根使用一致的 security-policy digest；
- 新建 synthetic claim/file 在实际 runner token 下获得预期 append-only allow/deny 矩阵；
- synthetic probe 能通过一个**仅持有预打开 handle**的受限 helper 精确清理；
- probe nonce、probe object、helper identity、live ledger object/policy/runner identity 全部进入 runtime identity v3；
- 任一 proof 缺失、过期、漂移或 cleanup failure 都在 `_reservation()`、backend construction 与 image open 前 fail closed。

## 2. 信任根与固定路径

唯一 runtime 路径信任根仍是：

`approvals/n2b1p_runtime_configuration.json`

代码必须通过 strict `load_n2b1p_runtime_configuration()` 读取，不能向该 schema 偷塞 Real20 专用字段。

Real20 control-plane 只允许从其 `runtime_parent` 推导以下固定 leaf：

- `real20-execution-ledger`
- `real20-ledger-acl-probe`
- `real20-control-plane-bootstrap.json`

CLI/API 不接受 caller 提供 ledger/probe/cleanup filesystem path。

cache/work/root overlap、reparse 或异常已有对象全部 fail closed。

## 3. Bootstrap

未来经独立 Owner machine authority 后，`ledger-bootstrap` 只能：

1. bind 已批准 `runtime_parent`；
2. 创建固定 ledger/probe roots；
3. 不改 ACL；
4. 记录 handle-observed ledger/probe object identity；
5. 记录两个根的 read-only security-policy digest；
6. 写固定、Git-external、非 Owner receipt 的 bootstrap evidence；
7. 对 exact evidence + exact object identity 支持幂等复核。

如果 crash 留下 partial state，或已有对象却缺少/不匹配 bootstrap evidence，禁止自动接管、删除、重建或修 ACL。

## 4. Synthetic inheritance probe

`ledger-probe` 仅在固定 probe root 下创建一个随机 nonce 对应的 synthetic claim。

它必须：

- 生成至少 128-bit 随机 nonce，proof 绑定 `probe_nonce_sha256`；
- production ledger 只做 read-only identity/policy/effective-rights 验证，绝不创建 probe claim；
- synthetic claim 必须拒绝 DELETE_CHILD / DELETE / WRITE_DAC / WRITE_OWNER；
- synthetic reservation/terminal files 必须拒绝 FILE_WRITE_DATA / DELETE / WRITE_DAC / WRITE_OWNER，同时允许 FILE_APPEND_DATA；
- unknown AccessCheck = failure；
- probe root policy digest 必须与 production ledger root policy digest 相同；
- 分别记录 `probe_object_sha256` 与 `ledger_object_sha256`。

probe 创建完成后 runner-side append-only handles 必须关闭，再进入 cleanup handle 交接。

## 5. Restricted cleanup helper

清理能力由两个东西共同定义：

1. `cleanup_capability`
2. 一个已经打开并绑定到**精确 synthetic probe object**的 handle

helper 本身：

- 没有 filesystem path 参数；
- 不允许按路径重新打开对象；
- 不允许递归清理；
- 不允许 sibling traversal；
- 不访问 source/cache/output/production ledger；
- 不改 ACL；
- 只允许删除 nonce 对应的 `reservation.json` 与 `terminal-v1-<nonce_sha256>.json`；
- 文件清空后只删除当前已绑定 probe directory；
- live object identity 必须与 cleanup capability 的 `probe_object_sha256` 相同。

`cleanup_identity_sha256` 是 restricted helper/capability contract 的 fingerprint，不是第二个 Windows 用户账户的 SID 要求。

父 orchestration 先打开只有 cleanup 所需 rights 的精确目录 handle，再将该 handle 标记为 inheritable；Windows helper 子进程通过 `STARTUPINFOEX handle_list` 只继承这个对象 handle。helper adoption 会重新验证 object identity 与 reparse 状态并清除 inheritable 标志；父进程在 helper 结束后关闭自己的 raw handle。

## 6. Runtime identity v3

新的 Real20 execution admission 只接受 runtime identity v3：

```text
schema_version = 3.0
runtime_observation
ledger_acl_probe v2
cleanup_capability
```

`ledger_acl_probe v2` 新增 `probe_nonce_sha256`。

完整 runtime identity canonical SHA-256 继续绑定 credential/anchor；live model/GPU probe 只与 `runtime_observation` 子对象比较。

cleanup capability 必须精确匹配同一 proof 的 probe nonce、probe object 和 cleanup helper identity。

v2 只保留历史/低层 evidence compatibility，不能满足 public Real20 admission。

## 7. Live attestation

public admission 的 module-owned live attestor 对已经绑定的 production ledger handle 做 read-only 检查，并返回：

- current runner token identity fingerprint；
- live ledger security-policy digest；
- live ledger object identity。

它不读照片、不运行模型、不创建 reservation、不改 ACL。

这些 live 值必须与 runtime identity v3 proof 精确匹配，然后才允许继续其他 admission checks。public `run_real20()` 不暴露 caller-controlled attestor override。

## 8. Pre-reservation ordering

必须保持：

```text
strict fixed controls
-> bound production ledger
-> live attestation
-> runtime identity v3 + cleanup-capability binding
-> ledger mutation-denial checks
-> existing data/review/quality/source/cache gates
-> runtime_observation check
-> final revalidation on same ledger object
-> _reservation()
```

以下任一异常时：`_reservation()` call count = 0、backend construction count = 0、source-image open count = 0。

异常包括 missing/stale proof、cleanup failed、nonce/object/helper mismatch、runner/policy/ledger-object mismatch、live attestation unavailable、credential/control drift。

## 9. 资源与权限边界

本 code-only 阶段明确不做：Windows runtime bootstrap execution、native probe、cleanup helper real-handle execution、ACL change/repair、credential/anchor issuance、Real20 reservation、model/CUDA、real photo/EXIF、SQLite、cache mutation、main merge/tag/release。

仓库中仅提供 `DRAFT_NOT_AUTHORIZED` Owner authority 模板。未来 approved authority 必须作为 `<runtime_parent>/owner-approvals/real20_control_plane_authority.json` 的 Git-external fixed control materialize，并绑定 exact reviewed candidate commit/tree/source-manifest 与 runtime-configuration digest；它不能作为 Git 内文件制造 candidate 自引用。只有该外部 authority 通过 bound-control 读取并精确匹配后，machine execution 才可进入。

## 10. 通过条件

代码层必须完成 fixed-path trust derivation、bootstrap exact-object evidence、nonce-bound synthetic probe、pre-opened-handle-only helper、runtime identity v3、live attestation、strict schemas、synthetic positive/negative tests、Windows-native primitive tests、reservation/backend/image zero-call regressions、manifest/handoff 完整。

机器层仍由后续 Owner gate 单独验收；code PASS 不等于 resource PASS、Real20 PASS 或 N2B2 unlock。
