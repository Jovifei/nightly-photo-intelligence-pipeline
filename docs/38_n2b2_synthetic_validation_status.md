# N2B2 合成验证状态与审查边界

## 结论

当前 review candidate 已完成 N2B2 的 synthetic-only 模型栈验证：三张 S3 smoke
fixture、固定二十张 S20 fixture、CUDA 视觉链、Qwen 事实绑定、synthetic validation
bundle、checkpoint 和 no-op resume 均有本地运行证据。它不是生产 N2B2 完成，也不构成
真实照片或 Real20 授权。

```text
runtime-source candidate: cbd34f6d5ebd1cdfb7c4e833e160ad33c8775778
candidate parent: c1008132654d32e7ac6a2032eb5d3a2c7e07cdb6
runtime status: N2B2_SYNTHETIC_MODEL_STACK_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW
production N2B2: LOCKED
Real20: NOT_PERFORMED
production Bundle: NOT_CREATED
```

## 验证范围

| 层 | 实际验证 | 结论 |
|---|---|---|
| Pose | Keypoint R-CNN，CUDA `cuda:0` | S3 A/B/C 人数为 `1/2/0`；正例有 17 点 keypoint group |
| Segmentation | LRASPP 与 DeepLabV3 comparator，VOC `person` 类 | 正例有 person mask；negative control 两个 ratio 均为 0 |
| 事实合同 | 两轮完整视觉链 | 20 case canonical facts bytes 与 digest 均一致 |
| Qwen | qwen3.5:9b / Q4_K_M，只消费不可变 facts | schema、digest echo、合法 fact IDs 通过；forbidden fields 为 0 |
| S20 输出 | 20 synthetic validation bundles | strict/observation/negative/unsupported = `10/8/1/1` |
| 恢复 | COMPLETE checkpoint 的 no-op resume | 149 个 release 文件前后 hash 不变，未重新加载模型 |

运行时 evidence 位于 Git 外、内容校验的 `EXTERNAL_RUNTIME_WORK` 别名下。Git 只保留
schema、门禁、测试、脱敏报告和任务合同；不会跟踪 fixture 图片、模型、Ollama blob、
原始日志或任何真实来源数据。

## 资源与质量证据

- GPU：RTX 4070 SUPER；最终 S20 v2 峰值 `11338 MiB`，低于 `11500 MiB` 上限；
  卸载后 GPU 使用量回落。
- 模型生命周期：Pose、LRASPP、DeepLab 串行 load/infer/unload；Qwen 阶段前无
  TorchVision resident role，Qwen 完成后显式卸载。
- 本地质量：`pytest 540 passed`、Ruff check/format PASS、mypy PASS（68 source
  files）、`tools/run_quality.py` 为 `7 PASS / 0 FAIL`、preflight `16/0`、handoff
  `7/0`、sensitive scan `0`。
- 所有硬计数为 0：真实照片、EXIF、G1 source、SQLite ingest、App 写入、Obsidian
  runtime 写入和模型下载。

## 授权与停止条件

本 candidate 使用 N2B1P completion record 和 Owner synthetic-only receipt 绑定运行时
门禁。运行前会验证 completion hash、receipt scope、所有禁止边界和
`PROJECT_STATE.phase_status.N2B2 == LOCKED`。因此该授权不会解除生产锁。

以下动作仍然禁止：真实照片或 EXIF 读取、G1 source、SQLite ingest、Real20、生产
Bundle、App、模型下载/替换、推送到生产 main、G1 renewal 与全量夜间流水线。

## 下一门

下一步是对精确 candidate SHA 的独立外部 Review。Review PASS 后仍需 Owner 的下一次
明确决策，才可建立 Real20 control-plane 的后续任务。synthetic PASS 不能自动推进到
真实照片。
