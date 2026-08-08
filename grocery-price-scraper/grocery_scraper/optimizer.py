"""Turns per-store price quotes into a single-store-vs-split recommendation.

Rule (as specified): work out the cheapest way to buy everything from ONE
store, and separately the cheapest way to split the list across stores by
item. If splitting saves more than the threshold (default £5) over the best
single-store run, recommend the split; otherwise recommend sticking with one
store for convenience, even though the split might be a few pence cheaper.

The split allocation is a greedy "cheapest matched price per item" choice,
then fulfillment fees are computed on whatever subtotal actually lands at
each store used. This isn't a full combinatorial optimum (fulfillment fees
interact with which items get grouped where), but for a short weekly list
across a handful of stores it's a good, easily-explained approximation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import FulfillmentOption, PriceQuote, ShoppingItem, StoreConfig

DEFAULT_SPLIT_SAVINGS_THRESHOLD = 5.0


@dataclass
class StoreTotal:
    store: str
    subtotal: float
    missing_items: list[str]
    fulfillment_option: FulfillmentOption | None
    fulfillment_cost: float | None
    total: float | None  # None if this store can't fulfil the whole list or has no fulfillment option available
    # kind ("delivery"/"click_collect"/"in_store") -> cost at this subtotal, for every available
    # option - lets the report show delivery vs click&collect vs in-store side by side per store,
    # not just whichever one happened to be cheapest.
    fulfillment_breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def full_coverage(self) -> bool:
        return not self.missing_items


@dataclass
class SplitPlan:
    allocations: dict[str, PriceQuote]  # item_name -> chosen quote
    per_store_subtotal: dict[str, float]
    per_store_fulfillment_cost: dict[str, float]
    unmatched_items: list[str]
    total: float


@dataclass
class Recommendation:
    mode: str  # "single" | "split" | "incomplete"
    threshold: float
    savings: float
    best_single: StoreTotal | None
    split_plan: SplitPlan
    all_single_totals: list[StoreTotal] = field(default_factory=list)
    message: str = ""


def compute_single_store_totals(
    shopping_list: list[ShoppingItem],
    stores: list[StoreConfig],
    quotes: dict[str, dict[str, PriceQuote]],  # store_name -> item_name -> quote
) -> list[StoreTotal]:
    totals = []
    for store in stores:
        store_quotes = quotes.get(store.name, {})
        subtotal = 0.0
        missing = []
        for item in shopping_list:
            q = store_quotes.get(item.name)
            if q is None:
                missing.append(item.name)
            else:
                subtotal += q.price * item.quantity

        breakdown = {}
        for opt in store.fulfillment:
            c = opt.cost_for_subtotal(subtotal)
            if c is not None:
                breakdown[opt.kind] = round(c, 2)

        option, cost = store.cheapest_fulfillment(subtotal) if not missing else (None, None)
        total = (subtotal + cost) if (not missing and cost is not None) else None

        totals.append(
            StoreTotal(
                store=store.name,
                subtotal=round(subtotal, 2),
                missing_items=missing,
                fulfillment_option=option,
                fulfillment_cost=cost,
                total=round(total, 2) if total is not None else None,
                fulfillment_breakdown=breakdown,
            )
        )
    return totals


def compute_split_plan(
    shopping_list: list[ShoppingItem],
    stores: list[StoreConfig],
    quotes: dict[str, dict[str, PriceQuote]],
) -> SplitPlan:
    store_by_name = {s.name: s for s in stores}
    allocations: dict[str, PriceQuote] = {}
    unmatched: list[str] = []

    for item in shopping_list:
        candidates = [
            quotes[store.name][item.name]
            for store in stores
            if item.name in quotes.get(store.name, {})
        ]
        if not candidates:
            unmatched.append(item.name)
            continue
        allocations[item.name] = min(candidates, key=lambda q: q.price)

    per_store_subtotal: dict[str, float] = {}
    for item in shopping_list:
        quote = allocations.get(item.name)
        if quote is None:
            continue
        per_store_subtotal[quote.store] = per_store_subtotal.get(quote.store, 0.0) + quote.price * item.quantity

    per_store_fulfillment_cost: dict[str, float] = {}
    for store_name, subtotal in per_store_subtotal.items():
        store = store_by_name[store_name]
        _, cost = store.cheapest_fulfillment(subtotal)
        per_store_fulfillment_cost[store_name] = cost if cost is not None else 0.0

    total = round(
        sum(per_store_subtotal.values()) + sum(per_store_fulfillment_cost.values()),
        2,
    )

    return SplitPlan(
        allocations=allocations,
        per_store_subtotal={k: round(v, 2) for k, v in per_store_subtotal.items()},
        per_store_fulfillment_cost={k: round(v, 2) for k, v in per_store_fulfillment_cost.items()},
        unmatched_items=unmatched,
        total=total,
    )


def recommend(
    shopping_list: list[ShoppingItem],
    stores: list[StoreConfig],
    quotes: dict[str, dict[str, PriceQuote]],
    threshold: float = DEFAULT_SPLIT_SAVINGS_THRESHOLD,
) -> Recommendation:
    single_totals = compute_single_store_totals(shopping_list, stores, quotes)
    split_plan = compute_split_plan(shopping_list, stores, quotes)

    full_coverage_totals = [t for t in single_totals if t.full_coverage and t.total is not None]
    best_single = min(full_coverage_totals, key=lambda t: t.total) if full_coverage_totals else None

    if best_single is None:
        return Recommendation(
            mode="incomplete",
            threshold=threshold,
            savings=0.0,
            best_single=None,
            split_plan=split_plan,
            all_single_totals=single_totals,
            message=(
                "No single store stocks every item on your list (at the prices matched). "
                "Showing the best split across stores instead."
            ),
        )

    savings = round(best_single.total - split_plan.total, 2)

    if savings > threshold:
        mode = "split"
        message = (
            f"Splitting across {len(split_plan.per_store_subtotal)} stores saves "
            f"£{savings:.2f} vs the cheapest single-store shop ({best_single.store}) - "
            f"above your £{threshold:.2f} threshold, so it's worth the extra trips/orders."
        )
    else:
        mode = "single"
        message = (
            f"Splitting would only save £{savings:.2f} (or cost more) vs shopping entirely at "
            f"{best_single.store} - below your £{threshold:.2f} threshold, so stick with one store for ease."
        )

    return Recommendation(
        mode=mode,
        threshold=threshold,
        savings=savings,
        best_single=best_single,
        split_plan=split_plan,
        all_single_totals=single_totals,
        message=message,
    )
