# Grocery price scraper

Weekly tool that prices your regular shopping list across UK supermarkets,
then tells you whether to shop entirely at one store or split the list
across a couple of stores — using a simple rule: **only recommend splitting
if it saves more than £5 versus the cheapest single-store shop**; otherwise
stick with one store for convenience.

It also shows delivery vs click & collect vs in-store cost at each store, so
the "£5 rule" is applied to the *cheapest available fulfillment option* per
store, not just item prices.

## How it works

1. `config/shopping_list.yaml` — your regular items.
2. `config/stores.yaml` — which store, which [Apify](https://apify.com) actor
   scrapes it, and each store's delivery/click&collect fees.
3. `grocery_scraper/run.py` calls each store's actor, matches results back to
   your list items by name similarity, then `optimizer.py` computes:
   - the cheapest **single store** that stocks everything, including its
     cheapest fulfillment option,
   - the cheapest **split** (buy each item wherever it's cheapest, then add
     each store's fulfillment cost for whatever landed there),
   - and recommends split only if it beats the single-store total by more
     than the threshold (default £5, `--threshold` to change it).
4. Writes a dated HTML report to `output/`.

## Quick start (no Apify account needed)

```bash
cd grocery-price-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m grocery_scraper.run --demo
open output/report-$(date +%F).html   # or just open the file in a browser
```

This runs the whole pipeline against `fixtures/sample_prices.json` (made-up
prices) so you can see the report format and sanity-check the decision logic
before spending anything on real scraping.

## Running for real

1. Create a free [Apify](https://apify.com) account and get an API token
   (Settings → Integrations). Apify actor runs are pay-per-use — a handful of
   search terms across ~7 stores once a week is a small, low-cost usage
   pattern, but check current Apify pricing yourself before relying on it.
2. Edit `config/shopping_list.yaml` to match what you actually buy.
3. `export APIFY_TOKEN=your-token-here`
4. `python -m grocery_scraper.run -v`
5. Open the report in `output/`.

Run with `-v` the first few times — it writes each store's raw actor output
to `output/raw/<Store>.raw.json`. **Check these** if an item shows as
"missing" that you know the store stocks — it usually means the actor's
output field names don't match `fields:` in `stores.yaml` (see below), not
that the product doesn't exist.

## Things you need to verify before trusting this with real money

- **Fulfillment fees**: `config/stores.yaml` marks each fee `verified: true`
  or `false`. Only Tesco, Asda and Sainsbury's fee/threshold figures were
  confirmed against current sources at the time of writing (Aug 2026).
  Morrisons, Waitrose, Ocado, Iceland fees are placeholders — check each
  store's own delivery pricing page and correct them, since delivery fees
  vary by postcode/slot and change over time.
- **Actor output field names**: the `fields:` block per store (`name`,
  `price`, `unit_price`, `in_stock`) is a best guess at each Apify actor's
  output schema from its public description, not a verified contract. After
  your first live (non-`--demo`) run, check `output/raw/<Store>.raw.json`
  and fix the field names if a store's items all come back unmatched.
- **Poundland**: no reliable Apify scraper actor exists for it (it's not
  price-tagged for online ordering) — disabled by default in `stores.yaml`.
  It's also in-store only, so if you want it included you'd need to check
  prices manually.
- **Ocado / Iceland**: no dedicated Apify actor was confirmed for these at
  time of writing — `apify_actor_id: null`, so they're currently skipped in
  real runs (the demo fixture still includes made-up sample data for them so
  you can see how the report looks). `config/stores.yaml` also documents an
  alternative: a single actor that scrapes
  [Trolley.co.uk](https://www.trolley.co.uk/) itself and already aggregates
  Tesco/Asda/Sainsbury's/Morrisons/Waitrose/Ocado/Aldi comparisons — worth
  trying instead of running 6+ separate actors, but not wired up by default
  since its output schema hasn't been verified either.
- **Item matching**: matching is fuzzy name-similarity (see `match_score` %
  in the report) — it will happily match "own brand" substitutes across
  stores, which may not be the product you actually want. Check the matched
  product name in the report each week, especially on items with a low match
  score.
- **Split optimizer is a heuristic, not a true optimum**: it assigns each
  item to whichever store has the lowest matched price, then adds up
  fulfillment fees for whichever stores that lands on. It doesn't search for
  combinations that might do better by deliberately consolidating items into
  fewer stores to dodge a delivery fee — for a short list across a handful of
  stores the difference should be small, but it's worth sanity-checking the
  "per-store cost if splitting" table in the report.

## Scraping is against most supermarkets' terms of service

Every price source here is a third-party scraper of a public store website,
not an official retailer API. This is built for personal, low-frequency,
single-user use (once a week, one shopping list) — not for redistribution,
resale, or high-frequency polling. Keep it that way, and expect it to break
occasionally when a store changes its site (that's what the raw-output dump
and field-mapping config are for).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover the optimizer's decision logic (single vs split totals, the £5
threshold, fulfillment fee thresholds) with synthetic data — no network or
Apify calls involved.
