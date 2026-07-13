# 模型候选登记摘要

所有状态：`RESEARCH_ONLY / DOWNLOAD_NOT_AUTHORIZED`。

## Pose

### MMPose RTMPose / RTMW family

评估：

- 人体/whole-body keypoint 集；
- 左右和镜像；
- 遮挡/裁切；
- 许可与训练数据；
- 12GB VRAM；
- 输出坐标与可视化；
- Windows/WSL/Docker 维护性。

不得仅因为官方支持 133 keypoints 就假设收藏图可用率。

## Segmentation

### Lightweight person segmentation

先定义质量阈值，再选择实现。目标是大多数图低成本完成。

### SAM 2

只作为精细升级候选。代码许可和具体 checkpoint 条款分别核验。不得 N0/N1 下载。

## VLM

### Qwen3-VL 2B class

仅作为本地小模型 Benchmark 候选。需验证：

- exact model card/revision/license；
- BF16/量化来源；
- 12GB 峰值；
- 视觉 token/像素预算；
- 中文结构化输出；
- 受限断言；
- JSON 修复率；
- 离线 telemetry。

社区量化需单独供应链审查。

## Embedding

尚不选型。先建立 20–50 个检索查询及相关性标注，再比较图像/多模态 embedding。
