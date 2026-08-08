"""Matches raw scraped products to shopping list items by name similarity."""

from __future__ import annotations

from difflib import SequenceMatcher

from .models import FieldMapping, PriceQuote, ShoppingItem

MIN_MATCH_SCORE = 0.35


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def best_match(
    item: ShoppingItem,
    store_name: str,
    raw_products: list[dict],
    fields: FieldMapping,
) -> PriceQuote | None:
    """Pick the closest-matching product for one shopping list item at one store.

    raw_products is the normalised list of dicts already read out of the
    store's Apify actor output (or demo fixture), one dict per product, with
    at least `fields.name` and `fields.price` keys present.
    """
    search_terms = [item.name, *item.aliases]
    best_score = 0.0
    best_product = None

    for product in raw_products:
        name = product.get(fields.name)
        price = product.get(fields.price)
        if not name or price is None:
            continue
        score = max(_similarity(term, name) for term in search_terms)
        if score > best_score:
            best_score = score
            best_product = product

    if best_product is None or best_score < MIN_MATCH_SCORE:
        return None

    return PriceQuote(
        store=store_name,
        item_name=item.name,
        matched_product_name=best_product[fields.name],
        price=float(best_product[fields.price]),
        unit_price=best_product.get(fields.unit_price),
        in_stock=bool(best_product.get(fields.in_stock, True)),
        match_score=round(best_score, 3),
    )
