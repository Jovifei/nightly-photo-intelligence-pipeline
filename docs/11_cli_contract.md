# CLI 合同

## 最终命令

```text
npi preflight
npi ingest --input <READ_ONLY_PHOTO_DIR>
npi run --profile calibration --limit 20
npi run --profile pilot --limit 100
npi run --profile nightly
npi resume
npi status
npi report --latest
npi export --release-id <ID>
```

## N0 实现范围

### `npi preflight`

只读检查并输出：

- Python、OS/WSL、Git；
- Docker/Compose 是否可查询；
- `nvidia-smi` 是否可查询；
- 工作目录可写性；
- fixture 目录只读策略；
- runtime/source 是否隔离；
- Schema 和 handoff 版本；
- 缺失项标为 `NOT_AVAILABLE`，不自动修复。

禁止 pull 镜像、安装驱动、改配置。

### `npi status`

N0 输出：

- DB 是否存在；
- DB schema version；
- 各状态计数；
- 最近阶段运行；
- 当前授权 phase/data gate；
- 不泄露绝对源路径。

空数据库必须正常返回，不应报错。

### `npi ingest --input <DIR> --dry-run`

- 仅允许 `--dry-run` 在 N0；
- 枚举支持格式；
- 流式 SHA-256；
- 调用版本化感知 Hash 接口；
- 显示重复候选；
- 不写 assets、stage_runs 或 outputs；
- 不改源；
- 拒绝 symlink escape 和源/输出重叠；
- 日志脱敏；
- 相同输入顺序和结果稳定。

没有 `--dry-run` 时以明确错误退出，说明 N1 未授权。

## 退出码

| Code | 意义 |
|---:|---|
| 0 | 成功 |
| 2 | CLI 参数错误 |
| 3 | Preflight 不满足，但未做修改 |
| 4 | 安全边界拒绝 |
| 5 | Schema/配置错误 |
| 6 | 状态库错误 |
| 7 | 任务部分失败 |
| 8 | 当前 Gate 未授权 |
| 9 | 完整性失败 |
| 10 | 未预期内部错误 |

## 输出

人类默认文本；未来可支持 `--format json`。错误输出必须含稳定 `error_code`，不得含 Token 或完整个人路径。
