# vps-deals — VPS price radar

An independent VPS price radar. It reads the **published prices** from hosting providers'
own public pricing pages, and rebuilds a static site from them every 6 hours.

**Live site: https://vps-deals.pages.dev**

- No server. No API keys. No third-party Python packages. Standard library only.
- No estimated numbers. If a provider does not publish a machine-readable price, the offer
  is listed *without* a price instead of being filled in by hand.
- Every number is traceable to the page it was read from — see `site/sources.html`.

## What it does

```
scraper.py   ->  data/offers.json  ->  build.py  ->  site/
   fetch            dataset            render        static site
```

| File | Job |
| --- | --- |
| `.ilang/site.ilang` | The single source of truth for configuration: brand, domain, provider list, fields, page rules, schedule. |
| `ilang_config.py` | Parses `site.ilang`. Nothing else holds a provider list. |
| `scraper.py` | Fetches each provider's public pricing page, extracts prices, writes `data/offers.json`. |
| `build.py` | Renders `site/`: index, provider pages, deal pages, compare, sources, sitemap, robots. |
| `og_image.py` | Generates the social share image with a hand-written PNG encoder. |
| `templates/` | Page layouts. Plain text with `{{PLACEHOLDER}}` tokens. |
| `.github/workflows/update.yml` | Runs the whole pipeline on a schedule and commits the result. |

## How to use it

Run it locally — nothing to install, Python 3.11+ is enough:

```bash
python scraper.py     # refresh data/offers.json from the public pages
python build.py       # rebuild site/
```

Preview locally:

```bash
python -m http.server 8000 --directory site
```

Then open <http://localhost:8000>.

### Change what is tracked

Edit `.ilang/site.ilang`, then re-run `scraper.py` and `build.py`. The provider list, the brand,
the domain, the page size and the schedule all live in that one file — there is no second copy
of the provider list anywhere in the code.

```
Name | website | pricing-page-url | affiliate-url | extraction-profile
```

The 4th column is an affiliate link. Leave it empty to use the plain link; fill it in once an
affiliate programme approves the site — no code change needed. The 5th column is optional and
selects the extraction profile (`auto`, `jsonld`, `regex`).

### Deploying

The workflow commits the freshly built `site/` directory, so any static host can serve it.

On Cloudflare Pages there are two routes:

- **Git integration** — build command `python build.py`, output directory `site`.
- **Direct upload** — no Git app authorisation needed, an API token with
  *Cloudflare Pages: Edit* is enough:

  ```bash
  CLOUDFLARE_API_TOKEN=xxx CLOUDFLARE_ACCOUNT_ID=yyy ./deploy.sh
  ```

  `CLOUDFLARE_ACCOUNT_ID` is required, not optional: a token scoped to Pages only
  cannot read the account list, so `wrangler` cannot discover the account on its own.
  The account ID is the 32-hex string in the dashboard URL
  (`dash.cloudflare.com/<account-id>/...`).

`build.py` also emits `site/404.html` and `site/_headers` (security and cache headers),
both of which Cloudflare Pages picks up automatically.

## Rules this project holds itself to

- Only public pages are read: official pricing pages, sitemaps and feeds.
- `robots.txt` is respected. Bot protection is never bypassed, nothing behind a login is touched.
- Prices are never invented, estimated, or back-filled. A missing price stays missing.
- Affiliate links, when present, follow the public terms of established networks. No brand-bidding,
  no cookie injection, no self-referral.
- Ranking is by published price only. Nobody can pay to move up.

## Adding a provider

1. Check the page returns prices to a plain HTTP client (many do not — they render prices in
   JavaScript, and those are deliberately excluded rather than guessed at).
2. Add one line to the `PROVIDERS` module in `.ilang/site.ilang`.
3. Run `python scraper.py` and confirm the row reports `ok` with offers found.

The `sources.html` page reports, per provider, the HTTP status, the extraction method and how
many offers were found — so gaps are visible instead of hidden.

---

Site rules are described using the I-Lang protocol — see `.ilang/site.ilang`. Protocol notes: ilang.ai
