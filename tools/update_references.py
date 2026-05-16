#!/usr/bin/env python3
"""
Gurobi 离线参考数据更新工具
从 Gurobi 官方文档和 gurobi-logtools 仓库拉取最新数据，
更新 references/ 目录下的 JSON 文件。

用法:
    python update_references.py                    # 全部更新
    python update_references.py --classes          # 只更新类信息
    python update_references.py --parameters       # 只更新参数
    python update_references.py --constants        # 只更新常量
    python update_references.py --patterns         # 只更新代码模式
    python update_references.py --check            # 检查是否有更新
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import re
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "references"
REFMAN_BASE = "https://docs.gurobi.com/projects/optimizer/en/current"


# ============================================================
# 工具函数
# ============================================================

def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {path.name} ({path.stat().st_size:,} bytes)")


def fetch_url(url: str) -> str:
    """获取网页内容（自动跟随重定向）"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            # 处理重定向
            final_url = resp.url
            return resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        # 308 重定向手动处理
        if e.code in (301, 302, 307, 308):
            new_url = e.headers.get("Location", "")
            if new_url:
                return fetch_url(new_url)
        print(f"  ⚠️  获取失败 {url}: HTTP {e.code}")
        return ""
    except urllib.error.URLError as e:
        print(f"  ⚠️  获取失败 {url}: {e}")
        return ""


# ============================================================
# 参数更新（从官方文档抓取参数表）
# ============================================================

def update_parameters():
    """从 Gurobi 文档抓取最新参数列表"""
    print("\n📦 更新参数...")

    # 已知的重要参数（手动维护 + 在线补充）
    existing = load_json(DATA_DIR / "parameters.json")

    # 尝试从文档页面抓取参数名列表
    url = f"{REFMAN_BASE}/reference/parameters.html"
    html = fetch_url(url)

    if html:
        # 从 HTML 中提取参数名（文档格式：<a href="...">ParamName</a>）
        found = re.findall(r'href="[^"]*"[^>]*>([A-Z][a-zA-Z0-9_]+)</a>', html)
        new_params = set(found) - set(existing.keys())

        if new_params:
            print(f"  发现 {len(new_params)} 个新参数")
            # 新参数暂时只记录名称，需要手动补充详情
            for p in sorted(new_params):
                if p.startswith("GRB") or p in ("Model", "Var", "Constr", "Env"):
                    continue
                existing[p] = {
                    "type": "unknown",
                    "default": "unknown",
                    "desc": f"[待补充] 详见 {REFMAN_BASE}/parameters.html",
                    "_source": "auto_discovered",
                    "_updated": datetime.now().isoformat()
                }
        else:
            print("  参数已是最新")

    save_json(DATA_DIR / "parameters.json", existing)
    return existing


# ============================================================
# 常量更新（从官方文档抓取状态码等）
# ============================================================

def update_constants():
    """从 Gurobi 文档抓取常量"""
    print("\n📦 更新常量...")
    existing = load_json(DATA_DIR / "constants.json")

    # 尝试抓取状态码页面
    url = f"{REFMAN_BASE}/attrmodelstatus.html"
    html = fetch_url(url)

    if html:
        # 提取状态码
        statuses = re.findall(r'GRB\.(STATUS_[A-Z_]+|OPTIMAL|INFEASIBLE|UNBOUNDED|TIME_LIMIT|NODE_LIMIT)[^<]*', html)
        new_statuses = set()
        for s in statuses:
            name = s.split()[0].replace("GRB.STATUS_", "").replace("GRB.", "")
            if name not in existing.get("status", {}):
                new_statuses.add(name)

        if new_statuses:
            print(f"  发现 {len(new_statuses)} 个新状态码")
            for s in sorted(new_statuses):
                existing.setdefault("status", {})[s] = f"[待补充] 详见文档"

    save_json(DATA_DIR / "constants.json", existing)
    return existing


# ============================================================
# 类信息更新
# ============================================================

def update_classes():
    """更新核心类信息"""
    print("\n📦 更新类信息...")
    existing = load_json(DATA_DIR / "classes.json")

    # 检查文档页面是否可访问
    for cls_name, cls_info in existing.items():
        url = cls_info.get("url", "")
        if url:
            html = fetch_url(url)
            if not html:
                print(f"  ⚠️  {cls_name} 文档页不可访问: {url}")

    save_json(DATA_DIR / "classes.json", existing)
    return existing


# ============================================================
# 错误码更新
# ============================================================

def update_error_codes():
    """更新错误码"""
    print("\n📦 更新错误码...")
    existing = load_json(DATA_DIR / "error_codes.json")

    # 尝试抓取错误码页面
    url = f"{REFMAN_BASE}/errorcodes.html"
    html = fetch_url(url)

    if html:
        # 提取错误码
        codes = re.findall(r'error\s*code\s*(\d{4,5})', html, re.IGNORECASE)
        new_codes = set(codes) - set(existing.keys())

        if new_codes:
            print(f"  发现 {len(new_codes)} 个新错误码")
            for code in sorted(new_codes):
                existing[code] = f"[待补充] 详见 {REFMAN_BASE}/errorcodes.html"

    save_json(DATA_DIR / "error_codes.json", existing)
    return existing


# ============================================================
# 代码模式更新（从 gurobi-logtools / modeling-examples 学习）
# ============================================================

def update_patterns_from_repo():
    """从 Gurobi 官方仓库学习新的代码模式"""
    print("\n📦 检查代码模式更新...")
    existing = load_json(DATA_DIR / "code_patterns.json")

    # 检查 modeling-examples 是否有新的常见模式
    url = "https://api.github.com/repos/Gurobi/modeling-examples/contents"
    try:
        html = fetch_url(url)
        if html:
            items = json.loads(html)
            folders = [i["name"] for i in items if i["type"] == "dir"]
            print(f"  modeling-examples 有 {len(folders)} 个案例目录")

            # 检查是否有新的常用模式关键词
            new_pattern_keywords = []
            known_keywords = set(k.lower() for k in existing.keys())
            for folder in folders:
                fl = folder.lower()
                if any(kw in fl for kw in ["scheduling", "routing", "inventory", "portfolio"]):
                    if fl not in known_keywords:
                        new_pattern_keywords.append(folder)

            if new_pattern_keywords:
                print(f"  💡 建议补充以下场景模板: {', '.join(new_pattern_keywords[:5])}")
    except Exception as e:
        print(f"  ⚠️  无法访问 GitHub API: {e}")

    save_json(DATA_DIR / "code_patterns.json", existing)
    return existing


# ============================================================
# 版本信息
# ============================================================

def update_version_info():
    """记录当前数据版本"""
    version_file = DATA_DIR / "_version.json"
    version_info = {
        "updated_at": datetime.now().isoformat(),
        "gurobi_doc_version": "current",
        "data_files": {},
    }

    for f in sorted(DATA_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        version_info["data_files"][f.name] = {
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }

    save_json(version_file, version_info)
    return version_info


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gurobi 离线参考数据更新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                全部更新
  %(prog)s --parameters   只更新参数
  %(prog)s --check        检查数据状态
        """,
    )
    parser.add_argument("--classes",    action="store_true", help="只更新类信息")
    parser.add_argument("--constants",  action="store_true", help="只更新常量")
    parser.add_argument("--parameters", action="store_true", help="只更新参数")
    parser.add_argument("--errors",     action="store_true", help="只更新错误码")
    parser.add_argument("--patterns",   action="store_true", help="只更新代码模式")
    parser.add_argument("--check",      action="store_true", help="检查数据状态")
    args = parser.parse_args()

    # 检查模式
    if args.check:
        print("📊 离线数据状态:\n")
        for f in sorted(DATA_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            data = load_json(f)
            count = len(data) if isinstance(data, dict) else 0
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {f.name:25s} {count:>4} 条  {f.stat().st_size:>6,} bytes  修改于 {mtime}")

        # 版本信息
        version = load_json(DATA_DIR / "_version.json")
        if version:
            print(f"\n  最后更新: {version.get('updated_at', '未知')}")
        return

    # 更新模式
    any_flag = args.classes or args.constants or args.parameters or args.errors or args.patterns

    print("=" * 50)
    print("  Gurobi 离线参考数据更新")
    print(f"  数据目录: {DATA_DIR}")
    print("=" * 50)

    if not any_flag:
        # 全部更新
        update_classes()
        update_constants()
        update_parameters()
        update_error_codes()
        update_patterns_from_repo()
    else:
        if args.classes:
            update_classes()
        if args.constants:
            update_constants()
        if args.parameters:
            update_parameters()
        if args.errors:
            update_error_codes()
        if args.patterns:
            update_patterns_from_repo()

    update_version_info()

    print("\n✅ 更新完成！")
    print(f"   数据目录: {DATA_DIR}")
    print(f"   使用 'python tools/refman_search.py --check' 查看数据状态")


if __name__ == "__main__":
    main()
