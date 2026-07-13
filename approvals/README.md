# 批准记录

本目录中的模板默认 `status: NOT_APPROVED`，不构成授权。

有效批准必须：

- 文件名不含 `TEMPLATE`；
- `status: APPROVED`；
- Owner 身份明确；
- UTC 时间；
- 范围、阶段、数据 Gate、动作和有效期明确；
- 引用待批准 manifest/模型文件 Hash；
- 不使用通配符扩大范围；
- 未被后续撤销；
- 与 `PROJECT_STATE.json` 一致。

智能体不能代签、复制签名、从聊天猜测或自动生成 APPROVED 文件。
