# 原图只读保护设计

原图保护是系统安全属性，不是一个布尔配置。

## 四层防护

### 1. 权限层

- Windows 侧优先使用只读/拒绝写入 ACL 或专用只读共享；
- Docker 使用显式 `:ro` / `read_only` 挂载；
- Pipeline 进程使用无管理员权限账户；
- 不给 OpenClaw 原图目录权限；
- 不通过修改原图权限来“实现只读”。

### 2. 路径层

- source root 与 runtime root 不得相等、互为父子或通过 symlink 指向重叠位置；
- source root 自身如果是 symlink，默认拒绝；
- 文件 symlink、junction、reparse point 需拒绝或证明仍在 root；
- 规范化路径后检查 containment；
- 不接受 `..` 逃逸。

### 3. API 层

- 只以二进制只读方式打开；
- 代码中不提供 delete/move/rename/write-back 接口；
- EXIF 库使用只读模式；
- 派生物永远写 runtime；
- 临时文件永远写 runtime；
- 不调用会原地修改的图像工具。

### 4. 证据层

对 fixture 和 Gate 抽样记录：

- pre SHA-256；
- pre size；
- pre mtime_ns；
- post SHA-256；
- post size；
- post mtime_ns。

文件系统可能改变 atime，因此 atime 不作为完整性要求。任何内容、size 或 mtime 改变都视为 P0 失败并停止。

## TOCTOU 与文件身份

- 枚举后打开时重新验证文件仍位于 root；
- 对打开的文件描述符进行 stat；
- 读完后再次 stat；
- 发生替换或变化则丢弃结果并进入安全错误；
- 不依赖扩展名判断真实格式。

## Dry-run 语义

N0 `ingest --dry-run`：

- 可读取 fixture；
- 可在内存计算；
- 不写资产表；
- 不创建派生图片；
- 允许向 stdout 输出脱敏摘要；
- 若写日志，只写 runtime/logs，不写 source；
- 退出后数据库资产计数不变。

## 负向测试

- 可写源仍不能被程序写入；
- 源内输出路径被拒绝；
- 输出内源路径被拒绝；
- symlink escape 被拒绝；
- 只读文件不被 chmod；
- 重复文件不被删除；
- 非图片伪装扩展名安全失败；
- Unicode/长文件名不导致路径逃逸。
