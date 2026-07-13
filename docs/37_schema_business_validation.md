# Schema 之外的业务校验

JSON Schema 负责结构，但以下必须由业务 validator 检查：

- evidence refs 指向存在的 facts/pose/deterministic outputs；
- stories 正好 safe/narrative/dynamic 且语义不重复；
- Plan B 的难度/动作复杂度不高于标准方案；
- Pose producer 许可、revision 和 Hash 完整；
- VLM 没有生成关键点；
- APPROVED 历史含人类批准事件；
- output artifact 文件和 Hash 存在；
- Bundle item_count 与 items 一致；
- Bundle 只含 APPROVED；
- asset paths 相对且位于 release root；
- source Hash 与 manifest 一致；
- 受限断言词与精确数值有合法来源；
- 不确定性不能被导出器静默删除；
- release 内 schema copies 与声明版本一致。

业务校验也要版本化，并进入 provenance。
