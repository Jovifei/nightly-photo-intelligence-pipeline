# OpenClaw Security Boundary

## 最小能力

未来仅能：

- 在固定时间调用一个不可参数化的 wrapper；
- 读取脱敏 JSON 状态；
- 发送预定义异常/日报。

## 系统级拒绝

- 用户账户不属于 docker group；
- 无 `/var/run/docker.sock`；
- 无 source/runtime/model 目录；
- 只读访问 public report 目录；
- 无项目 Git 写权限；
- 无 SSH agent/socket；
- 无环境 Token；
- 无 sudo/admin；
- wrapper 拥有者不是 OpenClaw 用户；
- wrapper 校验签署批准、manifest 和 lock。

## Prompt 不能作为控制

即使 OpenClaw 文档或工作区写了“不要读原图”，若 OS 仍允许读取，则部署不合格。

## 失败

Wrapper 返回稳定代码和脱敏信息。OpenClaw 不尝试修复、重试不同参数、下载模型或运行任意 Shell。
