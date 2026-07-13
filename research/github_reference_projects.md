# GitHub 参考工程与复用边界

## 1. PyPA Sample Project

仓库：`pypa/sampleproject`

复用：

- `pyproject.toml` 为中心；
- package metadata 与测试分离；
- `src/` layout；
- 标准入口点。

不复用：

- 具体依赖版本；
- 与本项目隐私无关的发布流程；
- 自动发布到 PyPI。

## 2. Cookiecutter Data Science

仓库：`drivendataorg/cookiecutter-data-science`

复用：

- 输入、中间数据、模型、报告职责分开；
- 研究结果与生产代码分开；
- 可读目录命名。

适配：

- 原始收藏不进入 `data/raw`；它始终是仓库外只读 source；
- 派生数据全部 Git ignore；
- 不默认使用云存储/DVC。

## 3. Kedro

仓库：`kedro-org/kedro`

复用：

- stage/node 有显式输入输出；
- 产物可重建；
- pipeline 分层；
- 参数/数据集与代码分离。

不采用 Kedro 运行时：

- 当前规模小；
- SQLite 已提供状态与恢复；
- 减少插件、配置和升级面；
- 保持 CLI 行为清晰。

## 4. Typer / Pydantic / pytest / Ruff / mypy

复用成熟工具，不自行造 CLI parser、Schema model、测试框架、lint 或 type checker。

采用前仍需：

- N0 锁定兼容版本；
- 生成 lock；
- 记录许可；
- 离线/可复现安装方案；
- 不让工具 telemetry 上传。

## 5. MMPose / SAM 2 / Qwen3-VL

只借鉴官方 adapter/API 与模型卡，不直接复制未经审查的 demo 到生产。任何 example notebook 需拆出：

- 输入边界；
- 显存生命周期；
- 权重 revision；
- 输出 Schema；
- 错误处理；
- 许可；
- 可重现参数。

## 6. 明确不照搬的仓库类型

- “一键 AI 图片分析”且无状态恢复；
- 默认上传第三方 API；
- 将结果直接写回源目录；
- 下载最新权重而不 pin；
- 把 UI、模型、数据库耦合在一个脚本；
- 只用自由文本输出；
- 用 Docker socket 控制任意容器；
- 自动删除 duplicate。

## 7. 代码复制政策

优先通过依赖使用，不复制源码。若必须复制少量代码：

- 记录原文件/commit/license；
- 保留版权头；
- 写入 `NOTICE`;
- 增加本项目测试；
- 不复制模型权重或训练数据；
- Reviewer 审查。
