"""Bangla vs English: per-pair ratios, overall totals, spread and one chart."""
import random
import statistics

LANGS = ("en", "bn")


def _ratio(a, b):
    return a / b if b else None


def pair_rows(results, overhead):
    by = {}
    for r in results:
        by.setdefault(r["id"], {})[r["language"]] = r
    rows = []
    for pid, d in by.items():
        if set(d) != set(LANGS):
            raise ValueError(f"pair {pid} is missing a language: has {sorted(d)}")
        en, bn = d["en"], d["bn"]
        en_c, bn_c = en["input_tokens"] - overhead, bn["input_tokens"] - overhead
        rows.append({
            "id": pid, "category": en["category"],
            "en_input": en["input_tokens"], "bn_input": bn["input_tokens"],
            "en_content": en_c, "bn_content": bn_c,
            "en_output": en["output_tokens"], "bn_output": bn["output_tokens"],
            "en_cost_usd": en["cost_usd"], "bn_cost_usd": bn["cost_usd"],
            "input_ratio": _ratio(bn["input_tokens"], en["input_tokens"]),
            "content_ratio": _ratio(bn_c, en_c),
            "output_ratio": _ratio(bn["output_tokens"], en["output_tokens"]),
            "total_cost_ratio": _ratio(bn["cost_usd"], en["cost_usd"]),
            "en_latency_s": en["latency_s"], "bn_latency_s": bn["latency_s"],
            "en_truncated": en["truncated"], "bn_truncated": bn["truncated"],
            "bn_answer_bengali_share": bn.get("output_bengali_share"),
        })
    return rows


def describe(values, n_boot=10000, seed=12345):
    """Mean, median, min, max and a 95% bootstrap interval for the mean."""
    values = [v for v in values if v is not None]
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(n_boot))
    return {"n": len(values), "mean": statistics.fmean(values),
            "median": statistics.median(values), "min": min(values), "max": max(values),
            "ci95_low": means[int(0.025 * n_boot)], "ci95_high": means[int(0.975 * n_boot) - 1]}


def overall(results):
    tot = {lang: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
           for lang in LANGS}
    for r in results:
        t = tot[r["language"]]
        t["calls"] += 1
        t["input_tokens"] += r["input_tokens"]
        t["output_tokens"] += r["output_tokens"]
        t["cost_usd"] += r["cost_usd"]
    en, bn = tot["en"], tot["bn"]
    return {**tot,
            "input_ratio": _ratio(bn["input_tokens"], en["input_tokens"]),
            "output_ratio": _ratio(bn["output_tokens"], en["output_tokens"]),
            "total_cost_ratio": _ratio(bn["cost_usd"], en["cost_usd"])}


def summarize(results, overhead):
    rows = pair_rows(results, overhead)
    cats = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    content = {"en": sum(r["en_content"] for r in rows), "bn": sum(r["bn_content"] for r in rows)}
    lat = {lang: [r["latency_s"] for r in results if r["language"] == lang] for lang in LANGS}
    bn_rows = [r for r in results if r["language"] == "bn"]
    return {
        "pairs": len(rows),
        "overhead_tokens": overhead,
        "overall": overall(results),
        "overall_content_ratio": _ratio(content["bn"], content["en"]),
        "content_tokens": content,
        "spread": {k: describe([r[k] for r in rows])
                   for k in ("input_ratio", "content_ratio", "output_ratio", "total_cost_ratio")},
        "by_category": {c: {"pairs": len(rs),
                            "content_ratio_mean": statistics.fmean(r["content_ratio"] for r in rs),
                            "input_ratio_mean": statistics.fmean(r["input_ratio"] for r in rs),
                            "total_cost_ratio_mean": statistics.fmean(r["total_cost_ratio"] for r in rs),
                            "en_content": sum(r["en_content"] for r in rs),
                            "bn_content": sum(r["bn_content"] for r in rs)}
                        for c, rs in cats.items()},
        "latency_s": {lang: {"mean": statistics.fmean(v), "median": statistics.median(v),
                             "total": sum(v)} for lang, v in lat.items()},
        "truncated": {lang: sum(1 for r in results if r["language"] == lang and r["truncated"])
                      for lang in LANGS},
        "bn_answers_mostly_bangla": sum(1 for r in bn_rows
                                        if (r.get("output_bengali_share") or 0) >= 0.5),
        "recount_mismatches": sum(1 for r in results if r.get("recount_matches") is False),
    }


# --- chart -------------------------------------------------------------------------------
# One series (the per-pair ratio), so one hue and no legend; categories are grouped on the
# x axis. Colors follow the reference palette; dark mode has its own steps.
_STYLE = """
  .surface { fill: #fcfcfb; } .bar { fill: #2a78d6; } .ink { fill: #0b0b0b; }
  .ink2 { fill: #52514e; } .muted { fill: #898781; } .grid { stroke: #e1e0d9; }
  .ref { stroke: #52514e; } .mean { stroke: #0b0b0b; }
  @media (prefers-color-scheme: dark) {
    .surface { fill: #1a1a19; } .bar { fill: #3987e5; } .ink { fill: #f0efec; }
    .ink2 { fill: #c3c2b7; } .grid { stroke: #2c2c2a; } .ref { stroke: #c3c2b7; }
    .mean { stroke: #f0efec; }
  }
  text { font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }
"""


def _bar_path(x, y, w, h, r=3):
    """A bar with rounded data-end (top) corners, anchored square to the baseline."""
    r = min(r, w / 2, h)
    return (f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
            f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z")


def svg_chart(rows, key="content_ratio",
              title="Bangla ÷ English content tokens, per prompt pair",
              subtitle="Content tokens = input tokens minus the fixed template/system overhead. "
                       "1× = same cost."):
    vals = [r[key] for r in rows if r[key] is not None]
    mean = statistics.fmean(vals)
    top = max(2, int(max(vals)) + 1)
    W, H = 820, 380
    left, right, ytop, ybot = 48, 84, 70, 300     # right margin holds the line labels
    groups = []
    for r in rows:
        if not groups or groups[-1][0] != r["category"]:
            groups.append((r["category"], []))
        groups[-1][1].append(r)
    gap_groups = 14
    slot = (W - left - right - gap_groups * (len(groups) - 1)) / len(rows)
    bw = max(2.0, slot - 2)            # 2px surface gap between adjacent bars

    def y(v):
        return ybot - (ybot - ytop) * v / top

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
           f'height="{H}" role="img" aria-label="{title}"><style>{_STYLE}</style>',
           f'<rect class="surface" width="{W}" height="{H}"/>',
           f'<text class="ink" x="{left}" y="26" font-size="16" font-weight="600">{title}</text>',
           f'<text class="ink2" x="{left}" y="46" font-size="12">{subtitle}</text>']
    for t in range(0, top + 1):
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y(t):.1f}" '
                   f'y2="{y(t):.1f}" stroke-width="1"/>')
        out.append(f'<text class="muted" x="{left - 8}" y="{y(t) + 4:.1f}" font-size="11" '
                   f'text-anchor="end">{t}×</text>')
    x = left
    for cat, rs in groups:
        x0 = x
        for r in rs:
            v = r[key]
            if v is not None:
                out.append(f'<path class="bar" d="{_bar_path(x + 1, y(v), bw, ybot - y(v))}">'
                           f'<title>{r["id"]} ({cat}): {v:.2f}× '
                           f'(EN {r["en_content"]} vs BN {r["bn_content"]} tokens)</title></path>')
            x += slot
        out.append(f'<text class="ink2" x="{(x0 + x) / 2:.1f}" y="{ybot + 18}" font-size="11" '
                   f'text-anchor="middle">{cat}</text>')
        out.append(f'<text class="muted" x="{(x0 + x) / 2:.1f}" y="{ybot + 32}" font-size="10" '
                   f'text-anchor="middle">{rs[0]["id"]}–{rs[-1]["id"]}</text>')
        x += gap_groups
    out.append(f'<line class="ref" x1="{left}" x2="{W - right}" y1="{y(1):.1f}" y2="{y(1):.1f}" '
               f'stroke-width="1.5" stroke-dasharray="2 3"/>')
    out.append(f'<line class="mean" x1="{left}" x2="{W - right}" y1="{y(mean):.1f}" '
               f'y2="{y(mean):.1f}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    out.append(f'<text class="ink" x="{W - right + 6}" y="{y(mean) + 4:.1f}" font-size="11">'
               f'mean {mean:.2f}×</text>')
    out.append(f'<text class="ink2" x="{W - right + 6}" y="{y(1) + 4:.1f}" font-size="11">'
               f'1× parity</text>')
    out.append(f'<text class="muted" x="{left}" y="{H - 14}" font-size="10">Each bar is one '
               f'prompt pair; hover a bar for its token counts.</text>')
    out.append("</svg>")
    return "\n".join(out)
