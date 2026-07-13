# 验收测试目录

## N0

| ID | 测试 |
|---|---|
| AT-N0-HO-01 | 交付包 manifest 与关键文件一致 |
| AT-N0-ENV-01 | Preflight 只读且不改系统 |
| AT-N0-CLI-01 | 三个 N0 命令帮助与退出码 |
| AT-N0-HASH-01 | SHA-256 与固定 manifest 一致 |
| AT-N0-HASH-02 | 感知 Hash 接口输出含算法/version |
| AT-N0-IDEM-01 | 两次 dry-run 同序同结果且 DB 零变化 |
| AT-N0-DB-01 | SQLite schema/reopen |
| AT-N0-STATE-01 | 无效迁移被拒绝 |
| AT-N0-REC-01 | 模拟中断可识别恢复 |
| AT-N0-SCHEMA-01 | 合法示例通过 |
| AT-N0-SCHEMA-02 | 三个非法示例按预期失败 |
| AT-N0-SEC-01 | source/runtime 重叠拒绝 |
| AT-N0-SEC-02 | symlink escape 拒绝 |
| AT-N0-SEC-03 | fixture pre/post 完整性相同 |
| AT-N0-SEC-04 | Git 敏感/大文件扫描 |
| AT-N0-LOG-01 | 日志路径脱敏 |
| AT-N0-GATE-01 | 非 dry-run ingest 返回 gate error |
| AT-N0-GATE-02 | N1–N8 全部锁定 |
| AT-N0-GIT-01 | 一个 isolated commit，无敏感文件 |

## 后续测试类别

- N1：任务领取、lease、DB 故障、manifest 越权；
- N2：关键点质量、左右/镜像、分割轮廓；
- N3：事实准确、受限断言、证据引用；
- N4：三类候选、Plan B 简化、可说出口；
- N5：人工批准、防伪、Bundle integrity；
- N6：100 张稳定性、恢复、性能、主观评分；
- N7：App schema compatibility；
- N8：固定调度、权限负向、全量 readiness。

测试实现不得用“存在函数”替代行为验证。
