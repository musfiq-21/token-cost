"""Per-pair ratios, spread and the chart. Written before tokencost/compare.py."""
import unittest

from tokencost.compare import describe, overall, pair_rows, svg_chart
from tokencost.counter import cost_usd


def res(pid, lang, inp, out, cat="question", latency=1.0):
    return {"id": pid, "category": cat, "language": lang, "input_tokens": inp,
            "output_tokens": out, "cost_usd": cost_usd(inp, out), "latency_s": latency,
            "truncated": False}


RESULTS = [res("p01", "en", 34, 10), res("p01", "bn", 88, 30),
           res("p02", "en", 25, 20, "arithmetic"), res("p02", "bn", 29, 20, "arithmetic")]


class PairTests(unittest.TestCase):
    def test_ratios_per_pair(self):
        rows = pair_rows(RESULTS, overhead=19)
        p1 = rows[0]
        self.assertEqual(p1["id"], "p01")
        self.assertAlmostEqual(p1["input_ratio"], 88 / 34)
        self.assertAlmostEqual(p1["content_ratio"], (88 - 19) / (34 - 19))
        self.assertAlmostEqual(p1["output_ratio"], 3.0)
        self.assertAlmostEqual(p1["total_cost_ratio"], cost_usd(88, 30) / cost_usd(34, 10))

    def test_missing_language_is_an_error(self):
        with self.assertRaises(ValueError):
            pair_rows(RESULTS[:3], overhead=19)


class SpreadTests(unittest.TestCase):
    def test_describe(self):
        d = describe([1.0, 2.0, 3.0, 4.0])
        self.assertEqual((d["mean"], d["median"], d["min"], d["max"]), (2.5, 2.5, 1.0, 4.0))
        self.assertLessEqual(d["ci95_low"], d["mean"])
        self.assertGreaterEqual(d["ci95_high"], d["mean"])
        self.assertGreaterEqual(d["ci95_low"], 1.0)
        self.assertLessEqual(d["ci95_high"], 4.0)

    def test_bootstrap_is_seeded(self):
        self.assertEqual(describe([1.0, 5.0, 2.0, 8.0]), describe([1.0, 5.0, 2.0, 8.0]))

    def test_constant_values_have_zero_width_interval(self):
        d = describe([2.0, 2.0, 2.0])
        self.assertEqual((d["ci95_low"], d["ci95_high"]), (2.0, 2.0))


class OverallTests(unittest.TestCase):
    def test_overall_ratio_is_ratio_of_totals_not_mean_of_ratios(self):
        o = overall(RESULTS)
        self.assertEqual(o["en"]["input_tokens"], 59)
        self.assertEqual(o["bn"]["input_tokens"], 117)
        self.assertAlmostEqual(o["input_ratio"], 117 / 59)
        en_cost = cost_usd(34, 10) + cost_usd(25, 20)
        bn_cost = cost_usd(88, 30) + cost_usd(29, 20)
        self.assertAlmostEqual(o["total_cost_ratio"], bn_cost / en_cost)


class ChartTests(unittest.TestCase):
    def test_one_bar_per_pair(self):
        svg = svg_chart(pair_rows(RESULTS, overhead=19))
        self.assertTrue(svg.startswith("<svg"))
        self.assertEqual(svg.count('class="bar"'), 2)
        self.assertIn("p01", svg)


if __name__ == "__main__":
    unittest.main()
