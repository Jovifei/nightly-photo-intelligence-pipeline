# ADR-0010：OpenClaw 延后且最小权限

状态：Accepted

OpenClaw 仅在 100 张 Pilot 稳定、N8 通过及独立激活批准后，调用固定白名单 wrapper 并读取脱敏报告。无 Docker socket、原图、Token、SSH、Git 写或管理员权限。

原因：提示词不是硬沙箱，调度器不应成为分析或权限控制平面。
