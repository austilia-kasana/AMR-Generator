"""AMR 生成器 · 存档体检 / 老档救援

check  <存档>    只看：这份存档对 mod 目录里每一份生成结果会掉多少件奇观
check            （不给路径就列出来让你挑，回车=主菜单【继续】里那个，a=全部）
rescue <存档>    看 + 把缺的键从订阅的 mod 里原文搬进来应急

原理：存档里每件奇观是按【定义里的键名】记账的（省份/等级/建成年份），
读档时引擎拿这本账和当前加载的定义对号 —— 账上有、定义里没有的那件会被
永久清掉。所以"老档能不能用"只看键集合盖不盖得住。

依赖：amr_env（目录/日志）、amr_script（括号与块解析）。
"""
import glob
import os
import re
import sys
import zipfile          # 存档有两种：zip（里面有 gamestate）和纯文本

from amr_env import CFGDIR, DOC, HERE, DIR_PREFIX, is_mine, mod_root
from amr_script import brace_close, find_blocks


# ============================================================ 存档体检 / 老档救援
# 存档里每件奇观是按【定义里的键名】记账的：
#     alhambra={ province=223  development_tier=0  date_built=1333.1.1 }
# 读档时引擎拿这本账去和【当前加载的定义】对号：账上有、定义里没有的那件就消失。
# 所以"老档能不能用"跟存档新老、玩了多久都无关，只看键集合盖不盖得住：
#   · 生成时的播放集 ⊇ 存档时的播放集 -> 安全（多出来的会按定义新建出来）
#   · 少开了某条 mod                   -> 那条 mod 的奇观被永久清掉
# check  = 把存档这本账和 mod 目录里每一份生成结果对一遍，不动任何文件
# rescue = 再进一步：把"缺的键"从本机订阅的 mod 里原文搬一份进去应急
_SAVE_BLOCK_RE = re.compile(r'(?m)^[ \t]*great_projects[ \t]*=[ \t]*\{')
_SAVE_KEY_RE = re.compile(r'(?m)^[ \t]*([A-Za-z0-9_.\-]+)[ \t]*=[ \t]*\{')
RESCUE_FILE = 'AMR_save_rescue.txt'


def _g1(pat, seg):
    m = re.search(pat, seg)
    return m.group(1) if m else '?'


def read_save_projects(path):
    """存档 -> {奇观键: (省份, 等级, 建成日期)}；读不了返回 (None, 出错信息)。
    存档有两种：zip（里面有 gamestate）和纯文本（EU4txt 开头），都要能读。"""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(2)
        if head == b'PK':
            with zipfile.ZipFile(path) as z:
                t = z.read('gamestate').decode('utf-8', 'ignore')
        else:
            t = open(path, encoding='utf-8', errors='ignore').read()
    except (OSError, zipfile.BadZipFile, KeyError, EOFError, ValueError) as e:
        return None, str(e)
    best = {}
    for m in _SAVE_BLOCK_RE.finditer(t):
        q = t.index('{', m.start())
        e = brace_close(t, q)
        if q < 0 or e < 0:
            continue
        inner = t[q + 1:e]
        # 省份里也有小块 great_projects（那件奇观在这个省），不是全局那本账
        if 'province' not in inner:
            continue
        d = {}
        for km in _SAVE_KEY_RE.finditer(inner):
            # 只看这一层的键：它前面的大括号必须是平衡的
            if inner[:km.start()].count('{') != inner[:km.start()].count('}'):
                continue
            q2 = inner.index('{', km.end() - 1)
            e2 = brace_close(inner, q2)
            seg = inner[q2 + 1:e2] if e2 > q2 else ''
            d[km.group(1)] = (_g1(r'province\s*=\s*(-?\d+)', seg),
                              _g1(r'development_tier\s*=\s*(-?\d+)', seg),
                              _g1(r'date_built\s*=\s*([0-9.]+)', seg))
        if len(d) > len(best):
            best = d
    return best, ''


def mod_gp_keys(dirpath):
    """某个 mod 目录里的奇观键 -> 它定义在哪个文件里。
    注意：【不过滤 type】：运河（type = canal）存档里也记账，算漏了会误报"会掉"。
    """
    out = {}
    gp = os.path.join(dirpath, 'common', 'great_projects')
    if not os.path.isdir(gp):
        return out
    for f in sorted(os.listdir(gp)):
        p = os.path.join(gp, f)
        if not (os.path.isfile(p) and f.lower().endswith('.txt')):
            continue
        t = open(p, 'rb').read().decode('latin-1', 'replace')
        for _n, _s, bo, bcl in find_blocks(t):
            out.setdefault(_n, p)
    return out


def local_gp_index():
    """本机所有【订阅/本地】mod 的奇观键 -> (mod 显示名, 定义文件)。
    用来回答"缺的这批是哪条 mod 的、现在没启用"。
    本工具自己生成的那几份（!AMR_ 开头）不算出处，否则会拿别份的美术资料来顶。
    另外返回一份【忽略大小写】的表：有些 mod 换过键名写法，档里是旧写法。"""
    idx, low = {}, {}
    for mf in sorted(glob.glob(os.path.join(DOC, 'mod', '*.mod'))):
        if os.path.basename(mf).startswith(DIR_PREFIX) or is_mine(mf):
            continue
        try:
            t = open(mf, encoding='utf-8-sig', errors='ignore').read()
        except OSError:
            continue
        mn = re.search(r'(?m)^[ \t]*name[ \t]*=[ \t]*"([^"]*)"', t)
        name = mn.group(1) if mn else os.path.basename(mf)
        root, _n2 = mod_root(mf)
        if not (root and os.path.isdir(root)):
            continue
        for k, p in mod_gp_keys(root).items():
            idx.setdefault(k, (name, p))
            low.setdefault(k.lower(), (name, p, k))
    return idx, low


def take_block(path, key):
    """从某个 mod 文件里把 key 那一段定义【连键名带注释】原文取出来。
    返回的是 latin-1 解出来的字符串 —— 原样写回去就是原来的字节（见下面的写文件）。"""
    try:
        t = open(path, 'rb').read().decode('latin-1', 'replace')
    except OSError:
        return ''
    for _n, _s, bo, bcl in find_blocks(t):
        if _n != key:
            continue
        # bo 是那个 { 的位置，键名在它前面那一行
        kstart = t.rfind('\n', 0, bo) + 1
        hstart = kstart
        for _ in range(4):          # 紧挨着的注释也一起带上
            if hstart <= 0:
                break
            prev = t.rfind('\n', 0, hstart - 1) + 1
            ln = t[prev:hstart]
            if ln.strip().startswith('#') or not ln.strip():
                hstart = prev
            else:
                break
        return t[hstart:bcl + 1].rstrip() + '\n'
    return ''


def _save_report_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return HERE


def _saves_by_time(limit=0):
    """save games 里的 .eu4，按修改时间从新到旧"""
    sg = os.path.join(DOC, 'save games')
    try:
        files = [f for f in os.listdir(sg) if f.lower().endswith('.eu4')]
    except OSError:
        return []
    files.sort(key=lambda f: os.path.getmtime(os.path.join(sg, f)), reverse=True)
    if limit:
        files = files[:limit]
    return [os.path.join(sg, f) for f in files]


def _continue_save():
    """主菜单/启动器上『继续』会读的那个存档。
    游戏自己把它记在文档目录的 continue_game.json 里（"filename": "save games/xx.eu4"）。"""
    p = os.path.join(DOC, 'continue_game.json')
    try:
        t = open(p, encoding='utf-8-sig', errors='ignore').read()
    except OSError:
        return ''
    m = re.search(r'"filename"\s*:\s*"([^"]+)"', t)
    if not m:
        return ''
    f = m.group(1).replace('/', os.sep)
    if os.path.isabs(f):
        return f if os.path.isfile(f) else ''
    cand = os.path.join(DOC, f)
    return cand if os.path.isfile(cand) else ''


def _pick_targets():
    """没给路径时列出来让用户挑。返回要体检的存档列表（可能好几个）。
    默认回车 = 『继续』里那个；a = 全部。"""
    saves = _saves_by_time(limit=12)
    cont = _continue_save()
    contname = os.path.basename(cont)
    if not saves:
        print('存档文件夹里一个 .eu4 都没有。')
        return []
    print('')
    print('要体检哪个存档？（『继续』= 主菜单上点继续会读的那个）')
    if contname:
        print('   直接回车 = 体检【继续】的那个：%s' % contname)
    print('   输入 a   = 把存档全部体检一遍（每份一行结论）')
    for _i, _f in enumerate(saves, 1):
        print('   %2d) %s%s' % (_i, os.path.basename(_f),
                                '   <- 继续' if _f == cont else ''))
    print('   0) 退出')
    print('')
    try:
        c = input('输入序号 / a / 直接回车：').strip()
    except (EOFError, KeyboardInterrupt):
        print('')
        return []
    if c == '0':
        return []
    if not c:
        if cont:
            return [cont]
        print('（没读到 continue_game.json，就用最新那个：%s）' % os.path.basename(saves[0]))
        return [saves[0]]
    if c.lower() in ('a', 'all', '全部'):
        return _saves_by_time()
    if not c.isdigit() or not (1 <= int(c) <= len(saves)):
        print('没看懂这个序号。')
        return []
    return [saves[int(c) - 1]]


_GPKEY_CACHE = {}


def _gp_keys_cached(d):
    """mod_gp_keys + 缓存：一次体检要拿同一份 mod 的键好几遍（每份存档一遍）"""
    try:
        mt = os.path.getmtime(os.path.join(d, 'common', 'great_projects'))
    except OSError:
        mt = 0
    hit = _GPKEY_CACHE.get(d)
    if hit and hit[0] == mt:
        return hit[1]
    ks = mod_gp_keys(d)
    _GPKEY_CACHE[d] = (mt, ks)
    return ks


def _scan_builds(proj):
    """把存档这本账和 mod 目录里每一份生成结果对一遍。
    返回 [[显示名, 目录, 键集合, 缺的键, 只是大小写不同的对], …]，按缺得少的排前面"""
    mdir = os.path.join(DOC, 'mod')
    builds = []
    for f in sorted(os.listdir(mdir)):
        d = os.path.join(mdir, f)
        if not (f.startswith(DIR_PREFIX) and os.path.isdir(d)):
            continue
        nm = f
        try:
            t = open(os.path.join(mdir, f + '.mod'), encoding='utf-8-sig',
                     errors='ignore').read()
            m = re.search(r'(?m)^[ \t]*name[ \t]*=[ \t]*"([^"]*)"', t)
            if m:
                nm = m.group(1)
        except OSError:
            pass
        ks = _gp_keys_cached(d)
        low = {}
        for k in ks:
            low.setdefault(k.lower(), k)
        caseonly = [(k, low[k.lower()]) for k in proj
                    if k not in ks and k.lower() in low]
        builds.append([nm, d, ks, [k for k in proj if k not in ks], caseonly])
    builds.sort(key=lambda b: (len(b[3]), b[0]))
    return builds


def _miss_sources(proj, builds, p, cap=0):
    """把"缺的那批"按出处分组打印出来（顺带返回分组结果）"""
    idx, lowidx = local_gp_index()

    def _find(k):
        hit = idx.get(k)
        if hit:
            return hit[0], hit[1], k
        h2 = lowidx.get(k.lower())
        if h2:
            return h2[0], h2[1], h2[2]
        return None, None, None

    by, orphan, src = {}, [], {}
    for k in builds[3]:
        nm, path, keyin = _find(k)
        if path:
            by.setdefault(nm, []).append(k)
            src[k] = (path, keyin)
        else:
            orphan.append(k)
    for nm, ks in sorted(by.items(), key=lambda x: -len(x[1])):
        p('    %-44s %4d 件（本机有，出处就是它）' % (nm[:42], len(ks)))
        p('        例：%s' % '、'.join(ks[:5]))
    if orphan:
        p('    %-44s %4d 件（本机找不到出处，多半是退订/删掉了）'
          % ('【已不在本机】', len(orphan)))
        p('        例：%s' % '、'.join(orphan[:5]))
    del cap
    return by, orphan, src


def save_check_all(targets):
    """一次把好几份存档都照一遍：每份一行结论，有问题的再展开说"""
    lines = []

    def p(s=''):
        lines.append(str(s))
        print(s)

    if not targets:
        p('存档文件夹里没有 .eu4。')
        _finish_save_report(lines)
        return 1
    p('一次体检 %d 份存档（结论按『会不会掉』排，有问题的排后面）' % len(targets))
    rows, bad = [], []
    for real in targets:
        proj, err = read_save_projects(real)
        if err:
            rows.append((os.path.basename(real), 0, '读不了：%s' % err))
            continue
        if not proj:
            rows.append((os.path.basename(real), 0, '档里还没奇观记录（刚开局？）'))
            continue
        builds = _scan_builds(proj)
        if not builds:
            rows.append((os.path.basename(real), len(proj), '还没有生成结果，先跑一次生成器'))
            continue
        b = builds[0]
        rows.append((os.path.basename(real), len(proj),
                     ('安全：勾【%s】' % b[0][:34]) if not b[3]
                     else '会掉 %d 件（最合适的是【%s】）' % (len(b[3]), b[0][:30])))
        if b[3]:
            bad.append((os.path.basename(real), b))
    p('')
    p('%-30s %6s  %s' % ('存档', '档内', '结论'))
    for nm, n, note in rows:
        p('%-30s %6d  %s' % (nm[:28], n, note))
    p('')
    if not bad:
        p('结论：每一份都能找到安全的那一份生成结果，放心开档。')
        _finish_save_report(lines)
        return 0
    p('下面这几份缺东西，展开说：')
    for nm, b in bad[:3]:
        p('')
        p('=== %s：最合适的是【%s】，缺 %d 件 ===' % (nm, b[0], len(b[3])))
        if b[4]:
            p('    其中 %d 件只是"大小写不一样"（那条 mod 换过写法）' % len(b[4]))
        _miss_sources(None, b, p)
        p('    → 把上面那些 mod 在启动器里勾上、重跑一次生成器，缺的就会回来。')
    if len(bad) > 3:
        p('')
        p('（还有 %d 份也有缺，就不一条条展开了：单独体检那一份会说得更细）'
          % (len(bad) - 3))
    p('')
    p('想把缺的那些先补上：单独体检那一份（再跑一次本工具，选它的序号），')
    p('提示里按 y 就会从你订阅的 mod 里把定义原文搬过来应急。')
    _finish_save_report(lines)
    return 2


def save_check(mode, savepath):
    """check / rescue 两个模式的全部实现（打完报告就 sys.exit）"""
    lines = []

    def p(s=''):
        lines.append(str(s))
        print(s)

    if not savepath:
        targets = _pick_targets()
        if not targets:
            print('没选存档，什么都没做。')
            return 3
        if len(targets) > 1:
            return save_check_all(targets)
        savepath = targets[0]

    # 路径容错：允许省略 .eu4，也允许只给文件名
    cand = [savepath, savepath + '.eu4',
            os.path.join(DOC, 'save games', savepath),
            os.path.join(DOC, 'save games', os.path.basename(savepath)),
            os.path.join(DOC, 'save games', os.path.basename(savepath) + '.eu4')]
    real = ''
    for c in cand:
        if c and os.path.isfile(c):
            real = c
            break
    if not real:
        p('找不到这个存档：%s' % savepath)
        p('把 .eu4 文件直接拖到 存档体检.bat 上就行。')
        _finish_save_report(lines)
        return 1

    proj, err = read_save_projects(real)
    if err:
        p('这个存档读不出来：%s' % err)
        _finish_save_report(lines)
        return 1
    p('存档：%s' % os.path.basename(real))
    if not proj:
        p('这个存档里一件奇观记录都没有（刚开局、还没到奇观出现的年份？）——')
        p('没有记录就没有对不上的东西，直接开档就行。')
        _finish_save_report(lines)
        return 0
    p('存档里记着 %d 件奇观（引擎是按【定义里的键名】记账的）' % len(proj))

    builds = _scan_builds(proj)
    if not builds:
        p('')
        p('mod 目录里还没有本工具生成的任何一份（!AMR_ 开头的文件夹）。')
        p('先跑一次 AMR_Generator.exe / 一键生成-源码版.bat 生成一份，再来体检。')
        _finish_save_report(lines)
        return 1

    builds.sort(key=lambda b: (len(b[3]), b[0]))
    p('')
    p('和 mod 目录里每一份生成结果对一遍：')
    for nm, d, ks, miss, co in builds:
        p('  %s' % nm)
        p('      定义 %d 件  ->  %s'
          % (len(ks), '安全：一件都不会掉' if not miss
             else '会掉 %d 件（缺定义）' % len(miss)))
    best = builds[0]
    p('')
    if not best[3]:
        p('结论：勾选【%s】开档是安全的。' % best[0])
        p('      （另外那几份是给别的播放集用的，勾错了才会掉奇观。）')
        _finish_save_report(lines)
        return 0

    if best[4]:
        p('其中 %d 件是【大小写不一样】：' % len(best[4]))
        for _a, _b in best[4][:8]:
            p('      存档写的是 %-34s 当前定义是 %s' % (_a, _b))
        p('      引擎把它们当两件不同的奇观，所以照样会掉 —— 这是那条 mod 换过写法')
        p('      （或换了版本）造成的，换回存档当时那个版本才能对上。')
        p('')

    p('最合适的一份是【%s】，但它缺 %d 件：' % (best[0], len(best[3])))
    by, orphan, src = _miss_sources(proj, best, p)
    p('')
    p('怎么办：把上面那些 mod 在启动器里勾上（并保持订阅），再重跑一次生成器，')
    p('        缺的就会回来。现在这样开档，那 %d 件会被永久清掉。' % len(best[3]))
    if best[4]:
        p('        其中那 %d 件"大小写不一样"的，勾上 mod 也救不回来（写法对不上），'
          % len(best[4]))
        p('        得换回存档当时那版 mod，或者用 rescue 把旧写法补回来。')

    if mode != 'rescue' and src:
        p('')
        p('要不要把缺的那些【原文搬运】过来，先让它们别消失？')
        p('  搬来的是原样定义（不能搬、加成按原条件），只当保命用；')
        p('  想彻底解决，还是把对应的 mod 在启动器里勾上、重跑一次生成器。')
        try:
            _ans = input('  补齐按 y 再回车，不补就直接回车：')
        except (EOFError, KeyboardInterrupt):
            _ans = ''
        if _ans.strip().lower() in ('y', 'yes', '1', '是', '好', '要'):
            mode = 'rescue'

    if mode == 'rescue' and src:
        dst = os.path.join(best[1], 'common', 'great_projects', RESCUE_FILE)
        got, lost = [], []
        for k in sorted(src):
            path, keyin = src[k]
            blk = take_block(path, keyin)
            if not blk:
                lost.append(k)
                continue
            if keyin != k:
                # 存档里是旧写法（大小写不同）：把块头改回存档认的键名，
                # 块里面那些引用（show_ambient_object 之类）不动。
                blk = re.sub(r'(?m)^([ \t]*)' + re.escape(keyin) + r'(?=[ \t]*=)',
                             lambda m: m.group(1) + k, blk, count=1)
            got.append((k, blk))
        lost += orphan
        if got:
            head = ('# 老档救援（AMR_save_rescue）\n'
                    '# 这些奇观键当前播放集里已经没有定义了，可你的存档还记着它们，\n'
                    '# 少了就会被引擎永久清掉。下面是从本机订阅的 mod 里【原文搬运】\n'
                    '# 过来的一份，只为让它们别消失。\n'
                    '# 注意：这些是原样搬来的，没套本 mod 的规则（不能搬、加成按原条件），\n'
                    '# 图标也来自那条 mod（它没启用时可能显示空白）。\n'
                    '# 想彻底解决：把对应的 mod 勾上，再重跑一次生成器；\n'
                    '# 重跑生成器会重建整个文件夹，本文件会被覆盖掉。\n'
                    '# 本次救援了 %d 件，名单：%s\n\n'
                    % (len(got), '、'.join(k for k, _b in got)))
            # 原文搬运：块内容是 latin-1 解出来的，写回去就是它原本的字节
            # （源文件是 UTF-8 的话，注释里的中文也跟着原样保留）。
            # 注意：不能走 write_text —— 它会把 latin-1 的字符串再编成 UTF-8，中文就变乱码。
            with open(dst, 'wb') as _fh:
                _fh.write(head.encode('utf-8'))
                for _k, _b in got:
                    _fh.write(_b.encode('latin-1', 'replace') + b'\r\n')
            p('')
            p('已救援：把 %d 件原文搬进了 %s' % (len(got), RESCUE_FILE))
            p('        位置：%s' % dst)
        if lost:
            p('救不了 %d 件（本机找不到定义，源 mod 已被删/退订）：%s'
              % (len(lost), '、'.join(lost[:8])))

    p('')
    _finish_save_report(lines)
    return 0 if not best[3] else 2


def _finish_save_report(lines):
    msg = '（这份报告也写进了 存档体检结果.txt，就在生成器文件夹里）'
    lines.append('')
    lines.append(msg)
    print(msg)
    txt = '\n'.join(lines)
    for _d in (_save_report_dir(), CFGDIR, HERE):
        try:
            open(os.path.join(_d, '存档体检结果.txt'), 'wb').write(
                txt.replace('\n', '\r\n').encode('utf-8'))
            break
        except OSError:
            continue
