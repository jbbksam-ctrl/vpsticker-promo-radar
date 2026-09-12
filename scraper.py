# ILANG
# [TYPE:module][PROJECT:vps-deals][LANG:zh]
# ::ROLE{抓取公开优惠数据 写 data/offers.json}
# ::INPUT{.ilang/site.ilang 的 PROVIDERS 与 FIELDS 模块 本文件不持有厂商清单}
# ::RULE{抓不到 price 就不写 price 字段 也不进结构化数据 不许拿估的填}
# ::RULE{每条 offer 必带 source_url 指向真实被抓的公开页面}
# ::BOUNDARY{never:编优惠 编价格 编佣金 抓登录后内容 绕反爬|scope:permanent}
"""scraper.py — 抓取公开优惠数据。

只用 Python 标准库，运行时零推理、零 API 密钥、零第三方依赖。
配置全部来自 .ilang/site.ilang（改那里，站就变）。
"""

from __future__ import annotations

import gzip
import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import ilang_config
from ilang_config import Provider, SiteConfig, slugify

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OFFERS_PATH = DATA_DIR / "offers.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "(+https://github.com/vps-deals-promo-radar; promo-radar-bot)"
)
TIMEOUT = 25
POLITE_DELAY = 1.2  # 同一家抓完歇一下，别把人站打疼

_OPENER = urllib.request.build_opener()
_OPENER_NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_ROBOTS_CACHE: dict[str, dict[str, list[str]]] = {}
BOT_TOKEN = "promo-radar-bot"

# ---------------------------------------------------------------- 抓取


def fetch(url: str) -> tuple[int, str, str]:
    """返回 (http状态, 正文, 最终URL)。先走默认 opener，失败再直连。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    last_err: Exception | None = None
    for opener in (_OPENER, _OPENER_NOPROXY):
        try:
            with opener.open(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc:
                    raw = gzip.decompress(raw)
                elif "deflate" in enc:
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                charset = resp.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                return resp.status, text, resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, "", url
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"抓取失败 {url}: {last_err}")


def robots_allowed(url: str) -> bool:
    """礼貌起见读一次 robots.txt。

    按 User-agent 分组判定：只有「匹配我们的组」（`*` 或组名出现在我们的 UA 里）
    明确写了 Disallow: / 才拒绝。别把给别的爬虫的规则算到自己头上。
    """
    m = re.match(r"(https?://[^/]+)", url)
    if not m:
        return True
    origin = m.group(1)
    if origin not in _ROBOTS_CACHE:
        groups: dict[str, list[str]] = {}
        try:
            code, body, _ = fetch(origin + "/robots.txt")
            if code == 200:
                cur: str | None = None
                for raw in body.splitlines():
                    line = raw.split("#")[0].strip()
                    if not line:
                        continue
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "user-agent":
                        cur = val.lower()
                        groups.setdefault(cur, [])
                    elif key == "disallow" and cur is not None:
                        groups[cur].append(val)
        except Exception:  # noqa: BLE001
            pass
        _ROBOTS_CACHE[origin] = groups

    ua_low = UA.lower()
    for agent, disallows in _ROBOTS_CACHE[origin].items():
        applies = agent == "*" or (agent and agent in ua_low)
        if applies and any(d == "/" for d in disallows):
            return False
    return True


# ---------------------------------------------------------------- 提取

_JSONLD_RE = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_OGTITLE_RE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\'](?:og:title|twitter:title)["\'][^>]+content\s*=\s*["\']([^"\']*)["\']',
    re.I,
)
_OGTITLE_RE2 = re.compile(
    r'<meta[^>]+content\s*=\s*["\']([^"\']*)["\'][^>]+(?:property|name)\s*=\s*["\'](?:og:title|twitter:title)["\']',
    re.I,
)

PERIODS = (
    (r"mo(?:nth)?", "month"),
    (r"yr|year|annual(?:ly)?", "year"),
)
_PRICE_RE = re.compile(
    r"(?P<cur>US\$|USD|EUR|GBP|\$|€|£)\s*(?P<amt>\d{1,4}(?:[.,]\d{1,2})?)\s*"
    r"(?:/|per\s+)?\s*(?P<per>mo|month|yr|year|annually|annual)\b",
    re.I,
)
CURRENCY_SYMBOL = {"$": "USD", "US$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}
MIN_PRICE, MAX_PRICE = 0.5, 3000.0


def page_title(html: str) -> str:
    for rx in (_OGTITLE_RE, _OGTITLE_RE2):
        m = rx.search(html)
        if m and m.group(1).strip():
            return html_mod.unescape(m.group(1)).strip()
    m = _TITLE_RE.search(html)
    if m:
        return html_mod.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    return ""


def _walk(obj: Any) -> Iterable[dict]:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _types(node: dict) -> set[str]:
    t = node.get("@type")
    if t is None:
        return set()
    if isinstance(t, str):
        return {t}
    if isinstance(t, list):
        return {str(x) for x in t}
    return set()


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _clean_price(raw: str) -> float | None:
    s = raw.strip().replace(" ", "")
    # 1.234,56 (EU) vs 1,234.56 (US)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _offer_dict(
    provider: Provider,
    title: str,
    price: float | None,
    currency: str,
    period: str,
    offer_url: str,
    valid_until: str,
    source_url: str,
    extraction: str,
) -> dict[str, Any]:
    """统一成一条 offer。price 为 None 时不写 price / currency / period 字段。"""
    item: dict[str, Any] = {
        "provider": provider.name,
        "provider_slug": provider.slug,
        "provider_link": provider.link,
        "title": title.strip(),
        "offer_url": offer_url or source_url,
        "source_url": source_url,
        "extraction": extraction,
    }
    if price is not None and MIN_PRICE <= price <= MAX_PRICE:
        item["price"] = round(price, 2)
        item["currency"] = currency
        item["period"] = period
        item["price_monthly"] = round(_to_monthly(price, period), 2)
    if valid_until:
        item["valid_until"] = valid_until
    return item


def _to_monthly(price: float, period: str) -> float:
    if period == "year":
        return price / 12.0
    return price


def parse_jsonld(html: str, provider: Provider, source_url: str) -> list[dict[str, Any]]:
    """从 schema.org JSON-LD 里取 Product / Service / Offer / AggregateOffer。"""
    out: list[dict[str, Any]] = []
    for block in _JSONLD_RE.findall(html):
        block = block.strip()
        if not block:
            continue
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue

        for node in _walk(data):
            if not isinstance(node, dict):
                continue
            kinds = _types(node)
            if not kinds & {"Product", "Service", "Offer", "AggregateOffer"}:
                continue

            name = str(node.get("name") or node.get("title") or "").strip()
            if kinds & {"AggregateOffer"}:
                price = _num(node.get("lowPrice"))
                cur = str(node.get("priceCurrency") or "")
                if price is not None:
                    out.append(
                        _offer_dict(
                            provider,
                            name or f"{provider.name} VPS",
                            price,
                            cur,
                            "month",
                            str(node.get("url") or source_url),
                            str(node.get("priceValidUntil") or ""),
                            source_url,
                            "jsonld:aggregate",
                        )
                    )
                continue

            if kinds & {"Product", "Service"}:
                offers = node.get("offers")
                offer_list = offers if isinstance(offers, list) else ([offers] if isinstance(offers, dict) else [])
                prod_url = str(node.get("url") or source_url)
                if not offer_list:
                    # Product 没挂 offer：只有它自己带 price 才算
                    if node.get("price") is not None:
                        price = _num(node.get("price"))
                        out.append(
                            _offer_dict(
                                provider,
                                name or f"{provider.name} VPS",
                                price,
                                str(node.get("priceCurrency") or ""),
                                "month",
                                prod_url,
                                str(node.get("priceValidUntil") or ""),
                                source_url,
                                "jsonld:product",
                            )
                        )
                    continue
                for off in offer_list:
                    if not isinstance(off, dict):
                        continue
                    price = _num(off.get("price"))
                    if price is None:
                        price = _num(off.get("lowPrice"))
                    if price is None:
                        continue
                    off_name = str(off.get("name") or "").strip()
                    # offer 自带名字就用它（更具体，例如 "KVM 1"），否则退回 Product 名
                    title = off_name or name or f"{provider.name} VPS"
                    out.append(
                        _offer_dict(
                            provider,
                            title,
                            price,
                            str(off.get("priceCurrency") or node.get("priceCurrency") or ""),
                            "month",
                            str(off.get("url") or prod_url),
                            str(off.get("priceValidUntil") or ""),
                            source_url,
                            "jsonld:product",
                        )
                    )
                continue

            if kinds & {"Offer"}:
                price = _num(node.get("price")) or _num(node.get("lowPrice"))
                if price is None:
                    continue
                out.append(
                    _offer_dict(
                        provider,
                        name or f"{provider.name} VPS",
                        price,
                        str(node.get("priceCurrency") or ""),
                        "month",
                        str(node.get("url") or source_url),
                        str(node.get("priceValidUntil") or ""),
                        source_url,
                        "jsonld:offer",
                    )
                )
    return _dedupe(out)


def parse_regex(html: str, provider: Provider, source_url: str) -> list[dict[str, Any]]:
    """HTML 正则兜底：找 价格+周期，只留月付/年付。标题用页面自己的标题。"""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(re.sub(r"\s+", " ", text))

    found: dict[tuple[float, str], str] = {}
    for m in _PRICE_RE.finditer(text):
        amt = _clean_price(m.group("amt"))
        if amt is None or not (MIN_PRICE <= amt <= MAX_PRICE):
            continue
        per_raw = m.group("per").lower()
        period = "year" if re.match(r"yr|year|annual", per_raw) else "month"
        found.setdefault((amt, period), CURRENCY_SYMBOL.get(m.group("cur").upper(), provider_currency(provider)))

    if not found:
        return []

    title = page_title(html) or f"{provider.name} VPS pricing"
    # 只留每个周期最便宜的那一档：优惠站要的就是「入门价」这条 headline，
    # 把整张价目表铺上去只会变成同标题刷屏。
    cheapest: dict[str, tuple[float, str]] = {}
    for (amt, period), cur in found.items():
        if period not in cheapest or amt < cheapest[period][0]:
            cheapest[period] = (amt, cur)

    out: list[dict[str, Any]] = []
    for period in ("month", "year"):
        if period not in cheapest:
            continue
        amt, cur = cheapest[period]
        out.append(
            _offer_dict(
                provider,
                f"{title} — from {amt:g}/{'mo' if period == 'month' else 'yr'}",
                amt,
                cur,
                period,
                source_url,
                "",
                source_url,
                "regex",
            )
        )
    return _dedupe(out)


def provider_currency(provider: Provider) -> str:
    return "USD"


def _dedupe(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """两级去重：先按内容精确去重，再把同厂商同价位同周期的合并成一条。

    同一家在同一价位上往往既有 AggregateOffer 又有 Product，标题长的那条更啰嗦，
    所以合并时留标题更短、更干净的那条。
    """
    seen: set[tuple] = set()
    stage1: list[dict[str, Any]] = []
    for o in offers:
        key = (o.get("title"), o.get("price"), o.get("period"), o.get("offer_url"))
        if key in seen:
            continue
        seen.add(key)
        stage1.append(o)

    best: dict[tuple, dict[str, Any]] = {}
    order: list[tuple] = []
    for o in stage1:
        k = (o.get("provider_slug"), o.get("price"), o.get("period"))
        if k not in best:
            best[k] = o
            order.append(k)
        elif len(o.get("title", "")) < len(best[k].get("title", "")):
            best[k] = o
    return [best[k] for k in order]


def extract(provider: Provider, html: str, source_url: str) -> list[dict[str, Any]]:
    mode = (provider.profile or "auto").lower()
    if mode == "jsonld":
        return parse_jsonld(html, provider, source_url)
    if mode == "regex":
        return parse_regex(html, provider, source_url)
    # auto：先结构化，空了再兜底
    return parse_jsonld(html, provider, source_url) or parse_regex(html, provider, source_url)


# ---------------------------------------------------------------- 主流程


def run(cfg: SiteConfig) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    offers: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for p in cfg.providers:
        rec: dict[str, Any] = {
            "provider": p.name,
            "url": p.source_url,
            "profile": p.profile,
            "http": None,
            "status": "error",
            "extraction": None,
            "offers": 0,
            "note": "",
        }
        try:
            if not robots_allowed(p.source_url):
                rec["status"] = "blocked_by_robots"
                rec["note"] = "robots.txt 不允许，跳过"
                sources.append(rec)
                continue

            code, html, final_url = fetch(p.source_url)
            rec["http"] = code
            if code != 200 or not html:
                rec["status"] = "http_error"
                rec["note"] = f"HTTP {code}"
                sources.append(rec)
                continue

            got = extract(p, html, final_url or p.source_url)
            for o in got:
                o["fetched_at"] = stamp
            offers.extend(got)
            rec["offers"] = len(got)
            if got:
                rec["status"] = "ok"
                rec["extraction"] = got[0].get("extraction")
            else:
                rec["status"] = "no_price"
                rec["note"] = "页面没给出可提取的公开价格（多为 JS 渲染），按规则不写 price 也不编"
        except Exception as e:  # noqa: BLE001
            rec["status"] = "error"
            rec["note"] = f"{type(e).__name__}: {e}"
        sources.append(rec)
        print(f"  [{rec['status']:>16s}] {p.name:16s} offers={rec['offers']} {rec['note']}", flush=True)
        time.sleep(POLITE_DELAY)

    offers.sort(key=lambda o: (o.get("price_monthly", 9e9), o.get("provider", "")))

    payload = {
        "generated_at": stamp,
        "brand": cfg.brand,
        "domain": cfg.domain,
        "locale": cfg.locale,
        "currency": cfg.currency,
        "config_source": str(cfg.path.name),
        "providers_configured": len(cfg.providers),
        "offers_total": len(offers),
        "sources": sources,
        "offers": offers,
    }
    return payload


def main() -> int:
    cfg = ilang_config.load()
    print(f"[scraper] 读配置 {cfg.path}")
    print(f"[scraper] 品牌={cfg.brand} 域名={cfg.domain} 厂商={len(cfg.providers)} 家")
    payload = run(cfg)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OFFERS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for s in payload["sources"] if s["status"] == "ok")
    print(f"[scraper] 出数 {ok}/{len(payload['sources'])} 家，共 {payload['offers_total']} 条 → {OFFERS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
