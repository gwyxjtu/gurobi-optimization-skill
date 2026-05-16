---
name: gurobi-optimization-skill
description: |
  基于 Gurobi/SCIP/OR-Tools/CBC 的数学优化建模全流程技能。
  从问题理解、数学建模、代码生成、求解验证到结果分析的完整闭环。
  支持 LP/MILP/QP/MIQP/QCQP/SOCP/NL/多目标优化。
  当用户提到优化模型、线性规划、整数规划、Gurobi、求解器、最优解、约束、目标函数时触发。
version: 1.0.0
homepage: https://github.com/Gurobi/modeling-examples
metadata:
  openclaw:
    emoji: 🧮
    requires:
      commands:
        - python3
  security:
    credentials_usage: |
      本技能不需要用户凭证。求解器许可证由用户本地环境管理。
      所有业务数据必须来自用户提供的文件，Agent 禁止编造数据。
---

# Gurobi 优化建模技能

## 技能概述
一个用于全流程数学优化建模的 Agent 技能（`gurobi-optimization-skill`），覆盖从问题理解到求解分析的完整闭环。

## 核心流程
技能遵循 **问题理解 → 数学建模 → 代码生成 → 求解验证 → 结果分析** 的线性流程。

## ⛔ 强制规则 — 建模前必读

1. **禁止凭空生成数据**：所有参数、系数、需求量、成本、产能等数值必须来自用户提供的数据文件（Excel/CSV/JSON）或用户在对话中明确给出。Agent 不得编造、假设、估算任何业务数据。
2. **数据来源必须可追溯**：每个参数值都要能指出"来自哪个文件的哪个字段"或"用户在对话中给出"。无法追溯的数值一律不得写入模型。
3. **缺失数据必须追问**：如果用户描述了问题但没给数据，Agent 必须明确列出"建模还需要以下数据"，要求用户提供后再继续。不得自行填充默认值或示例数据。
4. **代码中不得硬编码业务数据**：模型代码中的成本、需求、产能等数值必须从数据文件加载，不得写死在代码里。只有数学常数（如 M=1e6）和逻辑常数可以硬编码。
5. **区分"数学常数"和"业务数据"**：
   - ✅ 可以硬编码：M（大M法）、时间步长 dt、收敛容差
   - ❌ 不可以硬编码：单位成本、需求量、产能、价格、利润
6. **使用占位数据需明确标注**：如果用户明确要求"先用示例数据跑通"，代码中必须用 `# ⚠️ 示例数据，需替换为实际数据` 注释标注，并在交付时提醒用户替换。

```mermaid
graph LR
    A[Step 1: 问题理解] --> B[Step 2: 数据分析]
    B --> C[Step 3: 数学建模]
    C --> D[Step 4: 代码生成]
    D --> E[Step 5: 求解验证]
    E --> F[Step 6: 结果分析]
    F --> G[Step 7: 迭代优化]
```

**执行顺序**：Agent 必须按顺序读取并执行每个步骤对应的 `prompts/` 目录下的指令文件。

## 触发与迭代模式

**触发条件**
当用户提及优化相关关键词（如"优化模型"、"线性规划"、"整数规划"、"Gurobi"、"求解器"、"最优解"、"约束"、"目标函数"等）时启用。

**迭代模式**
- **核心规则**：当用户意图明显是在**已有模型或上一轮输出**上继续工作（如修改约束、调整目标、添加变量），**无需**固定关键词，**不必**确认，直接进入迭代流程。
- **禁止行为**：在迭代意图已成立时，默认回到主流程的早期步骤。
- **识别信号**：对话中已出现模型代码路径、求解结果或刚交付的方案时，优先按迭代处理。
- **操作路径**：
    1. **参数调整**：`Read` `iteration_context.md` → `Read` `parameter_tuning.md`
    2. **结构修改**：`Read` `iteration_context.md` → `Read` `model_revision.md`
- **输出规范**：迭代结果必须**另存为**带时间戳的新文件（`{问题名}_{YYYYMMDDHHmmss}.py`），**不覆盖**旧版本，并在项目目录追加 `优化迭代记录.md`。

## 关键工具与数据源

| 任务 | 建议方式/关键指令 |
| :--- | :--- |
| **环境检查** | `python3 ${SKILL_DIR}/tools/env_check.py` — 检查 Gurobi 许可证和依赖 |
| **API 查询** | `python3 ${SKILL_DIR}/tools/refman_search.py <关键词>` — 查询 Gurobi Python API 方法、参数、常量、错误码、代码模式 |
| **数据加载** | 支持 `.csv`, `.xlsx`, `.json`, `.dat` 格式，使用 `tools/data_loader.py` 统一加载 |
| **数据验证** | `python3 ${SKILL_DIR}/tools/data_validator.py --data <文件> --required "字段1,字段2"` — 建模前强制验证用户数据完整性 |
| **模型生成** | 按模板生成 Gurobi Python 代码，写入 `outputs/{问题名}/model.py` |
| **求解执行** | `python3 outputs/{问题名}/model.py` — 运行模型并输出结果 |
| **模型验证** | `python3 ${SKILL_DIR}/tools/model_validator.py --results results.json` — 求解后自动检查结果合理性 |
| **多求解器** | `python3 ${SKILL_DIR}/tools/solver_factory.py --list` — 检测可用求解器；`--solver gurobi/ortools/pulp_cbc/scip` 切换 |
| **日志分析** | `python3 ${SKILL_DIR}/tools/log_analyzer.py <日志路径>` — 解析 Gurobi 求解日志，提取关键指标（依赖 gurobi-logtools） |
| **结果可视化** | `python3 ${SKILL_DIR}/tools/result_visualizer.py` — 生成结果图表 |
| **敏感性分析** | `python3 ${SKILL_DIR}/tools/sensitivity_analysis.py` — 参数敏感性分析 |

## Prompt 文件映射（分步指令）

| 步骤 | 文件 | 用途 |
| :--- | :--- | :--- |
| Step 1 | `prompts/problem_intake.md` | 理解问题背景、优化目标、约束条件 |
| Step 2 | `prompts/data_analysis.md` | 分析输入数据，识别决策变量维度 |
| Step 3 | `prompts/model_formulation.md` | 构建数学模型：变量、目标、约束 |
| Step 4 | `prompts/code_generation.md` | 生成 Gurobi Python 代码 |
| Step 5 | `prompts/solve_and_validate.md` | 求解模型，验证可行性与最优性 |
| Step 6 | `prompts/result_analysis.md` | 分析结果，生成报告与可视化 |
| 迭代 | `prompts/iteration_context.md` | 迭代意图识别与上下文加载 |
| 迭代 | `prompts/parameter_tuning.md` | 参数调整（目标权重、约束松弛等） |
| 迭代 | `prompts/model_revision.md` | 结构修改（添加变量、修改约束、切换目标） |

## 优化问题类型支持
## 求解器选择

| 求解器 | 安装 | 许可 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **Gurobi** | `pip install gurobipy` | 商业（免费学术版） | 最快最稳，大规模 MILP/QP/NL，首选 |
| **SCIP** | `pip install pyscipopt` | Apache-2.0 免费 | 开源最强 MIP，支持非凸 MINLP |
| **OR-Tools** | `pip install ortools` | Apache-2.0 免费 | CP-SAT 擅长组合优化，Google 维护 |
| **CBC (PuLP)** | `pip install pulp` | EPL-2.0 免费 | 开箱即用，中小规模 MILP |

使用 `solver_factory.py` 统一接口，切换求解器只需改一行：
```python
from solver_factory import create_solver
solver = create_solver("auto")  # 自动选最佳可用
# solver = create_solver("gurobi")  # 指定
# solver = create_solver("scip")    # 免费替代
```

| 类型 | 说明 | Gurobi 模型 |
| :--- | :--- | :--- |
| **LP** | 线性规划 | `Model()` + 连续变量 + 线性目标/约束 |
| **MILP** | 混合整数线性规划 | `Model()` + `GRB.BINARY`/`GRB.INTEGER` |
| **QP** | 二次规划 | `Model()` + 二次目标 |
| **MIQP** | 混合整数二次规划 | `Model()` + 整数变量 + 二次目标 |
| **QCQP** | 二次约束规划 | `addQConstr()` |
| **SOCP** | 二阶锥规划 | `addConstr()` + `GenConstrExpPow()` |
| **NLP** | 非线性（Gurobi 11+） | `addGenConstrNL()` |
| **Multi-obj** | 多目标优化 | `model.ModelSense` + `setObjectiveN()` |

## 常见应用场景模板

| 场景 | 模板文件 |
| :--- | :--- |
| 生产排程 | `templates/production_scheduling.py` |
| 物流配送 | `templates/logistics_routing.py` |
| 资源分配 | `templates/resource_allocation.py` |
| 投资组合 | `templates/portfolio_optimization.py` |
| 选址问题 | `templates/facility_location.py` |
| 人员排班 | `templates/staff_scheduling.py` |
| 库存管理 | `templates/inventory_management.py` |
| 网络流 | `templates/network_flow.py` |

## Agent 工作流自检清单
- [ ] **求解后已用 model_validator.py 验证结果（状态/目标值/Gap/变量/约束）。**
- [ ] **已检测可用求解器，用户无 Gurobi 许可证时自动切换到免费替代（SCIP/CBC/OR-Tools）。**
- [ ] **所有业务数据来自用户提供的文件或对话明确给出，Agent 未编造任何数值。**
- [ ] **已用 data_validator.py 验证数据完整性，必需字段齐全。**

- [ ] 已按步骤顺序读取对应提示文件。
- [ ] 识别到修改意图时，已进入迭代流程（`iteration_context.md` → `parameter_tuning.md`/`model_revision.md`），并输出了带时间戳的新文件。
- [ ] 迭代操作后，已在对话中输出**变更摘要**，并追加了迭代记录文件。
- [ ] 数学模型的变量、约束、目标函数三要素完整且一致。
- [ ] 代码中已包含模型构建、求解、结果输出三部分。
- [ ] 求解状态已检查（`model.status == GRB.OPTIMAL`），非最优时已给出原因分析。
- [ ] 结果包含：目标函数值、决策变量取值、约束松弛情况。
- [ ] 最终输出 `.py` 文件和结果报告，文件名符合时间戳规则。
