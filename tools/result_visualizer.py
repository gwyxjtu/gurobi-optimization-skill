#!/usr/bin/env python3
"""
结果可视化工具
读取求解结果 JSON，生成图表。

用法:
    python result_visualizer.py --results results.json --output charts/
"""

import sys
import json
import os
import argparse
from pathlib import Path


def plot_variable_bar(results: dict, output_path: str):
    """变量取值柱状图"""
    import matplotlib.pyplot as plt

    variables = results.get("variables", results.get("schedule", []))
    if not variables:
        print("⚠️ 无可视化变量数据")
        return

    # 过滤非零变量，按值排序
    if isinstance(variables, dict):
        items = [(k, v["value"] if isinstance(v, dict) else v) for k, v in variables.items()]
    elif isinstance(variables, list):
        items = [(v["variable"], v["value"]) for v in variables]
    else:
        return

    items = [(k, v) for k, v in items if abs(v) > 1e-6]
    items.sort(key=lambda x: x[1], reverse=True)

    # 最多显示30个
    if len(items) > 30:
        items = items[:30]

    names, values = zip(*items)

    fig, ax = plt.subplots(figsize=(12, max(6, len(items) * 0.3)))
    bars = ax.barh(range(len(names)), values, color="#2196F3", alpha=0.8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("取值")
    ax.set_title("决策变量取值（非零）")
    ax.invert_yaxis()

    # 添加数值标签
    for bar, val in zip(bars, values):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f" {val:,.2f}", va="center", fontsize=7)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"📊 变量柱状图已保存: {output_path}")


def plot_summary(results: dict, output_path: str):
    """求解摘要图"""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # 状态
    status = results.get("status", "未知")
    color = "#4CAF50" if "最优" in str(status) else "#F44336"
    axes[0].text(0.5, 0.5, status, ha="center", va="center", fontsize=18, color=color, weight="bold")
    axes[0].set_title("求解状态")
    axes[0].set_xlim(0, 1)
    axes[0].set_ylim(0, 1)
    axes[0].axis("off")

    # 目标函数值
    obj = results.get("objective_value", results.get("objective"))
    if obj is not None:
        axes[1].text(0.5, 0.5, f"{obj:,.2f}", ha="center", va="center", fontsize=16, weight="bold")
    axes[1].set_title("目标函数值")
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(0, 1)
    axes[1].axis("off")

    # 求解时间
    t = results.get("solve_time", results.get("time", 0))
    axes[2].text(0.5, 0.5, f"{t:.2f}s", ha="center", va="center", fontsize=16)
    axes[2].set_title("求解时间")
    axes[2].set_xlim(0, 1)
    axes[2].set_ylim(0, 1)
    axes[2].axis("off")

    plt.suptitle("优化求解摘要", fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"📊 摘要图已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="优化结果可视化")
    parser.add_argument("--results", "-r", required=True, help="结果 JSON 文件")
    parser.add_argument("--output", "-o", default="charts", help="输出目录")
    args = parser.parse_args()

    with open(args.results, "r", encoding="utf-8") as f:
        results = json.load(f)

    os.makedirs(args.output, exist_ok=True)

    plot_summary(results, os.path.join(args.output, "summary.png"))
    plot_variable_bar(results, os.path.join(args.output, "variables.png"))

    print(f"\n✅ 所有图表已保存到 {args.output}/")


if __name__ == "__main__":
    main()
