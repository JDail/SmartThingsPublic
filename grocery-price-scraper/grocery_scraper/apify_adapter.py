"""Thin wrapper for running a store's Apify actor and getting raw product dicts back.

Actor input/output schemas differ per actor and can only be confirmed by
running them for real - see config/stores.yaml for the per-store field
mapping you'll likely need to adjust after your first live run.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import ShoppingItem, StoreConfig

logger = logging.getLogger(__name__)


class ApifyAdapter:
    def __init__(self, token: str, raw_dump_dir: Path | None = None):
        from apify_client import ApifyClient  # imported lazily - not needed in --demo mode

        self.client = ApifyClient(token)
        self.raw_dump_dir = raw_dump_dir

    def fetch_products(self, store: StoreConfig, items: list[ShoppingItem]) -> list[dict]:
        """Run the store's actor once with every shopping-list search term and
        return the raw product dicts it produced (before matching)."""
        if not store.apify_actor_id:
            logger.warning("%s has no apify_actor_id configured - skipping", store.name)
            return []

        search_terms = []
        for item in items:
            search_terms.append(item.name)
            search_terms.extend(item.aliases)

        run_input = {store.apify_search_field: search_terms, **store.apify_extra_input}

        logger.info("Running actor %s for %s (%d search terms)", store.apify_actor_id, store.name, len(search_terms))
        run = self.client.actor(store.apify_actor_id).call(run_input=run_input)
        # apify-client >=3 returns a typed Run model (snake_case attrs), not a raw dict -
        # run["defaultDatasetId"] used to work on older client versions but raises
        # "'Run' object is not subscriptable" on this one.
        dataset_id = run.default_dataset_id
        products = list(self.client.dataset(dataset_id).iterate_items())

        if self.raw_dump_dir is not None:
            self.raw_dump_dir.mkdir(parents=True, exist_ok=True)
            dump_path = self.raw_dump_dir / f"{store.name}.raw.json"
            dump_path.write_text(json.dumps(products, indent=2, default=str), encoding="utf-8")
            logger.info("Wrote raw output for %s to %s (check this if matches look wrong)", store.name, dump_path)

        return products
