# ADR-0004：显式阶段与单 GPU 重模型

状态：Accepted

Pose、分割、VLM、Embedding 分阶段顺序运行，每次只常驻一个重模型。重模型优先独立进程/容器，阶段后释放 GPU。

原因：12GB VRAM、可审计、失败隔离、便于 Benchmark。
