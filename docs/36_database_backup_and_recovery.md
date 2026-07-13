# SQLite 备份与恢复

## N0

只验证创建、事务回滚、关闭/重开和模拟中断。N0 不处理真实数据。

## N1+

- runtime DB 不进 Git；
- 在已知一致点使用 SQLite backup API，不直接复制活跃 DB/WAL；
- 定期 `PRAGMA integrity_check`；
- schema migration 前备份；
- 备份也属于敏感数据；
- 恢复到新路径后验证 schema、counts、transitions 和输出 Hash；
- 不在源照片目录保存 DB；
- DB 损坏时停止新任务，不根据文件目录猜造成功状态。

## 状态与文件对账

DB 说成功但产物缺失/Hash 不符：该 stage run 无效，不能跳过。  
产物存在但 DB 未提交：视为 orphan temp/候选，不能自动宣布成功。
