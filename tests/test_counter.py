"""Token counting and cost. Written before tokencost/counter.py."""
import unittest

from tests.fakes import FakeClock, FakeOllama
from tokencost.counter import (PRICE_IN_PER_M, PRICE_OUT_PER_M, SYSTEM_PROMPT, OllamaCounter,
                               bengali_share, cost_usd)


def counter(responder=None, clock=None, **kw):
    fake = FakeOllama(responder)
    return OllamaCounter("qwen2.5:3b", transport=fake, clock=clock or FakeClock(1.0, 3.5), **kw), fake


class CountTests(unittest.TestCase):
    def test_counts_come_from_ollama_fields(self):
        c, _ = counter(lambda b: (34, 10, "Tokyo.", "stop"))
        r = c.call("What is the capital of Japan?")
        self.assertEqual(r["input_tokens"], 34)
        self.assertEqual(r["output_tokens"], 10)
        self.assertEqual(r["output"], "Tokyo.")
        self.assertFalse(r["truncated"])

    def test_length_stop_is_marked_truncated(self):
        c, _ = counter(lambda b: (34, 512, "a very long", "length"))
        self.assertTrue(c.call("x")["truncated"])

    def test_missing_counts_raise(self):
        c, _ = counter(lambda b: (None, 3, "x", "stop"))
        with self.assertRaises(ValueError):
            c.call("x")

    def test_latency_is_measured_around_the_call(self):
        c, _ = counter(clock=FakeClock(10.0, 12.25))
        self.assertAlmostEqual(c.call("x")["latency_s"], 2.25)

    def test_cost_is_attached(self):
        c, _ = counter(lambda b: (1000, 500, "x", "stop"))
        self.assertAlmostEqual(c.call("x")["cost_usd"], cost_usd(1000, 500))


class SettingsTests(unittest.TestCase):
    def test_fixed_system_prompt_and_options_are_sent(self):
        c, fake = counter()
        c.call("hello")
        body = fake.bodies[0]
        self.assertEqual(body["messages"][0], {"role": "system", "content": SYSTEM_PROMPT})
        self.assertEqual(body["messages"][1], {"role": "user", "content": "hello"})
        self.assertEqual(body["options"]["temperature"], 0)
        self.assertEqual(body["options"]["seed"], 42)
        self.assertEqual(body["options"]["num_predict"], 512)
        self.assertFalse(body["stream"])

    def test_system_prompt_has_no_language_instruction(self):
        self.assertNotIn("language", SYSTEM_PROMPT.lower())
        self.assertNotIn("bangla", SYSTEM_PROMPT.lower())

    def test_num_predict_override_for_a_count_only_call(self):
        c, fake = counter(clock=FakeClock(0, 1, 2, 3))
        c.call("x", num_predict=1)
        self.assertEqual(fake.bodies[0]["options"]["num_predict"], 1)

    def test_overhead_is_the_count_for_an_empty_prompt(self):
        c, fake = counter(lambda b: (19 + len(b["messages"][-1]["content"]), 1, "", "length"))
        self.assertEqual(c.overhead(), 19)
        self.assertEqual(fake.bodies[0]["messages"][-1]["content"], "")


class CostTests(unittest.TestCase):
    def test_course_prices(self):
        self.assertEqual(PRICE_IN_PER_M, 0.15)
        self.assertEqual(PRICE_OUT_PER_M, 0.60)
        self.assertAlmostEqual(cost_usd(1_000_000, 0), 0.15)
        self.assertAlmostEqual(cost_usd(0, 1_000_000), 0.60)
        self.assertAlmostEqual(cost_usd(34, 100), 34 * 0.15e-6 + 100 * 0.60e-6)


class ScriptTests(unittest.TestCase):
    def test_bengali_share(self):
        self.assertEqual(bengali_share("Tokyo is the capital."), 0.0)
        self.assertEqual(bengali_share("জাপানের রাজধানী টোকিও।"), 1.0)
        self.assertAlmostEqual(bengali_share("ab জা"), 0.5)
        self.assertEqual(bengali_share("123 !"), 0.0)


if __name__ == "__main__":
    unittest.main()
