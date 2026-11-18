# -*- coding: utf-8 -*-
"""
amr_font_codec.py  --  EU4 中文自制字库编码 编解码器

用途
    读写《欧陆风云4》中文汉化 MOD 使用的自定义字库编码。
    汉化文件里的中文【不是】普通 UTF-8 汉字，而是每个汉字用三个码位表示，
    配合替换字体（如「汉仪文黑」字体 MOD）渲染。
    用普通 UTF-8 中文写进去 = 游戏里显示乱码，所以必须用本模块。

用法
    import amr_font_codec as fc

    # 解出中文（读别人的汉化）
    zh = fc.decode('\\x10ÝO\\x11²b\\x10ýV')          # -> '保护国'

    # 编码中文（写自己的汉化）
    raw = fc.encode('保护国')                         # -> 可直接写进 .yml

    # 写文件
    fc.write_yml(r'D:\\path\\file_l_english.yml', {'KEY': '中文文本'})

    # 读文件
    d = fc.read_yml(r'D:\\path\\file_l_english.yml')

依赖
    charmap.json  （同目录，4349 个汉字的编码表）

兼容
    EU4 v1.37.x + 汉仪文黑字体 MOD。同一套编码也被
    Chinese Language Mod for 1.37 / 战争前夜汉化 / 青沼系列中文版 使用。
"""

import json
import os
import re
import sys

__all__ = ["decode", "encode", "load_charmap", "read_yml", "write_yml",
           "self_test", "CHARMAP", "missing_chars"]

_HERE = os.path.dirname(os.path.abspath(__file__))
CHARMAP_PATH = os.path.join(_HERE, "charmap.json")

# ---------------------------------------------------------------- 字节映射
# 文件本身是 UTF-8，但每个字节都先经过 CP1252 映射再写成 UTF-8。
# 0x84 -> '„' (U+201E)   0x8E -> 'Ž' (U+017D)   等等。


def to_byte(ch):
    """文件里的一个码位 -> 它代表的真实字节"""
    try:
        return ch.encode("cp1252")[0]
    except Exception:
        return ord(ch) & 0xFF


def from_byte(b):
    """真实字节 -> 写进文件时该用的码位"""
    try:
        return bytes([b]).decode("cp1252")
    except Exception:
        return chr(b)


# ---------------------------------------------------------------- 页基准
def page_base(page):
    """
    cp = (低字节 | 高字节 << 8) + page_base(page)

    页成对出现，偶数页是基准，奇数页 = 基准 - 0x0E：
        0x10 -> 0x0000      0x11 -> -0x000E
        0x12 -> +0x0900     0x13 -> +0x08F2
    实测四页对字库的命中率均为 100.0%。
    """
    n = page - 0x10
    return ((n >> 1) * 0x900) - ((n & 1) * 0x0E)


# ---------------------------------------------------------------- 编解码
def decode(text):
    """把汉化文件里的原始字符串解成中文。"""
    out, i, n = [], 0, len(text)
    while i < n:
        if 0x10 <= ord(text[i]) <= 0x13 and i + 2 < n:
            pg = to_byte(text[i])
            b1 = to_byte(text[i + 1])
            b2 = to_byte(text[i + 2])
            out.append(chr(((b1 | (b2 << 8)) + page_base(pg)) & 0xFFFF))
            i += 3
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


CHARMAP = {}
if os.path.exists(CHARMAP_PATH):
    with open(CHARMAP_PATH, encoding="utf-8") as f:
        _raw = json.load(f)
    # 支持两种存法：char -> [page,b1,b2]  或  char -> {"page":..,"b1":..,"b2":..}
    for k, v in _raw.items():
        if isinstance(v, dict):
            CHARMAP[k] = (v["page"], v["b1"], v["b2"])
        else:
            CHARMAP[k] = (v[0], v[1], v[2])


def missing_chars(text):
    """返回 text 里【字库表没有】的汉字（这些字无法安全编码）。"""
    return [c for c in text if "\u4e00" <= c <= "\u9fff" and c not in CHARMAP]


def encode(text, strict=False):
    """
    把中文编成可写进 .yml 的字符串。

    strict=True  -> 遇到字库表里没有的字就抛异常（推荐：宁可报错也别写乱码）
    strict=False -> 表里没有的字退回「页 0x10 直写」（v = 码位本身）。
                    这在理论上正确，但未经游戏实测，可能显示错字。
    """
    out = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            if ch in CHARMAP:
                pg, b1, b2 = CHARMAP[ch]
            elif strict:
                raise KeyError(f"字库表没有这个字：{ch} U+{ord(ch):04X}")
            else:
                pg, b1, b2 = 0x10, ord(ch) & 0xFF, ord(ch) >> 8
            out.append(from_byte(pg) + from_byte(b1) + from_byte(b2))
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------- yml 读写
_KEY = re.compile(r'^\s*([A-Za-z0-9_.\-]+)\s*:\s*\d*\s*"(.*)"\s*$')


def read_yml(path):
    """读一个 l_english.yml，返回 {key: 中文}（自动解码）。"""
    d = {}
    with open(path, "rb") as f:
        txt = f.read().decode("utf-8-sig", "replace")
    for line in txt.split("\n"):
        m = _KEY.match(line.rstrip("\r"))
        if m:
            d[m.group(1)] = decode(m.group(2))
    return d


def write_yml(path, entries, lang="l_english", bom=True):
    """
    写一个汉化 yml。entries 可以是 {key: 中文} 或 [(key, 中文), ...]（保序）。

    注意：汉化文件必须带 UTF-8 BOM，且语言槽要和游戏语言一致
          （游戏 settings.txt 里 language="l_english" 就写 l_english）。
    """
    items = entries.items() if isinstance(entries, dict) else entries
    lines = []
    for k, v in items:
        lines.append(f' {k}:0 "{encode(v)}"')
    body = "\n".join(lines) + "\n"
    data = (b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------- 自检
def self_test(verbose=True):
    """用已知样本验证编解码器。返回 True/False。"""
    cases = [
        ("保", 0x10, 0xDD, 0x4F),
        ("护", 0x11, 0xB2, 0x62),
        ("国", 0x10, 0xFD, 0x56),
        ("是", 0x11, 0x3D, 0x66),
        ("的", 0x10, 0x84, 0x76),
    ]
    ok = True
    for ch, pg, b1, b2 in cases:
        raw = from_byte(pg) + from_byte(b1) + from_byte(b2)
        got = decode(raw)
        good = got == ch
        ok &= good
        if verbose:
            print(f"  {'OK ' if good else 'FAIL'}  {ch}  U+{ord(ch):04X}  "
                  f"page=0x{pg:02X} bytes={b1:02X} {b2:02X}  decode -> {got}")
    # 往返
    if CHARMAP:
        sample = "".join(list(CHARMAP.keys())[:200])
        rt = decode(encode(sample))
        good = rt == sample
        ok &= good
        if verbose:
            print(f"  {'OK ' if good else 'FAIL'}  往返 200 字: {len(sample)} -> {len(rt)}")
    if verbose:
        print(f"  charmap: {len(CHARMAP)} 字")
        print("  结果:", "全部通过" if ok else "有失败")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    self_test()
