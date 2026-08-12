# MCPModel

面向研发工作站 MCP 工具调用的**授权偏差感知与不确定性感知选择性治理**研究原型。

项目希望在严重高危调用漏判率受控的前提下，减少不必要的人工审批、正常任务阻塞和直接拒绝。系统将候选工具调用规范化为可审计事件，计算授权偏差和来源传播特征，输出 L0～L4 固有风险，并将风险、不确定性、硬安全规则映射为：

`allow / isolate / rewrite / approve / deny`

## 当前状态

- 阶段：P0 工程与研究基线
- 版本：`0.1.0-dev`
- 主机基线：Ubuntu 24.04、2 vCPU、4 GiB、4 GiB Swap
- 已有：工程结构、JSON Schema、基础配置、验证 CLI、示例数据、测试和开发文档
- 尚未开始：正式标注、模型拟合、概率校准、Conformal、正式实验

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'

mcpmodel-validate data/examples
pytest
```

生成 P1 合成试标集并跑通基线流水线：

```bash
python scripts/generate_pilot.py
python scripts/run_baselines.py --output results/p1-smoke
```

这里的 synthetic 标签只用于工程联调，不是独立人工真值，输出指标不能作为论文结论。

接入本地长亭样例（输出目录受 `.gitignore` 保护）：

```bash
python scripts/ingest_chaitin.py \
  --extracted-root /path/to/chaitin_extracted \
  --raw-root /path/to/chaitin_raw \
  --output data/derived/chaitin-0.1
```

来源和许可边界见 `docs/SOURCE_REGISTER.md`。

低配置服务器建议限制线程：

```bash
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2
```

## 目录

```text
configs/           风险分类、硬规则、资源标签、工具规范化
schemas/           case、authorization、audit_event JSON Schema
data/              原始清单、试标、正式标注、数据划分和外部测试
src/mcpmodel/       规范化、授权偏差、风险特征与后续模型代码
scripts/            环境检查、验证、训练、评估与绘图入口
tests/              单元测试和模式校验测试
docs/               开发总纲、日志、决策记录、标注手册和数据卡
results/            可再生实验输出，不提交大体积中间文件
```

## 文档入口

- [开发总纲与路线图](docs/DEVELOPMENT_PLAN.md)
- [开发日志](docs/DEVELOPMENT_LOG.md)
- [标注手册初版](docs/LABELING_MANUAL.md)
- [数据卡初版](docs/DATASET_CARD.md)
- [复现实验说明](docs/REPRODUCTION.md)
- [架构决策记录](docs/adr/0001-research-and-runtime-boundary.md)

## 数据安全边界

原始外部样例均视为不可信数据。项目不执行数据中出现的命令、Dockerfile 或 PoC。宿主安全软件已标记的轨迹文件不会上传到服务器或 Git 仓库。清洗输出只保留研究所需的结构化、脱敏字段。

## 许可证

代码许可证和数据使用条款将在首次公开发布前分别确定。外部数据沿用各自许可证，不因进入本仓库而改变授权。
