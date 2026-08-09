"""Interactive weekly item picker.

    python -m grocery_scraper.select_items

Reads your master catalog (config/catalog.yaml), lets you tick which items
you want this week and confirm/change quantities, then writes the result to
config/shopping_list.yaml - which the rest of the tool (run.py) reads as
usual. Run this before `python -m grocery_scraper.run` each week.

Everything in the catalog is ticked by default (space to untick, enter to
confirm) - if you want to buy your usual list, just press enter straight
away.
"""

from __future__ import annotations

from pathlib import Path

from .config import load_catalog, save_shopping_list
from .models import CatalogItem, ShoppingItem

BASE_DIR = Path(__file__).parent.parent


def _select_with_questionary(catalog: list[CatalogItem]) -> list[CatalogItem]:
    import questionary

    choices = [
        questionary.Choice(title=f"{item.name} (usually {item.default_quantity})", value=item, checked=True)
        for item in catalog
    ]
    selected = questionary.checkbox(
        "Select this week's items (space to toggle, enter to confirm):",
        choices=choices,
    ).ask()
    return selected if selected is not None else []


def _select_with_plain_input(catalog: list[CatalogItem]) -> list[CatalogItem]:
    print("Your catalog:")
    for i, item in enumerate(catalog, 1):
        print(f"  {i}. {item.name} (usually {item.default_quantity})")
    raw = input("Enter item numbers to include, comma-separated (blank = everything): ").strip()
    if not raw:
        return list(catalog)
    indices = {int(x.strip()) for x in raw.split(",") if x.strip()}
    return [item for i, item in enumerate(catalog, 1) if i in indices]


def main():
    catalog = load_catalog(BASE_DIR / "config" / "catalog.yaml")
    if not catalog:
        print("config/catalog.yaml has no items - add some first.")
        return

    try:
        selected = _select_with_questionary(catalog)
    except ImportError:
        selected = _select_with_plain_input(catalog)

    if not selected:
        print("Nothing selected - shopping_list.yaml left unchanged.")
        return

    items_out = []
    for item in selected:
        raw_qty = input(f"Quantity for '{item.name}' [{item.default_quantity}]: ").strip()
        try:
            quantity = float(raw_qty) if raw_qty else item.default_quantity
        except ValueError:
            print(f"  Couldn't read '{raw_qty}' as a number, using default {item.default_quantity}.")
            quantity = item.default_quantity
        items_out.append(ShoppingItem(name=item.name, quantity=quantity, unit=item.unit, aliases=item.aliases))

    out_path = BASE_DIR / "config" / "shopping_list.yaml"
    save_shopping_list(out_path, items_out)
    print(f"Wrote {len(items_out)} items to {out_path}")


if __name__ == "__main__":
    main()
