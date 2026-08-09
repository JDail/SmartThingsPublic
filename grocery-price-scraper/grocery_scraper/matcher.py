"""Matches raw scraped products to shopping list items by name similarity."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import FieldMapping, PriceQuote, ShoppingItem

MIN_MATCH_SCORE = 0.35

_WORD_RE = re.compile(r"[a-z0-9]+")


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _word_tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _score(term: str, candidate_name: str) -> float:
    """Character-sequence similarity alone is too forgiving of a dropped word
    or changed number (e.g. "Pepsi Max Cola" vs "Pepsi Cola" scored ~90% on
    character ratio alone, despite "Max" being a different product; "10
    Large Eggs" vs a 6-pack scored ~94% despite the pack size being wrong).
    Blend in word-token recall so a missing distinguishing word/number pulls
    the score down more honestly.
    """
    char_ratio = _similarity(term, candidate_name)
    term_tokens = _word_tokens(term)
    if not term_tokens:
        return char_ratio
    candidate_tokens = _word_tokens(candidate_name)
    word_overlap = len(term_tokens & candidate_tokens) / len(term_tokens)
    return 0.5 * char_ratio + 0.5 * word_overlap


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
        score = max(_score(term, name) for term in search_terms)
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
