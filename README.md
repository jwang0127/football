# 韩职与瑞超预测 20260705

本仓库按 `C:\Users\Administrator\Documents\世界杯预测` 中的世界杯 v3 模型流程，迁移生成 2026-07-05 韩职和瑞超竞彩预测。

## 输出

- `index.html`
- `20260705/index.html`
- `20260705/predict_20260705.html`
- `data/predictions_20260705.json`
- `data/sporttery_20260705.json`
- `data/sporttery_20260706.json`

## 数据源

- 赔率页面：https://m.sporttery.cn/mjc/jsq/zqzjq/
- 接口：`getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu`
- 模型参考：世界杯 v3 的 `knockout_prediction_model_v3.md`

2026-07-05 当前返回 6 场目标联赛比赛：韩职 3 场、瑞超 3 场。2026-07-06 当前 Sporttery 返回 2 场世界杯比赛，没有韩职或瑞超。

## 重跑

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fetch_sporttery.ps1 -Date 20260705 -OutFile .\data\sporttery_20260705.json -PoolCode "ttg,had,hhad,crs,hafu" -Force
powershell -ExecutionPolicy Bypass -File .\scripts\fetch_sporttery.ps1 -Date 20260706 -OutFile .\data\sporttery_20260706.json -PoolCode "ttg,had,hhad,crs,hafu" -Force
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\scripts\generate_kleague_allsvenskan_predictions.py
```

以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议。
