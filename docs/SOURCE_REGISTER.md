# 外部数据来源登记

## 归属与位置

- 提供方：长亭科技（Chaitin Technology）
- 本地原始归档：论文资料目录 `datasets/chaitin_raw/`
- 本地解压副本：论文资料目录 `datasets/chaitin_extracted/`
- 来源配置：`configs/sources.yaml`
- 构建器：`scripts/ingest_chaitin.py`
- 原始数据策略：只读、不执行、不提交 Git

## 归档指纹

| source_id | archive SHA-256 |
|---|---|
| `chaitin_agent_trajectory_sample` | `7043ad1202e0e7a9f4da7e64c0f293bf3fa224176ce342ab8ad1cfd2dd6d7cf7` |
| `chaitin_network_prompt_sample` | `593634121af17159893d2784f7f68bada99144c39f7e1374e1af11fee906d1ff` |
| `chaitin_ai_vuln_atlas_sample` | `11a1c4bfe0cc2e636d99d7b8515e440fc72c2f69ddf6580bd55e19de0cbb5feb` |
| `chaitin_cve_verification_sample` | `49288b69939e99d0adcb76dfafd9cbbad2c8e1c6759238ed1c3d57965f393d75` |
| `chaitin_deployment_sample` | `7d51f65d781af5bdbc0494136572bae2a1e572c02ae970316a8cf2cdfa831902` |

## 用途约束

- 轨迹和部署检查：可作为候选调用，但必须重建授权包络并重新盲标。
- Prompt 的 `safe/unsafe`：只作为来源/活动辅助标签，不转换为风险真值。
- CVE severity/CVSS：只作为漏洞证据和分层字段，不转换为治理动作。
- AI-VULNATLAS：保留作外部评测，避免参与特征和阈值调优。
- `reason.md`：攻击链证据，不与同轨迹工具调用拆分到不同正式数据集。

## 更新流程

新归档必须先登记文件哈希、README许可说明和允许用途。转换器版本变化后生成新目录，不覆盖旧派生数据；正式划分以 `source_id + scenario_group` 为组进行泄漏控制。
