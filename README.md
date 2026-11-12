# English vs Bangla Token Cost

Measures how much more a Bangla prompt costs than an English prompt with the same meaning,
on **`qwen2.5:3b`** served by Ollama. Python standard library only (no pip installs).
The findings are in [REPORT.md](REPORT.md).

## Run everything (4 commands)

Prerequisites: Python 3.10+, Ollama running (`ollama serve`, or the Ollama desktop app).

```bash
git clone <your-repo-url> && cd AgenticSWE/assignment2-token-cost
ollama pull qwen2.5:3b
python -m unittest
python -m tokencost.runner
```

- `unittest` runs the offline tests. No Ollama is needed: the backend is faked.
- `tokencost.runner` sends all 50 English and 50 Bangla prompts and writes
  `results/qwen2.5-3b/`. It takes about 15 minutes on a laptop GPU.

> Windows: if `python` opens the Microsoft Store, use `py` instead, or turn off the
> "App execution aliases" for python in Windows Settings.

### Other useful commands

```bash
python -m tokencost.runner --limit 3
```

```bash
python -m tokencost.runner --recompare results/qwen2.5-3b
```

```bash
python -m tokencost.runner --model qwen2.5:latest
```

- `--limit 3` is a smoke test on the first 3 pairs.
- `--recompare` rebuilds the comparison, summary and chart from a saved run, without calling
  the model.
- `--model` runs a second model; its results go to `results/<model>/`.

## Layout

```
data/dataset.csv          50 aligned pairs: id, category, english, bangla
tokencost/
  counter.py   one call -> input/output tokens (Ollama's counts), latency, cost; overhead()
  dataset.py   loads and validates the pairs
  runner.py    runs every prompt with identical settings, re-counts each prompt, writes files
  compare.py   per-pair ratios, totals, spread (bootstrap 95% CI), per-category means, chart
results/<model>/
  results.csv / results.jsonl   one row per call: id, language, prompt, output, input_tokens,
                                output_tokens, cost_usd, latency_s (+ content_tokens,
                                done_reason, truncated, output_bengali_share, recount check)
  comparison.csv                one row per pair: EN and BN tokens and every ratio
  summary.json                  totals, spread, per-category means, latency, truncation
  ratio_chart.svg               the per-pair content-token ratio chart used in the report
  run_meta.json                 settings, template overhead, Ollama version, model digest
tests/                          unittest suite with a fake Ollama backend
```

## How tokens are counted

- **Counts are Ollama's own.** Input tokens are `prompt_eval_count` and output tokens are
  `eval_count`, from the `/api/chat` response.
- **Template and system-prompt overhead.** Every call uses one fixed system prompt, which
  says nothing about which language to answer in. The runner measures the overhead once by
  sending an empty user message: 26 tokens on `qwen2.5:3b`. It reports two figures:
  - **input tokens:** what you would pay for;
  - **content tokens:** input minus the overhead. This isolates the tokenizer effect.

  Without a system prompt, Ollama inserts Qwen's default one, so a fixed system prompt
  is needed for a fair comparison.
- **Prompt caching.** Ollama can reuse a cached prompt, so after the main run every prompt is
  counted again, in reverse order, and the run records whether the count changed
  (`recount_matches`). On Ollama 0.40.16 the counts never changed. Caching only made
  repeated prompts faster. A warm-up call loads the model before any timed call.
- **Same settings for both languages:**
  - temperature 0, seed 42;
  - `num_predict` (max output tokens) 512;
  - `num_ctx` 4096.

  The order alternates (EN first, then BN first) from pair to pair, so slow-down over
  time affects both languages equally.
- **Cost.** Notional course prices: $0.15 per million input tokens and $0.60 per million
  output tokens.

## Model tag

`qwen2.5:3b` (Ollama id `357c53fb659c`). Model files are not committed.
