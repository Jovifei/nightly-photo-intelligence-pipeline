# 数据 Manifest 合同

## 为什么需要 manifest

目录权限只说明“技术上可读”，不说明“本次被授权处理”。每个数据 Gate 必须列出精确资产清单。

## 字段

- manifest id/version；
- data gate；
- source root fingerprint（不暴露绝对路径）；
- 每个文件的 source-relative path 或 opaque local id；
- expected SHA-256；
- size；
- media type；
- Owner approval reference；
- 最大资产数；
- 有效期；
- 允许阶段；
- 明确排除项。

## 规则

- `--limit` 不能把目录中未列项的文件纳入；
- manifest 的 real relative path 属于本地敏感配置，默认不提交；
- G0 fixture manifest 可提交；
- 文件 Hash 不匹配时停止该资产并报告；
- manifest 更新产生新版本和批准；
- 不允许 glob；
- 不允许“整个照片目录”作为一行；
- symlink 不被 manifest 授权；
- Gate 完成后 manifest 保留以便审计。

Schema：`schemas/data_gate_manifest_v1.schema.json`。
