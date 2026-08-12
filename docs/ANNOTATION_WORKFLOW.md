# P1 三人独立试标流程

## 角色

- 标注者 A/B/C：独立完成，不查看规则分数、模型预测或彼此答案。
- 裁决者：只在三份原始答案锁定后处理分歧。
- 数据维护者：检查格式、匿名化和版本哈希，不修改标签语义。

## 试标材料

从 `data/pilot/pilot-0.1.jsonl` 生成三份相同顺序的表。向标注者展示任务、授权包络、来源、候选调用和必要的前序事件；隐藏 `labels`、`metadata.label_status` 和后续模型输出。

每人填写：

```text
case_id
annotator_id
inherent_risk          L0/L1/L2/L3/L4
recommended_action     allow/isolate/rewrite/approve/deny
tool_scope             0/0.5/1
action_scope           0/0.5/1
resource_scope         0/0.5/1
sink_scope             0/0.5/1
temporal_scope         0/0.5/1
subject_scope          0/0.5/1
reason_codes
note
```

## 顺序

1. 冻结试标包哈希并分别发给 A/B/C。
2. 独立标注，不讨论个案。
3. 锁定三份 CSV，检查行数、枚举和 case ID。
4. 计算有序风险的加权 Kappa、动作一致率和逐类混淆。
5. 分歧会议只讨论定义和证据；保留原答案，另写裁决标签。
6. Kappa `<0.60`：停止扩标并重写手册；`0.60～0.70`：二次试标；`≥0.70`：可进入扩标评审。

统计口径：

- 风险等级主一致性指标：三组 pairwise quadratic weighted Cohen's Kappa 的均值；
- 辅助指标：无权重 Fleiss' Kappa、风险完全一致率；
- 推荐动作：无权重 Fleiss' Kappa、完全一致率；
- 不能把无权重 Fleiss' Kappa 写成“加权 Fleiss' Kappa”。

## 命令

```bash
# 生成三份盲标 CSV 包
python scripts/create_annotation_pack.py --output results/annotation-pack

# 回收后校验、计算一致性并生成裁决队列
python scripts/analyze_annotations.py \
  labels-A.csv labels-B.csv labels-C.csv \
  --output agreement.json \
  --adjudication adjudication.csv

# 裁决队列填写完成后形成最终人工标签
python scripts/finalize_annotations.py \
  labels-A.csv labels-B.csv labels-C.csv \
  --adjudication adjudication.csv \
  --output human-labels.csv
```

仓库同时提供 `data/annotation_pack/p1-v0.1/` 下三份 `.xlsx`。每份工作簿包含填写说明、冻结上下文、黄色输入区和枚举下拉框，分别交给 A/B/C；不要三人共用一份文件。

## 禁止事项

- 不得用合成标签作为标注者默认答案。
- 不得根据模型错误修改人工真值。
- 不得只报告删除“难标样本”后的 Kappa。
- 不得让同一反事实组跨正式数据划分。
