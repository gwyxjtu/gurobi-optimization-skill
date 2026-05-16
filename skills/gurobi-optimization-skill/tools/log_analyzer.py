#!/usr/bin/env python3
"""
Gurobi 求解日志分析工具
基于 gurobi-logtools 解析 .log 文件，提取关键指标并生成报告。

依赖:
    pip install gurobi-logtools

用法:
    python log_analyzer.py solve.log                    # 解析单个日志
    python log_analyzer.py *.log --output report.xlsx   # 批量解析并导出 Excel
    python log_analyzer.py solve.log --plot             # 生成可视化图表
    python log_analyzer.py solve.log --json             # JSON 格式输出
"""

import sys
import os
import json
import argparse
import glob
from pathlib import Path
from datetime import datetime


def check_dependency():
    """检查 gurobi-logtools 是否安装"""
    try:
        import gurobi_logtools
        return True, gurobi_logtools
    except ImportError:
        return False, None


def parse_log_files(log_paths: list[str]) -> dict:
    """解析日志文件，提取关键指标"""
    ok, glt = check_dependency()
    if not ok:
        return {"error": "未安装 gurobi-logtools，请运行: pip install gurobi-logtools"}

    try:
        results = glt.parse(log_paths)
        summary = results.summary()
    except Exception as e:
        return {"error": f"解析失败: {e}"}

    # 提取摘要信息
    report = {
        "log_files": log_paths,
        "parsed_at": datetime.now().isoformat(),
        "num_runs": len(summary) if hasattr(summary, '__len__') else 1,
        "summary": [],
        "warnings": [],
    }

    # 转换 summary DataFrame 为可序列化格式
    if hasattr(summary, 'to_dict'):
        summary_dict = summary.to_dict(orient='records')
        for row in summary_dict:
            # 清理 NaN
            cleaned = {}
            for k, v in row.items():
                if v is not None and str(v) != 'nan':
                    cleaned[k] = v
            report["summary"].append(cleaned)
    else:
        report["summary"] = str(summary)

    # 提取 nodelog 进度（如果有 MIP 求解）
    try:
        nodelog = results.progress("nodelog")
        if nodelog is not None and len(nodelog) > 0:
            report["nodelog_progress"] = {
                "entries": len(nodelog),
                "columns": list(nodelog.columns) if hasattr(nodelog, 'columns') else [],
                "final_gap": float(nodelog.iloc[-1].get('Gap', float('nan'))) if hasattr(nodelog, 'iloc') else None,
            }
    except Exception:
        pass

    return report


def analyze_single_log(log_path: str) -> dict:
    """分析单个日志文件，提取关键信息"""
    if not os.path.exists(log_path):
        return {"error": f"文件不存在: {log_path}"}

    # 基础解析：直接读取日志内容
    analysis = {
        "file": log_path,
        "file_size": os.path.getsize(log_path),
        "lines": 0,
        "phases": [],
        "metrics": {},
        "warnings": [],
        "errors": [],
    }

    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    analysis["lines"] = len(lines)

    # 解析关键信息
    in_presolve = False
    in_simplex = False
    in_barrier = False
    in_crossover = False
    in_mip = False

    for line in lines:
        line = line.strip()

        # 模型信息
        if "Optimize a model" in line or "Model has" in line:
            analysis["metrics"]["model_info"] = line
        elif "rows" in line and "columns" in line and "nonzeros" in line:
            analysis["metrics"]["dimensions"] = line

        # 预求解
        if "Presolve" in line:
            if "removed" in line or "rows" in line:
                analysis["metrics"]["presolve"] = line
                in_presolve = True

        # Simplex
        if "Iteration" in line and "Objective" in line:
            in_simplex = True
            analysis["phases"].append("simplex")
        if in_simplex and ("Optimal" in line or "infeasible" in line.lower()):
            analysis["metrics"]["simplex_result"] = line
            in_simplex = False

        # Barrier
        if "Barrier" in line and ("iterations" in line or "objective" in line):
            in_barrier = True
            analysis["phases"].append("barrier")
        if "Barrier solved model" in line:
            analysis["metrics"]["barrier_result"] = line
            in_barrier = False

        # Crossover
        if "Crossover" in line:
            in_crossover = True
            analysis["phases"].append("crossover")
        if "Solved with crossover" in line:
            in_crossover = False

        # MIP
        if "Found heuristic solution" in line:
            analysis["phases"].append("mip")
            in_mip = True
        if "Explored" in line and "nodes" in line:
            analysis["metrics"]["mip_nodes"] = line
        if "Best objective" in line or "Best bound" in line:
            analysis["metrics"]["mip_bounds"] = line
        if "gap" in line.lower() and ("%" in line):
            analysis["metrics"]["mip_gap_line"] = line

        # 求解时间
        if "Explored" in line and "seconds" in line:
            analysis["metrics"]["solve_time_line"] = line
        elif "Best objective" in line and "seconds" in line:
            analysis["metrics"]["solve_time_line"] = line

        # 状态
        if "Optimal solution found" in line:
            analysis["metrics"]["status"] = "OPTIMAL"
        elif "Model is infeasible" in line:
            analysis["metrics"]["status"] = "INFEASIBLE"
            analysis["errors"].append("模型不可行")
        elif "Model is unbounded" in line:
            analysis["metrics"]["status"] = "UNBOUNDED"
            analysis["errors"].append("模型无界")
        elif "Time limit reached" in line:
            analysis["metrics"]["status"] = "TIME_LIMIT"
            analysis["warnings"].append("达到时间限制")
        elif "MIP solution" in line:
            analysis["metrics"]["status"] = "MIP_SOLUTION"

        # 警告
        if "Warning" in line or "warning" in line:
            analysis["warnings"].append(line)
        if "numerical difficulties" in line.lower():
            analysis["warnings"].append("⚠️ 数值困难")
        if "infeasible" in line.lower() and "relaxation" in line.lower():
            analysis["warnings"].append("⚠️ 松弛不可行")

    return analysis


def generate_report(analyses: list[dict], output_path: str = None) -> str:
    """生成可读报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("  Gurobi 求解日志分析报告")
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append("")

    for i, analysis in enumerate(analyses):
        if "error" in analysis:
            lines.append(f"❌ 文件 {i+1}: {analysis.get('file', '未知')} — {analysis['error']}")
            lines.append("")
            continue

        lines.append(f"📄 文件 {i+1}: {analysis['file']}")
        lines.append(f"   大小: {analysis['file_size']:,} bytes, {analysis['lines']} 行")
        lines.append("")

        # 模型信息
        metrics = analysis.get("metrics", {})
        if "model_info" in metrics:
            lines.append(f"   📐 {metrics['model_info']}")
        if "dimensions" in metrics:
            lines.append(f"   📐 {metrics['dimensions']}")
        lines.append("")

        # 求解阶段
        phases = analysis.get("phases", [])
        if phases:
            unique_phases = list(dict.fromkeys(phases))  # 保序去重
            lines.append(f"   🔄 求解阶段: {' → '.join(unique_phases)}")
            lines.append("")

        # 关键指标
        if "presolve" in metrics:
            lines.append(f"   ⚡ 预求解: {metrics['presolve']}")
        if "simplex_result" in metrics:
            lines.append(f"   ⚡ Simplex: {metrics['simplex_result']}")
        if "barrier_result" in metrics:
            lines.append(f"   ⚡ Barrier: {metrics['barrier_result']}")
        if "mip_nodes" in metrics:
            lines.append(f"   🌳 MIP 节点: {metrics['mip_nodes']}")
        if "mip_bounds" in metrics:
            lines.append(f"   📊 MIP 界: {metrics['mip_bounds']}")
        if "mip_gap_line" in metrics:
            lines.append(f"   📊 Gap: {metrics['mip_gap_line']}")
        if "solve_time_line" in metrics:
            lines.append(f"   ⏱️  求解时间: {metrics['solve_time_line']}")

        # 状态
        status = metrics.get("status", "未知")
        status_emoji = {
            "OPTIMAL": "✅",
            "INFEASIBLE": "❌",
            "UNBOUNDED": "❌",
            "TIME_LIMIT": "⚠️",
            "MIP_SOLUTION": "✅",
        }.get(status, "❓")
        lines.append(f"\n   {status_emoji} 状态: {status}")

        # 警告和错误
        for w in analysis.get("warnings", []):
            lines.append(f"   ⚠️  {w}")
        for e in analysis.get("errors", []):
            lines.append(f"   ❌ {e}")

        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    report = "\n".join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"📄 报告已保存到: {output_path}")

    return report


def export_excel(log_paths: list[str], output_path: str):
    """导出到 Excel"""
    ok, glt = check_dependency()
    if not ok:
        print("❌ 需要安装 gurobi-logtools: pip install gurobi-logtools")
        return

    try:
        results = glt.parse(log_paths)
        summary = results.summary()
        summary.to_excel(output_path, index=True)
        print(f"📊 Excel 已导出到: {output_path}")
    except Exception as e:
        print(f"❌ 导出失败: {e}")


def plot_progress(log_paths: list[str], output_dir: str):
    """生成可视化图表"""
    ok, glt = check_dependency()
    if not ok:
        print("❌ 需要安装 gurobi-logtools: pip install gurobi-logtools")
        return

    try:
        results = glt.parse(log_paths)
        os.makedirs(output_dir, exist_ok=True)

        # 汇总图
        summary = results.summary()
        glt.plot(summary)
        glt.save_plot(os.path.join(output_dir, "summary.png"))
        print(f"📊 汇总图: {output_dir}/summary.png")

        # MIP Gap 收敛图
        try:
            nodelog = results.progress("nodelog")
            if nodelog is not None and len(nodelog) > 0:
                glt.plot(nodelog, x="Time", y="Gap", color="Log", type="line")
                glt.save_plot(os.path.join(output_dir, "gap_convergence.png"))
                print(f"📊 Gap 收敛图: {output_dir}/gap_convergence.png")
        except Exception:
            pass

        # Incumbent 收敛图
        try:
            norel = results.progress("norel")
            if norel is not None and len(norel) > 0:
                glt.plot(norel, x="Time", y="Incumbent", color="Log", type="line")
                glt.save_plot(os.path.join(output_dir, "incumbent_convergence.png"))
                print(f"📊 Incumbent 收敛图: {output_dir}/incumbent_convergence.png")
        except Exception:
            pass

    except Exception as e:
        print(f"❌ 可视化失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Gurobi 求解日志分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s solve.log                         解析单个日志
  %(prog)s *.log --output report.txt         批量解析并导出报告
  %(prog)s solve.log --excel results.xlsx    导出到 Excel
  %(prog)s solve.log --plot charts/          生成可视化图表
  %(prog)s solve.log --json                  JSON 格式输出
  %(prog)s solve.log --gurobi-logtools       使用 gurobi-logtools 完整解析
        """,
    )
    parser.add_argument("logs", nargs="+", help="日志文件路径 (支持通配符)")
    parser.add_argument("--output", "-o", help="输出报告文件路径")
    parser.add_argument("--excel", help="导出到 Excel 文件")
    parser.add_argument("--plot", help="生成可视化图表到指定目录")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--gurobi-logtools", action="store_true",
                        help="使用 gurobi-logtools 完整解析 (需安装)")
    args = parser.parse_args()

    # 展开通配符
    log_paths = []
    for pattern in args.logs:
        expanded = glob.glob(pattern)
        if expanded:
            log_paths.extend(expanded)
        else:
            log_paths.append(pattern)

    # 过滤存在的文件
    existing = [p for p in log_paths if os.path.exists(p)]
    if not existing:
        print(f"❌ 未找到日志文件: {log_paths}")
        sys.exit(1)

    print(f"📂 分析 {len(existing)} 个日志文件...")

    # Excel 导出
    if args.excel:
        export_excel(existing, args.excel)
        return

    # 可视化
    if args.plot:
        plot_progress(existing, args.plot)
        return

    # 使用 gurobi-logtools 完整解析
    if args.gurobi_logtools:
        report = parse_log_files(existing)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            if "error" in report:
                print(f"❌ {report['error']}")
            else:
                print(f"✅ 解析了 {report['num_runs']} 个求解运行")
                for row in report.get("summary", []):
                    print(f"\n  📊 {row}")
        return

    # 默认：基础解析
    analyses = []
    for path in existing:
        print(f"  解析: {path}")
        analyses.append(analyze_single_log(path))

    if args.json:
        print(json.dumps(analyses, ensure_ascii=False, indent=2))
    else:
        report = generate_report(analyses, args.output)
        if not args.output:
            print(report)


if __name__ == "__main__":
    main()
