#!/usr/bin/env python3
"""
多求解器抽象层
统一接口支持 Gurobi、OR-Tools、CBC (PuLP)、SCIP (PySCIPOpt)。

自动检测可用求解器，用户代码无需修改即可切换。

用法:
    python solver_factory.py                      # 检测可用求解器
    python solver_factory.py --solver gurobi      # 指定求解器
    python solver_factory.py --list               # 列出所有求解器
    python solver_factory.py --example            # 生成示例代码

在代码中使用:
    from solver_factory import create_solver
    solver = create_solver("auto")  # 自动选择最佳可用求解器
    model = solver.create_model("my_problem")
    x = solver.add_var(model, "x", vtype="C", lb=0)
    solver.set_objective(model, x, "minimize")
    solver.add_constr(model, x >= 1, "c1")
    result = solver.solve(model)
"""

import sys
import json
import argparse
from typing import Any


# ============================================================
# 求解器定义
# ============================================================

SOLVERS = {
    "gurobi": {
        "name": "Gurobi",
        "package": "gurobipy",
        "install": "pip install gurobipy",
        "license": "商业许可证（免费学术版）",
        "strengths": "最快、最稳定、支持最全（MILP/QP/QCQP/NL/多目标）",
        "vtypes": {"C": "GRB.CONTINUOUS", "B": "GRB.BINARY", "I": "GRB.INTEGER"},
        "status_map": {
            "2": "OPTIMAL", "3": "INFEASIBLE", "4": "INF_OR_UNBD",
            "5": "UNBOUNDED", "9": "TIME_LIMIT", "6": "CUTOFF",
        },
    },
    "ortools": {
        "name": "OR-Tools (Google)",
        "package": "ortools",
        "install": "pip install ortools",
        "license": "Apache-2.0 (免费)",
        "strengths": "免费、CP-SAT 求解器擅长组合优化、支持 CP/SAT/线性",
        "vtypes": {"C": "CONTINUOUS", "B": "BINARY", "I": "INTEGER"},
        "status_map": {
            "1": "OPTIMAL", "2": "FEASIBLE", "3": "INFEASIBLE",
            "4": "UNBOUNDED", "6": "TIME_LIMIT",
        },
    },
    "pulp_cbc": {
        "name": "CBC (via PuLP)",
        "package": "pulp",
        "install": "pip install pulp",
        "license": "EPL-2.0 (免费，CBC 自带)",
        "strengths": "完全免费、开箱即用、适合中小规模 MILP",
        "vtypes": {"C": "LpContinuous", "B": "LpBinary", "I": "LpInteger"},
        "status_map": {
            "1": "Optimal", "-1": "Infeasible", "-2": "Unbounded",
            "0": "Not Solved", "-3": "Undefined",
        },
    },
    "scip": {
        "name": "SCIP (via PySCIPOpt)",
        "package": "pyscipopt",
        "install": "pip install pyscipopt",
        "license": "Apache-2.0 (免费，学术/非商业)",
        "strengths": "开源最强 MIP 求解器、支持非凸 MINLP",
        "vtypes": {"C": "CONTINUOUS", "B": "BINARY", "I": "INTEGER"},
        "status_map": {
            "optimal": "OPTIMAL", "infeasible": "INFEASIBLE",
            "unbounded": "UNBOUNDED", "timelimit": "TIME_LIMIT",
        },
    },
}

# 优先级：选择求解器的顺序
PRIORITY = ["gurobi", "scip", "ortools", "pulp_cbc"]


# ============================================================
# 求解器适配器
# ============================================================

class GurobiAdapter:
    """Gurobi 适配器"""

    @staticmethod
    def check():
        try:
            import gurobipy
            return True, f"v{'.'.join(str(x) for x in gurobipy.gurobi.version())}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_model(name: str):
        import gurobipy as gp
        return gp.Model(name)

    @staticmethod
    def add_var(model, name: str, vtype: str = "C", lb: float = 0, ub: float = float("inf")):
        import gurobipy as gp
        type_map = {"C": gp.GRB.CONTINUOUS, "B": gp.GRB.BINARY, "I": gp.GRB.INTEGER}
        return model.addVar(lb=lb, ub=ub, vtype=type_map.get(vtype, gp.GRB.CONTINUOUS), name=name)

    @staticmethod
    def add_vars(model, indices, name: str, vtype: str = "C", lb: float = 0):
        import gurobipy as gp
        type_map = {"C": gp.GRB.CONTINUOUS, "B": gp.GRB.BINARY, "I": gp.GRB.INTEGER}
        return model.addVars(indices, lb=lb, vtype=type_map.get(vtype, gp.GRB.CONTINUOUS), name=name)

    @staticmethod
    def set_objective(model, expr, sense: str = "minimize"):
        import gurobipy as gp
        model.setObjective(expr, gp.GRB.MINIMIZE if sense == "minimize" else gp.GRB.MAXIMIZE)

    @staticmethod
    def add_constr(model, expr, name: str = ""):
        model.addConstr(expr, name=name)

    @staticmethod
    def solve(model, time_limit: int = 60, mip_gap: float = 0.01, verbose: bool = False):
        import gurobipy as gp
        model.setParam("TimeLimit", time_limit)
        model.setParam("MIPGap", mip_gap)
        model.setParam("OutputFlag", 1 if verbose else 0)
        model.optimize()

        status_map = {
            gp.GRB.OPTIMAL: "OPTIMAL",
            gp.GRB.INFEASIBLE: "INFEASIBLE",
            gp.GRB.UNBOUNDED: "UNBOUNDED",
            gp.GRB.TIME_LIMIT: "TIME_LIMIT",
            gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
        }

        result = {
            "solver": "gurobi",
            "status": status_map.get(model.status, f"UNKNOWN({model.status})"),
            "objective": model.ObjVal if model.status in (gp.GRB.OPTIMAL, gp.GRB.SUBOPTIMAL) else None,
            "time": model.Runtime,
            "gap": model.MIPGap if model.status == gp.GRB.OPTIMAL else None,
            "variables": {},
        }

        if model.status in (gp.GRB.OPTIMAL, gp.GRB.SUBOPTIMAL):
            for v in model.getVars():
                if abs(v.X) > 1e-6:
                    result["variables"][v.VarName] = round(v.X, 6)

        return result


class ORToolsAdapter:
    """OR-Tools 适配器"""

    @staticmethod
    def check():
        try:
            from ortools.linear_solver import pywraplp
            return True, "installed"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_model(name: str):
        from ortools.linear_solver import pywraplp
        return pywraplp.Solver.CreateSolver("SCIP")  # 默认用 SCIP

    @staticmethod
    def add_var(model, name: str, vtype: str = "C", lb: float = 0, ub: float = float("inf")):
        from ortools.linear_solver import pywraplp
        if vtype == "B":
            return model.IntVar(0, 1, name)
        elif vtype == "I":
            return model.IntVar(lb, ub, name)
        else:
            return model.NumVar(lb, ub, name)

    @staticmethod
    def set_objective(model, expr, sense: str = "minimize"):
        if sense == "minimize":
            model.Minimize(expr)
        else:
            model.Maximize(expr)

    @staticmethod
    def add_constr(model, expr, name: str = ""):
        model.Add(expr)

    @staticmethod
    def solve(model, time_limit: int = 60, mip_gap: float = 0.01, verbose: bool = False):
        from ortools.linear_solver import pywraplp
        model.SetTimeLimit(time_limit * 1000)  # 毫秒

        status = model.Solve()

        status_map = {
            pywraplp.Solver.OPTIMAL: "OPTIMAL",
            pywraplp.Solver.FEASIBLE: "FEASIBLE",
            pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
            pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
        }

        result = {
            "solver": "ortools",
            "status": status_map.get(status, f"UNKNOWN({status})"),
            "objective": model.Objective().Value() if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else None,
            "time": model.wall_time() / 1000,
            "variables": {},
        }

        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            for var in model.variables():
                if abs(var.solution_value()) > 1e-6:
                    result["variables"][var.name()] = round(var.solution_value(), 6)

        return result


class PuLPAdapter:
    """PuLP + CBC 适配器"""

    @staticmethod
    def check():
        try:
            import pulp
            return True, f"v{pulp.__version__}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_model(name: str):
        import pulp
        return pulp.LpProblem(name, pulp.LpMinimize)

    @staticmethod
    def add_var(model, name: str, vtype: str = "C", lb: float = 0, ub: float = float("inf")):
        import pulp
        type_map = {"C": pulp.LpContinuous, "B": pulp.LpBinary, "I": pulp.LpInteger}
        cat = type_map.get(vtype, pulp.LpContinuous)
        if vtype == "B":
            return pulp.LpVariable(name, cat=cat)
        return pulp.LpVariable(name, lowBound=lb, upBound=ub, cat=cat)

    @staticmethod
    def set_objective(model, expr, sense: str = "minimize"):
        import pulp
        if sense == "minimize":
            model += expr  # PuLP 默认最小化
        else:
            model += -expr  # 取负实现最大化

    @staticmethod
    def add_constr(model, expr, name: str = ""):
        import pulp
        model += (expr, name) if name else expr

    @staticmethod
    def solve(model, time_limit: int = 60, mip_gap: float = 0.01, verbose: bool = False):
        import pulp
        solver = pulp.PULP_CBC_CMD(timeLimit=time_limit, gapRel=mip_gap, msg=verbose)
        status = model.solve(solver)

        status_str = pulp.LpStatus[status]

        result = {
            "solver": "pulp_cbc",
            "status": status_str,
            "objective": pulp.value(model.objective) if status == 1 else None,
            "time": model.solutionTime if hasattr(model, 'solutionTime') else None,
            "variables": {},
        }

        for v in model.variables():
            if abs(v.varValue or 0) > 1e-6:
                result["variables"][v.name] = round(v.varValue, 6)

        return result


class SCIPAdapter:
    """SCIP 适配器"""

    @staticmethod
    def check():
        try:
            import pyscipopt
            return True, "installed"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_model(name: str):
        from pyscipopt import Model
        return Model(name)

    @staticmethod
    def add_var(model, name: str, vtype: str = "C", lb: float = 0, ub: float = float("inf")):
        from pyscipopt import Model
        type_map = {"C": "CONTINUOUS", "B": "BINARY", "I": "INTEGER"}
        vtype_str = type_map.get(vtype, "CONTINUOUS")
        if vtype == "B":
            return model.addVar(name=name, vtype="BINARY")
        return model.addVar(name=name, vtype=vtype_str, lb=lb, ub=ub)

    @staticmethod
    def set_objective(model, expr, sense: str = "minimize"):
        if sense == "minimize":
            model.setObjective(expr, sense="minimize")
        else:
            model.setObjective(expr, sense="maximize")

    @staticmethod
    def add_constr(model, expr, name: str = ""):
        if name:
            model.addCons(expr, name=name)
        else:
            model.addCons(expr)

    @staticmethod
    def solve(model, time_limit: int = 60, mip_gap: float = 0.01, verbose: bool = False):
        model.setParam("limits/time", time_limit)
        model.setParam("limits/gap", mip_gap)
        model.setParam("display/verblevel", 4 if verbose else 0)
        model.optimize()

        status = model.getStatus()

        result = {
            "solver": "scip",
            "status": status.upper(),
            "objective": model.getObjVal() if status == "optimal" else None,
            "time": model.getSolvingTime(),
            "variables": {},
        }

        if status == "optimal":
            for v in model.getVars():
                val = model.getVal(v)
                if abs(val) > 1e-6:
                    result["variables"][v.name] = round(val, 6)

        return result


ADAPTERS = {
    "gurobi": GurobiAdapter,
    "ortools": ORToolsAdapter,
    "pulp_cbc": PuLPAdapter,
    "scip": SCIPAdapter,
}


# ============================================================
# 工厂函数
# ============================================================

def detect_available() -> list[dict]:
    """检测所有可用求解器"""
    results = []
    for sid in PRIORITY:
        info = SOLVERS[sid]
        adapter = ADAPTERS[sid]
        ok, detail = adapter.check()
        results.append({
            "id": sid,
            "name": info["name"],
            "available": ok,
            "detail": detail,
            "install": info["install"],
            "license": info["license"],
            "strengths": info["strengths"],
        })
    return results


def create_solver(solver_id: str = "auto"):
    """创建求解器实例
    solver_id: "auto", "gurobi", "ortools", "pulp_cbc", "scip"
    """
    if solver_id == "auto":
        for sid in PRIORITY:
            ok, _ = ADAPTERS[sid].check()
            if ok:
                return ADAPTERS[sid]
        raise RuntimeError("没有可用的求解器！请安装: pip install gurobipy 或 pip install pulp 或 pip install pyscipopt 或 pip install ortools")

    if solver_id not in ADAPTERS:
        raise ValueError(f"未知求解器: {solver_id}。可选: {', '.join(ADAPTERS.keys())}")

    ok, detail = ADAPTERS[solver_id].check()
    if not ok:
        raise RuntimeError(f"求解器 {solver_id} 不可用: {detail}。请安装: {SOLVERS[solver_id]['install']}")

    return ADAPTERS[solver_id]


def generate_example(solver_id: str = "gurobi") -> str:
    """生成指定求解器的示例代码"""
    if solver_id == "gurobi":
        return '''# Gurobi 示例
import gurobipy as gp
from gurobipy import GRB

model = gp.Model("example")
x = model.addVar(vtype=GRB.CONTINUOUS, name="x")
y = model.addVar(vtype=GRB.CONTINUOUS, name="y")
model.setObjective(x + 2*y, GRB.MINIMIZE)
model.addConstr(x + y >= 1, "c1")
model.addConstr(x <= 2, "c2")
model.optimize()

if model.status == GRB.OPTIMAL:
    print(f"x={x.X}, y={y.X}, obj={model.ObjVal}")
'''
    elif solver_id == "ortools":
        return '''# OR-Tools 示例
from ortools.linear_solver import pywraplp

solver = pywraplp.Solver.CreateSolver("SCIP")
x = solver.NumVar(0, solver.infinity(), "x")
y = solver.NumVar(0, solver.infinity(), "y")
solver.Minimize(x + 2*y)
solver.Add(x + y >= 1)
solver.Add(x <= 2)
status = solver.Solve()

if status == pywraplp.Solver.OPTIMAL:
    print(f"x={x.solution_value()}, y={y.solution_value()}, obj={solver.Objective().Value()}")
'''
    elif solver_id == "pulp_cbc":
        return '''# PuLP + CBC 示例
import pulp

model = pulp.LpProblem("example", pulp.LpMinimize)
x = pulp.LpVariable("x", lowBound=0)
y = pulp.LpVariable("y", lowBound=0)
model += x + 2*y
model += x + y >= 1
model += x <= 2
model.solve()

print(f"x={x.varValue}, y={y.varValue}, obj={pulp.value(model.objective)}")
'''
    elif solver_id == "scip":
        return '''# SCIP 示例
from pyscipopt import Model

model = Model("example")
x = model.addVar("x", vtype="CONTINUOUS", lb=0)
y = model.addVar("y", vtype="CONTINUOUS", lb=0)
model.setObjective(x + 2*y, sense="minimize")
model.addCons(x + y >= 1)
model.addCons(x <= 2)
model.optimize()

print(f"x={model.getVal(x)}, y={model.getVal(y)}, obj={model.getObjVal()}")
'''
    return ""


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="多求解器管理工具")
    parser.add_argument("--list", action="store_true", help="列出所有求解器及状态")
    parser.add_argument("--solver", "-s", help="指定求解器 (gurobi/ortools/pulp_cbc/scip)")
    parser.add_argument("--example", action="store_true", help="生成示例代码")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    if args.list:
        available = detect_available()
        if args.json:
            print(json.dumps(available, ensure_ascii=False, indent=2))
        else:
            print("📦 求解器状态:\n")
            for s in available:
                status = "✅" if s["available"] else "❌"
                print(f"  {status} {s['name']:20s} {s['detail']}")
                if not s["available"]:
                    print(f"     安装: {s['install']}")
                print(f"     许可: {s['license']}")
                print(f"     优势: {s['strengths']}")
                print()
        return

    if args.example:
        solver = args.solver or "gurobi"
        print(generate_example(solver))
        return

    # 自动选择
    solver_id = args.solver or "auto"
    try:
        adapter = create_solver(solver_id)
        print(f"✅ 使用求解器: {solver_id}")
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
