"""Load and validate the aligned English/Bangla prompt pairs."""
import csv
import os

from . import PROJECT_ROOT

DATASET = os.path.join(PROJECT_ROOT, "data", "dataset.csv")
COLUMNS = ["id", "category", "english", "bangla"]


def load_dataset(path=DATASET):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"expected columns {COLUMNS}, got {reader.fieldnames}")
        pairs = []
        for row in reader:
            if any(not (row.get(c) or "").strip() for c in COLUMNS):
                raise ValueError(f"empty field in row {row}")
            pairs.append({c: row[c].strip() for c in COLUMNS})
    ids = [p["id"] for p in pairs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids")
    return pairs
