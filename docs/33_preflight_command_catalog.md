# N0 Preflight 命令目录

以下是候选只读命令；实现必须根据平台存在性安全调用并脱敏。

```text
python --version
python -c "import sys; print(sys.executable); print(sys.version)"
git --version
uname -a
cat /etc/os-release
df -h
docker version
docker compose version
nvidia-smi
```

注意：

- `docker version` 可能访问 daemon，但不修改；
- 不运行会 pull 镜像的 `docker run`；
- 不执行 `pip install`、`apt`、`wsl --update`、驱动工具；
- 不收集完整环境变量；
- 不打印 home、用户名、主机名、GPU serial；
- 每条命令要有 timeout；
- 不存在或权限不足时报告，不升级权限。
