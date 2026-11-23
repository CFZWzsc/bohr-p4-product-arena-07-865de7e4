---
name: latex-build-doctor
description: Use when a case supplies LaTeX source (main .tex plus optional .bib or template files) and asks to make it compile or to explain build failures; statically checks environments, brace balance, labels and cross-references, citation keys against BibTeX entries, table column specs, math mode, template fields and package requirements, then emits a line-anchored fix report plus a reproducible compile plan in /app/output/result.json while preserving case_id and every output_contract field. Deterministic standard library only; never runs a TeX engine or the network.
---

# LaTeX 源码诊断与可重复编译（行号—根因—修复计划）

## 用途与适用条件

当输入是一个 LaTeX 工程（主文件、可选子文件、`.bib`、模板说明），需要判断“为什么不编译/为什么引用是问号/为什么表格溢出”，并给出可复核的修复路径时使用。

适用：

- 单文件或多文件 `.tex`，含 `\documentclass`。
- 需要把错误定位到**文件 + 行号 + 根因**，而不是停在首条报错。
- 需要核对 `\label/\ref`、`\cite/.bib`、表格列数、数学环境、模板必填项。
- 需要给出可重复的编译轮次与依赖说明。

不适用：真正调用 TeX 引擎生成 PDF（本 Skill 只做静态诊断与计划）、替作者补写缺失章节、判断论文科学正确性。

## 输入

- `/input/case.json`：主输入。读取 `case_id`、`output_contract`、`task`，以及 `main_tex`、`tex`、`latex_source`、`files`、`template`、`bib`、`bibliography` 等字段。
- `task.md`：平台提供时读取 `/input/task.md` 或 `/app/work/task.md`，缺失不阻塞。
- 文件既可为内联字符串，也可为路径。脚本只读取存在、UTF-8 可解码、≤2MB 的文本；二进制/PDF 登记为未解析。
- 输出目录 `/app/output`，工作目录 `/app/work`。

## 处理流程（逐项覆盖评分维度）

脚本 `scripts/run_skill.py` 做确定性静态检查；Agent 依据报告改源码并复述编译计划。

1. **工程识别（调用与易用性）**：区分主文件（含 `\documentclass` 的最长文件）、子文件、`.bib`、模板文件；登记每个文件的行数与 SHA-256。
2. **环境配对（编译得通）**：用栈匹配 `\begin{env}`/`\end{env}`，报告未闭合、错序与多余 `\end`，附行号与最近上下文。
3. **括号平衡**：逐字符统计未转义 `{}`，报告首次深度为负的行与文件末残余深度；忽略 `\{`、`\}` 与注释行。
4. **交叉引用**：`\label` 与 `\ref/\eqref/\autoref/\cref` 求差集，报告未定义引用、重复标签、未被引用的标签。
5. **文献键（引用与参考文献）**：解析 `\cite{...}`（含多键与可选参数）与 BibTeX `@type{key,`，报告缺失条目、未被引用的条目；无 `.bib` 时明确说明无法核验。
6. **表格与浮动体**：统计 `tabular` 列格式列数与每行 `&` 数，报告列数不匹配；`[H]` 无 `float` 宏包、`table` 未置于浮动体等给出警告。
7. **数学模式**：未转义 `$` 奇偶性；`align/equation` 行是否含 `&` 对齐点；`\text` 外中文等提示。
8. **模板必填项**：检查 `\title`、`\author`、`abstract` 环境、`\keywords`；缺失项列为 `template_required_missing`，不代写内容。
9. **可重复构建**：输出轮次计划（含 bib 时 `pdflatex → bibtex → pdflatex → pdflatex`，否则两遍 `pdflatex`），并给出 `latexmk -pdf -interaction=nonstopmode` 等价命令与依赖清单。
10. **合同保留**：见输出契约。

## 输出契约

写入 `/app/output/result.json`：

- 顶层 `case_id` 与输入一致。
- **保留原始 `output_contract` 每个字段名**（字段字典 / 列表 / `fields` / Schema `properties` 均支持）。已知语义字段按别名填充；无法映射写 `null` 并在 `contract_status.unmapped_fields` 登记，状态降为 `partial`。组合 Schema 登记 `unsupported_features`。
- 固定字段：
  - `status`：`success | partial | insufficient_input | failed`
  - `result`：`compile_report`（`errors[]`、`warnings[]`）、`compile_plan`、`fix_plan`、`file_inventory`、`template_check`
  - `evidence`：每条问题对应的文件、行号、原文片段
  - `uncertainty`、`errors`、`stats`
- 每条问题字段：`code`、`severity`（`error|warning|info`）、`file`、`line`、`message`、`fix`。
- 退出码：`0` 完成；`1` 存在未映射合同字段；`2` 输入缺失/不可读。

## 异常处理

| 情形 | 处置 |
|---|---|
| `case.json` 不可读 | `status=failed`，`errors` 记录，退出码 2，不伪造诊断 |
| 无 `.tex` 源 | `status=insufficient_input`，说明需要源码，不猜内容 |
| 只有片段、无 `\documentclass` | `status=partial`，按片段检查并标 `fragment_only` |
| `.bib` 缺失但有 `\cite` | 报 `bib_missing`，不虚构条目 |
| 多主文件冲突 | 全部登记，按最长文件为默认主文件并标 `main_ambiguous` |
| 文件超限/非 UTF-8 | 登记 `unreadable`，其余文件继续检查 |
| 模板类文件缺失 | 报 `template_class_missing`，给出所需 `.cls/.sty` 名称而不是伪造内容 |
| 宏包未知 | 只提示“需确认发行版是否预装”，不声称已安装 |

## 限制与不适用

- 不运行 `pdflatex/latexmk/xelatex`，不生成或声称生成 PDF。
- 静态检查不能发现宏展开后才会出现的错误；行号对多文件工程按各文件独立编号。
- 不判断公式物理含义、不重排参考文献样式、不生成缺失的实验内容。
- 未读取的模板 PDF 只作为版式参考登记，不臆测约束。

## 最小调用示例（示例）

以下为合成示意，非官方案例。

```bash
python /skills/weekly-skill/scripts/run_skill.py \
  --case /input/case.json \
  --out /app/output/result.json \
  --work /app/work
```

合成 `case.json`：

```json
{
  "case_id": "synthetic-latex-demo",
  "output_contract": {"status": "string", "compile_report": "object", "compile_plan": "array", "sources": "array"},
  "main_tex": "\\documentclass{article}\n\\begin{document}\nSee Fig.~\\ref{fig:one}.\n\\begin{table}\\begin{tabular}{lc}A & B \\\\ 1 \\end{tabular}\\end{table}\n\\end{document}\n"
}
```

示意输出（节选，仅演示字段与定位方式）：

```json
{"case_id":"synthetic-latex-demo","status":"success","result":{"compile_report":{"errors":[{"code":"undefined_ref","line":3,"message":"\\ref{fig:one} has no matching \\label"}]},"compile_plan":["pdflatex -interaction=nonstopmode main.tex","pdflatex -interaction=nonstopmode main.tex"]},"evidence":[{"line":3,"snippet":"See Fig.~\\ref{fig:one}."}]}
```

## 自查清单

- [ ] `case_id` 保留，合同字段齐全；未映射项已登记。
- [ ] 每个 error 都有文件与行号（对单文件工程核对行号）。
- [ ] 未定义引用 / 缺失 cite 键分开报告，未混为一类。
- [ ] 未声称已编译、未声称生成了 PDF。
- [ ] 编译轮次含 bib 时确实包含 bibtex。
- [ ] 无网络调用、无第三方依赖。


## 自查清单

- [ ] `case_id` 与合同字段保留；未映射项已登记。
- [ ] 每条 error/warning 都有文件、行号、根因与修复动作。
- [ ] 未定义 `\ref` 与缺失 `\cite` 键分列，未混为一类。
- [ ] 编译轮次在含 `.bib` 时包含 bibtex，命令可复现。
- [ ] 未声称已运行 TeX 或生成 PDF。

## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--output` 指定。
2. **必须交付完整成品**：脚本只做静态检查；调用 Agent 必须把每条 error/warning 落到 `compile_report`（文件+行号+根因+修复）、写出完整 `fix_plan` 与可重复 `compile_plan`，覆盖全部检查项而非示例；若任务要求修复源码，须把修正后的 `.tex` 全文写入 `result.corrected_tex`；不得停在“仅诊断”或 `pending`。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 取本合同允许值 `success | partial | insufficient_input | failed`；正文无 `pending`/`TODO`/空占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
