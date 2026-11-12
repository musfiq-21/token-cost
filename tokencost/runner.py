"""Send every English and Bangla prompt to the model with identical settings; record all.

    python -m tokencost.runner                       # qwen2.5:3b -> results/qwen2.5-3b/
    python -m tokencost.runner --model qwen2.5:latest
    python -m tokencost.runner --recompare results/qwen2.5-3b   # rebuild comparison offline
"""
import argparse
import csv
import json
import os
import urllib.request

from . import DEFAULT_MODEL, PROJECT_ROOT, safe_console
from .compare import pair_rows, summarize, svg_chart
from .counter import OllamaCounter, bengali_share
from .dataset import DATASET, load_dataset

RESULT_COLUMNS = ["id", "category", "language", "prompt", "output", "input_tokens",
                  "output_tokens", "content_tokens", "cost_usd", "latency_s", "done_reason",
                  "truncated", "output_bengali_share", "recount_input_tokens", "recount_matches"]


def run(counter, pairs, log=lambda msg: None):
    counter.call("Hello", num_predict=1)          # warm-up: load the model before timing
    overhead = counter.overhead()
    results = []
    for i, p in enumerate(pairs):
        # alternate which language goes first so warm-up/thermal drift hits both equally
        order = ("en", "bn") if i % 2 == 0 else ("bn", "en")
        for lang in order:
            prompt = p["english"] if lang == "en" else p["bangla"]
            r = counter.call(prompt)
            row = {"id": p["id"], "category": p["category"], "language": lang,
                   "prompt": prompt, **r, "content_tokens": r["input_tokens"] - overhead,
                   "output_bengali_share": round(bengali_share(r["output"]), 3)}
            results.append(row)
            log(f'{p["id"]} {lang}: in {r["input_tokens"]:>4}  out {r["output_tokens"]:>4}  '
                f'{r["latency_s"]:6.2f}s{"  TRUNCATED" if r["truncated"] else ""}')
    # cache check: count every prompt again, in reverse order, after other prompts ran
    for row in reversed(results):
        again = counter.call(row["prompt"], num_predict=1)["input_tokens"]
        row["recount_input_tokens"] = again
        row["recount_matches"] = again == row["input_tokens"]
    meta = {"settings": counter.settings(), "overhead_tokens": overhead,
            "pairs": len(pairs), "calls": len(results)}
    return {"results": results, "meta": meta}


def _get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # metadata is best effort
        return {}


def ollama_info(host, model):
    tags = _get_json(host.rstrip("/") + "/api/tags").get("models", [])
    digest = next((m.get("digest", "")[:12] for m in tags if m.get("name") == model), "")
    return {"ollama_version": _get_json(host.rstrip("/") + "/api/version").get("version"),
            "model_digest": digest}


def write_outputs(out, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    results, meta = out["results"], out["meta"]
    with open(os.path.join(out_dir, "results.jsonl"), "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({c: r.get(c) for c in RESULT_COLUMNS}, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "results.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    rows = pair_rows(results, meta["overhead_tokens"])
    with open(os.path.join(out_dir, "comparison.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = summarize(results, meta["overhead_tokens"])
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(out_dir, "ratio_chart.svg"), "w", encoding="utf-8") as f:
        f.write(svg_chart(rows))
    with open(os.path.join(out_dir, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return summary


def load_results(out_dir):
    with open(os.path.join(out_dir, "results.jsonl"), encoding="utf-8") as f:
        results = [json.loads(line) for line in f]
    with open(os.path.join(out_dir, "run_meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    return {"results": results, "meta": meta}


def print_summary(s):
    o = s["overall"]
    sp = s["spread"]
    print(f'pairs {s["pairs"]}, template/system overhead {s["overhead_tokens"]} tokens')
    print(f'input tokens  EN {o["en"]["input_tokens"]}  BN {o["bn"]["input_tokens"]}  '
          f'ratio {o["input_ratio"]:.2f} (content only {s["overall_content_ratio"]:.2f})')
    print(f'output tokens EN {o["en"]["output_tokens"]}  BN {o["bn"]["output_tokens"]}  '
          f'ratio {o["output_ratio"]:.2f}')
    print(f'cost USD      EN {o["en"]["cost_usd"]:.6f}  BN {o["bn"]["cost_usd"]:.6f}  '
          f'ratio {o["total_cost_ratio"]:.2f}')
    for k in ("input_ratio", "content_ratio", "total_cost_ratio"):
        d = sp[k]
        print(f'{k:17} mean {d["mean"]:.2f} median {d["median"]:.2f} min {d["min"]:.2f} '
              f'max {d["max"]:.2f} 95% CI [{d["ci95_low"]:.2f}, {d["ci95_high"]:.2f}]')
    print(f'truncated {s["truncated"]}, recount mismatches {s["recount_mismatches"]}')


def main(argv=None):
    safe_console()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--num-predict", type=int, default=512, help="max output tokens")
    ap.add_argument("--limit", type=int, help="only the first N pairs (smoke test)")
    ap.add_argument("--out", help="output folder (default results/<model>)")
    ap.add_argument("--recompare", metavar="DIR",
                    help="rebuild comparison/summary/chart from a saved run, no model calls")
    args = ap.parse_args(argv)

    if args.recompare:
        print_summary(write_outputs(load_results(args.recompare), args.recompare))
        return
    pairs = load_dataset(DATASET)[: args.limit]
    counter = OllamaCounter(args.model, host=args.host, num_predict=args.num_predict)
    out = run(counter, pairs, log=print)
    out["meta"].update(ollama_info(args.host, args.model))
    out_dir = args.out or os.path.join(PROJECT_ROOT, "results", args.model.replace(":", "-"))
    print_summary(write_outputs(out, out_dir))
    print("written to", out_dir)


if __name__ == "__main__":
    main()
