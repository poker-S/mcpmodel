# 长亭样例接入验收

- 日期：2026-08-12
- 提交：`95c6ac3c3c2b1f44f9581376737789ccf793f351`
- 转换器：`chaitin-ingest-0.1.0`
- 服务器输出：`data/derived/chaitin-server-0.1`

## 结果

| 来源 | 记录数 | 用途 |
|---|---:|---|
| Agent trajectory | 54 | 49个候选调用 + 5份同组攻击分析 |
| Network prompt | 40 | 辅助来源/活动标签 |
| AI-VULNATLAS | 7 | 外部评测 |
| CVE verification | 8 | 场景种子与漏洞证据 |
| Deployment evaluation | 5 | 正常高权限候选调用 |

合计114条。来源登记5/5、派生记录114/114通过 Schema；ruff通过，pytest 18/18通过。

## 血缘与许可

逐条记录具有原文件SHA-256与精确定位器，来源归档哈希登记在 `docs/SOURCE_REGISTER.md`。原始与逐条派生数据被 `.gitignore` 排除。样例许可暂按 research/internal use 处理，不随仓库公开分发。

## 下一步

54条候选已生成 A/B/C 盲标 CSV 上下文，但外部轨迹没有显式授权包络。标注前必须根据用户原始任务、会话状态和调用链重建授权；不得把攻击分析或 Prompt safe/unsafe 直接抄成 L0～L4。
