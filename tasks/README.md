# 阶段与数据 Gate 任务合同

- `phase_n0_environment_scaffold.yaml` 与 `phase_n1_ingest_state_machine.yaml` 是已完成的工程阶段合同。
- `gate_g1_calibration_20.yaml` 是当前唯一 `AUTHORIZED` 的数据 Gate 合同。
- N2-N8 与 G2-G3 均保持 `LOCKED`；G1 不授权任何 N2 能力。
- YAML 中列出的模型名不构成下载授权。
- Owner 批准必须通过 `approvals/` 中范围明确、未过期且与 `PROJECT_STATE.json` 一致的记录表达。
