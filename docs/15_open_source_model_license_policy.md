# 开源代码、模型、权重和数据许可政策

## 原则

“开源仓库”不等于“所有权重和训练数据均可自由用于本项目”。必须分别登记：

- 代码仓库许可；
- 模型架构许可；
- 具体 checkpoint/weight 许可；
- 训练数据已知许可/限制；
- 推理输出使用限制；
- 商业/再分发限制；
- NOTICE/归属要求；
- exact revision 与文件 Hash。

## 采用前 Gate

候选要进入正式流程，必须：

1. 来源为官方仓库/模型卡或可验证维护者；
2. exact revision 固定；
3. 下载文件清单和 SHA-256 固定；
4. 许可审查记录完整；
5. 12GB 硬件 Benchmark 通过；
6. 数据质量 Benchmark 通过；
7. Owner 签署下载和采用批准；
8. SBOM/NOTICE 更新；
9. 回滚方式明确。

## 不能做的事

- 从非官方网盘下载未知量化权重；
- 因 Hugging Face 页面可见就推断可用许可；
- 只记录库版本，不记录模型 revision；
- 把数据集许可继承为权重许可；
- 将收藏图用于训练而没有新的明确批准；
- 将第三方原图打包到 App；
- 让智能体做最终法律意见。

## 当前候选

见 `model_registry/candidates.yaml`。所有候选状态均为 `RESEARCH_ONLY / DOWNLOAD_NOT_AUTHORIZED`。
