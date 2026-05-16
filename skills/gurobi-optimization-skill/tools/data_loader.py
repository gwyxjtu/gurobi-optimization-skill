#!/usr/bin/env python3
"""
数据加载工具
统一加载 CSV/Excel/JSON 格式的优化问题数据。

用法:
    python data_loader.py --input data.csv --output data.json
    python data_loader.py --input data.xlsx --format json
"""

import sys
import json
import argparse
from pathlib import Path


def load_csv(path: str) -> list[dict]:
    import pandas as pd
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def load_excel(path: str, sheet: str = None) -> list[dict]:
    import pandas as pd
    df = pd.read_excel(path, sheet_name=sheet)
    return df.to_dict(orient="records")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    mapping = {".csv": "csv", ".xlsx": "excel", ".xls": "excel", ".json": "json"}
    return mapping.get(ext, "unknown")


def main():
    parser = argparse.ArgumentParser(description="优化问题数据加载器")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出 JSON 路径")
    parser.add_argument("--sheet", help="Excel 工作表名")
    parser.add_argument("--format", choices=["csv", "excel", "json"], help="强制指定格式")
    parser.add_argument("--preview", type=int, default=5, help="预览行数")
    args = parser.parse_args()

    fmt = args.format or detect_format(args.input)
    print(f"📂 加载文件: {args.input} (格式: {fmt})")

    if fmt == "csv":
        data = load_csv(args.input)
    elif fmt == "excel":
        data = load_excel(args.input, args.sheet)
    elif fmt == "json":
        data = load_json(args.input)
    else:
        print(f"❌ 不支持的格式: {fmt}")
        sys.exit(1)

    # 预览
    if isinstance(data, list):
        print(f"📊 共 {len(data)} 条记录")
        for i, row in enumerate(data[: args.preview]):
            print(f"  [{i}] {row}")
    else:
        print(f"📊 JSON 对象，键: {list(data.keys())[:10]}")

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存到 {args.output}")
    else:
        print("\n--- JSON ---")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
