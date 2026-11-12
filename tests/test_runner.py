"""The runner with a fake backend. Written before tokencost/runner.py."""
import csv
import json
import os
import tempfile
import unittest

from tests.fakes import FakeOllama, ticking_clock
from tokencost.counter import OllamaCounter
from tokencost.runner import RESULT_COLUMNS, run, write_outputs

PAIRS = [
    {"id": "p01", "category": "question", "english": "Capital of Japan?", "bangla": "জাপানের রাজধানী কী?"},
    {"id": "p02", "category": "arithmetic", "english": "17 + 25?", "bangla": "১৭ + ২৫ কত?"},
    {"id": "p03", "category": "long", "english": "One. Two. Three?", "bangla": "এক। দুই। তিন?"},
]


def make(responder=None):
    fake = FakeOllama(responder)
    return OllamaCounter("qwen2.5:3b", transport=fake, clock=ticking_clock()), fake


class RunTests(unittest.TestCase):
    def test_one_row_per_prompt_and_language(self):
        c, _ = make()
        rows = run(c, PAIRS)["results"]
        self.assertEqual(len(rows), 6)
        self.assertEqual({(r["id"], r["language"]) for r in rows},
                         {(p["id"], l) for p in PAIRS for l in ("en", "bn")})
        bn = next(r for r in rows if r["id"] == "p01" and r["language"] == "bn")
        self.assertEqual(bn["prompt"], "জাপানের রাজধানী কী?")
        self.assertEqual(bn["input_tokens"], 19 + len("জাপানের রাজধানী কী?"))
        for col in RESULT_COLUMNS:
            self.assertIn(col, bn)

    def test_both_languages_get_identical_settings(self):
        c, fake = make()
        run(c, PAIRS)
        options = {json.dumps(b["options"], sort_keys=True) for b in fake.bodies
                   if b["options"]["num_predict"] != 1}
        systems = {b["messages"][0]["content"] for b in fake.bodies}
        self.assertEqual(len(options), 1)
        self.assertEqual(len(systems), 1)

    def test_language_order_alternates_between_pairs(self):
        c, _ = make()
        rows = run(c, PAIRS)["results"]
        firsts = [rows[i]["language"] for i in range(0, 6, 2)]
        self.assertEqual(firsts, ["en", "bn", "en"])

    def test_overhead_and_warmup_are_recorded(self):
        c, _ = make()
        out = run(c, PAIRS)
        self.assertEqual(out["meta"]["overhead_tokens"], 19)
        self.assertIn("settings", out["meta"])

    def test_recount_detects_a_changed_input_count(self):
        seen = {}

        def responder(body):
            user = body["messages"][-1]["content"]
            seen[user] = seen.get(user, 0) + 1
            n = 19 + len(user) - (5 if user == "17 + 25?" and seen[user] > 1 else 0)
            return n, 3, "ok", "stop"
        c, _ = make(responder)
        rows = run(c, PAIRS)["results"]
        bad = [r for r in rows if not r["recount_matches"]]
        self.assertEqual([(r["id"], r["language"]) for r in bad], [("p02", "en")])


class OutputTests(unittest.TestCase):
    def test_files_written(self):
        c, _ = make()
        out = run(c, PAIRS)
        with tempfile.TemporaryDirectory() as d:
            write_outputs(out, d)
            for name in ("results.csv", "results.jsonl", "comparison.csv", "summary.json",
                         "ratio_chart.svg", "run_meta.json"):
                self.assertTrue(os.path.exists(os.path.join(d, name)), name)
            with open(os.path.join(d, "results.csv"), encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 6)
            for col in ("id", "language", "prompt", "output", "input_tokens",
                        "output_tokens", "cost_usd", "latency_s"):
                self.assertIn(col, rows[0])
            with open(os.path.join(d, "comparison.csv"), encoding="utf-8") as f:
                comp = list(csv.DictReader(f))
            self.assertEqual(len(comp), 3)
            self.assertIn("input_ratio", comp[0])


if __name__ == "__main__":
    unittest.main()
