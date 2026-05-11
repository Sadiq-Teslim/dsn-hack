from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.data_store import get_data_store  # noqa: E402
from app.services.evaluation import fixture_metrics  # noqa: E402


def main() -> None:
    store = get_data_store()
    metrics = fixture_metrics(store.products, store.reviews)
    print(metrics.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
