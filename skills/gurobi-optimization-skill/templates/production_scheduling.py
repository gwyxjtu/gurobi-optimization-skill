#!/usr/bin/env python3
"""
生产排程优化模型模板
问题类型: MILP
场景: 多工厂、多产品、多周期生产计划

用法:
    python production_scheduling.py --data data.csv --output outputs/
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import json
import os
from datetime import datetime


def load_data(data_path: str) -> dict:
    """加载生产数据"""
    if data_path.endswith(".csv"):
        df = pd.read_csv(data_path)
    elif data_path.endswith(".xlsx"):
        df = pd.read_excel(data_path)
    else:
        raise ValueError(f"不支持的文件格式: {data_path}")

    # 示例数据结构（根据实际数据调整）
    data = {
        "products": df["product"].unique().tolist(),
        "factories": df["factory"].unique().tolist(),
        "periods": sorted(df["period"].unique().tolist()),
        "demand": {(r["product"], r["period"]): r["demand"] for _, r in df.iterrows()},
        "cost": {(r["product"], r["factory"]): r["unit_cost"] for _, r in df.iterrows()},
        "capacity": {r["factory"]: r["capacity"] for _, r in df.drop_duplicates("factory").iterrows()},
        "fixed_cost": {r["factory"]: r["fixed_cost"] for _, r in df.drop_duplicates("factory").iterrows()},
    }
    return data


def build_model(data: dict) -> gp.Model:
    """构建生产排程 MILP 模型"""
    model = gp.Model("ProductionScheduling")

    I = data["products"]   # 产品
    J = data["factories"]  # 工厂
    T = data["periods"]    # 周期

    # --- 决策变量 ---
    # x[i,j,t] = 产品i在工厂j周期t的生产量
    x = model.addVars(I, J, T, vtype=GRB.CONTINUOUS, lb=0, name="produce")
    # y[j,t] = 工厂j在周期t是否开工
    y = model.addVars(J, T, vtype=GRB.BINARY, name="open")

    # --- 目标函数: 最小化总成本 ---
    production_cost = gp.quicksum(
        data["cost"][i, j] * x[i, j, t]
        for i in I for j in J for t in T
    )
    fixed_cost = gp.quicksum(
        data["fixed_cost"][j] * y[j, t]
        for j in J for t in T
    )
    model.setObjective(production_cost + fixed_cost, GRB.MINIMIZE)

    # --- 约束条件 ---
    # 1. 需求必须满足
    for i in I:
        for t in T:
            model.addConstr(
                gp.quicksum(x[i, j, t] for j in J) >= data["demand"].get((i, t), 0),
                name=f"demand_{i}_{t}"
            )

    # 2. 产能上限
    for j in J:
        for t in T:
            model.addConstr(
                gp.quicksum(x[i, j, t] for i in I) <= data["capacity"][j] * y[j, t],
                name=f"capacity_{j}_{t}"
            )

    # 3. 逻辑约束: 生产则必须开工 (大M法)
    M = max(data["capacity"].values())
    for i in I:
        for j in J:
            for t in T:
                model.addConstr(
                    x[i, j, t] <= M * y[j, t],
                    name=f"logic_{i}_{j}_{t}"
                )

    return model


def solve_model(model: gp.Model, time_limit: int = 60, mip_gap: float = 0.01) -> dict:
    """求解模型"""
    model.setParam("TimeLimit", time_limit)
    model.setParam("MIPGap", mip_gap)
    model.optimize()

    status_map = {
        GRB.OPTIMAL: "最优解",
        GRB.INFEASIBLE: "不可行",
        GRB.UNBOUNDED: "无界",
        GRB.TIME_LIMIT: "达到时间限制",
    }

    results = {
        "status": status_map.get(model.status, f"未知({model.status})"),
        "objective": model.ObjVal if model.status in (GRB.OPTIMAL, GRB.SUBOPTIMAL) else None,
        "time": round(model.Runtime, 2),
        "gap": round(model.MIPGap, 4) if model.status == GRB.OPTIMAL else None,
        "schedule": [],
    }

    if model.status in (GRB.OPTIMAL, GRB.SUBOPTIMAL):
        for v in model.getVars():
            if v.X > 1e-6:
                results["schedule"].append({
                    "variable": v.VarName,
                    "value": round(v.X, 2),
                })

    return results


def save_results(results: dict, output_dir: str):
    """保存结果"""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")

    # JSON
    with open(os.path.join(output_dir, f"results_{ts}.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 可读报告
    with open(os.path.join(output_dir, f"report_{ts}.txt"), "w") as f:
        f.write(f"生产排程优化结果\n{'='*40}\n\n")
        f.write(f"求解状态: {results['status']}\n")
        f.write(f"目标函数值 (总成本): {results['objective']:,.2f}\n")
        f.write(f"求解时间: {results['time']}s\n")
        f.write(f"MIP Gap: {results['gap']}\n\n")
        f.write(f"排程方案 ({len(results['schedule'])} 个非零变量):\n")
        f.write("-" * 40 + "\n")
        for item in results["schedule"]:
            f.write(f"  {item['variable']:30s} = {item['value']:,.2f}\n")

    print(f"✅ 结果已保存到 {output_dir}/")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生产排程优化")
    parser.add_argument("--data", required=True, help="数据文件路径 (.csv/.xlsx)")
    parser.add_argument("--output", default="outputs/scheduling", help="输出目录")
    parser.add_argument("--time-limit", type=int, default=60, help="求解时间限制(秒)")
    parser.add_argument("--mip-gap", type=float, default=0.01, help="MIP Gap 容差")
    args = parser.parse_args()

    data = load_data(args.data)
    model = build_model(data)
    results = solve_model(model, args.time_limit, args.mip_gap)
    save_results(results, args.output)
