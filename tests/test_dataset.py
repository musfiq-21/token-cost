"""The real dataset file: 50 aligned pairs, varied kinds and lengths."""
import re
import unittest
from collections import Counter

from tokencost.counter import bengali_share
from tokencost.dataset import DATASET, load_dataset


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs = load_dataset(DATASET)

    def test_fifty_pairs_with_unique_ids(self):
        self.assertEqual(len(self.pairs), 50)
        self.assertEqual(len({p["id"] for p in self.pairs}), 50)
        self.assertEqual(set(self.pairs[0]), {"id", "category", "english", "bangla"})

    def test_languages_are_in_the_right_column(self):
        for p in self.pairs:
            self.assertEqual(bengali_share(p["english"]), 0.0, p["id"])
            self.assertGreater(bengali_share(p["bangla"]), 0.7, p["id"])

    def test_mixed_kinds(self):
        counts = Counter(p["category"] for p in self.pairs)
        self.assertGreaterEqual(len(counts), 6)
        self.assertTrue(all(n >= 5 for n in counts.values()), counts)

    def test_lengths_vary(self):
        words = [len(p["english"].split()) for p in self.pairs]
        self.assertGreaterEqual(max(words), 5 * min(words))

    def test_long_prompts_have_three_to_five_sentences(self):
        for p in self.pairs:
            if p["category"] == "long":
                for text in (p["english"], p["bangla"]):
                    n = len(re.findall(r"[.?!।](?=\s|$)", text))
                    self.assertTrue(3 <= n <= 6, (p["id"], n))

    def test_bad_file_is_rejected(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("id,category,english\np01,question,Hi\n")
            with self.assertRaises(ValueError):
                load_dataset(path)


if __name__ == "__main__":
    unittest.main()
