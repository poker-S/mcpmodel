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

初始化脚本默认使用阿里云 PyPI 镜像，以适配当前 ECS 的网络路径；也可以显式覆盖：

```bash
PIP_INDEX_URL=https://pypi.org/simple PIP_TRUSTED_HOST=pypi.org ./scripts/bootstrap.sh
```

## 结果目录约定

正式实验写入带时间戳或运行 ID 的目录；必须包含配置快照、Git commit、Python/依赖版本、随机种子、数据哈希、指标和逐样本预测。不得覆盖旧运行。

```text
results/<run_id>/
  reproduction-manifest.json
  config-snapshot/
  metrics.json
  predictions-<role>.csv
  selective-model.joblib
```

## P3 选择性治理冒烟

```bash
python scripts/run_selective_pipeline.py --output results/p3-selective-smoke
```

固定数据角色如下：

1. `train` 只拟合有序风险模型；
2. `probability_calibration` 只拟合温度参数；
3. `conformal_calibration` 只计算非一致性分数分位数；
4. `test` 只在所有参数固定后生成冒烟评估，不参与拟合、校准或阈值选择。

所有角色按 `scenario_group` 隔离。输出目录原子发布且禁止覆盖；复现清单保存输入和配置
SHA-256、Git commit、Python/依赖版本。当前 synthetic Pilot 不具备独立人工真值，且校准
样本数不足，`metrics.json` 中的 `formal_research_use_allowed` 必须为 `false`。

## 冻结原则

测试集只做一次正式报告。出现未达目标时，返回标签、规范化、授权或特征阶段排查，不能修改测试真值。
