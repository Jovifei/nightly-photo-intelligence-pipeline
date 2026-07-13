# Source Guard 参考伪代码

```text
validate_roots(source, runtime):
  source_real = strict_realpath(source)
  runtime_real = strict_realpath(runtime)
  reject if source is symlink/reparse point under current policy
  reject if source_real == runtime_real
  reject if source contains runtime or runtime contains source

open_source_file(candidate):
  reject extension not allowed (then sniff)
  reject symlink/junction
  resolved = strict_realpath(candidate)
  reject unless resolved is descendant of source_real
  pre = stat(resolved)
  fd = open(resolved, O_RDONLY | platform_no_follow_if_available)
  fd_stat = fstat(fd)
  reject if fd identity differs from pre
  stream bytes to decoder/hash; never expose write handle
  post = fstat(fd)
  reject if size/mtime identity changed
  close
```

平台差异必须有测试。不能把伪代码当作已经证明 Windows reparse point 安全。
