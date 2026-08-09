# Grocery price scraper

Weekly tool that prices your regular shopping list across UK supermarkets,
then tells you whether to shop entirely at one store or split the list
across a couple of stores — using a simple rule: **only recommend splitting
if it saves more than £5 versus the cheapest single-store shop**; otherwise
stick with one store for convenience.

It also shows delivery vs click & collect vs in-store cost at each store, so
the "£5 rule" is applied to the *cheapest available fulfillment option* per
store, not just item prices.

## Current status (9 Aug 2026)

- **Working, confirmed against real data**: Asda, Morrisons (via
  [Apify](https://apify.com) actors, automated).
- **Iceland**: manual price entry (see below) — no working scraper exists
  for it after extensive investigation; see `config/stores.yaml`'s notes on
  the Iceland entry for the full trail (no dedicated actor, Trolley
  aggregator exceeds free-tier budget, Amazon's marketplace/grocery-partner
  routes return the wrong catalog or wrong currency).
- **Parked, not working**: Tesco, Sainsbury's, Waitrose, Aldi, Ocado. Each
  has a documented history of attempts in `config/stores.yaml` (rental
  actors, actors that ignore search terms, actors that crash and lose all
  data, cost estimates exceeding budget). Worth revisiting once Apify credit
  resets or better actors turn up — read the per-store comments in
  `config/stores.yaml` before trying again so you don't repeat a dead end.
- **Poundland**: no online ordering/scraper exists at all — in-store only,
  disabled by default.

## How it works

1. `config/catalog.yaml` — your **master catalog**: everything you might
   buy, with a default quantity, search aliases, and any manual prices
   you've noted for stores with no scraper (e.g. Iceland).
2. `python -m grocery_scraper.select_items` — an interactive checklist
   (tick what you want this week, confirm/change quantities) that generates
   `config/shopping_list.yaml` from your catalog. Run this before each
   price review. Don't hand-edit `shopping_list.yaml` — it gets overwritten.
3. `config/stores.yaml` — which store, which Apify actor scrapes it (or
   `manual: true` for stores priced from the catalog instead), and each
   store's delivery/click&collect fees.
4. `grocery_scraper/run.py` calls each enabled scraper-backed store's actor,
   matches results back to your list items by name similarity, merges in
   any manual-priced stores, then `optimizer.py` computes:
   - the cheapest **single store** that stocks everything, including its
     cheapest fulfillment option,
   - the cheapest **split** (buy each item wherever it's cheapest, then add
     each store's fulfillment cost for whatever landed there),
   - and recommends split only if it beats the single-store total by more
     than the threshold (default £5, `--threshold` to change it).
5. Writes a dated HTML report to `output/`.

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
before spending anything on real scraping. Note the demo fixture still uses
an old placeholder item list, not your real catalog — it's just there to
prove the pipeline works.

## Running for real, week to week

1. Create a free [Apify](https://apify.com) account and get an API token
   (Settings → Integrations). Apify actor runs are pay-per-use — check
   current Apify pricing yourself before relying on it long-term. The free
   tier gives $5/month in credit, no card required, which comfortably covers
   Asda + Morrisons once a week.
2. `export APIFY_TOKEN=your-token-here`
3. `python -m grocery_scraper.select_items` — tick this week's items, set
   quantities.
4. `python -m grocery_scraper.run -v`
5. Open the report in `output/`.

Run with `-v` the first few times — it writes each store's raw actor output
to `output/raw/<Store>.raw.json`. **Check these** if an item shows as
"missing" that you know the store stocks — it usually means the actor's
output field names don't match `fields:` in `stores.yaml` (see below), not
that the product doesn't exist.

### Re-checking a fix without spending more Apify credit

```bash
python -m grocery_scraper.run --from-raw -v
```

Re-renders the report from whatever's already cached in `output/raw/*.raw.json`
instead of calling Apify again. Use this after tweaking a store's `fields:`
mapping in `stores.yaml`, or after a matcher/report code change, to confirm
the fix without paying for another live run.

### Iceland's manual prices

Since there's no working scraper for Iceland, `config/catalog.yaml` has a
`manual_prices` field per item. Whenever you shop there, jot the current
price into the relevant item's `manual_prices: {Iceland: X.XX}` — exact
name-based lookup, no fuzzy matching, so there's no risk of it picking the
wrong product. Stale prices are still better than no price, but don't let
them go too many weeks without a refresh.

## Things you need to verify before trusting this with real money

- **Fulfillment fees**: `config/stores.yaml` marks each fee `verified: true`
  or `false`. Only Tesco, Asda and Sainsbury's fee/threshold figures were
  confirmed against current sources at the time of writing (Aug 2026).
  Others are placeholders — check each store's own delivery pricing page and
  correct them, since delivery fees vary by postcode/slot and change over
  time.
- **Actor output field names**: the `fields:` block per store (`name`,
  `price`, `unit_price`, `in_stock`) is only as good as what's been
  confirmed against a real run — check `output/raw/<Store>.raw.json` if a
  store's items come back unmatched. Field paths can be dotted for nested
  values (e.g. `currentPrice.value`) — see `matcher.py`'s `_get_path`.
- **Item matching**: matching blends character-sequence similarity with
  word-token overlap (see `match_score` % in the report, and anything under
  85% gets highlighted) — but it can still pick the wrong pack size or
  variant if the right one isn't in the store's search results at all. Check
  the matched product name each week, especially on highlighted rows.
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

Covers the optimizer's decision logic (single vs split totals, the £5
threshold, fulfillment fee thresholds), the matcher's scoring (including
regression tests anchored to real bad matches found in production, like
"Pepsi Max" matching plain "Pepsi"), and the manual-price quote builder —
all with synthetic/offline data, no network or Apify calls involved.
