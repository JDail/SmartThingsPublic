"""CLI entrypoint.

    python -m grocery_scraper.run --demo
        Runs the whole pipeline against fixtures/sample_prices.json - no
        Apify account needed. Good for trying it out / testing changes.

    APIFY_TOKEN=xxx python -m grocery_scraper.run
        Runs for real: calls each enabled store's Apify actor, matches
        results to your shopping list, and writes a dated HTML report.

    python -m grocery_scraper.run --from-raw
        Re-renders the report from whatever's already in output/raw/*.raw.json
        (written by a previous real run) without calling Apify again. No
        token needed. Use this after tweaking config/stores.yaml's `fields:`
        mapping to check the fix without spending more Apify credit.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from .config import load_shopping_list, load_stores
from .matcher import best_match
from .models import PriceQuote
from .optimizer import DEFAULT_SPLIT_SAVINGS_THRESHOLD, recommend
from .report import render_report

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent


def _unwrap(raw_products: list[dict], data_root: str | None) -> list[dict]:
    """Some actors wrap each result in an envelope, e.g. {"success": true, "data": {...}}.
    Unwrap to the inner dict (per store.apify_data_root) before field-mapping is applied."""
    if not data_root:
        return raw_products
    return [p[data_root] for p in raw_products if isinstance(p.get(data_root), dict)]


def build_quotes_from_raw(shopping_list, stores, raw_by_store: dict[str, list[dict]]):
    quotes: dict[str, dict[str, PriceQuote]] = {}
    for store in stores:
        raw_products = _unwrap(raw_by_store.get(store.name, []), store.apify_data_root)
        store_quotes = {}
        for item in shopping_list:
            match = best_match(item, store.name, raw_products, store.fields)
            if match is not None and match.in_stock:
                store_quotes[item.name] = match
        quotes[store.name] = store_quotes
    return quotes


def fetch_live(shopping_list, stores, output_dir: Path) -> dict[str, list[dict]]:
    from .apify_adapter import ApifyAdapter

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("APIFY_TOKEN not set - pass --demo to try the pipeline with sample data, "
              "or export APIFY_TOKEN=<your Apify API token> to run for real.", file=sys.stderr)
        sys.exit(1)

    adapter = ApifyAdapter(token, raw_dump_dir=output_dir / "raw")
    raw_by_store = {}
    for store in stores:
        if not store.enabled or not store.apify_actor_id:
            continue
        try:
            raw_by_store[store.name] = adapter.fetch_products(store, shopping_list)
        except Exception as exc:
            # Don't let one bad actor (wrong input schema, rental required, down, etc.)
            # take out the whole run - log it and let the other stores still produce a report.
            logger.warning("%s actor run failed, skipping this store: %s", store.name, exc)
            raw_by_store[store.name] = []
    return raw_by_store


def load_from_raw_dumps(stores, output_dir: Path) -> dict[str, list[dict]]:
    raw_by_store = {}
    raw_dir = output_dir / "raw"
    for store in stores:
        dump_path = raw_dir / f"{store.name}.raw.json"
        if dump_path.exists():
            raw_by_store[store.name] = json.loads(dump_path.read_text(encoding="utf-8"))
        else:
            logger.warning("No cached raw dump for %s at %s - skipping (run without --from-raw first)", store.name, dump_path)
            raw_by_store[store.name] = []
    return raw_by_store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="Use fixtures/sample_prices.json instead of calling Apify")
    parser.add_argument("--from-raw", action="store_true",
                         help="Re-use output/raw/*.raw.json from a previous real run instead of calling Apify again")
    parser.add_argument("--shopping-list", type=Path, default=BASE_DIR / "config" / "shopping_list.yaml")
    parser.add_argument("--stores-config", type=Path, default=BASE_DIR / "config" / "stores.yaml")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "output")
    parser.add_argument("--threshold", type=float, default=DEFAULT_SPLIT_SAVINGS_THRESHOLD,
                         help="Minimum £ saving for a split shop to be recommended over one store")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    shopping_list = load_shopping_list(args.shopping_list)
    stores = [s for s in load_stores(args.stores_config) if s.enabled]

    if args.demo:
        fixture_path = BASE_DIR / "fixtures" / "sample_prices.json"
        raw_by_store = {k: v for k, v in json.loads(fixture_path.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    elif args.from_raw:
        raw_by_store = load_from_raw_dumps(stores, args.output_dir)
    else:
        raw_by_store = fetch_live(shopping_list, stores, args.output_dir)

    quotes = build_quotes_from_raw(shopping_list, stores, raw_by_store)
    recommendation = recommend(shopping_list, stores, quotes, threshold=args.threshold)

    report_path = args.output_dir / f"report-{date.today().isoformat()}.html"
    render_report(shopping_list, recommendation, report_path)

    print(recommendation.message)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
