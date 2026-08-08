"""Unit tests for the single-store-vs-split decision logic.

Pure/offline: builds synthetic ShoppingItem/StoreConfig/PriceQuote objects
directly, no network or Apify calls involved.
"""

from grocery_scraper.models import FulfillmentOption, PriceQuote, ShoppingItem, StoreConfig
from grocery_scraper.optimizer import compute_single_store_totals, compute_split_plan, recommend


def make_store(name, delivery_fee=3.0, free_over=None):
    return StoreConfig(
        name=name,
        fulfillment=[
            FulfillmentOption(kind="delivery", available=True, fee=delivery_fee, free_over=free_over, verified=True),
            FulfillmentOption(kind="in_store", available=True, fee=0.0, verified=True),
        ],
    )


def quote(store, item_name, price):
    return PriceQuote(store=store, item_name=item_name, matched_product_name=item_name, price=price, match_score=1.0)


def test_single_store_totals_full_coverage():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread")]
    stores = [make_store("A", delivery_fee=3.0), make_store("B", delivery_fee=1.0)]
    quotes = {
        "A": {"Milk": quote("A", "Milk", 1.0), "Bread": quote("A", "Bread", 1.0)},
        "B": {"Milk": quote("B", "Milk", 1.5), "Bread": quote("B", "Bread", 1.5)},
    }
    totals = compute_single_store_totals(items, stores, quotes)
    by_store = {t.store: t for t in totals}
    assert by_store["A"].full_coverage
    # cheapest fulfillment is in_store (£0) for both, so total == subtotal
    assert by_store["A"].total == 2.0
    assert by_store["B"].total == 3.0


def test_single_store_totals_missing_item_has_no_total():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread")]
    stores = [make_store("A")]
    quotes = {"A": {"Milk": quote("A", "Milk", 1.0)}}  # Bread missing
    totals = compute_single_store_totals(items, stores, quotes)
    assert totals[0].total is None
    assert totals[0].missing_items == ["Bread"]


def test_split_plan_picks_cheapest_per_item():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread")]
    stores = [make_store("A"), make_store("B")]
    quotes = {
        "A": {"Milk": quote("A", "Milk", 1.0), "Bread": quote("A", "Bread", 2.0)},
        "B": {"Milk": quote("B", "Milk", 1.5), "Bread": quote("B", "Bread", 1.0)},
    }
    plan = compute_split_plan(items, stores, quotes)
    assert plan.allocations["Milk"].store == "A"
    assert plan.allocations["Bread"].store == "B"
    assert plan.per_store_subtotal == {"A": 1.0, "B": 1.0}


def test_recommend_prefers_single_store_below_threshold():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread")]
    stores = [make_store("A"), make_store("B")]
    # Splitting only saves a few pence - should recommend staying with one store (the cheapest one, B).
    quotes = {
        "A": {"Milk": quote("A", "Milk", 1.00), "Bread": quote("A", "Bread", 1.00)},
        "B": {"Milk": quote("B", "Milk", 0.98), "Bread": quote("B", "Bread", 1.00)},
    }
    rec = recommend(items, stores, quotes, threshold=5.0)
    assert rec.mode == "single"
    assert rec.best_single.store == "B"


def test_recommend_prefers_split_above_threshold():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread"), ShoppingItem(name="Eggs")]
    stores = [make_store("A", delivery_fee=0), make_store("B", delivery_fee=0)]
    # Big price gaps on each item, no fulfillment fees in the way -> split should win by a lot.
    # A: 6+6+0.50=12.50, B: 0.50+0.50+6=7.00 -> best single is B at £7.00.
    # Split: milk+bread from B (£1.00), eggs from A (£0.50) -> split total £1.50, saving £5.50.
    quotes = {
        "A": {
            "Milk": quote("A", "Milk", 6.00),
            "Bread": quote("A", "Bread", 6.00),
            "Eggs": quote("A", "Eggs", 0.50),
        },
        "B": {
            "Milk": quote("B", "Milk", 0.50),
            "Bread": quote("B", "Bread", 0.50),
            "Eggs": quote("B", "Eggs", 6.00),
        },
    }
    rec = recommend(items, stores, quotes, threshold=5.0)
    assert rec.mode == "split"
    assert rec.savings > 5.0


def test_recommend_incomplete_when_no_store_has_full_list():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread")]
    stores = [make_store("A"), make_store("B")]
    quotes = {
        "A": {"Milk": quote("A", "Milk", 1.0)},  # no Bread
        "B": {"Bread": quote("B", "Bread", 1.0)},  # no Milk
    }
    rec = recommend(items, stores, quotes, threshold=5.0)
    assert rec.mode == "incomplete"
    assert rec.best_single is None
    # split plan should still cover both items between the two stores
    assert set(rec.split_plan.allocations.keys()) == {"Milk", "Bread"}


def test_threshold_boundary_is_strictly_greater_than():
    items = [ShoppingItem(name="Milk"), ShoppingItem(name="Bread")]
    stores = [make_store("A", delivery_fee=0), make_store("B", delivery_fee=0)]
    # Both stores total £7.00 for the full list (tie -> best_single is A, the first store).
    # Split: milk from A (£1.00), bread from B (£1.00) -> split total £2.00, saving exactly £5.00.
    # Rule is "over £5", not "£5 or more", so this should NOT trigger split.
    quotes = {
        "A": {"Milk": quote("A", "Milk", 1.00), "Bread": quote("A", "Bread", 6.00)},
        "B": {"Milk": quote("B", "Milk", 6.00), "Bread": quote("B", "Bread", 1.00)},
    }
    rec = recommend(items, stores, quotes, threshold=5.0)
    assert rec.savings == 5.0
    assert rec.mode == "single"
