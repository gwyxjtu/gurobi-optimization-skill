# Step 4: 代码生成 (Code Generation)

## 目标
根据数学模型生成可运行的 Gurobi Python 代码。

## 代码结构规范

所有生成的代码必须遵循以下结构：

```python
#!/usr/bin/env python3
"""
{问题名} 优化模型
问题类型: {LP/MILP/QP/...}
生成时间: {YYYY-MM-DD HH:MM:SS}
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import json
import os
from datetime import datetime

# ============================================================
# 1. 数据加载
# ============================================================
def load_data(data_path: str) -> dict:
    """加载输入数据"""
    # 根据数据格式选择加载方式
    ...

# ============================================================
# 2. 模型构建
# ============================================================
def build_model(data: dict) -> gp.Model:
    """构建优化模型"""
    model = gp.Model("{问题名}")

    # --- 决策变量 ---
    x = model.addVars(I, J, T, vtype=GRB.CONTINUOUS, name="x")
    y = model.addVars(J, T, vtype=GRB.BINARY, name="y")

    # --- 目标函数 ---
    model.setObjective(
        gp.quicksum(cost[i,j] * x[i,j,t] for i in I for j in J for t in T)
        + gp.quicksum(fixed_cost[j] * y[j,t] for j in J for t in T),
        GRB.MINIMIZE
    )

    # --- 约束条件 ---
    # 约束1: 需求满足
    for i in I:
        for t in T:
            model.addConstr(
                gp.quicksum(x[i,j,t] for j in J) >= demand[i,t],
                name=f"demand_{i}_{t}"
            )

    # 约束2: 产能限制
    for j in J:
        for t in T:
            model.addConstr(
                gp.quicksum(x[i,j,t] for i in I) <= capacity[j] * y[j,t],
                name=f"capacity_{j}_{t}"
            )

    return model

# ============================================================
# 3. 求解
# ============================================================
def solve_model(model: gp.Model, time_limit: int = 60, mip_gap: float = 0.01) -> dict:
    """求解模型并返回结果"""
    model.setParam("TimeLimit", time_limit)
    model.setParam("MIPGap", mip_gap)
    model.optimize()

    results = {
        "status": model.status,
        "status_text": _status_text(model.status),
        "objective_value": None,
        "variables": {},
        "solve_time": model.Runtime,
        "mip_gap": model.MIPGap if model.status == GRB.OPTIMAL else None,
    }

    if model.status in (GRB.OPTIMAL, GRB.SUBOPTIMAL):
        results["objective_value"] = model.ObjVal
        for v in model.getVars():
            if v.X != 0:  # 只记录非零变量
                results["variables"][v.VarName] = {
                    "value": round(v.X, 6),
                    "lb": v.LB,
                    "ub": v.UB,
                    "rc": round(v.RC, 6) if hasattr(v, 'RC') else None,
                }

    return results

# ============================================================
# 4. 结果输出
# ============================================================
def save_results(results: dict, output_dir: str):
    """保存结果到文件"""
    os.makedirs(output_dir, exist_ok=True)

    # JSON 格式
    with open(os.path.join(output_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 可读文本
    with open(os.path.join(output_dir, "results.txt"), "w", encoding="utf-8") as f:
        f.write(f"求解状态: {results['status_text']}\n")
        f.write(f"目标函数值: {results['objective_value']}\n")
        f.write(f"求解时间: {results['solve_time']:.2f}s\n")
        f.write(f"MIP Gap: {results['mip_gap']}\n\n")
        f.write("决策变量取值:\n")
        for name, info in results["variables"].items():
            f.write(f"  {name} = {info['value']}\n")

    print(f"✅ 结果已保存到 {output_dir}/")

# ============================================================
# 5. 辅助函数
# ============================================================
def _status_text(status: int) -> str:
    mapping = {
        GRB.OPTIMAL: "最优解",
        GRB.INFEASIBLE: "不可行",
        GRB.INF_OR_UNBD: "不可行或无界",
        GRB.UNBOUNDED: "无界",
        GRB.SUBOPTIMAL: "次优解",
        GRB.TIME_LIMIT: "达到时间限制",
        GRB.NODE_LIMIT: "达到节点限制",
        GRB.SOLUTION_LIMIT: "达到解数量限制",
        GRB.INTERRUPTED: "中断",
    }
    return mapping.get(status, f"未知状态({status})")

# ============================================================
# 主程序
# ============================================================
if __name__ == "__main__":
    # 配置
    DATA_PATH = "data.csv"
    OUTPUT_DIR = "outputs/{问题名}"
    TIME_LIMIT = 60
    MIP_GAP = 0.01

    # 执行
    data = load_data(DATA_PATH)
    model = build_model(data)
    results = solve_model(model, TIME_LIMIT, MIP_GAP)
    save_results(results, OUTPUT_DIR)
```

## 代码质量要求

1. **注释**：每个变量、约束、目标都要有中文注释
2. **命名**：变量名和约束名要有意义（如 `demand_i_t` 而非 `c0`）
3. **模块化**：数据加载、模型构建、求解、结果输出分离
4. **错误处理**：检查求解状态，处理不可行/无界等情况
5. **可配置**：时间限制、gap 容差等参数要可配置
6. **输出**：同时保存 JSON（程序可读）和 TXT（人类可读）

## 输出文件
将代码写入 `outputs/{问题名}/model.py`。
