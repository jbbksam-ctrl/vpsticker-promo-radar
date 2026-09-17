# ILANG
# [TYPE:module][PROJECT:vpsticker][LANG:zh]
# ::ROLE{读 data/offers.json 加 .ilang/site.ilang 渲染静态站到 site/}
# ::INPUT{data/offers.json 与 .ilang/site.ilang 的 PROVIDERS PAGE FIELDS 模块}
# ::MUST{每页一条 canonical 每个优惠详情页嵌 Offer 结构化数据 sitemap 由本文件生成}
# ::RULE{抓不到 price 的 offer 不写 price 字段 也不进结构化数据 不许拿估的填}
# ::BOUNDARY{never:编价格 编折扣幅度 编佣金|scope:permanent}
"""build.py — 把 offers.json 渲染成静态站。

只用 Python 标准库。模板是纯文本 + {{占位符}}，重复块在 Python 里拼好再注入。
配置来自 .ilang/site.ilang，本文件不持有厂商清单、品牌名或域名。
"""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ilang_config
from ilang_config import Provider, SiteConfig, slugify
from og_image import build_og_image

ROOT = Path(__file__).resolve().parent
SITE_DIR = ROOT / "site"
TPL_DIR = ROOT / "templates"
DATA_PATH = ROOT / "data" / "offers.json"

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
CURRENCY_SIGN = {"USD": "$", "EUR": "\u20ac", "GBP": "\u00a3"}


# ---------------------------------------------------------------- 小工具


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def render(template: str, mapping: dict[str, Any]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def load_tpl(name: str) -> str:
    return (TPL_DIR / name).read_text(encoding="utf-8")


def money(o: dict[str, Any]) -> str:
    price = o.get("price")
    if price is None:
        return ""
    sign = CURRENCY_SIGN.get(o.get("currency", ""), "")
    if sign:
        body = f"{sign}{price:,.2f}".rstrip("0").rstrip(".")
    else:
        body = f"{price:,.2f}"
    return f"{body} {o.get('currency', '')}".strip()


def per(o: dict[str, Any]) -> str:
    return "/mo" if o.get("period") == "month" else ("/yr" if o.get("period") == "year" else "")


def price_label(o: dict[str, Any]) -> str:
    if o.get("price") is None:
        return "See site"
    return f"{money(o)}{per(o)}"


def short_title(title: str, limit: int = 96) -> str:
    title = title.strip()
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "\u2026"


def is_expired(o: dict[str, Any], now: datetime) -> bool:
    raw = o.get("valid_until")
    if not raw:
        return False
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < now
    except ValueError:
        return False


def jsonld_script(*nodes: dict[str, Any]) -> str:
    payload = {"@context": "https://schema.org", "@graph": [n for n in nodes if n]}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/")


def rel(path: str) -> str:
    """站内相对路径 -> 站内绝对路径。

    Cloudflare Pages 会把 x.html 308 到无扩展名的 /x，所以这里直接输出最终地址：
    站内链接和 canonical 都不再指向一次多余的跳转。index.html 归一成 /。
    非 .html 的资源（如 assets/og.png）原样保留。
    """
    p = path.lstrip("/")
    if p in ("index.html", ""):
        return "/"
    if p.endswith(".html"):
        p = p[:-5]
    return "/" + p


# ---------------------------------------------------------------- 页面外壳


class Builder:
    def __init__(self, cfg: SiteConfig, data: dict[str, Any]) -> None:
        self.cfg = cfg
        self.data = data
        self.base = cfg.base_url
        self.noun = cfg.noun
        self.headline = cfg.headline
        self.offers: list[dict[str, Any]] = data.get("offers", [])
        self.sources: list[dict[str, Any]] = data.get("sources", [])
        self.now = datetime.now(timezone.utc)
        self.generated_at = data.get("generated_at", self.now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        try:
            gen_dt = datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        except ValueError:
            gen_dt = self.now
        self.stamp_month = f"{MONTHS[gen_dt.month - 1]} {gen_dt.year}"
        self.stamp_date = gen_dt.strftime("%Y-%m-%d")
        self.pages: list[dict[str, str]] = []

    # ---- 通用 ----

    def url_for(self, path: str) -> str:
        return self.base.rstrip("/") + rel(path)

    def active_offers(self) -> list[dict[str, Any]]:
        return [o for o in self.offers if not is_expired(o, self.now)]

    def by_provider(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for o in self.active_offers():
            grouped.setdefault(o["provider_slug"], []).append(o)
        return grouped

    def provider_by_slug(self) -> dict[str, Provider]:
        return {p.slug: p for p in self.cfg.providers}

    def emit(self, path: str, content: str, lastmod: str | None = None) -> None:
        target = SITE_DIR / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.pages.append({"path": path, "lastmod": lastmod or self.stamp_date})

    def shell(
        self,
        *,
        path: str,
        title: str,
        description: str,
        content: str,
        jsonld: str,
        og_type: str = "website",
    ) -> str:
        canonical = self.url_for(path)
        hreflang = "\n".join(
            [
                f'<link rel="alternate" hreflang="{self.cfg.locale}" href="{canonical}">',
                f'<link rel="alternate" hreflang="x-default" href="{canonical}">',
            ]
        )
        return render(
            load_tpl("base.html"),
            {
                "LANG": self.cfg.locale,
                "TITLE": esc(title),
                "DESCRIPTION": esc(description),
                "CANONICAL": esc(canonical),
                "HREFLANG": hreflang,
                "OG_TYPE": og_type,
                "OG_IMAGE": esc(self.url_for("assets/og.png")),
                "OG_LOCALE": self.cfg.locale.replace("-", "_"),
                "BRAND": esc(self.cfg.brand),
                "JSONLD": jsonld,
                "CONTENT": content,
                "FOOTER_NOTE": esc(self.footer_note()),
                "FOOTER_LINKS": self.footer_links(),
                "GENERATED": esc(f"Data last refreshed {self.generated_at} (UTC)."),
            },
        )

    def footer_note(self) -> str:
        return (
            f"{self.cfg.brand} is an independent price radar. It is not affiliated with the "
            f"providers listed. Prices are read from each provider's own public pages and are "
            f"shown as published; always confirm on the provider's site before buying. "
            f"Some outbound links may be affiliate links. "
            f"Site rules are described in the I-Lang protocol \u2014 see .ilang/site.ilang "
            f"(protocol notes: ilang.ai)."
        )

    def footer_links(self) -> str:
        items = [
            ("Deals", "index.html"),
            ("Compare", "compare.html"),
            ("Sources", "sources.html"),
            ("About", "about.html"),
            ("Contact", "contact.html"),
            ("Privacy", "privacy.html"),
        ]
        return "".join(
            f'<a href="{esc(rel(path))}">{esc(label)}</a>' for label, path in items
        )

    # ---- 组件 ----

    def card(self, o: dict[str, Any]) -> str:
        expired = is_expired(o, self.now)
        price_html = (
            f"{esc(money(o))}<small>{esc(per(o))}</small>"
            if o.get("price") is not None
            else '<small>price not published on source page</small>'
        )
        flag = (
            '<span class="stale">expired</span>'
            if expired
            else '<span class="badge ok">in stock</span>'
        )
        return (
            f'<article class="card">'
            f'<span class="prov">{esc(o["provider"])}</span>'
            f'<a class="ttl" href="{esc(rel(self.deal_path(o)))}">{esc(short_title(o["title"]))}</a>'
            f'<span class="pr">{price_html}</span>'
            f'<span class="foot"><span>{flag}</span>'
            f'<span>checked {esc(str(o.get("fetched_at", ""))[:10])}</span></span>'
            f"</article>"
        )

    def deal_path(self, o: dict[str, Any]) -> str:
        return f"deal/{o['_slug']}.html"

    def provider_path(self, slug: str) -> str:
        return f"provider/{slug}.html"

    def crumbs(self, *items: tuple[str, str | None]) -> str:
        parts = []
        for label, href in items:
            parts.append(f'<a href="{esc(href)}">{esc(label)}</a>' if href else f"<span>{esc(label)}</span>")
        return " <span>&rsaquo;</span> ".join(parts)

    def stats(self, items: list[tuple[str, str]]) -> str:
        return "".join(f'<div class="stat"><b>{esc(v)}</b>{esc(k)}</div>' for k, v in items)

    def faq_html(self, qa: list[tuple[str, str]]) -> str:
        return "".join(
            f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in qa
        )

    # ---- 结构化数据 ----

    def ld_offer(self, o: dict[str, Any], page_url: str) -> dict[str, Any]:
        node: dict[str, Any] = {
            "@type": "Offer",
            "name": o["title"],
            "url": page_url,
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": o["provider"],
                "url": o.get("provider_link") or None,
            },
        }
        if o.get("price") is not None:
            node["price"] = o["price"]
            node["priceCurrency"] = o.get("currency") or self.cfg.currency
        if o.get("valid_until"):
            node["priceValidUntil"] = str(o["valid_until"])[:10]
        return {k: v for k, v in node.items() if v is not None}

    def ld_itemlist(self, entries: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "url": u, "name": n}
                for i, (n, u) in enumerate(entries, start=1)
            ],
        }

    def ld_breadcrumb(self, entries: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": n, "item": u}
                for i, (n, u) in enumerate(entries, start=1)
            ],
        }

    # ---- 生成 ----

    def build_all(self) -> None:
        self.assign_slugs()
        self.build_index()
        self.build_providers()
        self.build_deals()
        self.build_compare()
        self.build_sources()
        self.build_about()
        self.build_contact()
        self.build_privacy()
        self.build_sitemap()
        self.build_robots()
        self.build_404()
        self.build_headers()
        self.copy_assets()

    def assign_slugs(self) -> None:
        used: set[str] = set()
        for o in self.offers:
            base = slugify(f"{o['provider']}-{o['title']}-{o.get('price') or 'na'}-{o.get('period') or 'na'}")
            slug = base[:70] or "offer"
            n = 2
            while slug in used:
                slug = f"{base[:66]}-{n}"
                n += 1
            used.add(slug)
            o["_slug"] = slug

    # index
    def build_index(self) -> None:
        active = self.active_offers()
        cheapest: dict[str, dict[str, Any]] = {}
        for o in active:
            if o.get("price_monthly") is None:
                continue
            cur = cheapest.get(o["provider_slug"])
            if cur is None or o["price_monthly"] < cur["price_monthly"]:
                cheapest[o["provider_slug"]] = o
        picks = sorted(cheapest.values(), key=lambda o: o["price_monthly"])

        cards = "".join(self.card(o) for o in picks)
        chips = "".join(
            f'<a class="chip" href="{esc(rel(self.provider_path(p.slug)))}">{esc(p.name)}</a>'
            for p in self.cfg.providers
            if p.slug in cheapest
        )

        ok = sum(1 for s in self.sources if s.get("status") == "ok")
        stats = self.stats(
            [
                ("providers tracked", str(len(self.cfg.providers))),
                ("live offers", str(len(active))),
                ("providers returning data", f"{ok}/{len(self.sources) or len(self.cfg.providers)}"),
                ("last refresh", self.stamp_date),
            ]
        )

        qa = [
            (
                "Are these prices real?",
                "Yes. Every price is read from the provider's own public pricing page and shown exactly as published. "
                "When a provider does not publish a machine-readable price, that offer is listed without a price instead "
                "of guessing one.",
            ),
            (
                "How often is this updated?",
                "The scraper and the site rebuild run on a schedule, every 6 hours. Every page carries the exact UTC "
                "timestamp of the fetch it was built from, so you can always tell how fresh what you are reading is.",
            ),
            (
                "Do you earn from these links?",
                "Some outbound links are affiliate links. That does not change the price you pay, and it never changes "
                "which offers are listed or how they are ranked \u2014 ranking is purely by published price.",
            ),
            (
                "Why are some well-known providers missing?",
                "Because we could not read a published price from their public pages without bypassing their bot "
                "protection. We do not use workarounds, and we do not invent numbers to fill the gap.",
            ),
        ]

        top_entries = [(o["title"], self.url_for(self.deal_path(o))) for o in picks[:12]]
        jsonld = jsonld_script(
            {
                "@type": "WebSite",
                "name": self.cfg.brand,
                "url": self.base,
                "description": self.cfg.get("tagline"),
            },
            self.ld_itemlist(top_entries),
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a},
                    }
                    for q, a in qa
                ],
            },
        )

        method = (
            f"Once every 6 hours a plain Python scraper fetches the public pricing page of each of the "
            f"{len(self.cfg.providers)} providers listed below, reads the published prices, and writes them to a JSON "
            f"file. A second script renders that file into these static pages. "
            f"No inference runs at build time, no API keys are used, and nothing is filled in by hand. "
            f"Providers whose pages hide prices behind JavaScript are listed as such rather than approximated \u2014 "
            f"see the <a href=\"{rel('sources.html')}\">sources page</a> for the exact status of every provider on the last run."
        )

        title = (
            f"{self.headline} \u2014 Live {self.noun} Prices from "
            f"{len(self.cfg.providers)} Providers ({self.stamp_month})"
        )
        description = (
            f"Independent {self.noun} price radar. Lowest published monthly price from "
            f"{len(self.cfg.providers)} hosting "
            f"providers, refreshed every 6 hours. {len(active)} live offers, no estimated numbers."
        )

        content = render(
            load_tpl("index.html"),
            {
                "H1": esc(f"{self.headline}, read straight from the source ({self.stamp_month})"),
                "LEDE": esc(self.cfg.get("tagline")),
                "STATS": stats,
                "CARDS": cards or '<p class="muted">No offers with a published price on this run.</p>',
                "CHIPS": chips,
                "METHOD": method,
                "FAQ": self.faq_html(qa),
            },
        )
        self.emit(
            "index.html",
            self.shell(
                path="index.html",
                title=title,
                description=description,
                content=content,
                jsonld=jsonld,
            ),
        )

    # provider pages
    def build_providers(self) -> None:
        grouped = self.by_provider()
        pmap = self.provider_by_slug()
        for p in self.cfg.providers:
            offers = grouped.get(p.slug, [])
            if not offers:
                continue
            priced = [o for o in offers if o.get("price") is not None]
            prices = [o["price"] for o in priced]
            cards = "".join(self.card(o) for o in offers)

            if prices:
                lo, hi = min(prices), max(prices)
                lead = (
                    f"from {money(priced[0])}{per(priced[0])}"
                    if lo == hi
                    else f"{lo:g}\u2013{hi:g} {priced[0].get('currency', '')}"
                )
            else:
                lead = "price not published"

            stats = self.stats(
                [
                    ("offers tracked", str(len(offers))),
                    ("entry price", lead),
                    ("last refresh", str(offers[0].get("fetched_at", ""))[:10]),
                ]
            )

            agg: dict[str, Any] = {
                "@type": "AggregateOffer",
                "priceCurrency": priced[0].get("currency", self.cfg.currency) if priced else self.cfg.currency,
                "offerCount": len(priced),
                "offers": [self.ld_offer(o, self.url_for(self.deal_path(o))) for o in priced],
            }
            if prices:
                agg["lowPrice"] = min(prices)
                agg["highPrice"] = max(prices)

            product: dict[str, Any] = {
                "@type": "Product",
                "name": f"{p.name} {self.noun}",
                "brand": {"@type": "Brand", "name": p.name},
                "url": self.url_for(self.provider_path(p.slug)),
                "category": self.cfg.get("niche"),
            }
            if priced:
                product["offers"] = agg

            jsonld = jsonld_script(
                product,
                self.ld_breadcrumb(
                    [
                        (self.cfg.brand, self.base),
                        ("Providers", self.url_for("compare.html")),
                        (p.name, self.url_for(self.provider_path(p.slug))),
                    ]
                ),
            )

            title = (
                f"{p.name} {self.noun} Pricing \u2014 {lead} ({self.stamp_month}) | {self.cfg.brand}"
                if prices
                else f"{p.name} {self.noun} Offers ({self.stamp_month}) | {self.cfg.brand}"
            )
            description = (
                f"{len(offers)} {self.noun} offers tracked at {p.name} as of {self.stamp_date}. "
                f"Prices read from {p.name}'s own public page. Entry price: {lead}."
            )

            content = render(
                load_tpl("provider.html"),
                {
                    "CRUMBS": self.crumbs(
                        (self.cfg.brand, "/"),
                        ("Providers", rel("compare.html")),
                        (p.name, None),
                    ),
                    "H1": esc(f"{p.name} {self.noun} offers \u2014 {self.stamp_month}"),
                    "LEDE": esc(
                        f"Every offer below was read from {p.name}'s own public pricing page on "
                        f"{str(offers[0].get('fetched_at', ''))[:10]}. Nothing is estimated."
                    ),
                    "STATS": stats,
                    "CARDS": cards,
                    "SOURCE_URL": esc(p.source_url),
                },
            )
            self.emit(
                self.provider_path(p.slug),
                self.shell(
                    path=self.provider_path(p.slug),
                    title=title,
                    description=description,
                    content=content,
                    jsonld=jsonld,
                    og_type="product",
                ),
                lastmod=str(offers[0].get("fetched_at", self.stamp_date))[:10],
            )

    # deal pages
    def build_deals(self) -> None:
        grouped = self.by_provider()
        for o in self.offers:
            expired = is_expired(o, self.now)
            siblings = [s for s in grouped.get(o["provider_slug"], []) if s["_slug"] != o["_slug"]]
            cards = "".join(self.card(s) for s in siblings[:4])

            facts = [
                ("Provider", f'<a href="{esc(rel(self.provider_path(o["provider_slug"])))}">{esc(o["provider"])}</a>'),
                ("Price", esc(money(o)) or "not published on the source page"),
                ("Billing period", esc("monthly" if o.get("period") == "month" else "annual" if o.get("period") == "year" else "not stated")),
                ("Currency", esc(o.get("currency", "")) or "not stated"),
                ("Valid until", esc(str(o.get("valid_until", ""))[:10]) or "not stated by the provider"),
                ("Extracted", esc(o.get("extraction", ""))),
                ("Source page", f'<a href="{esc(o.get("source_url", ""))}" rel="nofollow noopener" target="_blank">{esc(o.get("source_url", ""))}</a>'),
                ("Fetched at", esc(o.get("fetched_at", ""))),
            ]
            facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)

            page_url = self.url_for(self.deal_path(o))
            graph = [
                self.ld_breadcrumb(
                    [
                        (self.cfg.brand, self.base),
                        (o["provider"], self.url_for(self.provider_path(o["provider_slug"]))),
                        (short_title(o["title"], 60), page_url),
                    ]
                )
            ]
            if not expired:
                graph.insert(0, self.ld_offer(o, page_url))
            jsonld = jsonld_script(*graph)

            price_txt = f"{money(o)}{per(o)}" if o.get("price") is not None else "Price not published"
            title = (
                f"{short_title(o['title'], 60)} \u2014 {price_txt} ({self.stamp_month}) | {self.cfg.brand}"
                if o.get("price") is not None
                else f"{short_title(o['title'], 60)} ({self.stamp_month}) | {self.cfg.brand}"
            )
            description = (
                f"{o['provider']} offer: {short_title(o['title'], 90)}. "
                + (f"Published price {price_txt}. " if o.get("price") is not None else "Price not published by the provider. ")
                + f"Read from {o['provider']}'s public page on {str(o.get('fetched_at', ''))[:10]}."
            )

            provenance = (
                "This listing is marked expired: the validity date published by the provider has passed. "
                "It is kept for the record only and is excluded from structured data."
                if expired
                else "This page is generated from a scheduled fetch of the provider's public page. "
                "Prices can change at any time \u2014 confirm on the provider's site before buying."
            )

            content = render(
                load_tpl("deal.html"),
                {
                    "CRUMBS": self.crumbs(
                        (self.cfg.brand, "/"),
                        (o["provider"], rel(self.provider_path(o["provider_slug"]))),
                        (short_title(o["title"], 40), None),
                    ),
                    "H1": esc(short_title(o["title"], 110)),
                    "PRICE": (
                        f"{esc(money(o))}<small>{esc(per(o))}</small>"
                        if o.get("price") is not None
                        else '<small>not published</small>'
                    ),
                    "LEDE": esc(
                        f"{o['provider']} \u00b7 read from the provider's public page on "
                        f"{str(o.get('fetched_at', ''))[:10]}"
                    ),
                    "PROVIDER": esc(o["provider"]),
                    "OFFER_URL": esc(o.get("offer_url") or o.get("source_url", "")),
                    "FACTS": facts_html,
                    "CARDS": cards or '<p class="muted">No other offers tracked for this provider on this run.</p>',
                    "PROVENANCE": esc(provenance),
                },
            )
            self.emit(
                self.deal_path(o),
                self.shell(
                    path=self.deal_path(o),
                    title=title,
                    description=description,
                    content=content,
                    jsonld=jsonld,
                    og_type="product",
                ),
                lastmod=str(o.get("fetched_at", self.stamp_date))[:10],
            )

    # compare
    def build_compare(self) -> None:
        grouped = self.by_provider()
        pmap = self.provider_by_slug()
        rows: list[tuple[float, Provider, list[dict[str, Any]]]] = []
        for slug, offers in grouped.items():
            p = pmap.get(slug)
            if not p:
                continue
            priced = [o for o in offers if o.get("price_monthly") is not None]
            if not priced:
                continue
            rows.append((min(o["price_monthly"] for o in priced), p, offers))
        rows.sort(key=lambda r: r[0])

        body = []
        entries: list[tuple[str, str]] = []
        for rank, (_, p, offers) in enumerate(rows, start=1):
            priced = [o for o in offers if o.get("price_monthly") is not None]
            cheapest = min(priced, key=lambda o: o["price_monthly"])
            best_annual = [o for o in priced if o.get("period") == "year"]
            annual = min(best_annual, key=lambda o: o["price_monthly"]) if best_annual else None
            url = self.url_for(self.provider_path(p.slug))
            entries.append((p.name, url))
            body.append(
                "<tr>"
                f'<td class="num">{rank}</td>'
                f'<td><a href="{esc(rel(self.provider_path(p.slug)))}">{esc(p.name)}</a></td>'
                f'<td class="num">{esc(money(cheapest))}{esc(per(cheapest))}</td>'
                f'<td class="num">{esc(money(annual)) + esc(per(annual)) if annual else "\u2014"}</td>'
                f'<td class="num">{len(offers)}</td>'
                f'<td><a href="{esc(cheapest.get("offer_url") or p.source_url)}" rel="nofollow sponsored noopener" target="_blank">visit</a></td>'
                "</tr>"
            )

        head = (
            "<tr><th>#</th><th>Provider</th><th>Cheapest monthly</th><th>Cheapest annual</th>"
            "<th>Offers tracked</th><th>Link</th></tr>"
        )
        jsonld = jsonld_script(
            self.ld_itemlist(entries),
            self.ld_breadcrumb([(self.cfg.brand, self.base), ("Compare", self.url_for("compare.html"))]),
        )
        content = render(
            load_tpl("compare.html"),
            {
                "CRUMBS": self.crumbs((self.cfg.brand, "/"), ("Compare", None)),
                "H1": esc(f"{self.noun} price comparison \u2014 {self.stamp_month}"),
                "LEDE": esc(
                    "Ranked purely by the lowest published monthly price we could read from each provider's own "
                    "page. No sponsor placement, no paid ordering."
                ),
                "THEAD": head,
                "TBODY": "".join(body) or '<tr><td colspan="6">No priced offers on this run.</td></tr>',
                "NOTE": esc(
                    "Ranking is by published price only. A cheaper entry price does not mean better hardware, "
                    "support, or network \u2014 read the provider's own specification before buying."
                ),
            },
        )
        self.emit(
            "compare.html",
            self.shell(
                path="compare.html",
                title=f"{self.noun} Price Comparison \u2014 {len(rows)} Providers ({self.stamp_month}) | {self.cfg.brand}",
                description=(
                    f"Side-by-side {self.noun} pricing from {len(rows)} providers, ranked by published entry price, "
                    f"as read on {self.stamp_date}."
                ),
                content=content,
                jsonld=jsonld,
            ),
        )

    # sources
    def build_sources(self) -> None:
        label = {
            "ok": ("ok", "price extracted"),
            "no_price": ("warn", "no price published in the HTML (JavaScript-rendered)"),
            "blocked_by_robots": ("warn", "blocked by robots.txt \u2014 skipped"),
            "http_error": ("warn", "request refused by the site (HTTP error)"),
            "error": ("warn", "fetch error"),
        }
        body = []
        for s in self.sources:
            kind, why = label.get(s.get("status", "error"), ("warn", s.get("status", "")))
            body.append(
                "<tr>"
                f'<td><a href="{esc(s.get("url", ""))}" rel="nofollow noopener" target="_blank">{esc(s.get("provider", ""))}</a></td>'
                f'<td class="num">{esc(s.get("http") if s.get("http") is not None else "\u2014")}</td>'
                f'<td>{esc(why)}</td>'
                f'<td class="num">{esc(s.get("offers", 0))}</td>'
                f'<td>{esc(s.get("extraction") or "\u2014")}</td>'
                "</tr>"
            )
        head = "<tr><th>Provider</th><th>HTTP</th><th>Result</th><th>Offers</th><th>Extraction</th></tr>"
        jsonld = jsonld_script(
            self.ld_breadcrumb([(self.cfg.brand, self.base), ("Sources", self.url_for("sources.html"))])
        )
        content = render(
            load_tpl("sources.html"),
            {
                "CRUMBS": self.crumbs((self.cfg.brand, "/"), ("Sources", None)),
                "H1": esc("Sources and extraction status"),
                "LEDE": esc(
                    f"Exactly what the last run did, provider by provider, at {self.generated_at}. "
                    "Rows that produced no price are listed too \u2014 a gap we could not fill is still a fact."
                ),
                "THEAD": head,
                "TBODY": "".join(body),
                "NOTE": esc(
                    "We read only public pages, respect robots.txt, and do not bypass bot protection or log in anywhere. "
                    "Where a provider returns no machine-readable price, the offer is shown without a price rather than estimated."
                ),
            },
        )
        self.emit(
            "sources.html",
            self.shell(
                path="sources.html",
                title=f"Sources \u2014 where every price comes from ({self.stamp_date}) | {self.cfg.brand}",
                description=(
                    f"Per-provider extraction status for the {self.stamp_date} run: HTTP result, offers found, "
                    f"and extraction method."
                ),
                content=content,
                jsonld=jsonld,
            ),
        )

    # about / contact / privacy —— 散文页
    def prose_page(
        self,
        *,
        path: str,
        crumb: str,
        h1: str,
        lede: str,
        body: str,
        title: str,
        description: str,
        show_updated: bool = True,
    ) -> None:
        updated_line = (
            f'<p class="updated">Last updated {esc(self.stamp_date)}.</p>'
            if show_updated
            else ""
        )
        content = render(
            load_tpl("page.html"),
            {
                "CRUMBS": self.crumbs((self.cfg.brand, "/"), (crumb, None)),
                "H1": esc(h1),
                "LEDE": esc(lede),
                "UPDATED_LINE": updated_line,
                "BODY": body,
            },
        )
        self.emit(
            path,
            self.shell(
                path=path,
                title=title,
                description=description,
                content=content,
                jsonld=jsonld_script(
                    self.ld_breadcrumb(
                        [(self.cfg.brand, self.base), (crumb, self.url_for(path))]
                    )
                ),
            ),
        )

    def build_about(self) -> None:
        brand = esc(self.cfg.brand)
        sources = esc(rel("sources.html"))
        body = (
            f"<p>{brand} is an independent {esc(self.noun)} price radar. It reads the prices that "
            "hosting providers publish on their own public pricing pages, and rebuilds this site "
            "from them every six hours.</p>"

            "<h2>How it works</h2>"
            "<p>A scheduled job fetches each provider's public pricing page, extracts the prices "
            "that are actually published there, and writes them into this site. There is no "
            "database, no account, and no hand-entered data.</p>"
            "<p>Every offer links back to the exact page it was read from. The "
            f'<a href="{sources}">Sources</a> page shows, provider by provider, the HTTP result, '
            "how the price was extracted, and how many offers were found on the last run "
            "&mdash; including the providers that produced nothing.</p>"

            "<h2>What this site does not do</h2>"
            "<ul>"
            "<li>It does not estimate, average, or back-fill a missing price. If a provider does "
            "not publish a machine-readable price, the offer is listed <em>without</em> a price.</li>"
            "<li>It does not bypass bot protection, log in anywhere, or read anything that is not "
            "a public page.</li>"
            "<li>It does not accept payment for placement. Ordering is by published price only "
            "&mdash; nobody can pay to move up.</li>"
            "<li>It is not affiliated with any of the providers listed.</li>"
            "</ul>"

            "<h2>Affiliate disclosure</h2>"
            "<p>Some outbound links on this site may be affiliate links. If you sign up through "
            "one, we may earn a commission at no extra cost to you. Affiliate status never affects "
            "whether a provider is listed, where it ranks, or what price is shown &mdash; the "
            "numbers are read from the providers' own pages either way.</p>"

            "<h2>Why a price here may differ from what you see</h2>"
            "<p>Prices change. A price shown here was true on the provider's own page at the "
            "timestamp printed on the offer. Always confirm on the provider's site before "
            "buying.</p>"
        )
        self.prose_page(
            path="about.html",
            crumb="About",
            h1=f"About {self.cfg.brand}",
            lede="What this site is, how the prices are collected, and what it refuses to do.",
            body=body,
            title=f"About \u2014 how the prices are collected | {self.cfg.brand}",
            description=(
                f"{self.cfg.brand} is an independent {self.noun} price radar: public prices read "
                f"from providers' own pages every six hours. No paid placement, no estimated numbers."
            ),
        )

    def build_contact(self) -> None:
        email = self.cfg.contact_email
        if not email:
            raise ValueError(
                "site.ilang 的 ::STATE{@SITE ...} 里没有 contact_email，"
                "拒绝生成 contact.html —— 联系方式不许留空或占位"
            )
        mailto = f'<p><a href="mailto:{esc(email)}">{esc(email)}</a></p>'
        sources = esc(rel("sources.html"))
        privacy = esc(rel("privacy.html"))
        body = (
            f"<p>The fastest way to reach {esc(self.cfg.brand)} is email.</p>"
            "<h2>Email</h2>"
            f"{mailto}"

            "<h2>What we can help with</h2>"
            "<ul>"
            "<li>A price on this site that does not match the provider's own page.</li>"
            "<li>A link that is broken or points at the wrong offer.</li>"
            "<li>A provider we should be tracking &mdash; or one we should stop tracking.</li>"
            f'<li>A question about how the data is collected. The <a href="{sources}">Sources</a> '
            "page usually answers it first.</li>"
            "</ul>"

            "<h2>What we cannot help with</h2>"
            "<ul>"
            "<li>Billing, refunds, server problems, or support tickets. We do not sell hosting and "
            "are not affiliated with any provider &mdash; please contact the provider directly.</li>"
            "<li>Sales enquiries. Nothing on this site is for sale, and we do not accept paid "
            "placement.</li>"
            "</ul>"

            "<h2>Response time</h2>"
            "<p>We read everything, but we cannot promise a reply time.</p>"

            "<h2>Privacy</h2>"
            f'<p>What we do with your message is covered on the <a href="{privacy}">privacy '
            "page</a>.</p>"
        )
        self.prose_page(
            path="contact.html",
            crumb="Contact",
            h1="Contact",
            lede="Corrections, broken links, and questions about the data.",
            body=body,
            title=f"Contact | {self.cfg.brand}",
            description=(
                f"How to reach {self.cfg.brand} about a wrong price, a broken link, or how the "
                f"data is collected."
            ),
        )

    def build_privacy(self) -> None:
        domain = esc(self.cfg.domain)
        contact = esc(rel("contact.html"))
        body = (
            f"<p>This policy explains what happens to your data when you visit {domain}. "
            "It is short, because this site does very little with it.</p>"

            "<h2>What this site collects directly</h2>"
            "<ul>"
            "<li><strong>No accounts.</strong> There is nothing to sign up for.</li>"
            "<li><strong>No forms.</strong> There are no contact forms, comment boxes, or "
            "newsletter sign-ups on this site.</li>"
            "<li><strong>No cookies set by this site.</strong> We do not set cookies, and we do "
            "not use local storage or anything similar.</li>"
            "<li><strong>No analytics or tracking of our own.</strong> We do not run our own "
            "analytics script, tag manager, or session recorder on this site.</li>"
            "<li><strong>Third-party advertising.</strong> This site displays ads from third-party "
            "ad networks. Those networks may set their own cookies and collect data (such as your IP "
            "address, browser type, and pages visited) under their own privacy policies. You can "
            "usually control or disable advertising cookies in your browser settings or through the "
            "ad network's opt-out page.</li>"
            "</ul>"

            "<h2>What ad networks may collect</h2>"
            "<p>When you visit a page that shows an ad, the ad network's script runs in your browser. "
            "Depending on the network, it may collect:</p>"
            "<ul>"
            "<li>Your IP address and approximate location.</li>"
            "<li>Your browser type, screen size, and operating system.</li>"
            "<li>Which pages you viewed on this site.</li>"
            "<li>A cookie or similar identifier so the network can remember your preferences or "
            "limit how often you see the same ad.</li>"
            "</ul>"
            "<p>We do not control what the ad network collects &mdash; that is governed by the "
            "network's own privacy policy. What we can promise is that ad placement never changes "
            "which deals are listed or how they rank. Ranking is always by published price.</p>"

            "<h2>What the hosting provider sees</h2>"
            "<p>This site is a set of static files served by Cloudflare. Like any web host or "
            "content delivery network, Cloudflare processes request data &mdash; such as your IP "
            "address, user agent, and the page requested &mdash; in order to deliver the page and "
            "protect the site from abuse. That processing is carried out by Cloudflare under "
            '<a href="https://www.cloudflare.com/privacypolicy/" rel="nofollow noopener" '
            'target="_blank">Cloudflare\'s own privacy policy</a>. We do not run a separate '
            "analytics system on top of it.</p>"

            "<h2>Outbound links</h2>"
            "<p>Links to hosting providers take you to someone else's website. Once you are there, "
            "that provider's own privacy and cookie policies apply &mdash; not this one. Some of "
            "those links may be affiliate links, meaning a commission may be paid to us if you sign "
            "up. Affiliate status never affects what is listed or how it ranks.</p>"

            "<h2>Email</h2>"
            f'<p>If you email us, we keep your message and your address so we can reply. We do not '
            f'add you to any mailing list, and we do not sell or share your address. See the '
            f'<a href="{contact}">contact page</a>.</p>'

            "<h2>What we do not do</h2>"
            "<ul>"
            "<li>We do not sell, rent, or trade personal data.</li>"
            "<li>We do not build visitor profiles.</li>"
            "<li>We do not knowingly collect data from children.</li>"
            "</ul>"

            "<h2>Changes to this policy</h2>"
            "<p>If this policy changes, the date at the top of this page changes with it.</p>"
        )
        self.prose_page(
            path="privacy.html",
            crumb="Privacy",
            h1="Privacy policy",
            lede="What this site does and does not do with your data.",
            body=body,
            title=f"Privacy policy | {self.cfg.brand}",
            description=(
                "No accounts, no forms, no cookies set by this site, no first-party analytics. "
                "This site shows third-party ads; see what ad networks may collect and how to opt out. "
                "What Cloudflare sees as the host, and what happens when you click an outbound link."
            ),
        )

    # sitemap / robots / assets
    def build_sitemap(self) -> None:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        priority = {
            "index.html": "1.0",
            "compare.html": "0.8",
            "sources.html": "0.5",
            "about.html": "0.4",
            "contact.html": "0.3",
            "privacy.html": "0.2",
        }
        for page in self.pages:
            loc = self.url_for(page["path"])
            pri = priority.get(page["path"], "0.7")
            lines.append(
                f"  <url><loc>{html.escape(loc)}</loc>"
                f"<lastmod>{page['lastmod']}</lastmod>"
                f"<changefreq>daily</changefreq>"
                f"<priority>{pri}</priority></url>"
            )
        lines.append("</urlset>")
        (SITE_DIR / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def build_robots(self) -> None:
        (SITE_DIR / "robots.txt").write_text(
            "User-agent: *\nAllow: /\n\n"
            f"Sitemap: {self.url_for('sitemap.xml')}\n",
            encoding="utf-8",
        )

    def build_404(self) -> None:
        """404 页直接写盘，不进 sitemap。"""
        picks = sorted(
            [o for o in self.active_offers() if o.get("price_monthly") is not None],
            key=lambda o: o["price_monthly"],
        )[:6]
        cards = "".join(self.card(o) for o in picks)
        content = (
            '<section class="hero"><h1>Page not found</h1>'
            '<p class="lede">That URL is not on this site. It may have been a deal that was '
            "withdrawn, or a typo. Here is what is live right now.</p>"
            '<p><a class="btn" href="/">All deals</a> '
            '<a class="btn" href="/compare">Compare</a></p></section>'
            f'<div class="cards">{cards}</div>'
        )
        page = self.shell(
            path="404.html",
            title=f"Page not found | {self.cfg.brand}",
            description=f"That page is not on this site. Browse the live {self.headline} instead.",
            content=content,
            jsonld=jsonld_script(
                self.ld_breadcrumb([(self.cfg.brand, self.base), ("404", self.url_for("404.html"))])
            ),
        )
        (SITE_DIR / "404.html").write_text(page, encoding="utf-8")

    def build_headers(self) -> None:
        """Cloudflare Pages 响应头。被别的托管忽略也无害。"""
        (SITE_DIR / "_headers").write_text(
            "/*\n"
            "  X-Content-Type-Options: nosniff\n"
            "  Referrer-Policy: strict-origin-when-cross-origin\n"
            "  X-Frame-Options: SAMEORIGIN\n"
            "  Permissions-Policy: geolocation=(), microphone=(), camera=()\n"
            "\n"
            "/assets/*\n"
            "  Cache-Control: public, max-age=604800, immutable\n"
            "\n"
            "/*.html\n"
            "  Cache-Control: public, max-age=300\n",
            encoding="utf-8",
        )

    def copy_assets(self) -> None:
        assets = SITE_DIR / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TPL_DIR / "style.css", assets / "style.css")
        shutil.copyfile(TPL_DIR / "favicon.svg", assets / "favicon.svg")
        build_og_image(
            assets / "og.png",
            self.cfg.brand.upper(),
            self.cfg.get("niche").upper(),
            "REAL PRICES FROM PUBLIC SOURCES",
            f"{len(self.active_offers())} LIVE OFFERS - UPDATED {self.stamp_date}",
        )
        (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")


def main() -> int:
    cfg = ilang_config.load()
    if not DATA_PATH.exists():
        raise SystemExit(f"缺少 {DATA_PATH}，先跑 scraper.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)

    b = Builder(cfg, data)
    b.build_all()
    print(f"[build] 品牌={cfg.brand} 域名={cfg.domain}")
    print(f"[build] 页面 {len(b.pages)} 个，优惠 {len(b.offers)} 条 → {SITE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
