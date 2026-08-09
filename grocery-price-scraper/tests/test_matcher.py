"""Tests for the fuzzy product matcher, anchored to real mismatches found in
a live run (9 Aug 2026): "Pepsi Max Cola 2L" matching plain "Pepsi Cola" at
90% character-similarity, and a 10-pack of eggs matching a 6-pack at 94%.
Both are wrong products/pack sizes that should score lower once word-token
overlap is factored in, even if character sequences are very similar.
"""

from grocery_scraper.matcher import best_match
from grocery_scraper.models import FieldMapping, ShoppingItem

FIELDS = FieldMapping(name="name", price="price", unit_price="unitPrice", in_stock="inStock")


def test_dropped_distinguishing_word_scores_lower_than_exact_match():
    item = ShoppingItem(name="Pepsi Max Cola 2L Bottle")
    products = [
        {"name": "Pepsi Cola Bottle 2L", "price": 1.60},
        {"name": "Pepsi Max No Caffeine No Sugar Cola Bottle", "price": 1.75},
    ]
    match = best_match(item, "Store", products, FIELDS)
    # Neither candidate is a perfect match, but scores should clearly separate
    # a same-brand-different-variant product from an actual Max product.
    assert match is not None
    plain_pepsi_score = match.match_score if match.matched_product_name == "Pepsi Cola Bottle 2L" else None
    assert plain_pepsi_score is None or plain_pepsi_score < 0.85


def test_wrong_pack_size_scores_lower_than_character_ratio_alone():
    item = ShoppingItem(name="Happy Egg Company 10 Large Free Range Eggs",
                         aliases=["free range eggs 10 large"])
    products = [{"name": "Free Range Eggs 6 Large", "price": 2.83}]
    match = best_match(item, "Store", products, FIELDS)
    assert match is not None
    # Pure character-ratio scored this ~0.94 in the real run; word-overlap
    # blending should pull it down noticeably since "10" != "6".
    assert match.match_score < 0.90


def test_exact_name_still_scores_very_high():
    item = ShoppingItem(name="Warburtons Toastie White Bread 800g")
    products = [{"name": "Warburtons Toastie White Bread 800g", "price": 1.40}]
    match = best_match(item, "Store", products, FIELDS)
    assert match is not None
    assert match.match_score > 0.95


def test_no_plausible_match_returns_none():
    item = ShoppingItem(name="Cheddar cheese 400g")
    products = [{"name": "Fresh Basil Plant", "price": 1.50}]
    match = best_match(item, "Store", products, FIELDS)
    assert match is None


def test_nested_price_field_via_dotted_path():
    # Sainsbury's actor (dromb/sainsburys-uk-grocery-price-availability) nests
    # price two levels deep: {"currentPrice": {"value": 0.99, ...}}.
    fields = FieldMapping(name="name", price="currentPrice.value", unit_price="unitPrice.value", in_stock="availability")
    item = ShoppingItem(name="Whole Cucumber")
    products = [{
        "name": "Sainsbury's Whole Cucumber",
        "currentPrice": {"value": 0.99, "currency": "GBP"},
        "unitPrice": {"value": 0.99, "unit": "ea"},
        "availability": "available",
    }]
    match = best_match(item, "Sainsburys", products, fields)
    assert match is not None
    assert match.price == 0.99
    assert match.unit_price == 0.99
    assert match.in_stock is True


def test_string_unavailable_is_not_treated_as_in_stock():
    fields = FieldMapping(name="name", price="price", unit_price="unitPrice", in_stock="availability")
    item = ShoppingItem(name="Whole Cucumber")
    products = [{"name": "Whole Cucumber", "price": 0.99, "availability": "unavailable"}]
    match = best_match(item, "Store", products, fields)
    assert match is not None
    assert match.in_stock is False
