"""AMR 生成器 · 环境与基础工具（generate.py 与 amr_saves.py 共用）

- 控制台编码、日志 report/log()、写文件 write_text()
- 目录定位：HERE / CFGDIR / DOC / TMP / VAN / WS（_cfg_path / _find_doc_dir / _steam_roots）
- mod 定位：DIR_PREFIX / MINE* / is_mine() / mod_root()

改这里的任何东西都要重新封包 exe，而且会影响所有模块。
"""
import os, re, sys


if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
for _s in ('stdout', 'stderr'):
    try:
        getattr(sys, _s).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
# exe 运行时 __file__ 指向临时解包目录（跑完就删），用户在那边放的 config.txt
# 读不到、写出来的 说明.txt 也会跟着消失。所以"用户能看见的那个目录"要单独算：
# 冻结成 exe 时 = exe 自己所在的目录；直接跑源码时 = 脚本所在目录。
CFGDIR = HERE
if getattr(sys, 'frozen', False):
    try:
        CFGDIR = os.path.dirname(os.path.abspath(sys.executable)) or HERE
    except Exception:
        CFGDIR = HERE
else:
    # 源码版：.py 现在放在子文件夹里（<工具文件夹>\源码（需要 Python）\），
    # 这时"用户看得见的那个目录"是它的上一层。靠 config.txt / exe 在哪一层来判断，
    # 所以子文件夹改什么名字都不影响。
    _up = os.path.dirname(HERE)
    if _up and not os.path.isfile(os.path.join(HERE, 'config.txt')):
        if (os.path.isfile(os.path.join(_up, 'config.txt'))
                or os.path.isfile(os.path.join(_up, 'AMR_Generator.exe'))):
            CFGDIR = _up


def _cfg_path():
    """用户在 config.txt 里写的开关/路径。优先取 exe（或脚本）旁边那份。"""
    for c in (os.path.join(CFGDIR, 'config.txt'), os.path.join(HERE, 'config.txt')):
        if os.path.isfile(c):
            return c
    return ''


# 万一中途抛异常：把已经攒下的日志 + traceback 也写到"看得见的目录"里，
# 这样用户能直接把 生成日志.txt 发给作者，而不是只看到一闪而过的报错。
def _dump_log_on_error(exc_type, exc, tb):
    import traceback
    _rep = globals().get('report') or []
    body = '\n'.join(_rep)
    body += '\n\n!!! 出错（把这份日志发给我）!!!\n'
    body += ''.join(traceback.format_exception(exc_type, exc, tb))
    for _d in (CFGDIR, HERE):
        try:
            with open(os.path.join(_d, '生成日志.txt'), 'w', encoding='utf-8') as _fh:
                _fh.write(body)
        except OSError:
            pass
    traceback.print_exception(exc_type, exc, tb)


sys.excepthook = _dump_log_on_error
# 中间的临时文件（补出来的 AMR_fill_*.txt）也放"看得见的目录"，别丢进源码子文件夹。
TMP = CFGDIR


def _find_doc_dir():
    """找出 EU4 的用户目录（mod 要写进它的 mod/ 下面）。

    以前是直接取脚本所在目录的上一级，但本工具要上传创意工坊 ——
    订阅后脚本会落在 Steam 的 workshop 目录里，那时上一级是错的，
    会把 mod 写到 steam 目录里。所以改成优先按用户目录去找，
    找不到再退回"脚本上一级"（也就是现在这种本地摆放方式）。"""
    cands = []
    env = os.environ.get('EU4_DOC_DIR')
    if env:
        cands.append(env)
    home = os.path.expanduser('~')
    for base in (os.path.join(home, 'Documents'), os.path.join(home, 'OneDrive', 'Documents'),
                 os.path.join(home, 'OneDrive', '文档'), os.path.join(home, '文档'),
                 os.path.join(home, '我的文档')):
        cands.append(os.path.join(base, 'Paradox Interactive', 'Europa Universalis IV'))
    cands.append(os.path.dirname(HERE))
    for c in cands:
        if not c or not os.path.isdir(os.path.join(c, 'mod')):
            continue
        if (os.path.exists(os.path.join(c, 'dlc_load.json'))
                or os.path.isdir(os.path.join(c, 'save games'))
                or os.path.exists(os.path.join(c, 'settings.txt'))):
            return c
    return os.path.dirname(HERE)


DOC = _find_doc_dir()                       # Europa Universalis IV 用户目录
def _steam_roots():
    """找 Steam 的 workshop 与游戏本体目录（可用同目录 config.txt 覆盖）"""
    found = {'ws': None, 'van': None}
    cfg = _cfg_path()
    if cfg:
        for ln in open(cfg, encoding='utf-8', errors='ignore'):
            ln = ln.strip()
            low = ln.lower()
            if low.startswith('workshop='):
                found['ws'] = ln.split('=', 1)[1].strip().strip('"').replace('/', os.sep)
            elif low.startswith('game='):
                found['van'] = ln.split('=', 1)[1].strip().strip('"').replace('/', os.sep)
    mods = os.path.join(DOC, 'mod')
    if os.path.isdir(mods):
        for f in sorted(os.listdir(mods)):
            if not f.lower().endswith('.mod'):
                continue
            try:
                t = open(os.path.join(mods, f), encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            # 必须锚定行首：.mod 里 replace_path="..." 也含 "path="，
            # 用宽松写法时会抓成 common/bookmarks 这种假路径，整个 mod 被跳过。
            m = re.search(r'(?m)^[ \t]*path[ \t]*=[ \t]*"([^"]+)"', t)
            if not m:
                continue
            p = m.group(1).replace('/', os.sep)
            if os.path.isabs(p) and 'workshop' in p.lower() and os.path.isdir(p):
                sa = p
                while os.path.basename(sa).lower() != 'steamapps' and os.path.dirname(sa) != sa:
                    sa = os.path.dirname(sa)
                found['ws'] = found['ws'] or os.path.join(sa, 'workshop')
                found['van'] = found['van'] or os.path.join(sa, 'common', 'Europa Universalis IV')
    for cand in (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam', r'D:\Steam',
                 r'D:\SteamLibrary', r'E:\Steam', r'E:\SteamLibrary', r'F:\SteamLibrary'):
        van = os.path.join(cand, 'steamapps', 'common', 'Europa Universalis IV')
        if not found['van'] and os.path.isdir(van):
            found['van'] = van
            found['ws'] = found['ws'] or os.path.join(cand, 'steamapps', 'workshop')
    return found


ROOTS = _steam_roots()
WS = os.path.join(ROOTS['ws'], 'content', '236850') if ROOTS['ws'] else ''
VAN = ROOTS['van'] or ''
report = []


def log(s=''):
    report.append(str(s))


# ------------------------------------------------------------------ helpers
def write_text(path, text, nl='\n', bom=False):
    """bom=True 时保证文件以【一个】UTF-8 BOM (EF BB BF) 开头。
    本地化 .yml 需要 BOM；但只能有一个 —— 两个 BOM 游戏会报
    "Invalid key name at line 1 and column 1"，整个文件都不生效。"""
    t = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', nl)
    if bom:
        while t[:1] == '\ufeff':
            t = t[1:]
        # 只靠 utf-8-sig 加 BOM，不要再手动拼一个，否则会有两个
        with open(path, 'wb') as fh:
            fh.write(t.encode('utf-8-sig'))
        return
    with open(path, 'wb') as fh:
        fh.write(t.encode('utf-8-sig' if bom else 'utf-8'))
MINE = {'all_monuments_relocatable', 'all_monuments_relocatable_generic'}
MINE_PREFIX = 'all_monuments_relocatable'
# 自己生成的东西用过的所有前缀（老的 all_monuments_relocatable_* + 现在的 !AMR_*）
MINE_PREFIXES = ('all_monuments_relocatable', '!AMR_', 'AMR_')


def is_mine(mf, root=None):
    """这个 mod 是不是本生成器自己生成的那一份（绝不能当成素材再吃一遍，
    否则每跑一次就会在自己上次的输出上再套一层，甚至把自己的输出删掉再崩）。
    注意：文件名/文件夹名曾经是 all_monuments_relocatable_*，后来改成 !AMR_*，
    两种都得认，否则用户把本 mod 勾上之后再来生成就会崩。"""
    for s in (os.path.splitext(os.path.basename(mf))[0],
              os.path.basename(os.path.normpath(root)) if root else ''):
        if not s:
            continue
        if s in MINE or s.startswith(MINE_PREFIXES) or '(Generator)' in s:
            return True
    return False


def mod_root(mf):
    try:
        t = open(os.path.join(DOC, mf.replace('/', os.sep)), encoding='utf-8', errors='ignore').read()
    except OSError:
        return None, '?'
    # 锚定行首：'replace_path="common/bookmarks"' 里也含 "path="，
    # 宽松匹配会把它当成 mod 目录，于是整个 mod 被静默跳过（漏掉它的全部奇观）。
    p = re.search(r'(?m)^[ \t]*path[ \t]*=[ \t]*"([^"]+)"', t)
    n = re.search(r'(?m)^[ \t]*name[ \t]*=[ \t]*"([^"]+)"', t)
    name = n.group(1) if n else '?'
    path = ''
    if p:
        path = p.group(1).replace('/', os.sep)
        if not os.path.isabs(path):
            for base in (DOC, WS):
                if base and os.path.isdir(os.path.join(base, path)):
                    path = os.path.join(base, path)
                    break
            else:
                path = os.path.join(DOC, path)
    if path and os.path.isdir(path):
        return path, name
    # 路径读不出来、或者指到不存在的地方：退回创意工坊，按 remote_file_id 定位。
    # 宁可绕一圈，也不要静默漏掉一个 mod 的全部奇观（旧 exe 就是这么翻车的）。
    r = re.search(r'(?m)^[ \t]*remote_file_id[ \t]*=[ \t]*"?([0-9]+)"?', t)
    if r and WS:
        cand = os.path.join(WS, r.group(1))
        if os.path.isdir(cand):
            return cand, name
    return (path or None), name
DIR_PREFIX = '!AMR_'
