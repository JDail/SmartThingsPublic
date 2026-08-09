"""Local web UI for managing your grocery catalog and picking this week's list.

    python -m grocery_scraper.webui

Opens a small Flask app at http://127.0.0.1:5050 - add new products, update
manual prices (e.g. Iceland), and tick this week's items with quantities.
Writes directly to config/catalog.yaml and config/shopping_list.yaml.

This does NOT call Apify or spend any money - it only manages your product
list. Run `python -m grocery_scraper.run` separately afterwards to actually
fetch prices and generate the comparison report.

Runs on localhost only (127.0.0.1) - not reachable from other devices on
your network, and not intended to be exposed beyond your own machine.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from .config import load_catalog, load_stores, save_catalog, save_shopping_list
from .models import CatalogItem, ShoppingItem

BASE_DIR = Path(__file__).parent.parent
CATALOG_PATH = BASE_DIR / "config" / "catalog.yaml"
SHOPPING_LIST_PATH = BASE_DIR / "config" / "shopping_list.yaml"
STORES_PATH = BASE_DIR / "config" / "stores.yaml"

app = Flask(__name__)


def _manual_store_names() -> list[str]:
    return [s.name for s in load_stores(STORES_PATH) if s.manual]


def _price_field_values(entry) -> dict:
    """Normalise a manual_prices entry (plain number or deal dict) into the
    three form-field values the template needs, so no type-branching
    happens in Jinja."""
    if entry is None:
        return {"price": "", "deal_quantity": "", "deal_price": ""}
    if isinstance(entry, dict):
        return {
            "price": entry.get("price", ""),
            "deal_quantity": entry.get("deal_quantity", ""),
            "deal_price": entry.get("deal_price", ""),
        }
    return {"price": entry, "deal_quantity": "", "deal_price": ""}


@app.route("/", methods=["GET"])
def index():
    catalog = load_catalog(CATALOG_PATH)
    manual_stores = _manual_store_names()
    saved = request.args.get("saved")
    price_fields = {
        item.name: {store: _price_field_values(item.manual_prices.get(store)) for store in manual_stores}
        for item in catalog
    }
    return render_template(
        "webui.html",
        catalog=catalog,
        manual_stores=manual_stores,
        price_fields=price_fields,
        saved=saved,
    )


@app.route("/catalog/add", methods=["POST"])
def add_item():
    catalog = load_catalog(CATALOG_PATH)
    name = request.form.get("name", "").strip()
    if name and not any(c.name == name for c in catalog):
        aliases = [a.strip() for a in request.form.get("aliases", "").split(",") if a.strip()]
        try:
            default_quantity = float(request.form.get("default_quantity") or 1)
        except ValueError:
            default_quantity = 1.0
        catalog.append(CatalogItem(
            name=name,
            unit=request.form.get("unit", "each").strip() or "each",
            default_quantity=default_quantity,
            aliases=aliases,
            manual_prices={},
        ))
        save_catalog(CATALOG_PATH, catalog)
    return redirect(url_for("index"))


@app.route("/catalog/<path:name>/delete", methods=["POST"])
def delete_item(name):
    catalog = [c for c in load_catalog(CATALOG_PATH) if c.name != name]
    save_catalog(CATALOG_PATH, catalog)
    return redirect(url_for("index"))


@app.route("/catalog/<path:name>/price", methods=["POST"])
def update_price(name):
    catalog = load_catalog(CATALOG_PATH)
    store = request.form.get("store", "").strip()
    raw_price = request.form.get("price", "").strip()
    raw_deal_qty = request.form.get("deal_quantity", "").strip()
    raw_deal_price = request.form.get("deal_price", "").strip()

    for item in catalog:
        if item.name != name or not store:
            continue
        if not raw_price:
            item.manual_prices.pop(store, None)
            continue
        try:
            price = float(raw_price)
        except ValueError:
            continue
        if raw_deal_qty and raw_deal_price:
            try:
                item.manual_prices[store] = {
                    "price": price,
                    "deal_quantity": int(raw_deal_qty),
                    "deal_price": float(raw_deal_price),
                }
            except ValueError:
                item.manual_prices[store] = price
        else:
            item.manual_prices[store] = price

    save_catalog(CATALOG_PATH, catalog)
    return redirect(url_for("index"))


@app.route("/select", methods=["POST"])
def select_this_week():
    catalog_by_name = {c.name: c for c in load_catalog(CATALOG_PATH)}
    items_out = []
    for name in request.form.getlist("selected"):
        item = catalog_by_name.get(name)
        if item is None:
            continue
        raw_qty = request.form.get(f"qty__{name}", "").strip()
        try:
            quantity = float(raw_qty) if raw_qty else item.default_quantity
        except ValueError:
            quantity = item.default_quantity
        items_out.append(ShoppingItem(name=item.name, quantity=quantity, unit=item.unit, aliases=item.aliases))

    save_shopping_list(SHOPPING_LIST_PATH, items_out)
    return redirect(url_for("index", saved=len(items_out)))


def main():
    print("Grocery catalog UI running at http://127.0.0.1:5050 (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
