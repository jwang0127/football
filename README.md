# 竞彩足球预测流水线

按 Sporttery 竞彩业务日生成每日预测页（韩职、瑞超、挪超、芬超、巴甲、美职、欧冠/欧联资格赛），
并保留冻结快照、复盘与严格审计。所有页面均注明：仅为公开信息整理后的娱乐分析，不构成任何购彩建议。

## 模型架构（2026-07-26 升级）

预测由四层组成，全部只依赖标准库：

1. **市场基线层**（`scripts/market_model.py`）
   - 幂方法去水（power de-vig）：替代等比例归一化，纠正"热门-冷门偏差"，
     胜平负、总进球、比分矩阵、半全场四个玩法统一处理；
   - Dixon-Coles 双泊松比分模型：对去水后的比分矩阵（含 homeOther/drawOther/awayOther
     尾部桶）拟合主客队期望进球 λ 与低比分相关参数 ρ，
     方向、总进球、比分、半全场从同一联合分布导出，互相不再矛盾；
   - 半全场概率表：按上半场约 45% 进球占比拆分 λ，替代"总进球≤2 即半场平"的经验规则。
2. **联赛校准层**（`scripts/generate_date_pages.py` 中 `COMPETITION_MODELS`）
   - 每个联赛独立权重（胜平负/比分矩阵/联赛先验）、进球偏移、平局与零封加成；
   - 小样本收缩：复盘参数与 12 场中性先验加权，防止单日赛果过拟合。
3. **证据情境层**（`data/match_context_*.json`）
   - 赛程、休息天数、伤停、动机等只有公开来源可核验时才修正方向概率，否则保持中性并降低置信度。
4. **发布层**
   - 三比分池（主选+两备选）、尾部审计、串关组合；每场附价值审计
     （EV = 模型概率 × 赔率 − 1）与比分矩阵拟合参数，便于赛后复核。

## 日常工作流

```bash
# 1. 抓取赔率（Windows）
powershell -ExecutionPolicy Bypass -File .\scripts\fetch_sporttery.ps1 -Date 20260727 -OutFile .\data\sporttery_20260727_latest.json -PoolCode "ttg,had,hhad,crs,hafu" -Force

# 2. 生成某日预测页（自动读取 data/match_context_<date>.json 与最新复盘）
python scripts/generate_date_pages.py --date 20260727 --source data/sporttery_20260727_latest.json
#    验证输出而不覆盖已发布页面：加 --output-root <目录>

# 3. 校验页面与数据一致性
python scripts/validate_date_pages.py --date 20260727 --expected-matches <N>

# 3.5 采集比赛级外部证据（赛果/赛程/天气；失败会写入来源状态，不会伪造数据）
python scripts/fetch_match_evidence.py --date 20260727 --source data/sporttery_20260727_latest.json
python scripts/build_public_context.py --date 20260727 --source data/sporttery_20260727_latest.json

# 4. 赛后：写入已核实赛果与分联赛复盘（参照 scripts/apply_20260725_review.py）
#    然后重建未来页并刷新首页
python scripts/update_review_and_future.py --review-date 20260727
```

## 审计与回测

```bash
# 冻结快照严格审计（命中率 + 方向Brier分/对数损失），输出 accuracy/index.html
python scripts/build_model_review_audit.py

# 全历史回测：合并所有已核实赛果，输出命中率、概率质量与校准表
python scripts/backtest_calibration.py   # 写 data/backtest_report.json
```

回测校准表把"声称的主方向概率"分桶对比实际命中频率：`claimed_mean` 明显高于
`realised_rate` 说明该区间过度自信，应加强收缩；反之说明先验/平局加成稀释过度，
可提高市场权重。调整 `COMPETITION_MODELS` 时以该表为准，而不是单日赛果。

## 测试

```bash
cd scripts
python -m unittest test_market_model test_competition_calibration test_score_pool_model test_site_workflow
```

## 目录约定

- `data/sporttery_<date>_latest.json`：官方赔率快照（结算后复制为 `data/<date>.json` 并写入赛果）
- `data/external_context_<date>.json`：逐场外部接口证据缓存，包含 provider 状态、匹配记录、天气响应和缺口原因
- `data/predictions_<date>.json` 与 `<date>/index.html`：冻结的当日预测（发布后不回填修改）
- `data/review_<date>_competitions.json`：分联赛复盘
- `data/settled_results_*.json`（含 `*_extra.json`）：已核实赛果
- `accuracy/`：严格审计页；首页由 `scripts/generate_homepage.py` 生成

## 数据源

- 赔率页面：https://m.sporttery.cn/mjc/jsq/zqzjq/
- 接口：`getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu`

以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。
