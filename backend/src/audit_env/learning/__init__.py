"""Learned auditor: public-record features + a small trained detector (see DESIGN.md §12)."""

from .features import FEATURES, HEADS, Candidate, coverage, extract, labels
from .model import DEFAULT_PATH, FORMAT, Detector, fit

__all__ = [
    "FEATURES",
    "HEADS",
    "Candidate",
    "coverage",
    "extract",
    "labels",
    "DEFAULT_PATH",
    "FORMAT",
    "Detector",
    "fit",
]
