# 人工审核工作流

## 原则

自动模型不能自我批准。只有 Owner 或明确指定的人类 Reviewer 可将条目设为 APPROVED。

## Review Card

静态 HTML 第一版包含：

- sanitized asset id；
- 缩略图；
- skeleton/contour（存在时）；
- observed facts；
- photographic interpretation；
- safe/narrative/dynamic；
- standard/dramatic/Plan B/technical；
- uncertainties 和模型冲突；
- provenance；
- Schema 结果；
- 审核动作说明。

Review Card 默认不嵌入原图；可使用本地相对缩略图。生成目录 Git ignore。

## 状态

```text
PENDING_REVIEW
APPROVED
REJECTED
CHANGES_REQUESTED
```

与资产状态 `NEEDS_REVIEW/APPROVED` 映射，但审核历史独立保存。

## 修改

- 自动原始输出不可覆盖；
- 人工修改保存 JSON Patch 或结构化 before/after；
- 记录 Reviewer、时间、理由；
- 修改后重新验证；
- 修改模型/Prompt 不自动使旧批准失效，但 release 需标明版本；
- 关键事实修改可触发关联解释/提示重新审核。

## 导出

Exporter 在 DB 查询、Item 文件和审核记录三处交叉验证 APPROVED。任何不一致 fail closed。
