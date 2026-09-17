"""Precision/recall/F1/false-positive-rate over a set of benchmark rows.

"Positive" = an attack session (expected_label == BLOCK). This module
has no knowledge of systems or fixtures; it just aggregates
already-computed pass/fail rows.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Metrics:
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


def compute_metrics(rows) -> Metrics:
    """rows: iterable of objects with .expected_label ('ALLOW'/'BLOCK')
    and .actual_decision ('ALLOW'/'BLOCK'/'ESCALATE')."""
    tp = fp = tn = fn = 0
    for r in rows:
        expected_block = r.expected_label == "BLOCK"
        actual_block = r.actual_decision != "ALLOW"
        if expected_block and actual_block:
            tp += 1
        elif expected_block and not actual_block:
            fn += 1
        elif not expected_block and actual_block:
            fp += 1
        else:
            tn += 1
    return Metrics(tp=tp, fp=fp, tn=tn, fn=fn)
