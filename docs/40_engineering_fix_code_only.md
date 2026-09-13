# 审核与接下来的最小工程路线

## 一、已独立核对的远端事实

2026-09-13读取GitHub：
- 最新工具提交：3b453efed300dbe4d9e7f410697da1fb2d797f70。
- 唯一parent：da638bab6a61fe6fc466521cc60abcacfea9120a。
- Tree：75a15abf49302b793ee3163a5c43da3eef1c9006。
- main：d83f96271f754763d61cedcc314fc725c840c86f。
- 最新提交为review_tools交付，而不是运行能力或生产阶段解锁。

Git外delivery_state_final.json、S20新checksum、quality_matrix等本轮未取得原文。
用户给的是部分缩写Hash；不得从缩写补全/猜测64位Hash或声称独立复算。

## 二、本地Codex哪里做得对

正常追加并推送、保留main、区分工具与运行候选、保留AGENTS用户修改、
没有把skip或exit10写成PASS、没有复用已消费许可、没有接触真实照片，方向正确。
Windows symlink测试跳过是合理披露，不等于Windows路径威胁已验证。
3.14下测试通过可以保留为实验结果，但不满足>=3.11,<3.13的项目约束。

## 三、需要纠正的结论

“下一项只需要新synthetic execution lease”不完整。已确定代码缺口仍存在，
先消除代码问题、补支持环境、冻结最终候选，再申请一次新许可。
connection refused只证明当前调用环境的指定端点未能建立连接；并不证明模型
digest变化、checkpoint损坏或需要升级/降级Ollama。不得改端口、代理到云端或绑定0.0.0.0。

## 四、本轮进一步确认的缺口

### F0：Python preflight无条件PASS
`preflight.py::_check_python()`原实现直接status=PASS，不检查版本。
本包直接修补为3.11/3.12之外返回NPI_UNSUPPORTED_PYTHON；不修改pyproject支持范围。
新engineering_precheck还通过metadata检查原pin，缺依赖报告NOT_AVAILABLE，不pip、不导入模型。

### F1：方向空余面积
本包直接替换生产函数的bbox求和/四方向相等算法为裁剪矩形并集。
- 事实Schema版本从1.1到1.2；创建新schema文件，原1.1文件保留。
- 明确method、measurement_kind、coordinate_system、directional_denominator。
- fact-negative-space替换为fact-bbox-empty-area。
- uncertainty说明其他物体/显著性/美学留白并未测量。
- 非有限数值不再自动变成0；严格canonical拒绝NaN/Infinity。
- 新旧事实digest不兼容是正确结果；必须新输出，不迁移旧checkpoint冒充等价。
当前frame_contact仍只取首个人物框；它不是本轮F1完整的多主体构图升级。

### F2：一次性许可
新增lease组件：外部Owner可信receipt摘要、完整候选/树/manifest/identity绑定、有效期、
精确synthetic范围。目录名只取receipt SHA，因此换output/候选不能重置消费额度。
原子mkdir竞争只有一个成功；崩溃留下空占用也视为已消费；FAILED不释放；terminal只写一次。
此组件必须接在模型首次加载之前。它不靠新建SQLite实现。
Ledger必须为Owner已批准的固定本地根目录，不能由调用者每次换ledger规避。
收据摘要本身不是Owner签名；可信摘要必须来自包外真实Owner批准，不能自行生成APPROVED。

### F3：路径整体检查
新增path_policy：所有output两两检查，同所有fixture/Git/cache/旧evidence/保护根检查。
先检查symlink/reparse祖先，再使用路径；拒绝现存output、..、网络根/ADS。
只检查已知根目录元数据，不扫描真实source目录。
在写入前复查祖先身份；这不是完整Windows句柄级无竞态证明。继续复用已有bound-handle
保护并由本地完成junction/reparse/权限负测，不能把Linux/mock测试算Windows PASS。

### F4：真实证据
新增quality_matrix、五次identity观察和resume证据验证器。
拒绝一行摘要、缺命令/版本/退出码/日志摘要、漏质量项、skip冒充PASS、未知模型加载计数当0。
它验证记录，不执行命令，也不提供操作系统审计。Codex必须接入真实命令采集器和一次观察一次保存。
旧quality_matrix和一行remediation_result保持原样，补充说明写新review目录，缺失历史观察不补造。

### F5：GPU数值
直接修改完成产物校验：缺失/字符串/bool/NaN/Inf/非正值/超限全部拒绝，int和float一致。
保留11500MiB原批准边界，不靠提高阈值过测试。
旧单测若构造“不含gpu的成功产物”，应修正测试fixture以表达完整合同，而非恢复宽松检查。

### F6：全源码绑定
新增full_source_identity包含每个tracked文件的mode/blob/size/SHA256及HEAD/Tree。
要求clean、非浅克隆，无symlink/submodule条目，前后HEAD不变。全清单输出必须在Git外。
最终Owner lease在候选commit确定之后外置生成，解决“审批文件包含自己SHA”的循环问题。
原27项manifest仅保留为历史辅助，不当全源码证明。

### Windows兼容修复的观察
3b453efe的read_regular移除st_ctime_ns比较是全平台行为，不只Windows。
SHA-256、inode、size、mtime与前后审计仍保留，不能直接据此判证据无效。
后续应将兼容分支限制为已复现的平台，并保留POSIX侧更严格行为和相应回归测试。

## 五、实施顺序与验收

E0：代码与环境预检查（现在执行，无GPU许可）
- 已有3.12.10可直接跑无依赖unittest；不要用裸python误选3.14。
- 查已知venv/可信wheel来源；缺少整仓依赖时一次列全需要的pin和来源。
- 不更改全局Python，不扩大项目版本范围，不自动联网安装。

E1：本包应用与整仓集成（现在执行，无GPU许可）
- 直接补丁F0/F1/F5。
- 接入F2/F3/F4/F6到新的受控入口。
- 所有旧已消费run入口在新候选上不得当成fresh-run授权。
- 新增code-only候选profile。它只验收代码，不改变PROJECT_STATE和旧approval。
- 更新精确Git拓扑测试及Schema catalog；保留历史profile，不删除安全断言。
- 全tracked索引生成新的根MANIFEST；历史overlay verifier只用于3b453efe，不用于新修复HEAD。

E2：冻结最终运行代码候选
- 受支持Python整仓pytest、Ruff、format、mypy、schema、manifest、sensitive、source binding。
- 正常追加commit，不重写da638bab/3b453efe/main。没有自动merge。
- 不在报告中填写未知最终SHA；从真实git读取。
- 代码Review通过后，将精确candidate/Tree/source/环境/路径/fixture摘要提交Owner。

E3：一次新synthetic lease（之后另行批准）
- 绑定最终代码候选，确认服务在相同Windows执行环境loopback可达，identity稳定。
- 新S3/S20目录，整批一次；记录five observations、真实CLI no-op resume退出码。
- 必须先validate+reserve后model load；故障也消耗lease；禁止重复跑到PASS。
- 本包不发出任何APPROVED lease；DRAFT不能运行。

E4：Real20与第一份真实产品
独立Review + Owner采纳synthetic结果后才建立fresh Real20数据授权。
按真实样本检查人数/Pose/分割/构图正确性，p50/p95全链路耗时与人工修改成本。
最短用户价值闭环：真实照片 → 有依据的解释和提示 → 人工Approve/Edit/Reject →
APPROVED-only Bundle → 独立App导入、展示、回滚。
先做这一条，再100张，再500–600张，再夜间调度。不在本轮换RTMW/SAM或引入新平台。

## 六、来源

GitHub已读取固定commit上的pyproject、preflight、vision_facts、s20_bundle、review_tools等。
https://github.com/Jovifei/nightly-photo-intelligence-pipeline/commit/3b453efed300dbe4d9e7f410697da1fb2d797f70
https://packaging.python.org/en/latest/specifications/pyproject-toml/
https://docs.ollama.com/api/introduction
https://docs.ollama.com/windows

本轮没有重新选择模型或部署开源平台；此前FiftyOne/Label Studio/CVAT等借鉴方向仍用于
后续质量评价和审核机制，不应成为本轮修复的额外依赖。
