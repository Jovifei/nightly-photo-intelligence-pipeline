# 依赖与供应链策略

## N0

- 不联网安装；
- 先盘点已有 Python/tooling；
- 若需要建立可复现环境，提出 wheel/lock 计划并由 Owner 决定；
- 不运行任意 curl|bash；
- 不添加 Git URL 浮动依赖；
- 不使用 `latest` Docker tag；
- 不拉大型基础镜像。

## 采用规则

- Python 依赖 pin 到兼容版本并生成 hash lock；
- Docker 镜像 pin digest；
- 模型 pin exact revision 和文件 SHA；
- 记录 transitive license/SBOM；
- 禁用/审查 telemetry；
- 依赖更新单独 commit 与 regression；
- 安全修复不能绕过模型/数据 Gate。

## 缓存

pip/uv/Hugging Face/Torch/Triton 缓存都在 runtime/cache，Git ignore。缓存命中不等于权重获得授权。
