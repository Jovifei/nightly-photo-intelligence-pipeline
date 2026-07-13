# 仓库与运行目录布局

## 仓库布局原则

采用 PyPA `src/` 布局，测试与包分离；借鉴 Cookiecutter Data Science 的输入/中间/输出分层思想，但原始收藏不复制进仓库；借鉴 Kedro 的显式节点/阶段和可重跑思想，但不引入 Kedro 运行时。

## N0 后建议仓库

```text
nightly-photo-intelligence-pipeline/
├── pyproject.toml
├── src/nightly_photo_intelligence_pipeline/
├── tests/
├── docs/
├── tasks/
├── schemas/
├── fixtures/
├── config/
├── reports/
├── tools/
├── AGENTS.md
├── CLAUDE.md
└── MASTER_EXECUTION_CONTRACT.md
```

## 运行目录

由本地配置给出，不得硬编码：

```text
source_root: <READ_ONLY_PHOTO_DIR>
runtime_root: <NPI_RUNTIME_ROOT>
```

运行目录可以保存数据库、日志、派生图、缓存和权重，但全部 Git ignore。

## 路径规则

- 配置中支持环境变量或本地忽略文件；
- 数据库内绝对源路径属于本地敏感数据；
- 导出中只出现 sanitized name 或 asset_id；
- 日志默认显示 `<SOURCE_ROOT>/relative/path` 或 Hash 前缀；
- Windows 与 WSL 路径转换必须显式，不猜测；
- 不在代码中写 `/mnt/c/Users/<name>/...`。
