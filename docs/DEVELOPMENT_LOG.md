# 开发日志

日志按时间追加，不覆写历史。每次记录包含：目标、执行、产物、验证、问题、决策和下一步。

## 2026-08-12 — P0 环境与仓库初始化

### 目标

- 建立可持续开发的 GitHub 仓库和远程实验主机；
- 将研究方案转化为可执行工程路线；
- 建立第一版数据契约、配置、验证入口和测试。

### 环境记录

| 项 | 值 |
|---|---|
| 云主机 | 阿里云 ECS `ecs.u2a-c1m2.large` |
| OS | Ubuntu 24.04 x86-64 |
| CPU / RAM | 2 vCPU / 4 GiB（系统显示约 3.4 GiB） |
| Swap | 4 GiB |
| 系统盘 | 80 GiB ESSD，初始化时可用约 68 GiB |
| Python | 3.12.3 |
| Git | 2.43.0 |
| Codex CLI | 0.147.0 |
| Node / npm | 18.19.1 / 9.2.0 |
| 远程用户 | `codex`（公钥登录，非 root） |

### 已执行

1. 创建独立 `codex` 用户、SSH 公钥和 `/home/codex/workspace`。
2. 安装 Python、venv、pip、Git、编译工具、Node 和 Codex CLI。
3. 创建 4 GiB Swap。
4. 从本地上传论文材料至 `/home/codex/workspace/thesis`。
5. 上传包 SHA-256：`9a5348e51af4a11e4d657f6b2b7b06100ce7eada6b8d953096bbc9533577efdd`。
6. 未上传被宿主安全软件标记的 `datasets/ct_a_short/case_05-session.jsonl`。
7. 确认 GitHub 仓库 `git@github.com:poker-S/mcpmodel.git` 可访问且初始为空。
8. 建立仓库骨架、开发路线、Schema、配置、示例和测试。
9. 首次推送 GitHub：`3ec9b143cf4d08d9e9dfd8078eef11f9dd4d9da5`。
10. 用 Git bundle 将同一提交部署到 `/home/codex/workspace/thesis/mcpmodel`，远端保留原空仓库备份。
11. 建立 `.venv`，安装开发与建模依赖；项目脚本限制数值计算库最多使用 2 线程。

### 重要问题与处理

- 本机 Clash Verge TUN 全局模式曾接管 SSH 并导致 banner 交换失败。关闭 TUN 后直连正常；系统代理可保留。
- 独立 Codex 安装脚本未产生二进制，改用 `npm install -g @openai/codex`。
- 服务器为抢占式实例，不能作为唯一数据副本；Git 推送和结果回传是强制流程。
- ECS 到官方 PyPI 的连接超时，切换阿里云 PyPI 镜像后安装恢复；初始化脚本允许通过环境变量覆盖镜像。

### 验证

- SSH 公钥登录成功；
- 服务器内存和 Swap 状态正常；
- 上传包本地/远程 SHA-256 一致；
- `mcpmodel-validate data/examples`：2/2 通过；
- `ruff check .`：通过；
- `pytest`：7/7 通过；
- Python 3.12.3；NumPy 2.5.2；pandas 2.3.3；scikit-learn 1.9.0；
- 验证后约 2.8 GiB 可用内存、4 GiB 空闲 Swap、66.56 GiB 可用磁盘。

### 下一步

- 生成 30 条 Pilot；
- 三人独立试标并计算 Fleiss' Kappa；
- 实现 normalizer、authorization gap 和第一组 Rule/ACL 基线。

## 2026-08-12 — P1 合成试标与基线流水线

### 目标

- 将 30 条/15 组反事实样本变成可复现数据产物；
- 证明分组切分不会泄漏；
- 跑通硬规则与成本敏感 Multinomial Logistic；
- 明确区分“工程验收标签”和“独立人工真值”。

### 已执行

1. Schema 增加 `calls_used` 与 `actual_subject`，授权偏差补齐 `subject_gap`。
2. 补充资源标签、调用参数特征和声明式硬规则引擎。
3. 确定性生成 `pilot-0.1`：30 条、15 个场景组，L0～L4 均有覆盖。
4. 固定种子 `20260812`，按组切分为 18/6/6，场景组无跨集合泄漏。
5. 实现并跑通规则与成本敏感多项逻辑回归基线。
6. 新增 ADR-0003，禁止把 synthetic smoke-test 指标当作论文证据。

### 本地验证

- Pilot canonical SHA-256：`381a03cfdcfd65c5194f358193f1f5c3a4db1b8eb82f68ae50366e026f3489c5`；
- split assignment SHA-256：`f88fac8f3e728b3adef3a79cc808099966888b720dde3fe6bf464456118be59e`；
- 32 个 JSON/JSONL 文档通过 Schema；
- `ruff` 通过；`pytest` 12/12 通过；
- 首次 Logistic 运行暴露 scikit-learn 1.9 不再允许 `liblinear` 直接多分类，改用 `lbfgs` 后恢复。

### 当前结论

流水线已经闭环，但 30 条设计标签过少且不是独立真值。测试划分上 Logistic 严重风险召回为 0，恰好说明此结果只能用作失败可见的 smoke test，下一步必须先进行三人盲标，而不是围绕这 6 条测试样本调参。

### 服务器验收

提交 `e3b9a0688f5582ca033573500b169836a84c5517` 已同步至服务器。30/30 Schema、ruff、14 项 pytest 均通过；基线训练评估耗时 1.20 秒，峰值 RSS 约 155.6 MiB，未使用 Swap。详细记录见 `docs/logs/2026-08-12-p1-smoke.md`。
