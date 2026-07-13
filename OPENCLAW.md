# OPENCLAW.md — OpenClaw 入口与当前禁止状态

## 当前状态

```text
OPENCLAW_ACTIVATION = NOT_AUTHORIZED
IMPLEMENTATION_ROLE = FORBIDDEN
SCHEDULING_ROLE = FORBIDDEN_UNTIL_N8_AND_SEPARATE_APPROVAL
```

OpenClaw 当前不得：

- 修改代码；
- 读取原图目录；
- 连接 Docker socket；
- 持有模型 Token、SSH 私钥、管理员权限或 Git merge 权限；
- 动态生成逐图 Shell 命令；
- 启动 N0–N7；
- 自行判定阶段或数据门禁通过。

## 未来允许的最窄角色

仅当以下全部满足时，Owner 才可单独激活：

1. N8 获授权并通过；
2. 100 张 Pilot 已通过人工 Gate；
3. `approvals/openclaw_activation_*.yaml` 已签署；
4. 最小权限负向测试通过；
5. 只提供一个白名单固定命令包装器；
6. OpenClaw 只能读取脱敏状态/报告目录；
7. 无 Docker socket、无原图、无模型 Token、无 Git 写权限。

未来职责仅限固定命令调度、进度检查、异常通知和早晨日报。真正处理图片的仍是受控 Python/Docker 运行时。

详见 `openclaw/SECURITY_BOUNDARY.md`。
