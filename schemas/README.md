# JSON Schema

- 采用 JSON Schema Draft 2020-12；
- 所有跨仓库合同使用明确 major/minor；
- production export 必须使用 bundled schema copies；
- `additionalProperties: false` 用于核心合同；
- 路径必须相对且禁止 `..`；
- Schema 结构验证之外，还需要跨字段业务验证：
  - `item_count == len(items)`；
  - item 文件 SHA 与 manifest 一致；
  - item review 必须 APPROVED；
  - evidence refs 必须存在；
  - Pose producer 不得是 VLM；
  - Bundle 不得含绝对路径或原图；
  - item 自身 Hash 计算时需采用定义好的 canonicalization，不能直接自引用造成循环。

`output_hashes.item_json_sha256` 在草稿示例可为 null。正式导出建议将 item hash 放在 Bundle manifest 中，并避免在被哈希 JSON 内自引用。
