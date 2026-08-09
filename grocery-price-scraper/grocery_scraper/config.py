"""Loads shopping_list.yaml and stores.yaml into typed objects."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import FieldMapping, FulfillmentOption, ShoppingItem, StoreConfig


def load_shopping_list(path: Path) -> list[ShoppingItem]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        ShoppingItem(
            name=item["name"],
            quantity=item.get("quantity", 1.0),
            unit=item.get("unit", "each"),
            aliases=item.get("aliases", []),
            notes=item.get("notes", ""),
        )
        for item in data["items"]
    ]


def _fulfillment_from_dict(d: dict) -> FulfillmentOption:
    return FulfillmentOption(
        kind=d["kind"],
        available=d.get("available", True),
        fee=d.get("fee", 0.0),
        free_over=d.get("free_over"),
        surcharge_under=d.get("surcharge_under"),
        surcharge_amount=d.get("surcharge_amount", 0.0),
        verified=d.get("verified", False),
        notes=d.get("notes", ""),
    )


def load_stores(path: Path) -> list[StoreConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stores = []
    for s in data["stores"]:
        fields_dict = s.get("fields", {})
        stores.append(
            StoreConfig(
                name=s["name"],
                enabled=s.get("enabled", True),
                apify_actor_id=s.get("apify_actor_id"),
                apify_search_field=s.get("apify_search_field", "searchTerms"),
                apify_extra_input=s.get("apify_extra_input", {}),
                apify_data_root=s.get("apify_data_root"),
                fields=FieldMapping(
                    name=fields_dict.get("name", "title"),
                    price=fields_dict.get("price", "price"),
                    unit_price=fields_dict.get("unit_price", "unitPrice"),
                    in_stock=fields_dict.get("in_stock", "inStock"),
                ),
                fulfillment=[_fulfillment_from_dict(f) for f in s.get("fulfillment", [])],
                notes=s.get("notes", ""),
            )
        )
    return stores
