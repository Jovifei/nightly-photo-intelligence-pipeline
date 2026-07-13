# OpenClaw 未来安全边界

OpenClaw 不是安全沙箱。提示词约束不能替代系统权限。

## 未来部署结构

```text
OpenClaw
  └─ execute one allowlisted wrapper
       └─ validates phase/data approval
          └─ invokes npi fixed profile
```

## 必须拒绝

- `/var/run/docker.sock`；
- 原图 mount；
- 模型下载凭据；
- SSH keys；
- Git remote write；
- admin/sudo；
- 任意 Shell；
- 动态路径参数；
- 用户提供的命令片段；
- 读取未脱敏数据库。

## 允许的只读信息

- `npi status --format json` 的脱敏视图；
- `reports/public/latest_summary.json`；
- 固定 exit code；
- 预定义告警文本。

## 固定命令

未来可由 Owner 批准类似：

```text
/usr/local/bin/npi-nightly-approved-wrapper
```

包装器内部校验批准文件、manifest、磁盘、锁和环境。OpenClaw 不直接调用 `docker compose`，更不能控制 socket。

## 激活负向测试

必须证明 OpenClaw：

- 不能列出原图；
- 不能读任意文件；
- 不能写 Git；
- 不能调用未白名单命令；
- 不能改变 profile/limit/input；
- 不能访问 Token；
- 不能提升权限；
- 不能绕过停止 Gate。

仅完成 N8 不自动激活，还需要独立 Owner 签署。
