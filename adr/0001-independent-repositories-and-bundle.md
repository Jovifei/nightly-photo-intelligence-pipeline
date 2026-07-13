# ADR-0001：独立仓库与 Bundle 集成

状态：Accepted  
日期：2026-07-12

## 决策

Pipeline 与 App 是两个独立 Git 仓库，不共享数据库，不互相导入业务源码。MVP 通过 approved-only `Photo Intelligence Bundle v1` 单向集成。

## 理由

允许独立开发、fixture-first、离线运行、版本回滚，并防止 App 对数据工厂内部实现形成耦合。
