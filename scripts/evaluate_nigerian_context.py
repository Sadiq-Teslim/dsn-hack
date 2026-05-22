from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

MARKERS = {
    "nigerian_pidgin": {"dey", "no", "am", "e", "na", "wahala", "sha"},
    "yoruba": {"o da", "sha", "rara", "gan", "e je"},
    "hausa": {"gaskiya", "wallahi", "ba", "sosai"},
    "igbo": {"o di", "mma", "no long story"},
    "local_context": {"lagos", "abuja", "traffic", "harmattan", "visitors", "family", "hot weather"},
}


def marker_score(text: str) -> float:
    lowered = text.lower()
    hits = 0
    total = 0
    for markers in MARKERS.values():
        total += 1
        hits += int(any(marker in lowered for marker in markers))
    return round(hits / total, 4)


def evaluate(path: Path, output: Path) -> dict:
    examples = json.loads(path.read_text(encoding="utf-8"))
    by_register: dict[str, int] = defaultdict(int)
    scores = []
    tags = Counter()
    for example in examples:
        by_register[example["register"]] += 1
        scores.append(marker_score(example["text"]))
        tags.update(example.get("tags", []))
    generic_without_context = [
        "This product is good and useful. I recommend it for daily use.",
        "The quality is acceptable and the price is reasonable.",
        "It performs well for the category and should satisfy most users.",
    ]
    report = {
        "exemplar_count": len(examples),
        "register_counts": dict(sorted(by_register.items())),
        "top_tags": tags.most_common(12),
        "proxy_authenticity_with_context": round(sum(scores) / max(1, len(scores)), 4),
        "proxy_authenticity_without_context": round(
            sum(marker_score(text) for text in generic_without_context) / len(generic_without_context),
            4,
        ),
        "method_note": (
            "Automated proxy only: scores local register markers and Nigerian contextual cues. "
            "This is not a substitute for the optional human authenticity rating before final submission."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    report = evaluate(
        Path("data/nigerian_context/review_examples.json"),
        Path("docs/nigerian_context_report.json"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
