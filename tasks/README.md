# 阶段与数据 Gate 任务合同

- `phase_n0_environment_scaffold.yaml` 与 `phase_n1_ingest_state_machine.yaml` 是已完成的工程阶段合同。
- `phase_n2b0_7_gpu_native_qualification.yaml` 是当前唯一可执行的工程阶段合同；它只允许官方来源/许可/环境元数据审查，不允许真实照片、模型 payload、安装或推理。
- N2-N8 与 G2-G3 均保持 `LOCKED`；G1 不授权任何 N2 能力。
- YAML 中列出的模型名不构成下载授权。
- Owner 批准必须通过 `approvals/` 中范围明确、未过期且与 `PROJECT_STATE.json` 一致的记录表达。
