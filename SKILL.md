---
name: latex-build-doctor
description: Use when a case supplies LaTeX source (main .tex plus optional .bib or template files) and asks to make it compile or to explain build failures; statically checks environments, brace balance, labels and cross-references, citation keys against BibTeX entries, table column specs, math mode, template fields and package requirements, then emits a line-anchored fix report plus a reproducible compile plan in /app/output/result.json while preserving case_id and every output_contract field. Deterministic standard library only; never runs a TeX engine or the network.
---

# LaTeX 源码诊断与可重复编译（行号—根因—修复计划）

## 用途与适用条件

当输入是一个 LaTeX 工程（主文件、可选子文件、`.bib`、模板说明），需要判断“为什么不编译/为什么引用是问号/为什么表格溢出”，并给出可复核的修复路径时使用。

适用：单文件或多文件 `.tex`（含 `\documentclass`）；需要把错误定位到**文件 + 行号 + 根因**；需要核对 `\label/\ref`、`\cite/.bib`、表格列数、数学环境、模板必填项；需要给出可重复的编译轮次与依赖说明。

不适用：真正调用 TeX 引擎生成 PDF（本 Skill 只做静态诊断与计划）、替作者补写缺失章节、判断论文科学正确性。

## 输入

- `/input/case.json`（必需，`--case` 可覆盖）：读取 `case_id`、`output_contract`、`task`，以及 `main_tex`、`tex`、`latex_source`、`files`、`template`、`bib`、`bibliography` 等字段。
- `task.md`：读 `/input/task.md` 或 `/app/work/task.md`，缺失不阻塞；其中的字段要求优先于本文件。
- 文件既可为内联字符串，也可为路径。脚本只读取存在、UTF-8 可解码、≤2MB 的文本；二进制/PDF 登记为未解析。
- 输出目录 `/app/output`，工作目录 `/app/work`。

## 处理流程

脚本 `scripts/run_skill.py` 做确定性静态检查；Agent 依据报告改源码并复述编译计划。

1. **工程识别**：区分主文件（含 `\documentclass` 的最长文件）、子文件、`.bib`、模板文件；登记每个文件的行数与 SHA-256。
2. **环境配对**：栈匹配 `\begin{env}`/`\end{env}`，报告未闭合、错序与多余 `\end`，附行号。
3. **括号平衡**：统计未转义 `{}`，报告首次深度为负的行与文件末残余深度；忽略 `\{`、`\}` 与注释。
4. **交叉引用**：`\label` 与 `\ref/\eqref/\autoref/\cref` 求差集，报告未定义引用、重复标签、未被引用的标签。
5. **文献键**：解析 `\cite{...}`（含多键与可选参数）与 BibTeX `@type{key,`，报告缺失条目、未被引用的条目；无 `.bib` 时明确说明无法核验。
6. **表格与浮动体**：`tabular` 列格式列数与每行 `&` 数比对；`[H]` 无 `float` 宏包、`table` 未置于浮动体给警告。
7. **数学模式**：未转义 `$` 奇偶性；`align/equation` 是否含 `&`；`\text` 外中文提示。
8. **模板必填项**：`\title`、`\author`、`abstract` 环境、`\keywords`；缺失列入 `template_required_missing`，不代写内容。
9. **可重复构建**：轮次计划（含 bib 时 `pdflatex → bibtex → pdflatex → pdflatex`，否则两遍 `pdflatex`）与 `latexmk -pdf -interaction=nonstopmode` 等价命令；再由源码推断引擎（`fontspec`/CJK 宏包 → `xelatex` 或 `lualatex`，否则 `pdflatex`）与所用 `\usepackage` 清单，版本一律标 `unverified`，不声称已实测。
10. **合同保留**：见输出契约。

## 输出契约（字段 → 类型 → 含义/示例）

写入 `/app/output/result.json`。下表是脚本实际产出的结构；Agent 只需补 `patched_tex`、`build_environment`，并改写 `change_record` 中已落盘的条目。

| 字段 | 类型 | 含义 / 示例 |
|---|---|---|
| `case_id` | string | 输入原值：`"case-a"` |
| `status` | string | `success`｜`partial`｜`insufficient_input`｜`failed` |
| `result.compile_report` | object | `{"errors":[],"warnings":[],"info":[]}` |
| `result.compile_report.*[]` | object | `{"code":"undefined_ref","severity":"error","file":"main.tex","line":3,"message":"\\ref{fig:one} has no matching \\label","fix":"Add \\label{fig:one}.","snippet":"See Fig.~\\ref{fig:one}."}` |
| `result.compile_plan` | array[string] | 有序命令，如 `"pdflatex -interaction=nonstopmode -halt-on-error main.tex"` |
| `result.build_environment` | object | Agent 补：`{"engine":"pdflatex","engine_basis":"no fontspec/CJK package","packages":["amsmath"],"fonts":[],"version_status":"unverified"}` |
| `result.fix_plan` | array | `{"priority":1,"file":"main.tex","line":3,"action":"...","code":"undefined_ref"}` |
| `result.file_inventory` | array | `{"name","path","kind","lines","chars","sha256","is_main"}` |
| `result.template_check` | object | `documentclass_present`/`title_present`/`author_present`/`abstract_present`/`keywords_present` |
| `result.patched_tex` | string\|null | 修正后 `.tex` 全文，字段名就是 `patched_tex`（不是 `corrected_tex`）；脚本留 `null`，任务要求修改时必须由 Agent 填写 |
| `result.change_record` | array | `{"file","line","code","action","before","after","applied"}`；`before` 是原文该行，`applied=false` 表示尚未改入源码 |
| `result.manual_confirmation` | array | `{"item":"citation_keys","reason":"No .bib was supplied; citation keys remain unverified."}` |
| `evidence` | array | `{"code","file","line","snippet"}`，`snippet` 为原文该行片段，用于逐条复核 |
| `uncertainty` / `limitations` | array | 不确定性（如 `main_file` 歧义）与边界声明 |
| `errors` / `stats` | array / object | 运行级错误；文件数与 error/warning/info 计数 |
| `contract_status` | object | `declared_fields`/`preserved_fields`/`unmapped_fields`/`unsupported_features`/`contract_present` |

合同规则：原始 `output_contract` 每个字段名都保留（字典 / 列表 / `fields` / Schema `properties` 均支持）；已识别字段按别名填入，无法映射写 `null` 并登记 `unmapped_fields`，`status` 降为 `partial`。脚本进程始终以 0 结束，诊断看 `status` 与 `contract_status`，不要依赖退出码。

## 异常处理

| 情形 | 处置 |
|---|---|
| `case.json` 不可读 | `status=failed`，`errors` 记录，不伪造诊断 |
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

以下为合成示意，非官方案例，数据为构造。

```bash
python /skills/weekly-skill/scripts/run_skill.py \
  --case /input/case.json --out /app/output/result.json --work /app/work
```

输出节选（键名与实际运行一致）：

```json
{"case_id":"synthetic-latex-demo","status":"success","result":{"compile_report":{"errors":[{"code":"undefined_ref","severity":"error","file":"main.tex","line":3,"message":"\\ref{fig:one} has no matching \\label","fix":"Add \\label{fig:one}.","snippet":"See Fig.~\\ref{fig:one}."}]},"compile_plan":["pdflatex -interaction=nonstopmode -halt-on-error main.tex","pdflatex -interaction=nonstopmode -halt-on-error main.tex"],"patched_tex":null,"change_record":[{"file":"main.tex","line":3,"code":"undefined_ref","before":"See Fig.~\\ref{fig:one}.","after":null,"applied":false}],"manual_confirmation":[{"item":"build_environment","reason":"versions unverified"}]},"evidence":[{"code":"undefined_ref","file":"main.tex","line":3,"snippet":"See Fig.~\\ref{fig:one}."}],"contract_status":{"unmapped_fields":[]}}
```

## 交付顺序与自检

1. `python scripts/run_skill.py --case <输入> --out <输出>`（`--output` 等价；默认 `/input/case.json` → `/app/output/result.json`）。
2. 脚本只给诊断骨架。任务要求修复时，Agent 必须把修正后的完整 `.tex` 写入 `result.patched_tex`，在 `result.change_record` 逐条补 `after` 并置 `applied=true`，再补 `result.build_environment`；不得停在“仅诊断”。
3. 自检：`case_id` 与输入一致；`output_contract` 每字段存在；无 `pending`/`TODO`/空占位；每条 error/warning 有文件+行号+根因+修复；未定义 `\ref` 与缺失 `\cite` 键分列；含 `.bib` 的轮次含 bibtex；未声称已编译或生成 PDF；未联网。

评分对应：实际效果看可编辑 `.tex` 成品与逐条修复记录；使用增益看文件+行号+根因是否减少试编译；创新看错误分类与修复闭环；可靠体验看异常降级与重复运行一致性；生态贡献看调用说明、示例与自查清单。
