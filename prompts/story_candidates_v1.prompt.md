---
prompt_id: npi-story-candidates
version: 0.1-draft
status: NOT_AUTHORIZED
output_layer: story_candidates
---

基于已验证 facts 和 interpretation，固定生成一个：

1. safe：最低动作/道具依赖；
2. narrative：简单可理解的拍摄设定；
3. dynamic：包含动作瞬间，但服从空间限制。

所有故事：

- `fictional_candidate=true`；
- 有 feasibility、constraints、evidence_refs；
- 不冒充原图真实事件、人物心理或作者意图；
- 不引入图中不存在且现场难获得的道具；
- dynamic 不得违反空间/安全约束。
