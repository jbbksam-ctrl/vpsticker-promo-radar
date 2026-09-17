#!/usr/bin/env python3
"""线上实测：把 site/ 里的每一页都从线上拉一遍，验证状态码与站内链接。

用 curl 子进程（--noproxy '*' 绕开本机代理），只读，不改任何东西。
输出纯文本证据。
"""
from __future__ import annotations

import re
import subprocess
import sys
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
BASE = "https://vpsticker.com"

CURL = r"C:\Windows\System32\curl.exe"


def fetch(url: str) -> tuple[int, str]:
    """返回 (状态码, 正文)。--noproxy '*' 是关键：本机代理会对站点返回假故障。"""
    try:
        p = subprocess.run(
            [CURL, "-s", "-L", "--noproxy", "*", "--max-time", "30",
             "-w", "\n__CODE__%{http_code}", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40,
        )
        out = p.stdout or ""
        m = re.search(r"__CODE__(\d+)\s*$", out)
        code = int(m.group(1)) if m else 0
        body = out[: m.start()] if m else out
        return code, body
    except Exception as e:
        return 0, f"__ERR__ {e}"


pages = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob("*.html"))

# ---- 1. 线上路径映射 ----
def url_of(rel: str) -> str:
    if rel == "index.html":
        return BASE + "/"
    if rel.endswith(".html"):
        return BASE + "/" + rel[:-5]
    return BASE + "/" + rel


print("=" * 74)
print("线上实测：逐页状态码")
print("=" * 74)

results: dict[str, tuple[int, str]] = {}
bad = []
for rel in pages:
    u = url_of(rel)
    code, body = fetch(u)
    results[rel] = (code, body)
    if code != 200:
        bad.append((rel, code, u))
    print(f"  {code}  {u}")

print()
print(f"页面总数 {len(pages)}，非 200 的 {len(bad)} 个")
for rel, code, u in bad:
    print(f"  !! {code}  {u}")
print()

# ---- 2. 站内链接实测 ----
print("=" * 74)
print("线上实测：站内链接")
print("=" * 74)

LINK_RE = re.compile(r'<a\s[^>]*href="([^"]+)"', re.I)
IMG_RE = re.compile(r'<img\s[^>]*src="([^"]+)"', re.I)

internal: set[str] = set()
for rel, (code, body) in results.items():
    if code != 200:
        continue
    for href in LINK_RE.findall(body) + IMG_RE.findall(body):
        href = html.unescape(href).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if href.startswith(("http://", "https://")):
            if href.startswith(BASE):
                internal.add(href)
            continue
        internal.add(BASE + "/" + href.lstrip("/"))

print(f"站内唯一 URL 数（含被引用的资源）：{len(internal)}")
link_bad = []
for u in sorted(internal):
    code, _ = fetch(u)
    if code != 200:
        link_bad.append((code, u))
print(f"非 200 的：{len(link_bad)}")
for code, u in link_bad:
    print(f"  !! {code}  {u}")
if not link_bad:
    print("  OK 所有站内链接线上均 200")
print()

# ---- 3. 外链可达性（只报状态，不做修复）----
print("=" * 74)
print("外链可达性（信息性，不修）")
print("=" * 74)
ext: set[str] = set()
for rel, (code, body) in results.items():
    if code != 200:
        continue
    for href in LINK_RE.findall(body):
        href = html.unescape(href).strip()
        if href.startswith(("http://", "https://")) and not href.startswith(BASE):
            ext.add(href)
for u in sorted(ext):
    code, _ = fetch(u)
    print(f"  {code}  {u}")
print()

# ---- 4. 线上正文厚度抽样 ----
print("=" * 74)
print("线上正文厚度抽样（验证部署的是新版）")
print("=" * 74)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
BODY_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
for rel in ["deal/ionos-vps-2-0-month.html", "about.html", "privacy.html",
            "provider/hostinger.html", "compare.html", "sources.html", "contact.html"]:
    code, body = results.get(rel, (0, ""))
    if code != 200:
        print(f"  {rel}: HTTP {code}")
        continue
    m = BODY_RE.search(body)
    inner = SCRIPT_RE.sub(" ", m.group(1) if m else body)
    txt = re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", inner))).strip()
    print(f"  {len(txt.split()):>5} words   {rel}")
print()
