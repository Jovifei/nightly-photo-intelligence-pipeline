# Prompt 版本策略

- Draft：`0.x-draft`，不可生产；
- 首个生产：`1.0.0`；
- 文案微调但语义兼容：patch；
- 输出策略/含义变化：minor；
- 数据层或受限断言改变：major；
- 每次 run 记录 prompt file SHA-256；
- 旧输出不被覆盖；
- Prompt 升级需要 regression set；
- 修复 Prompt 独立版本；
- Reviewer 必须看到 Prompt diff。
