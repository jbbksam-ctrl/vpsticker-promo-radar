# ILANG
# [TYPE:module][PROJECT:vps-deals][LANG:zh]
# ::ROLE{生成社交分享大图 site/assets/og.png 纯 Python 手写 PNG 零依赖}
# ::WHY{没有 og:image 社交平台转发出来就是一条裸链 有大图才有卡片}
# ::BOUNDARY{never:引入第三方图像库 调用在线图片服务|scope:permanent}
"""og_image.py — 手写 PNG 编码器 + 5x7 点阵字体，生成 Open Graph 大图。

只用标准库（zlib / struct）。不联网，不依赖 PIL。
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------- 5x7 点阵字体
# 每个字形 7 行 x 5 列，'#' 为实心。用 '/' 分行。
_GLYPHS = {
    " ": "...../...../...../...../...../...../.....",
    "-": "...../...../...../#####/...../...../.....",
    ".": "...../...../...../...../...../.##../.##..",
    "$": "..#../.####/#.#../.###./..#.#/####./..#..",
    "/": "....#/....#/...#./..#../.#.../#..../#....",
    ":": "...../.##../.##../...../.##../.##../.....",
    "%": "##..#/##.#./..#../.#.../#.##./..##./.....",
    "?": ".###./#...#/....#/...#./..#../...../..#..",
    "0": ".###./#...#/#..##/#.#.#/##..#/#...#/.###.",
    "1": "..#../.##../..#../..#../..#../..#../.###.",
    "2": ".###./#...#/....#/...#./..#../.#.../#####",
    "3": "#####/...#./..#../...#./....#/#...#/.###.",
    "4": "...#./..##./.#.#./#..#./#####/...#./...#.",
    "5": "#####/#..../####./....#/....#/#...#/.###.",
    "6": "..##./.#.../#..../####./#...#/#...#/.###.",
    "7": "#####/....#/...#./..#../.#.../.#.../.#...",
    "8": ".###./#...#/#...#/.###./#...#/#...#/.###.",
    "9": ".###./#...#/#...#/.####/....#/...#./.##..",
    "A": ".###./#...#/#...#/#####/#...#/#...#/#...#",
    "B": "####./#...#/#...#/####./#...#/#...#/####.",
    "C": ".###./#...#/#..../#..../#..../#...#/.###.",
    "D": "####./#...#/#...#/#...#/#...#/#...#/####.",
    "E": "#####/#..../#..../####./#..../#..../#####",
    "F": "#####/#..../#..../####./#..../#..../#....",
    "G": ".###./#...#/#..../#.###/#...#/#...#/.###.",
    "H": "#...#/#...#/#...#/#####/#...#/#...#/#...#",
    "I": "#####/..#../..#../..#../..#../..#../#####",
    "J": "....#/....#/....#/....#/#...#/#...#/.###.",
    "K": "#...#/#..#./#.#../##.../#.#../#..#./#...#",
    "L": "#..../#..../#..../#..../#..../#..../#####",
    "M": "#...#/##.##/#.#.#/#...#/#...#/#...#/#...#",
    "N": "#...#/##..#/#.#.#/#..##/#...#/#...#/#...#",
    "O": ".###./#...#/#...#/#...#/#...#/#...#/.###.",
    "P": "####./#...#/#...#/####./#..../#..../#....",
    "Q": ".###./#...#/#...#/#...#/#.#.#/#..#./.##.#",
    "R": "####./#...#/#...#/####./#.#../#..#./#...#",
    "S": ".####/#..../#..../.###./....#/....#/####.",
    "T": "#####/..#../..#../..#../..#../..#../..#..",
    "U": "#...#/#...#/#...#/#...#/#...#/#...#/.###.",
    "V": "#...#/#...#/#...#/#...#/#...#/.#.#./..#..",
    "W": "#...#/#...#/#...#/#...#/#.#.#/##.##/#...#",
    "X": "#...#/#...#/.#.#./..#../.#.#./#...#/#...#",
    "Y": "#...#/#...#/.#.#./..#../..#../..#../..#..",
    "Z": "#####/....#/...#./..#../.#.../#..../#####",
}

FONT_W, FONT_H = 5, 7


class Canvas:
    """极简 RGB 画布，只支持矩形填充和点阵文字。"""

    def __init__(self, width: int, height: int, bg: tuple[int, int, int]) -> None:
        self.w = width
        self.h = height
        self.buf = bytearray(bg * (width * height))

    def fill_rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            off = (yy * self.w + x0) * 3
            self.buf[off : off + len(row)] = row

    def text_width(self, text: str, scale: int, tracking: int = 1) -> int:
        if not text:
            return 0
        return (len(text) * (FONT_W + tracking) - tracking) * scale

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        scale: int,
        color: tuple[int, int, int],
        tracking: int = 1,
    ) -> None:
        cx = x
        for ch in text.upper():
            glyph = _GLYPHS.get(ch, _GLYPHS["?"])
            for row_i, row in enumerate(glyph.split("/")):
                for col_i, cell in enumerate(row):
                    if cell == "#":
                        self.fill_rect(
                            cx + col_i * scale,
                            y + row_i * scale,
                            scale,
                            scale,
                            color,
                        )
            cx += (FONT_W + tracking) * scale

    def to_png_bytes(self) -> bytes:
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)  # filter type 0
            raw.extend(self.buf[y * stride : (y + 1) * stride])

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )


# ---------------------------------------------------------------- 版式

BG = (11, 17, 32)
ACCENT = (56, 189, 248)
ACCENT2 = (34, 197, 94)
FG = (241, 245, 249)
MUTED = (148, 163, 184)


def build_og_image(
    path: Path,
    brand: str,
    niche: str,
    headline: str,
    footer: str,
    width: int = 1200,
    height: int = 630,
) -> Path:
    c = Canvas(width, height, BG)

    # 左侧色条
    c.fill_rect(0, 0, 16, height, ACCENT)
    # 右上角装饰块
    c.fill_rect(width - 300, 0, 300, 12, ACCENT2)

    c.draw_text(80, 120, brand, 8, ACCENT, tracking=1)
    c.draw_text(80, 220, niche, 4, FG, tracking=1)

    # 分隔线
    c.fill_rect(80, 290, 220, 6, ACCENT2)

    c.draw_text(80, 340, headline, 5, FG, tracking=1)

    c.fill_rect(80, height - 120, width - 160, 2, (51, 65, 85))
    c.draw_text(80, height - 90, footer, 3, MUTED, tracking=1)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(c.to_png_bytes())
    return path


if __name__ == "__main__":
    out = build_og_image(
        Path(__file__).resolve().parent / "site" / "assets" / "og.png",
        "VPS-DEALS",
        "VPS HOSTING DEALS",
        "REAL PRICES FROM PUBLIC SOURCES",
        "UPDATED EVERY 6 HOURS",
    )
    print(f"写出 {out} ({out.stat().st_size} bytes)")
