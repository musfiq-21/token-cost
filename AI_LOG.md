# AI-assistant use log

The course requires three lines per piece: what the assistant wrote, which test proves it,
and what I reviewed. The third column is for **me** to fill in after reading the code and
the data.

Assistant: Claude Code (Claude Opus 5.5). The test modules were written first and run red
(all 4 failed on import), then the code was written to make them pass.

| # | What it wrote | Test that proves it | What I reviewed |
|---|---|---|---|
| 1 | `data/dataset.csv`: 50 English prompts **and their Bangla versions**. The Bangla was written by the assistant, not by a translation tool. **Every pair must be checked by a Bangla speaker for same meaning and natural wording.** | `tests/test_dataset.py` (50 unique pairs, 6 categories, scripts in the right columns, length variety, 3–5 sentences in long prompts) | |
| 2 | `tokencost/counter.py`: Ollama call, token counts, latency, cost, template overhead | `tests/test_counter.py` (fake backend: counts, truncation, missing counts, settings, cost arithmetic) | |
| 3 | `tokencost/runner.py`: same-settings runner, alternating order, re-count cache check, output files | `tests/test_runner.py` (6 rows for 3 pairs, identical settings, order, re-count mismatch detected, files written) | |
| 4 | `tokencost/compare.py`: per-pair ratios, totals, bootstrap CI, per-category means, SVG chart | `tests/test_compare.py` (ratios, ratio of totals, seeded bootstrap, one bar per pair) | |
| 5 | `REPORT.md` draft, including the 10-pair quality check | No unit test. The numbers come from `results/qwen2.5-3b/summary.json`, and the quality verdicts must be re-checked by a Bangla speaker. | |

Found during development: the CSVs were first written with a UTF-8 byte-order mark (BOM),
so the first column read back as `﻿id`. `test_files_written` caught it, and the files
are now plain UTF-8.
