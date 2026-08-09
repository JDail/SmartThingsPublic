"""Tests for the manual-price quote builder (config/catalog.yaml -> PriceQuote),
used for stores with no working scraper (e.g. Iceland). Pure/offline."""

from grocery_scraper.models import CatalogItem, ShoppingItem
from grocery_scraper.run import build_manual_quotes


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
