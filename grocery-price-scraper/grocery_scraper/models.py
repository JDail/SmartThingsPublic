"""Core data types shared across the scraper, matcher, optimizer and report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShoppingItem:
    """One line on the regular shopping list."""

    name: str
    quantity: float = 1.0
    unit: str = "each"
    # Extra search phrasings to try against store search APIs, e.g. ["semi skimmed milk 2l"].
    aliases: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class FulfillmentOption:
    """One way to get a basket from a given store (delivery, click & collect, in-store)."""

    kind: str  # "delivery" | "click_collect" | "in_store"
    available: bool = True
    fee: float = 0.0
    # Fee drops to 0 once the basket subtotal is at/above this spend. None = never waived.
    free_over: Optional[float] = None
    # An extra surcharge applies if the basket subtotal is *below* this spend. None = no surcharge.
    surcharge_under: Optional[float] = None
    surcharge_amount: float = 0.0
    # False = figure is a placeholder guess, not confirmed against the store's current pricing page.
    verified: bool = False
    notes: str = ""

    def cost_for_subtotal(self, subtotal: float) -> Optional[float]:
        if not self.available:
            return None
        cost = 0.0 if (self.free_over is not None and subtotal >= self.free_over) else self.fee
        if self.surcharge_under is not None and subtotal < self.surcharge_under:
            cost += self.surcharge_amount
        return cost


@dataclass
class FieldMapping:
    """Where to find name/price/unit-price in a given Apify actor's output items.

    Actor output schemas vary and can only be confirmed by inspecting a real
    run's dataset - these are best-guess defaults, override per store in
    config/stores.yaml once you've checked a sample run.
    """

    name: str = "title"
    price: str = "price"
    unit_price: str = "unitPrice"
    in_stock: str = "inStock"


@dataclass
class StoreConfig:
    name: str
    enabled: bool = True
    apify_actor_id: Optional[str] = None
    apify_search_field: str = "searchTerms"
    apify_extra_input: dict = field(default_factory=dict)
    # Some actors wrap each result in an envelope, e.g. {"success": true, "data": {...actual product...}}.
    # Set this to the wrapper key (e.g. "data") to unwrap before applying `fields:` below.
    apify_data_root: Optional[str] = None
    fields: FieldMapping = field(default_factory=FieldMapping)
    fulfillment: list[FulfillmentOption] = field(default_factory=list)
    notes: str = ""

    def cheapest_fulfillment(self, subtotal: float) -> tuple[Optional[FulfillmentOption], Optional[float]]:
        best_option, best_cost = None, None
        for option in self.fulfillment:
            cost = option.cost_for_subtotal(subtotal)
            if cost is None:
                continue
            if best_cost is None or cost < best_cost:
                best_option, best_cost = option, cost
        return best_option, best_cost


@dataclass
class PriceQuote:
    """A shopping-list item matched to a specific product at a specific store."""

    store: str
    item_name: str
    matched_product_name: str
    price: float
    unit_price: Optional[float] = None
    in_stock: bool = True
    match_score: float = 0.0
