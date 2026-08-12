# MCPModel Dataset Card（初版）

## 当前 Pilot 状态

`pilot-0.1` 含 30 条、15 个反事实场景组，标签由场景设计提供，仅用于工程联调，尚未经过三人独立标注。其指标不能解释为模型泛化性能或安全能力。

## 用途

支持研发工作站 MCP 工具调用的固有风险分级、授权偏差建模、选择性治理和外部案例分析。

## 组成

- 自建原子调用与多步调用链；
- 成对反事实样本；
- 经隔离、脱敏和结构化转换的公开安全样例；
- 独立外部测试集。

## 长亭科技样例接入

| 数据源 | 当前样例量 | 用法 | 是否直接作为 L0～L4 真值 |
|---|---:|---|---|
| Agent attack trajectory | 49 个工具调用 + 5 份攻击分析 | 真实候选调用，补全授权后盲标 | 否 |
| Network attack prompt | 40 条 | 来源风险/攻击活动辅助语料 | 否 |
| AI-VULNATLAS | 7 个 finding | 外部评测与攻击链案例 | 否 |
| CVE verification | 8 个 finding | 场景种子、严重性和验证证据 | 否 |
| Deployment evaluation | 5 个通过的检查 | 正常高权限调用候选 | 否 |

统一转换后共 114 条派生记录，其中 54 条候选工具调用、40 条辅助提示词、7 条外部评测记录、13 条场景种子。派生记录由 `schemas/derived_record.schema.json` 约束，来源登记由 `schemas/source_record.schema.json` 约束。

每条派生记录保留：`source_id`、原始相对路径、原文件 SHA-256、JSON/JSONL 定位器、场景组、转换器版本、允许用途和标签状态。多文件证据还保留 supporting source 路径与 SHA-256。

## 许可边界

样例 README 表述为 research/internal use，并要求许可细节联系维护者。当前采用 `research_internal_only`：原始包和逐条派生语料不进入 GitHub；仓库只提交来源配置、Schema、转换器、聚合统计和不可逆哈希。若公开发布论文附件、数据集或派生语料，必须先另行确认再分发许可。

## 不适用

- 通用用户恶意性判定；
- 真实生产系统自动授权；
- 直接执行 CVE PoC 或攻击轨迹；
- 将公开 `safe/unsafe` 文本标签直接当作 L0～L4 真值。

## 字段与模式

核心记录遵循 `schemas/case.schema.json`。授权包络遵循 `schemas/authorization.schema.json`。决策输出遵循 `schemas/audit_event.schema.json`。

## 隐私与安全

不收集真实个人凭据、Cookie、私钥或生产数据。路径、域名、Token 和账户均使用合成或脱敏值。外部样例作为不可信数据保存，原始区只读，研究仓库不包含被安全软件隔离的载荷文件。

## 划分与泄漏控制

所有模板变体和反事实样本按 `scenario_group` 整组划分。完整调用轨迹不得拆散跨集合。近重复检测结果和划分清单随数据版本保存。

## 已知限制

早期样本量小、工具类别有限、标注者来自同一项目组；外部案例与自建场景存在分布差异。论文必须报告这些限制和置信区间。
