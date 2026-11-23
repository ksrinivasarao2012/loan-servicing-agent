"""Tiny BM25 search over the SOP markdown files.

BM25 is keyword scoring: an SOP scores higher when it contains more of the
query's words, and rare words count more than common ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

SOP_DIR = Path(__file__).resolve().parents[2] / "sops"

_STOP = set(
    "a an the and or but to of for in on at by with my me i is are was were be "
    "it this that can you your please want would like need do does did have has "
    "from as so if not no what when how why which there their they we our".split()
)


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in _STOP]


@dataclass(frozen=True)
class SOP:
    sop_id: str
    text: str


@dataclass(frozen=True)
class Hit:
    sop_id: str
    score: float
    text: str


class SOPIndex:
    def __init__(self, sop_dir: Path = SOP_DIR):
        self.sops = [SOP(p.stem, p.read_text(encoding="utf-8")) for p in sorted(sop_dir.glob("*.md"))]
        self._bm25 = BM25Okapi([tokenize(s.text) for s in self.sops])

    def search(self, query: str, k: int = 3) -> list[Hit]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.sops, scores), key=lambda x: x[1], reverse=True)
        return [Hit(s.sop_id, float(score), s.text) for s, score in ranked[:k]]

    def get(self, sop_id: str) -> SOP | None:
        return next((s for s in self.sops if s.sop_id == sop_id), None)


@lru_cache(maxsize=1)
def default_index() -> SOPIndex:
    return SOPIndex()
