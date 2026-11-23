# Runtime contract

Bohrium Playground Period 4 submission — challenge `product-arena-07-865de7e4` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `bohr-writing-latex-compile`
- Summary: 当需要完成 LaTeX 写作与编译任务并产出可复核结果时使用。本题范围：写作13｜LaTeX 写作与编译。题目家族：学术写作（academic-writing）。任务要求：依据固定科研材料完成 LaTeX 源码的写作、修改与编译准备，覆盖编译问题到文件与行号的定位、公式与表格、交叉引用与参考文献、版式与模板必填项的一致性，交付可继续编辑的源码成果，并记录模板版本、宏包与字体版本、编译命令与轮次以支持重复构建；材料未报告的内容明确说明，不能联网补写。输出可编辑的目标产物、事实/证据映射、修改或生成记录和人工确认项；不得虚构材料外事实。产出 result.json，其中包含运行时 output_contract 要求的全部字段与 case_id，每条结论附带原文证据（段落定位 + 短引），无法从材料判断的部分如实写入 uncertainty 而非编造。

## Contents

| File |
|------|
| `LICENSE` |
| `README.md` |
| `SKILL.md` |
| `assets/contract-aliases.json` |
| `assets/policy.json` |
| `assets/result-schema.md` |
| `environment/resources.yaml` |
| `environment/runtime.txt` |
| `examples/demo-case/agent_judgement.example.json` |
| `examples/demo-case/case.json` |
| `examples/demo-case/material.md` |
| `examples/demo-case/task.md` |
| `examples/quickstart.md` |
| `references/artifact-pipeline.md` |
| `references/contract-handling.md` |
| `references/evidence-discipline.md` |
| `references/failure-modes.md` |
| `references/two-phase-workflow.md` |
| `scripts/artifacts.py` |
| `scripts/pptxgen.py` |
| `scripts/sk_base.py` |
| `scripts/sk_entry.py` |
| `scripts/sk_selftest.py` |
| `scripts/skill_profile.json` |
| `scripts/specialize.py` |
| `scripts/topic.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

Two passes are intended: the first writes `/app/work/agent_tasks.json` (evidence
skeleton) and `/app/output/result.json`; after the agent writes
`/app/work/agent_judgement.json`, the second pass merges and validates the result.
See `SKILL.md` and `references/two-phase-workflow.md`.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.
