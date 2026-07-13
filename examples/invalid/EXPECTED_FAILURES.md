# 预期非法示例

| 文件 | 必须失败原因 |
|---|---|
| `item_absolute_path.json` | `sanitized_name` 含路径分隔符/绝对路径 |
| `item_auto_approved.json` | APPROVED 但 `approved_by_human=false` |
| `item_pose_from_vlm.json` | Pose producer enum 不允许 VLM |

验证器不能只报告“失败”，应尽量定位规则。
