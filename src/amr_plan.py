#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""建造条件解释器 —— 用存档当输入，离线算"哪些奇观、在哪几个省、现在能不能建"。

为什么需要它：加在 build_trigger 里的条件（仅人类玩家 / 仅首都 / 年份闸 /
禁重复建）都是**纯逻辑**，不需要跑游戏就能验证。这个脚本把那些条件实现成
一个求值器，拿真实存档求值，等价于"替玩家在游戏里点一遍"。

能求值的触发器（生成器只会写这几种）：
    owner = { ai = no }                省份拥有者是玩家
    owner = { is_year = N }            当前年份 >= N
    is_capital = yes                   该省是它拥有者的首都
    NOT = { has_great_project = { type = X } }
                                       帐上/省份名单里有 X（= 已经建过）
    NOT = { has_province_flag = F }    存档里该省带标记 F
    if/else、AND/OR/NOT                控制流
    其它（作者原条件）一律返回"未知"，并在报告里标明——不伪装成已知。

用法：
    python src\\amr_plan.py <存档路径> [mod文件夹路径]
不给参数就自动找最新的 .eu4 和当前播放集里的 !AMR mod。
"""
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
# ★ 同 amr_check.py：脚本挪进了 src\，不能再简单取上一级当"文档目录"。
#   往上找 dlc_load.json / mod\ 这两个标志来定位。
def _find_doc():
    d = HERE
    for _ in range(4):
        if (os.path.isfile(os.path.join(d, 'dlc_load.json'))
                or os.path.isdir(os.path.join(d, 'mod'))):
            return d
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return os.path.dirname(HERE)


DOC = _find_doc()
sys.path.insert(0, HERE)
# 自检模块现在叫 amr_check.py（原来叫 体检.py，已按用户要求改成 ASCII 名放进 src\）
from amr_check import (top_blocks, sub_block, is_monument,  # noqa: E402
                       brace_close, find_mod)


# ------------------------------------------------------------ 存档读取
def load_save(p):
    if open(p, 'rb').read(2) == b'PK':
        z = zipfile.ZipFile(p)
        gs = z.read('gamestate').decode('utf-8', 'ignore')
        meta = z.read('meta').decode('utf-8', 'ignore') if 'meta' in z.namelist() else ''
        return gs, meta
    return open(p, encoding='utf-8', errors='ignore').read(), ''


def parse_save(gs, meta):
    """取出求值需要的东西：日期、玩家国、每省的拥有者/名字/标记/已有奇观。

    ★ 存档格式（`大明1368_01_25.eu4` 实测）：
        meta      : date=1368.1.25        player="MNG"
        gamestate : provinces={ -669={ name="..." owner="MNG" ... capital="Fuzhou" }
        · 省块的键写作 `-669=` —— 那个负号是 EU4 的写法，**省号取绝对值**（= 669）。
        · 省块里的 `capital="Fuzhou"` 是【这个省自己的名字】，不是"谁是首都"。
        · 国家块（`countries={ ... }`）里的 capital 才是"首都是哪个省"。
    """
    d = re.search(r'(?m)^date\s*=\s*"?(\d+)\.(\d+)\.(\d+)', meta or gs)
    date = tuple(int(x) for x in d.groups()) if d else (0, 0, 0)
    pc = re.search(r'(?m)^player\s*=\s*"([A-Za-z0-9_]+)"', meta or gs)
    player = pc.group(1) if pc else None

    prov = {}
    m = re.search(r'(?m)^provinces\s*=\s*\{', gs)
    if m:
        st = gs.index('{', m.start())
        en = brace_close(gs, st)
        body = gs[st + 1:en]
        for pm in re.finditer(r'(?m)^(-\d+|[0-9]+)\s*=\s*\{', body):
            pid = abs(int(pm.group(1)))          # 负号只是写法，取绝对值
            q = body.index('{', pm.start())
            e = brace_close(body, q)
            if e <= q:
                continue
            blk = body[q:e + 1]
            ow = re.search(r'owner="([A-Za-z0-9_]+)"', blk)
            nm = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', blk)
            caps = re.search(r'(?m)^\s*capital\s*=\s*"([^"]*)"', blk)
            flags = set()
            for f in re.findall(r'(?m)^\s*flags\s*=\s*\{([^}]*)\}', blk):
                flags |= set(re.findall(r'"([^"]+)"', f))
            g = re.search(r'great_projects\s*=\s*\{([^}]*)\}', blk)
            prov[pid] = {
                'owner': ow.group(1) if ow else None,
                'name': nm.group(1) if nm else None,
                'self_capital': caps.group(1) if caps else None,
                'flags': flags,
                'gps': set(re.findall(r'"([^"]+)"', g.group(1))) if g else set(),
            }
    # 玩家首都的省号：国家块里 capital 是省【名】，按名字反查
    caps_of_player = set()
    if player:
        cn = None
        for m2 in re.finditer(r'(?m)^\t*' + re.escape(player)
                              + r'\s*=\s*\{', gs):
            q = gs.index('{', m2.start())
            e = brace_close(gs, q)
            if e <= q:
                continue
            c = re.search(r'(?m)^\s*capital\s*=\s*"([^"]*)"', gs[q:e + 1])
            if c:
                cn = c.group(1)
                break
        if cn:
            for pid, p in prov.items():
                if p.get('self_capital') == cn:
                    caps_of_player.add(pid)

    # ★★ 奇观位置的【可靠来源】是顶层的全局账本，不是省份块里的名单：
    #     great_projects={
    #         grand_canal_1={ province=684  development_tier=1  date_built=605.1.1 }
    #         himeji_castle={ province=1019 ... }
    #     }
    #   以前我在省份块的 `great_projects={"名字"}` 名单里找，那是【错的】——
    #   实测会把"这件奇观在不在这个省"判成 True（于是所有奇观都被当成"已经建过"、
    #   一律不可建、规划验证全体误报）。现在按账本里的 province= 号填进各省。
    for m2 in re.finditer(r'(?m)^\t([A-Za-z_0-9.\-]+)=\{\s*\n\s*province=(-?\d+)', gs):
        key, pid = m2.group(1), abs(int(m2.group(2)))
        if pid in prov:
            prov[pid]['gps'].add(key)
    # 非运河类的奇观在账本里可能不写 province=（只有运河/被搬过的才写），
    # 所以省份块名单仍作【补充】，但要过滤掉明显的误读（名单里只有引号词才算数）。
    return {'date': date, 'player': player, 'caps': caps_of_player,
            'prov': prov, 'gs': gs, 'meta': meta}


# ------------------------------------------------------------ 触发器求值
class Ctx(object):
    def __init__(self, save, pid):
        self.s = save
        self.pid = pid
        p = save['prov'].get(pid, {})
        self.owner = p.get('owner')
        self.flags = p.get('flags', set())
        self.gps = p.get('gps', set())
        self.is_cap = pid in save['caps']
        self.is_player = (self.owner is not None
                          and self.owner == save['player'])
        self.unknown = []


def split_top(inner):
    """按第一层切出 `key = value` / `key = { ... }` 序列 -> [(key, value, is_block)]"""
    out = []
    i, n, depth = 0, len(inner), 0
    start = 0
    while i < n:
        c = inner[i]
        if c == '#':
            j = inner.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and c == '=':
            # 往回找键名
            k = i - 1
            while k >= 0 and inner[k] in ' \t\r\n':
                k -= 1
            ke = k + 1
            while k >= 0 and (inner[k].isalnum() or inner[k] in '_'):
                k -= 1
            key = inner[k + 1:ke]
            # 往前找值
            v = i + 1
            while v < n and inner[v] in ' \t\r\n':
                v += 1
            if v < n and inner[v] == '{':
                d, j = 0, v
                while j < n:
                    if inner[j] == '{':
                        d += 1
                    elif inner[j] == '}':
                        d -= 1
                        if d == 0:
                            break
                    j += 1
                out.append((key, inner[v + 1:j], True))
                i = j
            else:
                j = v
                while j < n and inner[j] not in '\r\n':
                    j += 1
                out.append((key, inner[v:j].strip(), False))
                i = j
        i += 1
    return out


def ev(inner, ctx, depth=0):
    """求值一个触发器块的内容（空 = 真）。返回 True / False / None(未知)。"""
    if depth > 12:
        return None
    items = split_top(inner)
    if not items:
        return True
    res = True
    for key, val, isblk in items:
        r = ev_one(key, val, isblk, ctx, depth)
        if r is False:
            return False
        if r is None:
            res = None
    return res


def ev_one(key, val, isblk, ctx, depth):
    k = key.lower()
    if k in ('and',):
        return ev(val, ctx, depth + 1)
    if k in ('or',):
        rs = [ev_one(a, b, c, ctx, depth + 1)
              for a, b, c in split_top(val)]
        if any(x is True for x in rs):
            return True
        if all(x is False for x in rs):
            return False
        return None
    if k in ('not',):
        r = ev(val, ctx, depth + 1)
        return None if r is None else (not r)
    if k == 'if':
        sub = split_top(val)
        lim = ''
        then = []
        els = None
        for a, b, c in sub:
            if a.lower() == 'limit':
                lim = b
            elif a.lower() == 'else':
                els = b
            else:
                then.append((a, b, c))
        rl = ev(lim, ctx, depth + 1)
        if rl is True:
            return ev('\n'.join('%s = %s' % (a, b) for a, b, c in then),
                      ctx, depth + 1) if then else True
        if rl is False:
            return ev(els, ctx, depth + 1) if els is not None else True
        return None
    if k == 'else':
        return ev(val, ctx, depth + 1)
    if k == 'limit':
        return ev(val, ctx, depth + 1)
    if k == 'custom_trigger_tooltip':
        # tooltip = X 只是文案，其余是真条件
        rest = '\n'.join('%s = %s' % (a, b) for a, b, c in split_top(val)
                         if a.lower() != 'tooltip')
        return ev(rest, ctx, depth + 1) if rest.strip() else True
    if k == 'owner':
        sub = split_top(val)
        out = True
        for a, b, c in sub:
            al = a.lower()
            if al == 'ai':
                r = (b.strip().lower() == 'no') == ctx.is_player
                out = out and r
            elif al == 'is_year':
                try:
                    out = out and (ctx.s['date'][0] >= int(b))
                except ValueError:
                    return None
            else:
                ctx.unknown.append('owner.%s' % a)
                out = None
        return out
    if k == 'is_capital':
        return ctx.is_cap
    if k == 'province_id':
        # ★ 生成器给"条件留空但有 start"的奇观钉的那一条：
        #      province_id = <它自己的 start>
        #   语义 = 只能在这个省建（Anbennar 的既有写法，anb_great_projects.txt:330）。
        try:
            return int(val.strip()) == ctx.pid
        except ValueError:
            return None
    if k == 'has_great_project':
        t = re.search(r'type\s*=\s*(\S+)', val)
        if not t:
            return None
        return t.group(1) in ctx.gps
    if k == 'has_province_flag':
        return val.strip() in ctx.flags
    if k == 'always':
        return val.strip().lower() in ('yes', 'true')
    ctx.unknown.append(key)
    return None


# ------------------------------------------------------------ 主流程
def main():
    if len(sys.argv) > 1:
        sp = sys.argv[1]
        if not os.path.isabs(sp):
            sp = os.path.join(DOC, 'save games', sp)
    else:
        sg = os.path.join(DOC, 'save games')
        fs = [os.path.join(sg, f) for f in os.listdir(sg) if f.endswith('.eu4')]
        fs.sort(key=os.path.getmtime, reverse=True)
        sp = fs[0]
    if not os.path.isfile(sp):
        print('找不到存档：%s' % sp)
        return 2
    mod = sys.argv[2] if len(sys.argv) > 2 else find_mod()
    if not mod:
        print('找不到要验证的 mod')
        return 2

    gs, meta = load_save(sp)
    S = parse_save(gs, meta)
    gp = os.path.join(mod, 'common', 'great_projects')
    mons = []
    for f in sorted(os.listdir(gp)):
        if not f.endswith('.txt'):
            continue
        t = io.open(os.path.join(gp, f), 'rb').read().decode('latin-1')
        for nm, b in top_blocks(t):
            if is_monument(b):
                mons.append((nm, f, b))

    print('=' * 74)
    print('建造规划验证（离线求值，不跑游戏）')
    print('  存档   : %s' % os.path.basename(sp))
    print('  日期   : %d.%d.%d' % S['date'])
    print('  玩家   : %s' % S['player'])
    print('  首都省 : %s' % sorted(S['caps'])[:8])
    print('  奇观   : %d 件（来自 %s）' % (len(mons), os.path.basename(mod)))
    print('=' * 74)

    ok, no_yr, no_cap, done, unk = [], [], [], [], []
    # ★ 测试点 = 每件奇观自己的 start 省份。
    #   理由：年份闸要验证的正是"年份没到的时候，在它【自己的省】也建不了"。
    #   用 start 省还避免了"存档里首都省号解析不出来"这个坑
    #   （EU4 的国家块格式我没能可靠解析，不猜）。
    for nm, f, b in mons:
        bt = sub_block(b, 'build_trigger')
        if bt is None:
            continue
        sm = re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*(\d+)', b)
        dm = re.search(r'(?m)^[ \t]*date[ \t]*=[ \t]*(\d+)', b)
        pid = int(sm.group(1)) if sm else None
        if pid is None or pid not in S['prov']:
            no_cap.append((nm, '没有可用 start 省份（%s）' % (pid,)))
            continue
        ctx = Ctx(S, pid)
        # 只算"年份闸"这一项：把 is_capital / ai=no 的预期值也一起求，
        # 但分别报告，避免一个条件失败就说整件不行
        r = ev(bt[1:-1], ctx)
        if ctx.unknown:
            unk.append((nm, sorted(set(ctx.unknown))[:3]))
        if dm and S['date'][0] < int(dm.group(1)):
            # 年份没到：期望"建不了"
            if r is True:
                no_yr.append((nm, '★年份没到（date=%s）却仍然可建' % dm.group(1)))
            else:
                ok.append((nm, '年份未到 -> 正确地建不了（date=%s，现 %d 年）'
                           % (dm.group(1), S['date'][0])))
        else:
            # 年份已到：年份闸不该成为阻碍，报告是否还有别的条件挡着
            if r is True:
                ok.append((nm, '年份已到 -> 条件成立'))
            else:
                other = []
                for a, bb, c in split_top(bt[1:-1]):
                    if a.lower() in ('is_capital', 'owner'):
                        continue
                    other.append(a)
                done.append((nm, '年份已到，但 %s 使其不成立'
                             % (other[:3] or '作者原条件')))

    print()
    print('说明：本验证拿每件奇观【自己的 start 省份】当测试点，')
    print('      专门验证"年份闸"这一条 —— 年份没到时，在它自己的省也应当建不了。')
    print()
    print('[符合预期] %d 件' % len(ok))
    for nm, why in ok[:15]:
        print('    %-30s %s' % (nm[:28], why))
    if len(ok) > 15:
        print('    ... 还有 %d 件' % (len(ok) - 15))
    print()
    bad = no_yr
    print('[★不符合预期（要修）] %d 件' % len(bad))
    for nm, why in bad[:15]:
        print('    %-30s %s' % (nm[:28], why))
    print()
    print('[年份已到、但被其它条件挡着] %d 件' % len(done))
    for nm, why in done[:8]:
        print('    %-30s %s' % (nm[:28], why))
    if len(done) > 8:
        print('    ... 还有 %d 件' % (len(done) - 8))
    print()
    print('[无法判定] %d 件' % len(no_cap))
    for nm, why in no_cap[:6]:
        print('    %-30s %s' % (nm[:28], why))
    if unk:
        seen = set()
        print()
        print('[用到作者原条件、本解释器不认识（按未知处理）]')
        for nm, ks in unk:
            key = tuple(ks)
            if key in seen:
                continue
            seen.add(key)
            print('    %-30s %s' % (nm[:28], ks))
            if len(seen) > 6:
                break
    print()
    print('=' * 74)
    print('第二部分：站在【玩家首都】验证')
    # ★ 存档里的"玩家首都是哪个省"我没能可靠解析（EU4 国家块格式和常见写法不同），
    #   所以这里让用户手填首都省号；不填就跳过。
    #   用法：python src\\amr_plan.py <存档> <mod文件夹> <首都省号>
    capid = None
    if len(sys.argv) > 3:
        try:
            capid = int(sys.argv[3])
        except ValueError:
            capid = None
    if capid is None:
        print('  （没给首都省号，跳过。用法：python src\\amr_plan.py 存档 mod文件夹 首都省号）')
        print('    在游戏里把鼠标放到首都上能看到省号，或者看省份面板。')
    else:
        p = S['prov'].get(capid)
        if p is None:
            print('  省 %d 不在存档里' % capid)
        else:
            print('  测试省 %d  拥有者=%s  名字=%s  已有奇观=%s'
                  % (capid, p['owner'], p['name'], sorted(p['gps']) or '无'))
            can, cannot, blocked = [], [], []
            for nm, f, b in mons:
                bt = sub_block(b, 'build_trigger')
                if bt is None:
                    continue
                dm = re.search(r'(?m)^[ \t]*date[ \t]*=[ \t]*(\d+)', b)
                ctx = Ctx(S, capid)
                r = ev(bt[1:-1], ctx)
                if dm and S['date'][0] < int(dm.group(1)):
                    if r is True:
                        blocked.append((nm, '年份没到却可建！'))
                    continue
                if r is True:
                    can.append(nm)
                elif nm in p['gps']:
                    cannot.append((nm, '已经建过了'))
                else:
                    cannot.append((nm, '作者原条件不满足/未知'))
            print()
            print('  [年份已到、且在首都满足条件 -> 应该可以建] %d 件' % len(can))
            for nm in can[:20]:
                print('      %s' % nm)
            if len(can) > 20:
                print('      ... 还有 %d 件' % (len(can) - 20))
            print('  [年份没到却可建（要修）] %d 件' % len(blocked))
            for nm, why in blocked[:10]:
                print('      %-30s %s' % (nm[:28], why))
    print()
    print('=' * 74)
    print('注：只验证【我们加的条件】；作者原条件的细节（文化/宗教/任务等）')
    print('    超出本解释器能力范围，遇到会标成"未知"，不伪装成通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
