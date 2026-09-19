---
license: cc0-1.0
language:
- en
pretty_name: vpsticker VPS price dataset
size_categories:
- n<1K
tags:
- tabular
- economics
- pricing
- hosting
configs:
- config_name: default
  data_files:
  - split: train
    path: vpsticker-vps-prices.csv
---

# vpsticker VPS price dataset

Published monthly and annual prices for virtual private server (VPS) plans, read directly
from the public pricing pages of 15 hosting providers.

**Snapshot: 30 offers across 15 providers.**

## Files

| File | Contents |
| --- | --- |
| `vpsticker-vps-prices.csv` | The offers as flat rows, for loading without any parsing. |
| `vpsticker-vps-prices.json` | The same data plus run metadata, as consumed by the site build. |
| `fetch-status.csv` | Per-provider fetch status for this snapshot: HTTP code, extraction method, offers found. Includes providers that returned nothing. |

## Columns

| Column | Meaning |
| --- | --- |
| `provider` | Hosting provider name, as written on their own site. |
| `title` | Plan or page title, as published by the provider. |
| `price` | The price exactly as published. |
| `currency` | `USD` or `EUR` — the currency the provider bills in. **Not converted.** |
| `period` | `month` or `year` — the billing cycle the price applies to. |
| `price_monthly` | Price normalised to a monthly figure (annual prices divided by 12). Normalises the *billing cycle*, not the *currency*. Equals `price` when `period` is `month`. |
| `offer_url` | Direct link to the offer page. |
| `source_url` | The public pricing page the price was read from. |
| `extraction` | How the price was read: `jsonld:product`, `jsonld:offer`, or `regex`. |
| `fetched_at` | UTC timestamp of the fetch (ISO 8601). |

## What this dataset is not

- **Not converted across currencies.** USD and EUR rows sit side by side unconverted. Do not
  rank across currencies without applying your own exchange rate.
- **Not a complete census of the market.** Providers whose pages hide prices behind
  JavaScript, or which block automated reads, are absent or listed without a price.
  `fetch-status.csv` records each case.
- **Not renewal pricing.** Promotional first-year rates are common in this market. A published
  price may not be the price a customer pays in year two.
- **Not estimated anywhere.** Where no machine-readable price exists, the offer is listed
  without a price rather than filled in. There are no interpolated or hand-entered numbers
  in this dataset.

## Links

- Live, continuously refreshed version: https://vpsticker.com/
- Per-provider extraction status: https://vpsticker.com/sources
- Source code and regeneration instructions: https://github.com/jbbksam-ctrl/vpsticker-promo-radar

## License

**CC0 1.0 Universal** (public domain dedication). Use it for anything, including
commercially, with no attribution required.
