"""AMR 生成器 · 播放集与素材扫描

找生成器自己的文件夹、读播放集、定位每个 mod 的 common/great_projects、
判断"接管目录"的 mod、原版奇观键表（白名单的来源）、地图 mod 的省份号比对。
"""

import collections
import glob
import json
import os
import re
import shutil

from amr_env import (CFGDIR, DOC, HERE, TMP, VAN, WS, DIR_PREFIX, log, report,
                     write_text, is_mine, mod_root)
from amr_script import *
from amr_script import _clean, _leaked_at
from amr_state import SOURCES, GP_TAKEOVER, MOD_GP_FILES, SKIPPED_MODS, SUBS, VAN_GP


# ---------------------------------------------------------------- 定位标记
# 一件奇观如果"没有 start、靠省份标记/修正定位"，而那个标记在整个播放集里
# 根本没人应用，它就注定不会出现在地图上（原神那几个就是这样）。
# 解锁模式要救它们，得先确认这一点，才敢把作者注释掉的 #start 恢复回去。
_APPLIED = None           # 播放集里被应用的 has_province_* 标记（一次扫描，缓存）
_MAPIDS = None            # 当前地图的合法省份号（缓存）


def _playset_text_roots():
    """本次播放集里各 mod 的根目录（从奇观文件反推）"""
    roots, seen = [], set()
    for files in MOD_GP_FILES.values():
        for path in files.values():
            p = os.path.abspath(path)
            i = p.lower().find(os.sep + 'common' + os.sep)
            if i > 0:
                r = p[:i]
                if r.lower() not in seen:
                    seen.add(r.lower())
                    roots.append(r)
            break
    if VAN and VAN.lower() not in seen:
        roots.append(VAN)
    return roots


def applied_markers():
    """扫一遍播放集的脚本类目录，收集所有被引用的 has_province_*(标记)。
    跳过 common/great_projects 自己 —— 奇观定义里的引用不算"有人应用它"。"""
    global _APPLIED
    if _APPLIED is not None:
        return _APPLIED
    out = set()
    pat = re.compile(r'(?m)^[ \t]*has_province_(?:modifier|flag|trigger)[ \t]*='
                     r'[ \t]*([A-Za-z0-9_.\-]+)')
    for root in _playset_text_roots():
        for sub in ('common', 'events', 'decisions', 'history', 'missions'):
            d = os.path.join(root, sub)
            if not os.path.isdir(d):
                continue
            for dp, dn, fn in os.walk(d):
                if os.path.normcase(os.path.basename(dp)) == 'great_projects':
                    dn[:] = []          # 奇观定义自己不算
                    continue
                for f in fn:
                    if not f.lower().endswith('.txt'):
                        continue
                    try:
                        t = open(os.path.join(dp, f), encoding='utf-8',
                                 errors='ignore').read()
                    except OSError:
                        continue
                    out.update(pat.findall(t))
    _APPLIED = out
    log('  定位标记 : 播放集里被应用的 has_province_* 标记 %d 个' % len(out))
    return out


def map_province_ids():
    """当前地图上真实存在的省份号（读原版 map/definition.csv；读不到就不限制）"""
    global _MAPIDS
    if _MAPIDS is not None:
        return _MAPIDS
    ids = set()
    if VAN:
        p = os.path.join(VAN, 'map', 'definition.csv')
        if os.path.isfile(p):
            try:
                for ln in open(p, encoding='utf-8', errors='ignore'):
                    c = ln.split(';')
                    if c and c[0].strip().isdigit():
                        ids.add(c[0].strip())
            except OSError:
                pass
    _MAPIDS = ids
    return ids


def _find_tool_folder():
    """生成器自己的上传包文件夹名。用户可能给它改过名（比如换成中文品牌名），
    所以按 descriptor.mod 里带 (Generator) 来认；认不到就用默认名。"""
    d = os.path.join(DOC, 'mod')
    # ★ 优先认 ASCII 安全名。原名含 `&` 和空格，Steam 的工坊上传工具把
    #   contentfolder 当命令行参数传，`&` 会被 cmd 当命令分隔符 -> 报
    #   「参数不正确」。所以上传包文件夹固定用 AMR_Generator。
    if os.path.isdir(os.path.join(d, 'AMR_Generator')):
        return 'AMR_Generator'
    try:
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            dm = os.path.join(p, 'descriptor.mod')
            if os.path.isdir(p) and os.path.isfile(dm):
                try:
                    if '(Generator)' in open(dm, encoding='utf-8', errors='ignore').read():
                        return f
                except OSError:
                    pass
    except OSError:
        pass
    return 'AMR_generator'


def active_playset():
    """当前启动器里激活的播放集名字。读不到就返回空串（不影响其它功能）。"""
    db = os.path.join(DOC, 'launcher-v2.sqlite')
    if not os.path.isfile(db):
        return ''
    try:
        import sqlite3
        from pathlib import Path
        con = sqlite3.connect(Path(db).as_uri() + '?mode=ro', uri=True)
        row = con.execute('SELECT name FROM playsets WHERE isActive=1').fetchone()
        con.close()
        return (row[0] or '').strip() if row and row[0] else ''
    except Exception:
        return ''


def active_playset_enabled_count():
    """启动器数据库里，当前激活的播放集【已启用】了几个 mod。读不到返回 None。
    用来和 dlc_load.json 里的列表对一下：切换播放集后如果没先启动过一次游戏，
    脚本读到的还是上一次的列表，那这次的素材就取错了。"""
    db = os.path.join(DOC, 'launcher-v2.sqlite')
    if not os.path.isfile(db):
        return None
    try:
        import sqlite3
        from pathlib import Path
        con = sqlite3.connect(Path(db).as_uri() + '?mode=ro', uri=True)
        row = con.execute('SELECT id FROM playsets WHERE isActive=1').fetchone()
        if not row:
            con.close()
            return None
        n = con.execute('SELECT COUNT(*) FROM playsets_mods WHERE playsetId=? AND enabled=1',
                        (row[0],)).fetchone()[0]
        con.close()
        return int(n)
    except Exception:
        return None


def playset_slug(name):
    """把播放集名字变成能安全当文件夹后缀的串（中文名会退化成 p+校验码）"""
    s = re.sub(r'[^0-9A-Za-z_-]+', '_', name).strip('_')[:20]
    if s:
        return s
    import zlib
    return 'p%08x' % (zlib.crc32(name.encode('utf-8')) & 0xffffffff)



def strip_comment_braces(text):
    """游戏把 # 注释里的 { } 也当括号，会把后面的定义整块带歪 -> 换成 ( )"""
    out, n = [], 0
    for ln in text.split('\n'):
        in_str, cut = False, -1
        for i, ch in enumerate(ln):
            if ch == '"':
                in_str = not in_str
            elif ch == '#' and not in_str:
                cut = i
                break
        if cut < 0:
            out.append(ln)
            continue
        tail = ln[cut:]
        if '{' in tail or '}' in tail:
            n += tail.count('{') + tail.count('}')
            tail = tail.replace('{', '(').replace('}', ')')
        out.append(ln[:cut] + tail)
    return '\n'.join(out), n

def mod_replace_paths(mf):
    """读 .mod 里的 replace_path="..." 列表（相对游戏根目录、正斜杠、小写）。

    这个很关键：只要有一个启用的 mod 声明 replace_path="common/great_projects"，
    原版那个目录就被它整个顶掉（原版的奇观在游戏里根本不存在）。本 mod 自己
    也声明了 replace_path，所以必须把那个 mod 的奇观文件【一个不少】带上，
    少一个文件它那份奇观就一个都不会出现。"""
    out = set()
    try:
        t = open(os.path.join(DOC, mf.replace('/', os.sep)),
                 encoding='utf-8', errors='ignore').read()
    except OSError:
        return out
    for m in re.finditer(r'(?m)^[ \t]*replace_path[ \t]*=[ \t]*"([^"]+)"', t):
        out.add(m.group(1).replace('\\', '/').strip().strip('/').lower())
    return out

def collect_known_keys():
    """从游戏本体自带的奇观文件里补齐合法键（拿不到就用上面的兜底清单）"""
    if not VAN:
        return
    base = os.path.join(VAN, 'common', 'great_projects')
    if not os.path.isdir(base):
        return
    for f in os.listdir(base):
        if not f.lower().endswith('.txt'):
            continue
        t = open(os.path.join(base, f), 'rb').read().decode('latin-1', 'ignore')
        for m in re.finditer(r'(?m)^([a-zA-Z_0-9._\-]+)[ \t]*=[ \t]*\{', t):
            j = t.index('{', m.start())
            bc = brace_close(t, j)
            blk = t[j:bc + 1]
            if not re.search(r'(?m)^\s*type\s*=\s*monument\s*$', blk):
                continue
            depth = 0
            for ln in blk.split('\n'):
                code = _clean(ln)
                if depth == 1:
                    m2 = re.match(r'[\t ]*([a-zA-Z_0-9.\-]+)[ \t]*=', ln)
                    if m2:
                        KNOWN_KEYS.add(m2.group(1))
                depth += code.count('{') - code.count('}')

def _is_map_mod(root):
    for rel in (('map', 'definition.csv'), ('map', 'provinces.bmp'), ('map', 'terrain')):
        if os.path.exists(os.path.join(root, *rel)):
            return True
    return False


def _starts_in(root):
    """{奇观键: start 省份号}"""
    gp = os.path.join(root, 'common', 'great_projects')
    out = {}
    if not os.path.isdir(gp):
        return out
    for f in sorted(os.listdir(gp)):
        p = os.path.join(gp, f)
        if not (os.path.isfile(p) and f.lower().endswith('.txt')):
            continue
        t = open(p, 'rb').read().decode('latin-1', 'replace')
        for _n, _s, bo, bcl in find_blocks(t):
            b = t[bo:bcl + 1]
            if not is_monument(b):
                continue
            st = re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*([0-9]+)', b)
            if st:
                out[_n] = st.group(1)
    return out
