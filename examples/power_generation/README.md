# Power Generation

**来源**: [Gurobi/modeling-examples](https://github.com/Gurobi/modeling-examples) — power_generation
**问题类型**: MILP
**描述**: 电力调度（MILP）— 机组组合与发电成本最小化

## 数据文件
- `demand.csv`
- `small_plant_data/plant_capacities.csv`
- `small_plant_data/fuel_costs.csv`
- `small_plant_data/operating_costs.csv`
- `small_plant_data/startup_costs.csv`

## 用法
```python
# 加载数据
import pandas as pd
data = pd.read_csv("data/demand.csv")
```

## 许可证
Apache-2.0 (Gurobi/modeling-examples)
