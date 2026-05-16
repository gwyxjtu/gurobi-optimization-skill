#!/usr/bin/env python3
"""
数据验证工具
在建模前检查用户提供的数据文件是否完整、格式正确。
确保所有业务数据都来自用户，不是 Agent 编造的。

用法:
    python data_validator.py --data data.csv --required "需求量,单位成本,产能"
    python data_validator.py --data data.xlsx --sheet Sheet1 --required "cost,demand,capacity"
    python data_validator.py --check-params "c_ij,d_it,K_j" --data data.csv
"""

import sys
import json
import argparse
from pathlib import Path


def validate_file_exists(data_path: str) -> dict:
    """检查数据文件是否存在"""
    p = Path(data_path)
    if not p.exists():
        return {
            "status": "❌",
            "error": f"数据文件不存在: {data_path}",
            "action": "请用户提供数据文件，或指定正确的文件路径",
        }
    if p.stat().st_size == 0:
        return {
            "status": "❌",
            "error": f"数据文件为空: {data_path}",
            "action": "请检查文件内容",
        }
    return {"status": "✅", "path": str(p.resolve()), "size": p.stat().st_size}


def validate_csv(data_path: str, required_fields: list[str] = None) -> dict:
    """验证 CSV 文件"""
    import pandas as pd

    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"status": "❌", "error": f"CSV 解析失败: {e}"}

    result = {
        "status": "✅",
        "rows": len(df),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": {col: int(cnt) for col, cnt in df.isnull().sum().items() if cnt > 0},
        "preview": df.head(3).to_dict(orient="records"),
    }

    # 检查必需字段
    if required_fields:
        missing = [f for f in required_fields if f not in df.columns]
        if missing:
            result["status"] = "⚠️"
            result["missing_fields"] = missing
            result["action"] = f"缺少必需字段: {missing}。请检查数据文件或调整字段名映射。"

    return result


def validate_excel(data_path: str, sheet: str = None, required_fields: list[str] = None) -> dict:
    """验证 Excel 文件"""
    import pandas as pd

    try:
        xls = pd.ExcelFile(data_path)
        sheets = xls.sheet_names
    except Exception as e:
        return {"status": "❌", "error": f"Excel 解析失败: {e}"}

    target_sheet = sheet or sheets[0]
    try:
        df = pd.read_excel(data_path, sheet_name=target_sheet)
    except Exception as e:
        return {"status": "❌", "error": f"读取工作表 '{target_sheet}' 失败: {e}"}

    result = {
        "status": "✅",
        "sheets": sheets,
        "active_sheet": target_sheet,
        "rows": len(df),
        "columns": list(df.columns),
        "missing_values": {col: int(cnt) for col, cnt in df.isnull().sum().items() if cnt > 0},
        "preview": df.head(3).to_dict(orient="records"),
    }

    if required_fields:
        missing = [f for f in required_fields if f not in df.columns]
        if missing:
            result["status"] = "⚠️"
            result["missing_fields"] = missing
            result["action"] = f"缺少必需字段: {missing}"

    return result


def validate_json(data_path: str, required_keys: list[str] = None) -> dict:
    """验证 JSON 文件"""
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "❌", "error": f"JSON 解析失败: {e}"}

    result = {
        "status": "✅",
        "type": type(data).__name__,
    }

    if isinstance(data, dict):
        result["keys"] = list(data.keys())
        if required_keys:
            missing = [k for k in required_keys if k not in data]
            if missing:
                result["status"] = "⚠️"
                result["missing_keys"] = missing
                result["action"] = f"缺少必需键: {missing}"
    elif isinstance(data, list):
        result["count"] = len(data)
        if data and isinstance(data[0], dict):
            result["item_keys"] = list(data[0].keys())

    return result


def generate_data_requirement_prompt(required_params: dict) -> str:
    """生成数据需求提示，让用户知道需要提供什么数据"""

    lines = []
    lines.append("建模需要以下数据，请提供：\n")
    lines.append("| 参数 | 含义 | 格式要求 | 示例 |")
    lines.append("|------|------|---------|------|")

    for param, info in required_params.items():
        name = info.get("name", param)
        desc = info.get("desc", "待说明")
        fmt = info.get("format", "数值")
        example = info.get("example", "—")
        lines.append(f"| {param} | {desc} | {fmt} | {example} |")

    lines.append("")
    lines.append("请以 Excel/CSV/JSON 文件形式提供，或直接在对话中给出具体数值。")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="优化建模数据验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --data data.csv --required "需求量,单位成本,产能"
  %(prog)s --data data.xlsx --sheet Sheet1 --required "cost,demand"
  %(prog)s --data params.json --required "c_ij,d_it,K_j"
  %(prog)s --prompt --params '{"d_it":{"name":"需求量","desc":"产品i在周期t的需求","format":"数值矩阵","example":"[[100,150],[200,180]]"}}'
        """,
    )
    parser.add_argument("--data", "-d", help="数据文件路径 (.csv/.xlsx/.json)")
    parser.add_argument("--required", "-r", help="必需字段列表（逗号分隔）")
    parser.add_argument("--sheet", "-s", help="Excel 工作表名")
    parser.add_argument("--prompt", action="store_true", help="生成数据需求提示")
    parser.add_argument("--params", help="参数定义 JSON（用于 --prompt 模式）")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    # 生成数据需求提示
    if args.prompt:
        if not args.params:
            print("❌ --prompt 模式需要 --params 参数")
            sys.exit(1)
        params = json.loads(args.params)
        print(generate_data_requirement_prompt(params))
        return

    if not args.data:
        parser.print_help()
        return

    # 验证文件
    file_check = validate_file_exists(args.data)
    if file_check["status"] != "✅":
        print(json.dumps(file_check, ensure_ascii=False, indent=2))
        sys.exit(1)

    required = [f.strip() for f in args.required.split(",")] if args.required else None
    ext = Path(args.data).suffix.lower()

    if ext == ".csv":
        result = validate_csv(args.data, required)
    elif ext in (".xlsx", ".xls"):
        result = validate_excel(args.data, args.sheet, required)
    elif ext == ".json":
        result = validate_json(args.data, required)
    else:
        result = {"status": "❌", "error": f"不支持的文件格式: {ext}"}

    # 输出
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"📊 数据验证: {args.data}\n")
        print(f"  状态: {result['status']}")

        if "error" in result:
            print(f"  错误: {result['error']}")
        if "action" in result:
            print(f"  建议: {result['action']}")
        if "rows" in result:
            print(f"  行数: {result['rows']}")
        if "columns" in result:
            print(f"  列名: {', '.join(result['columns'])}")
        if "missing_values" in result and result["missing_values"]:
            print(f"  缺失值: {result['missing_values']}")
        if "missing_fields" in result:
            print(f"  ❌ 缺少字段: {', '.join(result['missing_fields'])}")
        if "preview" in result:
            print(f"\n  前 3 行预览:")
            for i, row in enumerate(result["preview"]):
                print(f"    [{i}] {row}")

        # 关键提示
        if result["status"] == "✅":
            print(f"\n  ✅ 数据验证通过，可以开始建模")
            print(f"  📌 数据来源: {args.data}（用户提供的文件）")
        else:
            print(f"\n  ⚠️ 数据存在问题，请修正后再继续建模")


if __name__ == "__main__":
    main()
