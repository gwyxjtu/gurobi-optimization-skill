#!/usr/bin/env python3
"""
模型验证工具
求解后自动检查模型结果的合理性。

检查项：
  1. 求解状态是否最优
  2. 目标函数值是否在合理范围
  3. 约束松弛是否为 0（硬约束必须满足）
  4. 变量值是否符合物理意义（非负、整数、边界）
  5. 质量守恒检查（如适用）
  6. 数值稳定性（是否有极大/极小值、NaN）

用法:
    python model_validator.py --results results.json
    python model_validator.py --results results.json --model model.py
    python model_validator.py --lp model.lp
"""

import sys
import json
import argparse
import re
import math
from pathlib import Path


# ============================================================
# 检查函数
# ============================================================

def check_solve_status(results: dict) -> dict:
    """检查求解状态"""
    status = results.get("status", results.get("status_text", "未知"))
    status_str = str(status).upper()

    if "OPTIMAL" in status_str or "最优" in status_str:
        return {"pass": True, "level": "✅", "msg": f"求解状态: {status} (最优解)"}
    elif "INFEASIBLE" in status_str or "不可行" in status_str:
        return {"pass": False, "level": "❌", "msg": f"求解状态: {status} — 模型不可行！请检查约束是否矛盾，或使用 computeIIS() 找出冲突约束"}
    elif "UNBOUNDED" in status_str or "无界" in status_str:
        return {"pass": False, "level": "❌", "msg": f"求解状态: {status} — 目标函数无界！请检查是否缺少约束"}
    elif "TIME_LIMIT" in status_str or "时间" in status_str:
        sol_count = results.get("sol_count", results.get("SolCount", 0))
        if sol_count and sol_count > 0:
            return {"pass": True, "level": "⚠️", "msg": f"求解状态: {status} — 有可行解但未证明最优 (SolCount={sol_count})"}
        else:
            return {"pass": False, "level": "❌", "msg": f"求解状态: {status} — 无可行解，建议增加时间限制或检查模型"}
    else:
        return {"pass": True, "level": "⚠️", "msg": f"求解状态: {status} — 请人工确认结果有效性"}


def check_objective_value(results: dict, bounds: dict = None) -> dict:
    """检查目标函数值是否合理"""
    obj = results.get("objective_value", results.get("objective", None))

    if obj is None:
        return {"pass": False, "level": "❌", "msg": "目标函数值为空 — 求解可能未成功"}

    checks = []

    # 检查 NaN/Inf
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return {"pass": False, "level": "❌", "msg": f"目标函数值为 {obj} — 数值异常，模型可能有数值问题"}

    # 检查是否为 0（可能是退化解）
    if obj == 0:
        checks.append("目标函数值为 0 — 请确认是否为退化解")

    # 检查是否为负（取决于问题类型）
    if obj < 0:
        checks.append(f"目标函数值为负 ({obj:,.4f}) — 请确认是否有意义")

    # 检查是否极大（可能是数值溢出）
    if abs(obj) > 1e12:
        checks.append(f"目标函数值极大 ({obj:,.2e}) — 请检查是否有数值溢出")

    # 用户提供的合理范围
    if bounds:
        lb = bounds.get("lower", float("-inf"))
        ub = bounds.get("upper", float("inf"))
        if obj < lb:
            return {"pass": False, "level": "❌", "msg": f"目标函数值 {obj:,.4f} 低于预期下界 {lb:,.4f}"}
        if obj > ub:
            return {"pass": False, "level": "❌", "msg": f"目标函数值 {obj:,.4f} 超过预期上界 {ub:,.4f}"}

    if checks:
        return {"pass": True, "level": "⚠️", "msg": f"目标函数值: {obj:,.4f} — " + "; ".join(checks)}

    return {"pass": True, "level": "✅", "msg": f"目标函数值: {obj:,.4f}"}


def check_gap(results: dict, max_gap: float = 0.01) -> dict:
    """检查 MIP Gap"""
    gap = results.get("mip_gap", results.get("gap", None))

    if gap is None:
        return {"pass": True, "level": "ℹ️", "msg": "无 MIP Gap 信息（可能是 LP 问题）"}

    if isinstance(gap, float) and (math.isnan(gap) or math.isinf(gap)):
        return {"pass": True, "level": "⚠️", "msg": f"MIP Gap: {gap} — 可能是 LP 或求解未完成"}

    gap_pct = gap * 100 if gap < 1 else gap  # 兼容百分比和小数

    if gap_pct <= max_gap * 100:
        return {"pass": True, "level": "✅", "msg": f"MIP Gap: {gap_pct:.4f}% (容差: {max_gap*100}%)"}
    elif gap_pct <= 1.0:
        return {"pass": True, "level": "⚠️", "msg": f"MIP Gap: {gap_pct:.4f}% — 偏大，建议降低 MIPGap 参数或增加求解时间"}
    else:
        return {"pass": False, "level": "❌", "msg": f"MIP Gap: {gap_pct:.4f}% — 过大，解质量不可靠！建议增加 TimeLimit 或调整 MIPFocus"}


def check_variables(results: dict) -> dict:
    """检查变量值的合理性"""
    variables = results.get("variables", results.get("schedule", {}))

    if not variables:
        return {"pass": True, "level": "ℹ️", "msg": "无变量数据"}

    issues = []
    stats = {"total": 0, "zero": 0, "negative": 0, "very_large": 0, "fractional_integer": 0}

    items = variables if isinstance(variables, dict) else {
        v.get("variable", v.get("name", f"var_{i}")): v.get("value", v.get("val", 0))
        for i, v in enumerate(variables)
    }

    for name, val in items.items():
        if isinstance(val, dict):
            val = val.get("value", 0)

        stats["total"] += 1

        if abs(val) < 1e-6:
            stats["zero"] += 1
        elif val < 0:
            stats["negative"] += 1
            if stats["negative"] <= 3:
                issues.append(f"  负值变量: {name} = {val:,.6f}")

        if abs(val) > 1e10:
            stats["very_large"] += 1
            if stats["very_large"] <= 3:
                issues.append(f"  极大变量: {name} = {val:,.2e}")

        # 检查整数变量是否有小数（可能是数值误差）
        if "int" in name.lower() or "bin" in name.lower() or "y[" in name or "z[" in name:
            if abs(val - round(val)) > 1e-4:
                stats["fractional_integer"] += 1
                if stats["fractional_integer"] <= 3:
                    issues.append(f"  整数变量有小数: {name} = {val:,.6f} (应为 {round(val)})")

    msg_parts = [f"变量总数: {stats['total']}, 非零: {stats['total'] - stats['zero']}"]

    if stats["negative"] > 0:
        msg_parts.append(f"负值: {stats['negative']}")
    if stats["very_large"] > 0:
        msg_parts.append(f"极大值: {stats['very_large']}")
    if stats["fractional_integer"] > 0:
        msg_parts.append(f"整数变量小数: {stats['fractional_integer']}")

    if issues:
        msg_parts.append("问题:\n" + "\n".join(issues))

    has_issue = stats["very_large"] > 0 or stats["fractional_integer"] > 3
    level = "❌" if has_issue else ("⚠️" if (stats["negative"] > 0 or stats["fractional_integer"] > 0) else "✅")

    return {"pass": not has_issue, "level": level, "msg": "; ".join(msg_parts)}


def check_constraints(results: dict) -> dict:
    """检查约束松弛"""
    # 从 LP 文件或结果中提取约束信息
    constraints = results.get("constraints", {})

    if not constraints:
        return {"pass": True, "level": "ℹ️", "msg": "无约束松弛数据（需从模型中提取）"}

    violated = []
    for name, info in constraints.items():
        slack = info.get("slack", info.get("Slack", None))
        if slack is not None and slack < -1e-6:
            violated.append(f"  {name}: slack = {slack:,.6f}")

    if violated:
        return {
            "pass": False,
            "level": "❌",
            "msg": f"有 {len(violated)} 个约束被违反:\n" + "\n".join(violated[:5])
        }

    return {"pass": True, "level": "✅", "msg": "所有约束满足 (slack ≥ 0)"}


def check_solve_time(results: dict) -> dict:
    """检查求解时间"""
    t = results.get("solve_time", results.get("time", results.get("Runtime", None)))

    if t is None:
        return {"pass": True, "level": "ℹ️", "msg": "无求解时间信息"}

    if t < 1:
        return {"pass": True, "level": "✅", "msg": f"求解时间: {t:.2f}s (非常快)"}
    elif t < 60:
        return {"pass": True, "level": "✅", "msg": f"求解时间: {t:.1f}s"}
    elif t < 300:
        return {"pass": True, "level": "⚠️", "msg": f"求解时间: {t:.0f}s ({t/60:.1f}分钟) — 较慢，考虑调整参数"}
    else:
        return {"pass": True, "level": "⚠️", "msg": f"求解时间: {t:.0f}s ({t/60:.1f}分钟) — 很慢，建议调整 Presolve/Method/MIPFocus"}


def check_mass_balance(results: dict) -> dict:
    """质量守恒检查（如果有总和数据）"""
    variables = results.get("variables", results.get("schedule", {}))

    if not variables or not isinstance(variables, dict):
        return {"pass": True, "level": "ℹ️", "msg": "跳过质量守恒检查"}

    # 尝试检测是否有百分比类变量（占比之和应为 100%）
    pct_vars = {k: v.get("value", v) if isinstance(v, dict) else v
                for k, v in variables.items()
                if "pct" in k.lower() or "ratio" in k.lower() or "share" in k.lower()}

    if pct_vars:
        total = sum(pct_vars.values())
        if abs(total - 100) < 1:
            return {"pass": True, "level": "✅", "msg": f"百分比变量总和: {total:.2f}% ≈ 100%"}
        elif abs(total - 1.0) < 0.01:
            return {"pass": True, "level": "✅", "msg": f"比例变量总和: {total:.4f} ≈ 1.0"}
        else:
            return {"pass": True, "level": "⚠️", "msg": f"比例/百分比变量总和: {total:.4f} — 请确认是否合理"}

    return {"pass": True, "level": "ℹ️", "msg": "无百分比类变量，跳过守恒检查"}


# ============================================================
# 主验证函数
# ============================================================

def validate(results: dict, obj_bounds: dict = None, max_gap: float = 0.01) -> dict:
    """执行全部验证检查"""
    checks = [
        ("求解状态", check_solve_status(results)),
        ("目标函数值", check_objective_value(results, obj_bounds)),
        ("MIP Gap", check_gap(results, max_gap)),
        ("变量值", check_variables(results)),
        ("约束满足", check_constraints(results)),
        ("求解时间", check_solve_time(results)),
        ("质量守恒", check_mass_balance(results)),
    ]

    all_pass = all(c["pass"] for _, c in checks)

    return {
        "all_pass": all_pass,
        "summary": "✅ 全部通过" if all_pass else "⚠️ 存在问题，请检查下方详情",
        "checks": checks,
    }


def format_report(validation: dict) -> str:
    """格式化验证报告"""
    lines = []
    lines.append("=" * 50)
    lines.append("  模型验证报告")
    lines.append("=" * 50)
    lines.append("")

    for name, check in validation["checks"]:
        lines.append(f"  {check['level']} {name}")
        lines.append(f"     {check['msg']}")
        lines.append("")

    lines.append("-" * 50)
    lines.append(f"  {validation['summary']}")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gurobi 模型验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --results results.json
  %(prog)s --results results.json --obj-bounds '{"lower":0,"upper":100000}'
  %(prog)s --results results.json --max-gap 0.05 --json
        """,
    )
    parser.add_argument("--results", "-r", required=True, help="求解结果 JSON 文件")
    parser.add_argument("--obj-bounds", help="目标函数合理范围 JSON (如 '{\"lower\":0,\"upper\":100000}')")
    parser.add_argument("--max-gap", type=float, default=0.01, help="MIP Gap 容差 (默认 0.01 = 1%%)")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    # 加载结果
    with open(args.results, "r", encoding="utf-8") as f:
        results = json.load(f)

    # 目标函数范围
    obj_bounds = json.loads(args.obj_bounds) if args.obj_bounds else None

    # 验证
    validation = validate(results, obj_bounds, args.max_gap)

    # 输出
    if args.json:
        output = {
            "all_pass": validation["all_pass"],
            "summary": validation["summary"],
            "checks": [
                {"name": name, **check}
                for name, check in validation["checks"]
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(validation))

    sys.exit(0 if validation["all_pass"] else 1)


if __name__ == "__main__":
    main()
