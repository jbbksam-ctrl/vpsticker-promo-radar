#!/usr/bin/env python3
"""自检脚本：全站链接、薄内容、移动端、性能。

只读 site/ 下的产物，不改任何东西。输出纯文本证据。
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent / "site"

# 收集所有产出文件
files = sorted(p for p in SITE.rglob("*") if p.is_file())
html_files = sorted(p for p in SITE.rglob("*.html"))

print(f"[1] 产物统计：{len(files)} 个文件，其中 {len(html_files)} 个 HTML")
print()

# ---------------------------------------------------------------- ITEM:5 链接
print("=" * 72)
print("ITEM:5 内链检查")
print("=" * 72)

# 站内存在的路径集合（模拟 Pages 行为：x.html 与 /x 都算存在）
exists: set[str] = set()
for p in files:
    rp = p.relative_to(SITE).as_posix()
    exists.add("/" + rp)
    if rp.endswith(".html"):
        bare = rp[:-5]
        exists.add("/" + bare)
        exists.add("/" + bare + "/")
        if bare == "index":
            exists.add("/")
    if rp.endswith("index.html"):
        d = rp[: -len("index.html")]
        exists.add("/" + d)
exists.add("/")

LINK_RE = re.compile(r'<a\s[^>]*href="([^"]+)"', re.I)
IMG_RE = re.compile(r'<img\s[^>]*src="([^"]+)"', re.I)

broken: list[tuple[str, str]] = []
ext_links: set[str] = set()
total_links = 0

for f in html_files:
    text = f.read_text(encoding="utf-8", errors="replace")
    for href in LINK_RE.findall(text) + IMG_RE.findall(text):
        href = html.unescape(href).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if href.startswith(("http://", "https://")):
            ext_links.add(href)
            continue
        total_links += 1
        target = href.split("#")[0].split("?")[0]
        if not target:
            continue
        # 相对路径按当前文件所在目录解析
        if target.startswith("/"):
            resolved = target
        else:
            resolved = "/" + (f.parent.relative_to(SITE) / target).as_posix()
        norm = "/" + Path(resolved).as_posix().lstrip("/")
        if ".." in norm.split("/"):
            norm = "/" + Path(norm).as_posix()
        if norm not in exists:
            broken.append((f.relative_to(SITE).as_posix(), href))

print(f"站内链接总数（含图片）：{total_links}")
print(f"外链去重后：{len(ext_links)}")
print(f"断链：{len(broken)}")
for src, href in broken[:30]:
    print(f"  BROKEN  {src}  ->  {href}")
if not broken:
    print("  OK 无断链")
print()

# ---------------------------------------------------------------- ITEM:4 薄内容
print("=" * 72)
print("ITEM:4 薄内容 / 空壳页检查")
print("=" * 72)

BAD_PATTERNS = [
    ("lorem ipsum", re.compile(r"lorem\s+ipsum", re.I)),
    ("coming soon", re.compile(r"coming\s+soon", re.I)),
    ("placeholder", re.compile(r"placeholder", re.I)),
    ("TBD/TODO", re.compile(r"\b(TBD|TODO|FIXME)\b")),
    ("undefined", re.compile(r"\bundefined\b")),
    ("FILL_ME", re.compile(r"\{\{[A-Z_]+\}\}")),
]

# 去掉 head/nav/footer 后统计正文可见文字量
BODY_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def visible_text(raw: str) -> str:
    m = BODY_RE.search(raw)
    body = m.group(1) if m else raw
    body = SCRIPT_RE.sub(" ", body)
    body = TAG_RE.sub(" ", body)
    return re.sub(r"\s+", " ", html.unescape(body)).strip()


thin: list[tuple[str, int, int]] = []
patterns_hit: list[tuple[str, str, str]] = []

for f in html_files:
    raw = f.read_text(encoding="utf-8", errors="replace")
    rp = f.relative_to(SITE).as_posix()
    txt = visible_text(raw)
    words = len(txt.split())
    # <main> 里的段落数
    m = BODY_RE.search(raw)
    body = m.group(1) if m else ""
    paras = len(re.findall(r"<p[ >]", body, re.I))
    if words < 180:
        thin.append((rp, words, paras))
    for name, rx in BAD_PATTERNS:
        hit = rx.search(raw)
        if hit:
            patterns_hit.append((rp, name, hit.group(0)[:40]))

thin.sort(key=lambda x: x[1])
print(f"正文少于 180 词的页面：{len(thin)} / {len(html_files)}")
for rp, w, p in thin[:20]:
    print(f"  {w:>5} words  {p:>2} paras   {rp}")
if len(thin) > 20:
    print(f"  ... 另有 {len(thin) - 20} 页")
print()
print(f"命中模板占位/空壳关键词的页面：{len(patterns_hit)}")
for rp, name, snip in patterns_hit[:15]:
    print(f"  [{name}] {rp}  <- {snip!r}")
if not patterns_hit:
    print("  OK 无 lorem/coming soon/TBD/未渲染占位符")
print()

# ---------------------------------------------------------------- 文字量分布
print("正文词数分布：")
buckets = {"<100": 0, "100-179": 0, "180-399": 0, "400-799": 0, "800+": 0}
for f in html_files:
    raw = f.read_text(encoding="utf-8", errors="replace")
    w = len(visible_text(raw).split())
    if w < 100:
        buckets["<100"] += 1
    elif w < 180:
        buckets["100-179"] += 1
    elif w < 400:
        buckets["180-399"] += 1
    elif w < 800:
        buckets["400-799"] += 1
    else:
        buckets["800+"] += 1
for k, v in buckets.items():
    print(f"  {k:>9} words : {v:>3} 页")
print()

# ---------------------------------------------------------------- ITEM:6 移动端
print("=" * 72)
print("ITEM:6 移动端检查（静态可查部分）")
print("=" * 72)

no_viewport = []
for f in html_files:
    raw = f.read_text(encoding="utf-8", errors="replace")
    if "width=device-width" not in raw:
        no_viewport.append(f.relative_to(SITE).as_posix())
print(f"缺 viewport meta 的页：{len(no_viewport)}")
for rp in no_viewport[:10]:
    print(f"  {rp}")
if not no_viewport:
    print("  OK 全部页面都有 width=device-width")

css = SITE / "assets" / "style.css"
css_text = css.read_text(encoding="utf-8", errors="replace") if css.exists() else ""
print(f"style.css 字节数：{len(css_text)}")
print(f"含 @media 查询：{css_text.count('@media')} 处")
for m in re.finditer(r"@media[^{]*\{", css_text):
    print(f"  {m.group(0).strip()}")
# 固定宽度隐患
fixed = re.findall(r"width\s*:\s*(\d{3,})px", css_text)
print(f"CSS 里 >=100px 的固定 width：{len(fixed)} 处 {fixed[:10]}")
overflow = re.findall(r"overflow-x\s*:\s*([^;]+);", css_text)
print(f"overflow-x 声明：{overflow}")
ta = re.findall(r"table-layout\s*:\s*([^;]+);", css_text)
print(f"table-layout：{ta}")
print()

# ---------------------------------------------------------------- ITEM:7 性能
print("=" * 72)
print("ITEM:7 加载性能（产物体积）")
print("=" * 72)

by_ext: dict[str, list[int]] = {}
for p in files:
    by_ext.setdefault(p.suffix.lower() or "(none)", []).append(p.stat().st_size)
for ext, sizes in sorted(by_ext.items(), key=lambda kv: -sum(kv[1])):
    print(f"  {ext:<10} {len(sizes):>3} 个  合计 {sum(sizes)/1024:>8.1f} KB  最大 {max(sizes)/1024:>7.1f} KB")

print()
print("最大的 8 个文件：")
allf = sorted(files, key=lambda p: -p.stat().st_size)[:8]
for p in allf:
    print(f"  {p.stat().st_size/1024:>8.1f} KB  {p.relative_to(SITE).as_posix()}")

print()
print("各页总字节（HTML 自身）：")
sizes = sorted(((p.stat().st_size, p.relative_to(SITE).as_posix()) for p in html_files), reverse=True)
print(f"  最大 {sizes[0][0]/1024:.1f} KB  {sizes[0][1]}")
print(f"  最小 {sizes[-1][0]/1024:.1f} KB  {sizes[-1][1]}")
print(f"  中位 {sizes[len(sizes)//2][0]/1024:.1f} KB")
print(f"  平均 {sum(s for s, _ in sizes)/len(sizes)/1024:.1f} KB")
print()

# ---------------------------------------------------------------- 外链资源
print("外部资源引用（影响加载的外站请求）：")
ext_res = set()
for f in html_files:
    raw = f.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'<(?:script|link|img)\s[^>]*(?:src|href)="(https?://[^"]+)"', raw, re.I):
        ext_res.add(m.group(1))
for u in sorted(ext_res):
    print(f"  {u}")
if not ext_res:
    print("  OK 无外部 JS/CSS/字体请求（全站自包含）")
print()

print("sitemap 条数：", len(re.findall(r"<loc>", (SITE / "sitemap.xml").read_text(encoding="utf-8"))))
