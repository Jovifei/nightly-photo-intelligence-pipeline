# App 集成边界

## App 只消费 release

App 不能感知：

- SQLite 表；
- Pipeline runtime；
- 原图路径；
- 模型容器；
- 阶段内部状态；
- 未审核草稿。

它只认识 `Photo Intelligence Bundle v1`。

## Fixture-first

`examples/app_fixture_bundle_v1/` 提供最小合同样例。App 可基于 fixture 实现：

- Bundle 校验；
- 列表/检索 UI；
- Pose 模板展示；
- 导演提示；
- release 回滚。

Fixture 是合同演示，不是生产摄影结论。

## 将来反馈

喜欢、跳过、人工修正和 Plan B 使用结果属于下一版单独合同。MVP 不允许 App 直接写回 Pipeline DB。

## 兼容性

- App 声明支持的 schema major；
- Pipeline release notes 标明新增/废弃字段；
- 破坏性改变使用新 major；
- 未知字段按 Schema policy 处理；
- 不用仓库 commit 作为唯一 release identity。
