from __future__ import annotations

import math


def rmse(errors: list[float]) -> float:
    if not errors:
        return 0.0
    return round(math.sqrt(sum(error * error for error in errors) / len(errors)), 4)


def ndcg_at_k(ranked_ids: list[str], target_id: str, k: int) -> float:
    try:
        index = ranked_ids[:k].index(target_id)
    except ValueError:
        return 0.0
    return 1 / math.log2(index + 2)


def rouge_l_f1(candidate: str, reference: str) -> float:
    cand = candidate.lower().split()
    ref = reference.lower().split()
    if not cand or not ref:
        return 0.0
    lcs = _lcs_length(cand, ref)
    precision = lcs / len(cand)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return round((2 * precision * recall) / (precision + recall), 4)


def _lcs_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]
