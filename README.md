# Runtime contract

Bohrium Playground Period 4 submission — challenge `product-arena-07-865de7e4` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `latex-build-doctor`
- Summary: Use when a case supplies LaTeX source (main .tex plus optional .bib or template files) and asks to make it compile or to explain build failures; statically checks environments, brace balance, labels and cross-references, citation keys against BibTeX entries, table column specs, math mode, template fields and package requirements, then emits a line-anchored fix report plus a reproducible compile plan in /app/output/result.json while preserving case_id and every output_contract field. Deterministic standard library only; never runs a TeX engine or the network.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input/output contracts, error handling and a minimal
usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
