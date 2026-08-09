"""Tests for the manual-price quote builder (config/catalog.yaml -> PriceQuote),
used for stores with no working scraper (e.g. Iceland). Pure/offline."""

from grocery_scraper.models import CatalogItem, ShoppingItem
from grocery_scraper.run import _effective_manual_price, build_manual_quotes


def test_manual_quote_uses_catalog_price_for_named_store():
    shopping_list = [ShoppingItem(name="Cravendale Filtered Fresh Whole Milk 2L", quantity=6)]
    catalog = [
        CatalogItem(name="Cravendale Filtered Fresh Whole Milk 2L", manual_prices={"Iceland": 2.50}),
    ]
    quotes = build_manual_quotes(shopping_list, catalog, "Iceland")
    assert quotes["Cravendale Filtered Fresh Whole Milk 2L"].price == 2.50
    assert quotes["Cravendale Filtered Fresh Whole Milk 2L"].store == "Iceland"
    assert quotes["Cravendale Filtered Fresh Whole Milk 2L"].match_score == 1.0
    assert quotes["Cravendale Filtered Fresh Whole Milk 2L"].in_stock is True


def test_manual_quote_skipped_when_no_price_for_that_store():
    shopping_list = [ShoppingItem(name="Weetabix Chocolate 24 Biscuits")]
    catalog = [CatalogItem(name="Weetabix Chocolate 24 Biscuits", manual_prices={})]
    quotes = build_manual_quotes(shopping_list, catalog, "Iceland")
    assert quotes == {}


def test_manual_quote_skipped_when_item_not_in_catalog_at_all():
    shopping_list = [ShoppingItem(name="Some New Item Not Yet In Catalog")]
    catalog = [CatalogItem(name="Cravendale Filtered Fresh Whole Milk 2L", manual_prices={"Iceland": 2.50})]
    quotes = build_manual_quotes(shopping_list, catalog, "Iceland")
    assert quotes == {}


def test_manual_quote_only_returns_requested_store():
    shopping_list = [ShoppingItem(name="Cravendale Filtered Fresh Whole Milk 2L")]
    catalog = [CatalogItem(name="Cravendale Filtered Fresh Whole Milk 2L",
                            manual_prices={"Iceland": 2.50, "Asda": 1.80})]
    quotes = build_manual_quotes(shopping_list, catalog, "Iceland")
    assert quotes["Cravendale Filtered Fresh Whole Milk 2L"].price == 2.50
    assert quotes["Cravendale Filtered Fresh Whole Milk 2L"].store == "Iceland"


# --- Multi-buy deal pricing ("2 for £3, otherwise £1.75 each") ---

def test_deal_price_used_exactly_at_deal_quantity():
    entry = {"price": 1.75, "deal_quantity": 2, "deal_price": 3.00}
    # Buying exactly 2 -> £3.00 total -> £1.50/unit effective.
    assert _effective_manual_price(entry, 2) == 1.50


def test_deal_price_with_remainder_blends_deal_and_regular():
    entry = {"price": 1.75, "deal_quantity": 2, "deal_price": 3.00}
    # Buying 3 -> one deal pair (£3.00) + one regular (£1.75) = £4.75 total -> /3
    assert round(_effective_manual_price(entry, 3), 4) == round(4.75 / 3, 4)


def test_single_unit_below_deal_threshold_uses_regular_price():
    entry = {"price": 1.75, "deal_quantity": 2, "deal_price": 3.00}
    assert _effective_manual_price(entry, 1) == 1.75


def test_plain_number_entry_still_works_without_deal_fields():
    assert _effective_manual_price(2.50, 6) == 2.50


def test_build_manual_quotes_applies_deal_for_requested_quantity():
    shopping_list = [ShoppingItem(name="Cravendale Filtered Fresh Whole Milk 2L", quantity=3)]
    catalog = [CatalogItem(
        name="Cravendale Filtered Fresh Whole Milk 2L",
        manual_prices={"Iceland": {"price": 1.75, "deal_quantity": 2, "deal_price": 3.00}},
    )]
    quotes = build_manual_quotes(shopping_list, catalog, "Iceland")
    quote = quotes["Cravendale Filtered Fresh Whole Milk 2L"]
    # Effective per-unit price * quantity should reconstruct the true total (£4.75 for 3 units).
    assert round(quote.price * 3, 2) == 4.75
