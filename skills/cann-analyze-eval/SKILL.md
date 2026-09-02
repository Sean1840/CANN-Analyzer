---
name: cann-analyze-eval
description: >
  Run and interpret CANN-Analyze skill/tool evaluation. Use when the user asks
  to evaluate skills, golden cases, locate accuracy, 有效性, rubric, or
  /cann-analyze-eval. Do not use this skill to diagnose a production failure.
---

# Evaluate CANN-Analyze

Rubric (single source): [eval/rubric.md](../../eval/rubric.md)

## Run the tool bar

From repo root:

```text
python eval/run_eval.py
```

All committed cases must pass. A skill or extractor change that drops `locate_hit@1` or `no_verdict` is not shippable.

## Skill-only metrics

`stage_split` and `no_hallucination` need an agent JSON with `{ "id": "...", "stage": "...", "repos": [] }` per case. If that file is absent, mark those metrics skipped.

## When adding a real miss

1. Put the anonymized log under `fixtures/logs/`.
2. Add `eval/cases/<id>.json` with `expect.path_suffix` and `expect.stage`.
3. Re-run `python eval/run_eval.py`.
4. Fix extractor, catalog, or skill tree — not a one-off sentence in SKILL.md.
