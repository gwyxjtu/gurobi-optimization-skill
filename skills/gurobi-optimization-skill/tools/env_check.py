#!/usr/bin/env python3
"""
环境检查工具
检查 Gurobi 许可证、Python 依赖是否就绪。
"""

import sys
import subprocess
import json


def check_python_version():
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 9
    return {
        "name": "Python",
        "status": "✅" if ok else "❌",
        "detail": f"{v.major}.{v.minor}.{v.micro}",
        "required": ">= 3.9",
    }


def check_gurobi():
    try:
        import gurobipy as gp
        from gurobipy import GRB

        # 尝试获取版本
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()
        m = gp.Model(env=env)
        version = ".".join(str(x) for x in gp.gurobi.version())

        # 检查许可证类型
        license_type = "unknown"
        try:
            # 简单测试：创建一个小模型
            x = m.addVar(name="test")
            m.setObjective(x, GRB.MINIMIZE)
            m.addConstr(x >= 1)
            m.optimize()
            license_type = "valid"
        except gp.GurobiError as e:
            if "license" in str(e).lower():
                license_type = "expired_or_invalid"
            else:
                license_type = f"error: {e}"

        m.dispose()
        env.dispose()

        return {
            "name": "Gurobi",
            "status": "✅" if license_type == "valid" else "⚠️",
            "detail": f"v{version}, license={license_type}",
            "required": ">= 11.0",
        }
    except ImportError:
        return {
            "name": "Gurobi",
            "status": "❌",
            "detail": "未安装",
            "required": "pip install gurobipy",
        }
    except Exception as e:
        return {
            "name": "Gurobi",
            "status": "❌",
            "detail": str(e),
            "required": "检查许可证配置",
        }


def check_pandas():
    try:
        import pandas as pd

        return {
            "name": "pandas",
            "status": "✅",
            "detail": f"v{pd.__version__}",
            "required": ">= 1.5",
        }
    except ImportError:
        return {
            "name": "pandas",
            "status": "⚠️",
            "detail": "未安装（可选，用于数据加载）",
            "required": "pip install pandas",
        }


def check_openpyxl():
    try:
        import openpyxl

        return {
            "name": "openpyxl",
            "status": "✅",
            "detail": f"v{openpyxl.__version__}",
            "required": ">= 3.0（读写 Excel）",
        }
    except ImportError:
        return {
            "name": "openpyxl",
            "status": "⚠️",
            "detail": "未安装（可选，用于读取 .xlsx）",
            "required": "pip install openpyxl",
        }


def check_matplotlib():
    try:
        import matplotlib

        return {
            "name": "matplotlib",
            "status": "✅",
            "detail": f"v{matplotlib.__version__}",
            "required": ">= 3.5（可选，结果可视化）",
        }
    except ImportError:
        return {
            "name": "matplotlib",
            "status": "⚠️",
            "detail": "未安装（可选）",
            "required": "pip install matplotlib",
        }


def main():
    checks = [
        check_python_version(),
        check_gurobi(),
        check_pandas(),
        check_openpyxl(),
        check_matplotlib(),
    ]

    print("=" * 50)
    print("  Gurobi 优化建模环境检查")
    print("=" * 50)
    print()

    all_ok = True
    for c in checks:
        print(f"  {c['status']} {c['name']:15s}  {c['detail']}")
        if c["status"] == "❌":
            all_ok = False
            print(f"     → 需要: {c['required']}")

    print()
    if all_ok:
        print("✅ 环境就绪，可以开始建模！")
    else:
        print("❌ 环境不完整，请先安装缺失依赖。")
        print("   运行: pip install -r requirements.txt")

    # 输出 JSON 格式（供 Agent 解析）
    print("\n--- JSON ---")
    print(json.dumps(checks, ensure_ascii=False, indent=2))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
