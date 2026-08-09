"""One-off exploration script for the Trolley.co.uk aggregator actor
(studio-amba/uk-grocery-price-matrix). Its input/output schema is
unconfirmed - this just runs it once with your shopping list's plain item
names (not aliases, to keep this speculative first call small/cheap) and
dumps the raw output to output/raw/Trolley.raw.json so we can look at the
real shape before writing any parsing/integration code.

    APIFY_TOKEN=xxx python -m grocery_scraper.trolley_explore
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent.parent
ACTOR_ID = "studio-amba/uk-grocery-price-matrix"


def main():
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("Set APIFY_TOKEN first (see README).", file=sys.stderr)
        sys.exit(1)

    from apify_client import ApifyClient  # imported lazily, same pattern as apify_adapter.py

    shopping_list = yaml.safe_load((BASE_DIR / "config" / "shopping_list.yaml").read_text(encoding="utf-8"))
    search_terms = [item["name"] for item in shopping_list["items"]]

    client = ApifyClient(token)
    # Best-effort guess - the actor's real input schema hasn't been confirmed.
    # Its description mentions "fuzzy-name fallback" matching, which suggests
    # it does accept plain product name strings.
    run_input = {"searchTerms": search_terms}

    print(f"Running {ACTOR_ID} with {len(search_terms)} search terms: {search_terms}")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    products = list(client.dataset(run.default_dataset_id).iterate_items())

    out_path = BASE_DIR / "output" / "raw" / "Trolley.raw.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(products, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {len(products)} records to {out_path}")
    print("Paste the first ~60 lines of that file back so we can design the real parser against it.")


if __name__ == "__main__":
    main()
