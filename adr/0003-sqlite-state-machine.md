# ADR-0003：SQLite 持久状态机

状态：Accepted

首版使用 SQLite 记录资产、阶段运行、迁移、错误、版本和输出 Hash，不使用 Kafka/Celery/云数据库。

原因：单机单用户、数百图片、事务和恢复需求明确；降低运维与权限面。
