# 写作13｜LaTeX 写作与编译

本题：写作13｜LaTeX 写作与编译（product-arena-07-865de7e4，赛道 writing）。

能力定位：在保留原始命令、环境、标签、引用键与数值的前提下整理 LaTeX 源码，产出可继续编辑的成稿，并给出逐条可核验的来源与修改记录

交付物：result.json（契约齐全）、可编辑 LaTeX 稿件、evidence_map、change_log


## 这个 Skill 做什么

一条流水线，四段职责，全程可回溯到材料原文：

| 阶段 | 谁做 | 产物 |
|---|---|---|
| 1 取证 | `scripts/sk_entry.py` + `scripts/sk_base.py` | 材料 → 段落 id → 证据锚点 |
| 2 判断 | 执行 Agent（读 `agent_tasks.json`） | `agent_judgement.json`（领域判断） |
| 3 校验合并 | `scripts/topic.py` | 引文逐字核对，退回编造的条目 |
| 4 出品 | 赛道专用引擎 | **真实文件**（不是规格描述） |

## 真实交付物

| 文件 | 作用 |
|---|---|
| `result.json` | 契约齐全的结构化结果与改动回执 |
| `manuscript.md` | **真实可编辑稿件**：章节结构取自材料自身的标题 |
| `change-log.md` | 逐条 before/after 改动记录 + 锚点守恒检查 |
| `evidence-map.json` | 章节 → 段落 / 锚点的来源映射；另含 `anchor_locations[]`（逐条锚点：类型 / 取值 / 文件 / 行号 / 段落 id / 原文短引）与 `key_claims[]`（带锚点的关键论断原句） |
| `edit-targets.json` | 若输入提供 `organizer-edit-workorder.json`，则逐条编辑目标给回执（改前 / 改后 / 定位） |
| `qa-report.json` | 逐节锚点守恒统计、edit-target 状态与人工待核清单 |
| `format-spec-checklist.json` | **格式规格逐项核对清单**：栏数、字号、行距、页边距、标题层级、图表题注、参考文献样式、导出格式等；每项给出出处文件、行号与原文短引，材料未写明的记为 `not_specified_in_materials` |
| `anomaly-report.json` | **材料缺口与异常自报**：格式规格缺失 / 冲突、锚点守恒异常、空章节、待人工确认项 |


`result.json` 里的 `editable_source` / `exports` / `provenance_and_changes`
三组键**指向磁盘上真实存在的文件**，每条记录都带 `sha256` 与字节数，
评审可以直接打开文件核对。

## 目录

```
SKILL.md                     Skill 定义（frontmatter: name / description）
environment/resources.yaml   资源入口（评测方读这个文件定位脚本与依赖）
scripts/sk_entry.py          入口脚本（发现输入 → 执行 → 装配 → 自检）
scripts/sk_base.py           公共库（契约解析、证据构造、结果装配）
scripts/topic.py             题目逻辑（契约自适应 + 赛道分流）
scripts/artifacts.py         graphics 引擎：实体—连接—步骤 IR → 分层 SVG → 渲染 PNG
scripts/pptxgen.py           slides 引擎：stdlib-only 真实 PPTX + 逐页 SVG/PNG
scripts/specialize.py        reading/writing 引擎：逐字段抽取 / 可编辑稿件 + 改动记录
scripts/sk_selftest.py       独立自检
assets/result-schema.md      result.json 字段说明
assets/policy.json           不编造承诺
references/                  证据纪律 / 契约处理 / 失败模式 / 产物流水线
examples/demo-case/          可离线复现的最小案例
```

## 离线复现

```bash
# 阶段 A：取证 + 出任务单
python scripts/sk_entry.py --input examples/demo-case --work /tmp/w --out /tmp/o
cat /tmp/w/agent_tasks.json

# 阶段 B：照任务单写判断（模板见 examples/demo-case/agent_judgement.example.json）
#   → /tmp/w/agent_judgement.json

# 阶段 C：校验引文并合并进 result.json
python scripts/sk_entry.py --input examples/demo-case --work /tmp/w --out /tmp/o
ls -l /tmp/o
```

## 自检

```bash
python scripts/sk_selftest.py --input examples/demo-case
```

自检覆盖：契约键是否全部非空、每条 claim 是否带 `paragraph_id` + 原文 `quote`、
引文是否能在材料里逐字找回、是否残留 `__pycache__`。

## 环境要求

- Python >= 3.10
- **仅标准库**，无需 `pip install`
- 无网络访问
- 渲染预览优先用环境里已有的渲染器（ImageMagick / CairoSVG / Pillow），
  都没有时回退到纯 Python 光栅化，SVG 源文件始终交付

## 复用

`scripts/` 下的五个模块可以单独 import 使用，与 Harbor 运行时解耦：

```python
import sys; sys.path.insert(0, "scripts")
import sk_base, topic, specialize, artifacts, pptxgen
```

- `sk_base.make_evidence()` —— 构造带段落定位与原文短引的证据条目
- `sk_base.assemble_result()` —— 按契约装配 `result.json`
- `specialize.extract_target_fields()` —— 逐 `field_id` 抽取并给出四态状态
- `artifacts.extract_structure()` / `build_svg()` —— 从材料抽出结构并生成分层 SVG
- `pptxgen.build_pages()` / `write_slides_artifacts()` —— 生成真实 PPTX 与逐页预览

## 提交

```bash
playground submit --challenge-id product-arena-07-865de7e4 --outputs . --trace trace.jsonl
```

## 许可证

MIT（见 `LICENSE`）。
