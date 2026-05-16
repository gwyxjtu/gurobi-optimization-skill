# Facility Location

**来源**: [Gurobi/modeling-examples](https://github.com/Gurobi/modeling-examples) — optimization101/Modeling_Session_2
**问题类型**: MILP
**描述**: 设施选址+太阳能面板优化（MILP）— 建筑需求与供应匹配

## 数据文件
- `building_demand.csv`
- `expected_price.csv`
- `SolarPanel.csv`
- `schedule_demand.csv`
- `pred_solar_values.csv`

## 用法
```python
# 加载数据
import pandas as pd
data = pd.read_csv("data/building_demand.csv")
```

## 许可证
Apache-2.0 (Gurobi/modeling-examples)
