# 两个独立工程的关系

## 产品工程

`ai-photography-director-app` 面向用户，负责：

- 手机相机；
- 左中右交互；
- 实时人体 Pose；
- 骨架、轮廓、参考图 Overlay；
- 实时构图与姿势指导；
- 拍照和结果展示。

## 数据工厂

`nightly-photo-intelligence-pipeline` 离线运行，负责：

- 照片导入与去重；
- 图片质量/可处理性分类；
- 离线 Pose、角度、轮廓、分割；
- 场景、光线、构图和影调事实；
- 背景摄影价值；
- 三类故事候选；
- 标准引导、戏感、Plan B、摄影师技术提示；
- 人工审核；
- 导出 App 可消费知识包。

## 强制隔离

| 边界 | 规则 |
|---|---|
| Git | 两个独立仓库 |
| 数据库 | 不共享，不直连 |
| 源码 | 不互相导入业务源码 |
| 运行 | App 不依赖 Pipeline 在线运行 |
| 集成 | 只通过版本化 Bundle 文件 |
| 权限 | Pipeline 不获得 App 签名或发布权限 |
| 反馈 | MVP 无回流；后续另立合同 |

## MVP 单向合同

```text
Pipeline
  └─ 仅选择 review.status == APPROVED
     └─ JSON Schema 校验
        └─ 生成 Photo Intelligence Bundle v1
           └─ App 验证 Schema + Hash 后只读导入
```

App 可以使用 `examples/app_fixture_bundle_v1/` 独立开发。Pipeline 可以只生成 HTML Review Card，在 App 未完成时仍然闭环。

## 明确禁止的耦合

- App 直接查询 Pipeline SQLite；
- Pipeline 写入 App 数据库；
- 共享 Python/Swift 业务模型源码；
- 用绝对文件路径作为跨仓库接口；
- App 自动消费未审核条目；
- Bundle Schema 不变却悄悄改变语义。
