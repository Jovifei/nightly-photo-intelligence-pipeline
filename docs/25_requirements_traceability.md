# 需求追踪矩阵

完整机器映射见 `config/requirements_traceability.json`。

| 需求 | 设计 | 首次阶段 | 验收 |
|---|---|---|---|
| FR-ING-001 | 只读 dry-run | N0 | AT-N0-ING-01 |
| FR-ING-002 | 流式 SHA-256 | N0 | AT-N0-HASH-01 |
| FR-ING-003 | 感知 Hash 接口 | N0 | AT-N0-HASH-02 |
| FR-ING-005/006 | source guard | N0 | AT-N0-SEC-01..04 |
| FR-ING-007 | 幂等 | N0/N1 | AT-N0-IDEM-01 |
| FR-STA-001/002 | 状态/历史 | N0 | AT-N0-DB-01 |
| FR-STA-004 | 恢复 | N0/N1 | AT-N0-REC-01 |
| FR-STA-005 | 迁移守卫 | N0 | AT-N0-STATE-01 |
| FR-ANA-002/009 | 专业 Pose 来源 | N2 | AT-N2-POSE-* |
| FR-ANA-004/005 | facts/解释证据 | N3 | AT-N3-FACT-* |
| FR-ANA-006/007 | 三故事/四提示 | N4 | AT-N4-PROMPT-* |
| FR-REV-001..003 | 人工审核 | N5 | AT-N5-REV-* |
| FR-EXP-001..005 | Bundle | N5/N7 | AT-N5-EXP-* |
| NFR-SEC-001..003 | 本地/最小权限 | 全程 | SEC-* |
| NFR-REL-001..003 | 幂等/恢复 | N0/N1 | REL-* |
| NFR-AUD-001/002 | provenance/hash | N0 起 | AUD-* |
| NFR-PER-001 | 单重模型 | N2 起 | PERF-* |
