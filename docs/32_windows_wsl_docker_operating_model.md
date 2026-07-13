# Windows、WSL2 与 Docker 运行模型

## 原则

Windows 是主机，WSL2 是主要开发/运行环境，Docker 是后续模型阶段隔离方式。N0 只检查，不修改。

## 路径建议待实测

- 源照片可能位于 Windows 文件系统；
- Python 代码和 SQLite runtime 倾向 WSL ext4 以获得一致锁/性能；
- Docker bind mount source 为只读；
- 具体选择由 N0 文件系统报告和 N1 锁测试决定。

## Preflight 事实与推断分开

事实示例：

- 命令存在/不存在；
- 版本字符串；
- WSL distro；
- Docker daemon 可达；
- `nvidia-smi` 输出；
- 磁盘可用。

不能根据版本字符串直接宣布 GPU 容器可用；没有本地已批准测试镜像时写 `NOT_VERIFIED`。

## 禁止自动修复

- 不运行驱动安装；
- 不运行 WSL update/config；
- 不修改 Docker Desktop setting；
- 不启用 systemd；
- 不加入 docker group；
- 不拉 CUDA 镜像；
- 不改 Windows ACL。

报告给 Owner，再决定。
