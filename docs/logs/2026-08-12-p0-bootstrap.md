# P0 Bootstrap 验收记录

- 日期：2026-08-12
- 主机：`iZuf61652auueeij6x3lhhZ`
- 工作目录：`/home/codex/workspace/thesis/mcpmodel`
- 初始提交：`3ec9b143cf4d08d9e9dfd8078eef11f9dd4d9da5`

## 验收结果

```text
mcpmodel-validate data/examples  -> validated=2 schema=case
ruff check .                     -> All checks passed!
pytest                           -> 7 passed in 0.07s
```

## 运行基线

```text
OS            Ubuntu 24.04 / Linux 6.8.0-136-generic x86_64
Python        3.12.3
CPU           2 vCPU
RAM           3.4 GiB（验证后 available 约 2.8 GiB）
Swap          4.0 GiB（验证时未使用）
Disk free     66.56 GiB
mcpmodel      0.1.0.dev0
jsonschema    4.26.0
numpy         2.5.2
pandas        2.3.3
scikit-learn  1.9.0
pytest        8.4.2
ruff          0.16.2
```

## 复现命令

```bash
cd /home/codex/workspace/thesis/mcpmodel
./scripts/bootstrap.sh
source .venv/bin/activate
source scripts/env.sh
mcpmodel-validate data/examples
ruff check .
pytest
python scripts/check_environment.py
```

## 偏差与处置

官方 PyPI 路径在本机出现连接超时，阿里云镜像稳定。`bootstrap.sh` 默认使用阿里云镜像，同时保留 `PIP_INDEX_URL` 与 `PIP_TRUSTED_HOST` 覆盖入口。第一次服务器验收是在初始提交上加这两处待提交修订完成的；修订仅影响依赖下载源，不改变测试代码与验证逻辑。
