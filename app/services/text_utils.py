import math
import re
from collections import Counter
from typing import Iterable


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def keyword_set(*parts: object) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        if isinstance(part, dict):
            tokens.update(tokenize(" ".join(str(value) for value in part.values())))
        elif isinstance(part, Iterable) and not isinstance(part, str):
            tokens.update(tokenize(" ".join(str(value) for value in part)))
        else:
            tokens.update(tokenize(str(part)))
    return tokens


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def cosine_counter(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def stable_round(value: float, places: int = 3) -> float:
    return round(float(value), places)
