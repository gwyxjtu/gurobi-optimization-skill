#!/usr/bin/env python3
"""
Gurobi 参考手册查询工具（离线 + 在线）
从 references/ 目录加载离线数据，也支持在线查询。

用法:
    python refman_search.py Model.addConstr       查询 addConstr 方法
    python refman_search.py MIPGap                查询 MIPGap 参数
    python refman_search.py GRB.INFEASIBLE        查询求解状态常量
    python refman_search.py quicksum              查询 quicksum 用法
    python refman_search.py 10018                 查询错误码
    python refman_search.py --list-params         列出常用参数
    python refman_search.py --list-status         列出求解状态
    python refman_search.py --online Model        打开在线文档链接
"""

import sys
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "references"


# ============================================================
# 加载离线数据
# ============================================================

def load_json(name: str) -> dict:
    """从 references/ 加载 JSON 数据"""
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all() -> dict:
    """加载所有离线数据"""
    return {
        "classes": load_json("classes"),
        "constants": load_json("constants"),
        "parameters": load_json("parameters"),
        "error_codes": load_json("error_codes"),
        "code_patterns": load_json("code_patterns"),
    }


# ============================================================
# 搜索逻辑
# ============================================================

def search(query: str, data: dict) -> dict:
    """在离线数据中搜索"""
    query_clean = query.replace("GRB.", "").replace("GRB_", "")
    query_lower = query_clean.lower()
    raw_lower = query.lower()
    results = {"matches": []}

    # 1. 类
    for cls_name, cls_info in data["classes"].items():
        if query_lower in cls_name.lower() or raw_lower in cls_name.lower():
            results["matches"].append({"type": "class", "name": cls_name, "info": cls_info})

    # 2. 常量
    for cat_name, cat in data["constants"].items():
        for const_name, desc in cat.items():
            if query_lower in const_name.lower():
                results["matches"].append({
                    "type": "constant",
                    "name": f"GRB.{const_name}",
                    "desc": desc,
                    "category": cat_name,
                })

    # 3. 参数
    for param_name, param_info in data["parameters"].items():
        if query_lower in param_name.lower():
            results["matches"].append({
                "type": "parameter",
                "name": param_name,
                "info": param_info,
            })

    # 4. 代码模式
    for pattern_name, pattern_info in data["code_patterns"].items():
        if query_lower in pattern_name.lower() or raw_lower in pattern_name.lower():
            results["matches"].append({
                "type": "code_pattern",
                "name": pattern_name,
                "info": pattern_info,
            })

    # 5. 错误码
    if query_clean.isdigit():
        code_str = query_clean
        if code_str in data["error_codes"]:
            results["matches"].append({
                "type": "error_code",
                "code": int(code_str),
                "desc": data["error_codes"][code_str],
            })

    return results


# ============================================================
# 格式化输出
# ============================================================

def format_result(match: dict) -> str:
    """格式化单条匹配结果"""
    lines = []

    if match["type"] == "class":
        info = match["info"]
        lines.append(f"📦 类: {match['name']} — {info['desc']}")
        lines.append(f"   文档: {info['url']}")
        if info.get("key_methods"):
            lines.append(f"   方法: {', '.join(info['key_methods'][:10])}")
        if info.get("key_attributes"):
            lines.append(f"   属性: {', '.join(info['key_attributes'][:10])}")

    elif match["type"] == "constant":
        lines.append(f"🏷️  {match['name']} = {match['desc']}")
        lines.append(f"   类别: {match['category']}")

    elif match["type"] == "parameter":
        info = match["info"]
        lines.append(f"⚙️  参数: {match['name']}")
        lines.append(f"   类型: {info['type']}, 默认值: {info['default']}")
        lines.append(f"   说明: {info['desc']}")

    elif match["type"] == "code_pattern":
        info = match["info"]
        lines.append(f"📝 {match['name']} — {info['desc']}")
        lines.append("   示例:")
        for ex in info.get("examples", []):
            lines.append(f"     {ex}")

    elif match["type"] == "error_code":
        lines.append(f"❌ 错误码 {match['code']}: {match['desc']}")

    return "\n".join(lines)


# ============================================================
# 在线查询
# ============================================================

def online_url(query: str) -> str:
    """构造在线查询 URL"""
    q = urllib.parse.quote(f"gurobi python API {query} site:gurobi.com/documentation")
    return f"https://www.google.com/search?q={q}"


def check_direct_url(query: str) -> str:
    """尝试直接访问文档页"""
    try:
        url = f"https://www.gurobi.com/documentation/current/refman/py_{query.lower()}.html"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return url
    except Exception:
        pass
    return None


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gurobi 参考手册查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s Model.addConstr       查询 addConstr 方法
  %(prog)s MIPGap                查询 MIPGap 参数
  %(prog)s GRB.INFEASIBLE        查询求解状态常量
  %(prog)s quicksum              查询 quicksum 用法
  %(prog)s 10018                 查询错误码
  %(prog)s --list-params         列出常用参数
  %(prog)s --list-status         列出求解状态码
  %(prog)s --list-vtypes         列出变量类型
  %(prog)s --list-classes        列出核心类
  %(prog)s --patterns            列出常用代码模式
  %(prog)s --online Model        打开在线文档链接
  %(prog)s --refresh             更新离线数据（运行 updater）
        """,
    )
    parser.add_argument("query", nargs="?", help="查询关键词")
    parser.add_argument("--list-params",   action="store_true", help="列出常用求解参数")
    parser.add_argument("--list-status",   action="store_true", help="列出求解状态码")
    parser.add_argument("--list-vtypes",   action="store_true", help="列出变量类型")
    parser.add_argument("--list-classes",  action="store_true", help="列出核心类")
    parser.add_argument("--list-constants",action="store_true", help="列出所有常量分类")
    parser.add_argument("--patterns",      action="store_true", help="列出常用代码模式")
    parser.add_argument("--online",        action="store_true", help="同时查询在线文档")
    parser.add_argument("--json",          action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    data = load_all()

    # 列表模式
    if args.list_params:
        print("⚙️  常用 Gurobi 求解参数:\n")
        for name, info in data["parameters"].items():
            print(f"  {name:25s} [{info['type']:8s}] 默认={info['default']:12s}  {info['desc']}")
        return

    if args.list_status:
        print("📊 Gurobi 求解状态码:\n")
        for name, desc in data["constants"].get("status", {}).items():
            print(f"  GRB.{name:25s} — {desc}")
        return

    if args.list_vtypes:
        print("📐 Gurobi 变量类型:\n")
        for name, desc in data["constants"].get("vtype", {}).items():
            print(f"  GRB.{name:15s} — {desc}")
        return

    if args.list_classes:
        print("📦 Gurobi 核心类:\n")
        for name, info in data["classes"].items():
            print(f"  {name:15s} — {info['desc']}")
            print(f"                  {info['url']}")
        return

    if args.list_constants:
        for cat_name, cat in data["constants"].items():
            print(f"\n🏷️  {cat_name}:")
            for name, desc in cat.items():
                print(f"  GRB.{name:25s} — {desc}")
        return

    if args.patterns:
        print("📝 常用代码模式:\n")
        for name, info in data["code_patterns"].items():
            print(f"  {name:25s} — {info['desc']}")
        return

    if not args.query:
        parser.print_help()
        return

    # 查询
    results = search(args.query, data)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        return

    if results["matches"]:
        print(f"\n🔍 查询: {args.query}\n")
        for match in results["matches"]:
            print(format_result(match))
            print()
    else:
        print(f"❌ 本地未找到 '{args.query}'")

    # 在线
    if args.online:
        direct = check_direct_url(args.query)
        if direct:
            print(f"📖 在线文档: {direct}")
        else:
            print(f"🔍 搜索: {online_url(args.query)}")
    elif not results["matches"]:
        print(f"💡 试试: {sys.argv[0]} --online {args.query}")


if __name__ == "__main__":
    main()
