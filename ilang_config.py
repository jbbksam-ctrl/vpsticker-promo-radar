# ILANG
# [TYPE:module][PROJECT:vpsticker][LANG:zh]
# ::ROLE{解析 .ilang/site.ilang 的唯一实现 供 scraper.py 与 build.py 共用}
# ::MUST{配置的唯一真源是 .ilang/site.ilang 本文件只解析 不内置任何厂商 品牌 域名}
# ::BOUNDARY{never:在代码里另写一份厂商清单|scope:permanent}
"""
ilang_config.py — I-Lang 配置解析器。

职责：把 .ilang/site.ilang 读成一个结构化的 SiteConfig 对象。
边界：只解析，不做业务判断，不联网，不写文件。
      厂商清单 / 品牌 / 域名 / 字段 全部来自 site.ilang，本文件不含任何硬编码清单。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_REL_PATH = Path(".ilang") / "site.ilang"
CONTENT_REL_PATH = Path(".ilang") / "content.ilang"

_HEADER_RE = re.compile(r"\[([A-Za-z_]+):([^\]]*)\]")
_DIRECTIVE_RE = re.compile(r"^::([A-Z]+)\{(.*)\}\s*$")
_MODULE_HEAD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\|\s*(.*)$")
_MODULE_COMMENT_RE = re.compile(r"^\[[A-Z_]+\]")


@dataclass
class Provider:
    """一家厂商。第 5 列 profile 可选，留空等于 auto。"""

    name: str
    website: str
    source_url: str
    affiliate_url: str = ""
    profile: str = "auto"

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def link(self) -> str:
        """出站链接：填了联盟链接就用联盟链接，否则用裸链。"""
        return self.affiliate_url or self.website


@dataclass
class SiteConfig:
    path: Path
    header: dict[str, str] = field(default_factory=dict)
    state: dict[str, str] = field(default_factory=dict)
    modules: dict[str, dict[str, Any]] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    # 页面正文词库（来自 .ilang/content.ilang 的 ::BLOCK）
    # 结构：{ block_name: {"title": str, "lines": [str, ...]} }
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ---- 由 modules 派生 ----
    @property
    def providers(self) -> list[Provider]:
        out: list[Provider] = []
        for line in self.modules.get("PROVIDERS", {}).get("lines", []):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue
            name, website, source_url = parts[0], parts[1], parts[2]
            affiliate = parts[3] if len(parts) > 3 else ""
            profile = parts[4] if len(parts) > 4 and parts[4] else "auto"
            if not name or not source_url:
                continue
            out.append(Provider(name, website, source_url, affiliate, profile))
        return out

    @property
    def fields(self) -> list[str]:
        lines = self.modules.get("FIELDS", {}).get("lines", [])
        return lines[0].split() if lines else []

    @property
    def page(self) -> dict[str, str]:
        return _kv_lines(self.modules.get("PAGE", {}).get("lines", []))

    @property
    def schedule(self) -> dict[str, str]:
        return _kv_lines(self.modules.get("SCHEDULE", {}).get("lines", []))

    # ---- 便捷取值 ----
    def get(self, key: str, default: str = "") -> str:
        return self.state.get(key, default)

    @property
    def brand(self) -> str:
        return self.get("brand")

    @property
    def niche(self) -> str:
        return self.get("niche")

    @property
    def noun(self) -> str:
        """文案里指代本行业的名词（如 VPS）。配置里没写就从 niche 首个词兜底。"""
        explicit = self.get("noun")
        if explicit:
            return explicit
        words = self.niche.split()
        return words[0] if words else self.brand

    @property
    def headline(self) -> str:
        """首页标题用的短名词（如 VPS Deals）。没写就从 niche 派生：首词 + 末词。"""
        explicit = self.get("headline")
        if explicit:
            return explicit
        words = [w for w in self.niche.split() if w]
        if not words:
            return self.noun
        if len(words) == 1:
            return words[0]
        return f"{words[0]} {words[-1].capitalize()}"

    @property
    def domain(self) -> str:
        return self.get("domain")

    @property
    def base_url(self) -> str:
        d = self.domain.strip().rstrip("/")
        if not d:
            return ""
        return d if d.startswith("http") else f"https://{d}"

    @property
    def locale(self) -> str:
        return self.get("locale", "en-US")

    @property
    def currency(self) -> str:
        return self.get("currency", "USD")

    @property
    def contact_email(self) -> str:
        """联系页用的邮箱。配置里没写就返回空串，由调用方决定怎么处理。"""
        return self.get("contact_email").strip()

    @property
    def operator(self) -> str:
        """谁在运营这个站。关于页要用，配置里没写就返回空串（关于页会跳过那一节）。"""
        return self.get("operator").strip()

    @property
    def run_as(self) -> str:
        """运营方式的补充说明（如「副业项目」），可为空。"""
        return self.get("run_as").strip()

    @property
    def per_page(self) -> int:
        try:
            return int(self.page.get("per_page", "24"))
        except ValueError:
            return 24

    @property
    def sort(self) -> str:
        return self.page.get("sort", "price_asc")

    # ---- 正文词库 ----

    def block(self, name: str) -> list[str]:
        """取一个内容块的正文行。取不到就返回空列表，由调用方决定怎么降级。"""
        entry = self.blocks.get(name)
        if not entry:
            return []
        return list(entry.get("lines", []))

    def block_title(self, name: str, default: str = "") -> str:
        entry = self.blocks.get(name)
        return entry.get("title", default) if entry else default

    def tier_text(self, price: float | None) -> str:
        """按价格取一档「这个价位意味着什么」的解读。

        what_price_means 的行格式是「上限 | 一句话」，取第一个 >= price 的上限。
        价格缺失或整块缺失时返回空串 —— 不编。
        """
        if price is None:
            return ""
        tiers: list[tuple[float, str]] = []
        for line in self.block("what_price_means"):
            head, sep, text = line.partition("|")
            if not sep:
                continue
            try:
                cap = float(head.strip())
            except ValueError:
                continue
            tiers.append((cap, text.strip()))
        for cap, text in sorted(tiers):
            if price <= cap:
                return text
        return tiers[-1][1] if tiers else ""


def _kv_lines(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def slugify(text: str) -> str:
    """把厂商名 / 优惠名转成 URL 安全的 slug。纯 ASCII 兜底，无第三方依赖。"""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "item"


def _parse_state(body: str) -> dict[str, str]:
    """::STATE{@SITE, brand:x, niche:y} -> {'brand':'x','niche':'y'}

    值里含逗号会打断按逗号切分的逻辑，所以允许用 | 再分一组键值对：
    ::STATE{@SITE, operator:一个独立运营者|run_as:副业项目}
    """
    out: dict[str, str] = {}
    for group in body.split("|"):
        for chunk in group.split(","):
            chunk = chunk.strip()
            if not chunk or chunk.startswith("@"):
                continue
            key, sep, value = chunk.partition(":")
            if not sep:
                continue
            out[key.strip()] = value.strip()
    return out


def _load_content(cfg: SiteConfig) -> None:
    """把 .ilang/content.ilang 的 ::BLOCK 读进 cfg.blocks。

    文件不存在就静默跳过 —— 正文词库是可选增强，缺了页面照常渲染，只是没有那些段落。
    """
    path = cfg.path.parent / "content.ilang"
    if not path.exists():
        return
    raw = path.read_text(encoding="utf-8").splitlines()
    current: str | None = None
    for line in raw:
        stripped = line.strip()
        if not stripped or stripped.startswith(";;"):
            continue
        m = _DIRECTIVE_RE.match(stripped)
        if m and m.group(1) == "BLOCK":
            name_part, _, meta = m.group(2).partition("|")
            name = name_part.strip()
            entry: dict[str, Any] = {"lines": []}
            for pair in meta.split("|"):
                k, sep, v = pair.partition(":")
                if sep:
                    entry[k.strip()] = v.strip()
            cfg.blocks[name] = entry
            current = name
            continue
        if m:
            # 其他指令（STATE/RULE/BOUNDARY）不影响正文块
            current = None
            continue
        if current:
            cfg.blocks[current]["lines"].append(stripped)


def load(path: Path | str | None = None) -> SiteConfig:
    """读取并解析 site.ilang。路径默认为仓库根的 .ilang/site.ilang。"""
    cfg_path = Path(path) if path else Path(__file__).resolve().parent / CONFIG_REL_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"找不到 I-Lang 配置文件：{cfg_path}")

    raw = cfg_path.read_text(encoding="utf-8").splitlines()
    if not raw or raw[0].strip() != "ILANG":
        raise ValueError(f"{cfg_path} 第一行必须是 ILANG 抬头")

    cfg = SiteConfig(path=cfg_path)

    # 第二行：头部 token
    for line in raw[1:4]:
        found = _HEADER_RE.findall(line)
        if found:
            cfg.header.update({k: v for k, v in found})
            break

    current: str | None = None
    for line in raw[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = _DIRECTIVE_RE.match(stripped)
        if m:
            kind, body = m.group(1), m.group(2)
            current = None
            if kind == "STATE":
                cfg.state.update(_parse_state(body))
            elif kind == "MODULE":
                name_part, _, meta = body.partition("|")
                name = name_part.strip()
                entry: dict[str, Any] = {"lines": []}
                for pair in meta.split("|"):
                    k, sep, v = pair.partition(":")
                    if sep:
                        entry[k.strip()] = v.strip()
                cfg.modules[name] = entry
                current = name
            elif kind == "RULE":
                cfg.rules.append(body.strip())
            elif kind == "BOUNDARY":
                cfg.boundaries.append(body.strip())
            continue

        # 模块正文
        if current and not _MODULE_COMMENT_RE.match(stripped):
            cfg.modules[current]["lines"].append(stripped)

    if not cfg.providers:
        raise ValueError(f"{cfg_path} 里没有解析到任何厂商，PROVIDERS 模块为空或格式不对")

    _load_content(cfg)
    return cfg


if __name__ == "__main__":
    c = load()
    print(f"配置文件 : {c.path}")
    print(f"header   : {c.header}")
    print(f"brand    : {c.brand}")
    print(f"domain   : {c.domain}")
    print(f"locale   : {c.locale}  currency: {c.currency}")
    print(f"字段     : {c.fields}")
    print(f"排序     : {c.sort}  per_page: {c.per_page}")
    print(f"cron     : {c.schedule.get('cron')}")
    print(f"厂商 {len(c.providers)} 家：")
    for p in c.providers:
        print(f"  - {p.name:14s} profile={p.profile:7s} {p.source_url}")
    print(f"规则 {len(c.rules)} 条 / 边界 {len(c.boundaries)} 条")
