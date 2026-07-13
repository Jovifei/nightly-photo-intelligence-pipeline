# N0 文件级实施顺序

这是实施建议，不扩大任务合同。

## Step 0：完整性与仓库边界

- 运行 handoff verifier；
- 确认不在 App 仓库；
- `git init`；
- 检查 `.gitignore`；
- 建立报告文件。

## Step 1：`pyproject.toml`

- Python `>=3.11,<3.13`；
- package name 可用 `nightly-photo-intelligence-pipeline`；
- console script `npi=nightly_photo_intelligence_pipeline.cli:app`；
- runtime：Typer、Pydantic（按可用环境锁定）；
- dev：pytest、Ruff、mypy；
- 配置严格 typecheck/lint；
- 不添加模型依赖。

## Step 2：Domain

- `AssetState` enum；
- transition map；
- typed errors；
- stable exit codes；
- config models；
- authorization reader。

先测无效迁移和 Gate 拒绝。

## Step 3：Source guard + Hash

- canonical path；
- overlap；
- symlink escape；
- binary read；
- pre/post fingerprint；
- streamed SHA-256；
- perceptual hash protocol/result type。

先测 fixture 不变和 duplicate。

## Step 4：SQLite

- 创建 v0 schema；
- foreign keys；
- context-managed transactions；
- append transition；
- empty status；
- interruption marker/reopen；
- 不在 dry-run 写 assets。

## Step 5：CLI

- `preflight`；
- `status`；
- `ingest --dry-run`；
- 非 dry-run gate error；
- 文本脱敏；
- timeout/异常到 exit code。

## Step 6：证据

- 统一 quality；
- fixture hashes；
- schema valid/invalid；
- interrupted recovery；
- git sensitive scan；
- 报告；
- 根据真实环境更新 N1 plan。

## Step 7：Commit 与停止

- `git diff --check`；
- 确认 `PROJECT_STATE` 未解锁；
- 一个 commit；
- 输出停止消息；
- 不执行任何后续命令。
