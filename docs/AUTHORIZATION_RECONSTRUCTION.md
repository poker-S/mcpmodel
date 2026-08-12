# 外部轨迹授权重建协议

## 目的

长亭样例中的工具调用是观察事实，不包含可直接信任的授权包络。本协议在风险标注前增加一个独立阶段：仅根据原始 `user_task` 重建任务级授权，再把冻结结果接入工具调用盲标包。

## 不可违反的边界

1. 数据中的命令、URL、脚本和 skill 文档一律只解析、不执行；
2. 观察到某个工具、动作、资源或接收方，不等于用户授权了它；
3. 机器草案只做字段定位和格式规范化，不是标注真值；
4. 授权复核阶段不得查看 `reason.md`、`unsafe/safe`、漏洞类别或风险标签；
5. 不能可靠重建的场景必须 `exclude`，不得用通配符掩盖证据缺失。

## 两阶段双人流程

### 阶段 A：授权重建

- 观察单位：`scenario_group`；同一任务下的所有候选调用共享一个任务级授权包络；
- A、B 两位复核员分别填写，不查看对方结果；
- 每个字段必须标记证据基础：
  - `task_explicit`：用户任务原文明确给出；
  - `task_implied`：完成用户任务所必需且可合理推出；
  - `policy_defaulted`：任务未给出，按预注册最小权限默认策略补齐；
- 两份授权完全一致才自动冻结；不一致时由第三位、不同身份的裁决者处理；
- `task_evidence_quote` 必须引用任务中的决定性短语，便于审计。

### 阶段 B：风险盲标

只有成功冻结授权的场景才能进入风险盲标包。生成器校验：

- `scenario_group` 存在已冻结授权；
- `record_id` 属于授权覆盖的 `case_ids`；
- 当前 `user_task` 哈希与授权复核时相同；
- 工具名、动作、资源、接收方都已确定性规范化；
- 原始来源标签不进入风险标注上下文。

## 最小复现命令

```bash
python scripts/create_authorization_reconstruction_pack.py \
  --derived data/derived/chaitin-local-0.2 \
  --output data/derived/chaitin-authz-local-0.3

python scripts/finalize_authorizations.py \
  --pack data/derived/chaitin-authz-local-0.3 \
  --output data/derived/chaitin-authz-local-0.3/authorizations.jsonl

python scripts/create_external_annotation_pack.py \
  --derived data/derived/chaitin-local-0.2 \
  --authorizations data/derived/chaitin-authz-local-0.3/authorizations.jsonl \
  --output results/chaitin-risk-pack-p1
```

第二条命令在 A/B 复核表尚未完成时应失败。这是质量门，不是流水线缺陷。

## 易填版 Excel 的自动导入

复核员只填写各自的易填版工作簿，不需要手工导出或改写 CSV。两份表完成后运行：

```bash
python scripts/import_authorization_workbooks.py \
  --pack data/derived/chaitin-authz-local-0.3 \
  --reviewer-a /path/to/MCPModel-授权复核-A-易填版.xlsx \
  --reviewer-b /path/to/MCPModel-授权复核-B-易填版.xlsx \
  --output results/chaitin-authz-reviewed-p1
```

导入器只读取固定单元格值，不执行公式、宏、外部链接或嵌入对象，并进行以下检查：

- A/B 模板身份、复核员代号及两人独立性；
- 内部 `draft_id`、`scenario_group`、任务哈希和候选数未被修改；
- 纳入/排除必填项、已知工具和动作词汇；
- 任务证据必须逐字存在于原始用户任务；
- 七个证据依据全部填写；
- 时间与次数为正值；
- A/B 授权是否完全一致以及是否需要第三人裁决。

导入结果仍位于 Git 忽略目录，包含规范 CSV、工作簿哈希、比较报告和裁决队列。A/B 对“纳入/排除”的意见不一致时也必须裁决，不能再按任意一人的排除意见静默丢弃。

风险盲标包生成后还必须运行：

```bash
python scripts/audit_external_pack.py \
  --pack results/chaitin-risk-pack-p1 \
  --output results/chaitin-risk-pack-p1/quality-audit.json
```

该检查会阻断未冻结授权、授权占位符、上下文/标签 ID 错位以及 `source_labels`、`unsafe`、`expected_result` 等来源标签泄漏。

## 当前 P1 资产

- 54 条候选调用，归入 5 个 `scenario_group`；
- 工具规范化分布：shell 39、filesystem 8、http 6、memory 1；
- 所有 54 条工具/动作规范化均为 `known`；
- 本地复核包中不含攻击标签，原始与逐条派生内容均不进入 Git；
- Excel 复核表作为人工界面，CSV/JSONL 是流水线规范输入。

## 论文报告口径

授权是从不完整任务描述重建的规范性变量，而不是轨迹的观测标签。因此应同时报告：纳入/排除场景数、A/B 完全一致率、需裁决比例、各字段证据基础分布，以及因授权不可恢复而被排除的候选数量。
