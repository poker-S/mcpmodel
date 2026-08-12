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

### 重要问题与处理

- 本机 Clash Verge TUN 全局模式曾接管 SSH 并导致 banner 交换失败。关闭 TUN 后直连正常；系统代理可保留。
- 独立 Codex 安装脚本未产生二进制，改用 `npm install -g @openai/codex`。
- 服务器为抢占式实例，不能作为唯一数据副本；Git 推送和结果回传是强制流程。

### 验证

- SSH 公钥登录成功；
- 服务器内存和 Swap 状态正常；
- 上传包本地/远程 SHA-256 一致；
- 后续以 `pytest`、Schema 验证和环境检查脚本作为工程验收。

### 下一步

- 生成 30 条 Pilot；
- 三人独立试标并计算 Fleiss' Kappa；
- 实现 normalizer、authorization gap 和第一组 Rule/ACL 基线。
