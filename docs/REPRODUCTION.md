# 复现实验说明

## 环境

推荐 Ubuntu 24.04 x86-64、Python 3.12。最小 2 vCPU / 4 GiB + 4 GiB Swap。

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
python scripts/check_environment.py
mcpmodel-validate data/examples
pytest
```

## 结果目录约定

正式实验写入带时间戳或运行 ID 的目录；必须包含配置快照、Git commit、Python/依赖版本、随机种子、数据哈希、指标和逐样本预测。不得覆盖旧运行。

```text
results/<run_id>/
  run_manifest.json
  metrics.csv
  predictions.csv
  confidence_intervals.csv
  figures/
```

## 冻结原则

测试集只做一次正式报告。出现未达目标时，返回标签、规范化、授权或特征阶段排查，不能修改测试真值。
