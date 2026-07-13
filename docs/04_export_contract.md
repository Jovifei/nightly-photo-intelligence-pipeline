# Photo Intelligence Bundle v1 导出合同

## 目的

Bundle 是 Pipeline 与 App 的唯一 MVP 集成面。它是不可变、可校验、可回滚的 release，不是共享目录的临时快照。

## 目录

```text
photo-intelligence-bundle-v1_<release_id>/
├── bundle.json
├── CHECKSUMS.sha256
├── RELEASE_NOTES.md
├── schemas/
│   ├── photo_intelligence_bundle_v1.schema.json
│   └── photo_intelligence_item_v1.schema.json
├── items/
│   └── <asset_id>.json
└── assets/
    └── <asset_id>/
        ├── thumbnail.jpg            # 可选派生物
        ├── skeleton_overlay.png     # 可选
        ├── contour_overlay.png      # 可选
        └── person_cutout.png        # 可选
```

原图默认不进入 Bundle。所有路径必须相对 Bundle 根目录。

## 进入条件

每个条目必须同时满足：

- `review.status == "APPROVED"`；
- Item Schema 有效；
- 所有引用资产存在；
- 文件 Hash 与 manifest 一致；
- 模型、Prompt、Schema、代码和许可来源可追溯；
- 无本地绝对路径；
- 无 Token、原图目录、数据库路径；
- 不包含未经许可的原图复制品。

## App 消费规则

App 必须：

1. 先验证 `bundle.json`；
2. 核对 `CHECKSUMS.sha256`；
3. 拒绝未知 major schema；
4. 原子导入；
5. 保留上一 release 以便回滚；
6. 不访问 Pipeline DB；
7. 不推断未提供字段。

## 版本

- `1.x`：向后兼容字段扩展；
- `2.0`：破坏性语义或结构改变；
- Schema 与 Prompt 版本独立；
- release_id 建议使用 `npi-YYYYMMDD-<short_sha>-<sequence>`。

## N0 范围

N0 不实现生产导出，只需：

- 保留 Schema 和示例可验证；
- `npi status` 能报告 schema version；
- 不创建假 APPROVED 数据声称生产结果。
