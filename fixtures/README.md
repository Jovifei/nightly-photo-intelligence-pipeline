# 三张 N0 合成 fixture

- `fixture_a_corridor_abstract.png`
- `fixture_a_exact_copy.png`：与 A 字节完全相同，用于 exact duplicate
- `fixture_b_tonal_abstract.png`

它们是程序生成的几何图，没有真实人物、地点、EXIF 或第三方图片。只用于：

- 只读源保护；
- SHA-256；
- 感知 Hash 接口；
- exact duplicate；
- dry-run 幂等；
- 状态/恢复/日志/Schema 测试。

它们不能用于评估 Pose、分割、VLM 或摄影建议质量。解压工具可能不保留只读权限，因此 N0 测试必须证明程序本身没有写接口，而不能只依赖文件 mode。
