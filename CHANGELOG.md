# Changelog

## 2026-08-12 - CI dependency repair

- Installed the model extra in fresh GitHub Actions environments so annotation tests can import NumPy and scikit-learn.
- Updated official checkout/setup-python actions to their Node.js 24-compatible major versions.

## 2026-08-12 - Authorization reconstruction gate

- Added task-only, two-reviewer authorization reconstruction with adjudication.
- Added deterministic normalization for all 54 Chaitin candidate calls.
- Blocked external risk annotation until task hashes and reconstructed authorization are frozen.
- Removed source labels from external risk-annotation contexts.

## 0.1.0-dev - 2026-08-12

- 建立研究目标、路线图、数据卡、标注手册与复现规范。
- 建立 case、authorization、audit event 三类 JSON Schema。
- 加入工具规范化、授权偏差、透明基线特征和验证 CLI。
- 加入样例、单元测试、服务器初始化脚本和 GitHub Actions。
- 加入 30 条合成 Pilot、分组防泄漏切分、硬规则引擎和 Logistic 基线流水线。
- 加入三人 Excel 盲标包、一致性统计、分歧裁决和最终人工标签合并流程。
- 接入五类长亭样例，增加来源登记、文件指纹、统一派生 Schema 和用途隔离。
