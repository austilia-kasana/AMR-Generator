#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AMR 奇观 mod 自动体检 —— 一条命令查完所有该有的规则。

用法（在 奇观mod生成器 目录下）：
    python src\\amr_check.py          # 自动读当前播放集里启用的 AMR mod
    python src\\amr_check.py <mod文件夹路径>   # 或者指定一个

它查的是【生成结果】而不是源码，也就是你真正会拿去玩的那份文件。
每一条都打印 通过/不通过，最后给总结。不通过会指出具体是哪件奇观。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# ★ 2026-10-04：这个脚本从"生成器根目录"挪进了 src\（用户要求根目录只留
#   双击能用的东西），所以"文档目录"不能再简单取上一级 —— 从 src\ 上一级
#   拿到的是【工具文件夹】。这里往上找出真正的文档目录：认 dlc_load.json
#   和 mod\ 这两个标志，两种摆法（根目录 / src\）都能对上。
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
# config.txt 是用户级设置，先在工具文件夹（DOC\奇观mod生成器）找，
# 再退回脚本自己所在目录，最后退回 DOC。
_CFG_CANDS = [
    os.path.join(DOC, '奇观mod生成器', 'config.txt'),
    os.path.join(os.path.dirname(HERE), 'config.txt'),
    os.path.join(HERE, 'config.txt'),
    os.path.join(DOC, 'config.txt'),
]
CFG = next((p for p in _CFG_CANDS if os.path.isfile(p)), _CFG_CANDS[0])

GREEN, RED, DIM, END = '\033[32m', '\033[31m', '\033[2m', '\033[0m'
if os.name == 'nt' and not os.environ.get('WT_SESSION'):
    GREEN = RED = DIM = END = ''


# ---------------------------------------------------------------- 基础工具
def brace_close(s, i):
    """s[i] 是 '{'，返回配对 '}' 的下标；不配对返回 -1。注释/字符串跳过。"""
    d, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '#':
            j = s.find('\n', i)
            if j < 0:
                return -1
            i = j
        elif c == '"':
            j = s.find('"', i + 1)
            if j > 0:
                i = j
        elif c == '{':
            d += 1
        elif c == '}':
            d -= 1
            if d == 0:
                return i
        i += 1
    return -1


def top_blocks(text):
    """所有顶层 `name = { ... }` -> [(名字, 块文本)]"""
    out = []
    for m in re.finditer(r'(?m)^([A-Za-z_0-9.\-]+)[ \t]*=[ \t]*\{', text):
        q = text.index('{', m.start())
        e = brace_close(text, q)
        if e > q:
            out.append((m.group(1), text[q:e + 1]))
    return out


def sub_block(b, key):
    """块 b 里第一层的 `key = { ... }` 内容（不含花括号）；没有返回 None。"""
    for m in re.finditer(r'(?m)^\t' + re.escape(key) + r'[ \t]*=[ \t]*\{', b):
        q = b.index('{', m.start())
        e = brace_close(b, q)
        if e > q:
            return b[q:e + 1]
    return None


def val_of(b, key):
    m = re.search(r'(?m)^[ \t]*' + re.escape(key) + r'[ \t]*=[ \t]*(\S+)', b)
    return m.group(1) if m else None


def is_monument(b):
    return re.search(r'(?m)^\s*type\s*=\s*monument\s*$', b) is not None


def enabled_mods():
    """当前播放集里启用的 mod 文件夹绝对路径列表。"""
    p = os.path.join(DOC, 'dlc_load.json')
    if not os.path.isfile(p):
        return []
    try:
        cur = json.load(io.open(p, encoding='utf-8'))['enabled_mods']
    except Exception:
        return []
    out = []
    for m in cur:
        rel = m.replace('/', os.sep)
        if rel.endswith('.mod'):
            rel = rel[:-4]
        d = os.path.join(DOC, rel)
        if os.path.isdir(d):
            out.append(d)
    return out


def _dlc_loads():
    """可能放着 dlc_load.json 的目录，按优先级排列。

    ★ 工具包自己就躺在 mod\\ 里（mod\\全奇观解锁并搬迁…(Generator)\\），所以
      "往上找文档目录"会先撞上 mod\\ 这一层；生成结果又在 文档\\mod\\ 下面。
      这里把两种可能都列出来，逐个试。
    """
    cands = [DOC, os.path.dirname(DOC), os.path.dirname(os.path.dirname(DOC))]
    # 也能显式给：AMR_DOC 环境变量
    env = os.environ.get('AMR_DOC')
    if env:
        cands.insert(0, env)
    out = []
    for d in cands:
        if d and os.path.isdir(d) and d not in out:
            out.append(d)
    return out


def _mod_dir_under(base, rel):
    """在 base 和 base\\mod 下面找 rel 指向的文件夹"""
    for b in (base, os.path.join(base, 'mod')):
        d = os.path.join(b, rel)
        if os.path.isdir(d):
            return d
    return None


def find_mod():
    """优先命令行参数；否则从 dlc_load.json 里找启用的 !AMR_* mod。"""
    if len(sys.argv) > 1:
        p = sys.argv[1]
        return p if os.path.isdir(p) else None
    for base in _dlc_loads():
        p = os.path.join(base, 'dlc_load.json')
        if not os.path.isfile(p):
            continue
        try:
            cur = json.load(io.open(p, encoding='utf-8'))['enabled_mods']
        except Exception:
            continue
        for m in cur:
            rel = m.replace('/', os.sep)
            if '.mod' in rel:
                rel = rel[:-4]
            if not os.path.basename(rel).startswith('!AMR'):
                continue
            d = _mod_dir_under(base, rel)
            if d:
                return d
    # 最后的兜底：扫 !AMR* 文件夹，取【修改时间最新】的那个。
    # ★ 原来取名字排序第一个，会选到几个月前的旧产物（实测选到 9/26 的
    #   Anbennar 旧版），体检结果全是误报。
    cands = []
    for base in _dlc_loads():
        for b in (os.path.join(base, 'mod'), base):
            if not os.path.isdir(b):
                continue
            for n in os.listdir(b):
                p = os.path.join(b, n)
                if not (n.startswith('!AMR') and os.path.isdir(p)):
                    continue
                mt = 0.0
                try:
                    mt = os.path.getmtime(p)
                    for dp, _dn, fs in os.walk(p):
                        for f in fs:
                            mt = max(mt, os.path.getmtime(os.path.join(dp, f)))
                except OSError:
                    pass
                cands.append((mt, p))
    if cands:
        cands.sort(key=lambda x: -x[0])
        return cands[0][1]
    return None


# ---------------------------------------------------------------- 体检项
def run(moddir):
    gp = os.path.join(moddir, 'common', 'great_projects')
    if not os.path.isdir(gp):
        print('%s找不到奇观目录：%s%s' % (RED, gp, END))
        return 2
    files = sorted(f for f in os.listdir(gp) if f.endswith('.txt'))
    mons = []
    for f in files:
        t = io.open(os.path.join(gp, f), 'rb').read().decode('latin-1')
        for nm, b in top_blocks(t):
            if is_monument(b):
                mons.append((nm, f, b))
    cfg = io.open(CFG, encoding='utf-8', errors='ignore').read() \
        if os.path.isfile(CFG) else ''

    print('=' * 74)
    print('AMR 奇观 mod 体检')
    print('  mod  : %s' % os.path.basename(moddir))
    print('  文件 : %d 个，奇观 %d 件' % (len(files), len(mons)))
    print('=' * 74)
    if not mons:
        print('%s没有解析到任何奇观%s' % (RED, END))
        return 2

    fails = []

    def check(title, bad, extra=''):
        if bad:
            fails.append(title)
            print('%s[不通过]%s %s  (%d 件)%s'
                  % (RED, END, title, len(bad), extra))
            for x in bad[:6]:
                print('        - %s' % x)
            if len(bad) > 6:
                print('        ... 还有 %d 件' % (len(bad) - 6))
        else:
            print('%s[通过]%s %s' % (GREEN, END, title))

    # ① 建造条件：玩家分支仅人类玩家；AI 分支必须【能成立】
    #    ★ 2026-10-04 用户定案：「你就不能直接 ifelse 区分开来吗」
    #      结构应该是：
    #        build_trigger = {
    #            if   = { limit = { owner = { ai = no } }  <玩家规则> }
    #            else = { <AI 走作者原条件> }
    #        }
    #      ★ 特别要盯：AI 分支里【不能】残留 `owner = { ai = no }`
    #        —— 带着它 AI 分支永远不成立（等于把 AI 的建造堵死，那是错的）。
    no_human, no_cap, no_bt, bad_cap, ai_dead, no_split = [], [], [], [], [], []
    for nm, f, b in mons:
        bt = sub_block(b, 'build_trigger')
        if bt is None:
            no_bt.append('%s (%s)' % (nm, f))
            continue
        if not re.search(r'owner\s*=\s*\{\s*ai\s*=\s*no', bt):
            no_human.append('%s (%s)' % (nm, f))
        has_cap = re.search(r'(?m)^[ \t]*is_capital\s*=\s*yes', bt) is not None
        has_start = re.search(r'(?m)^[ \t]*start[ \t]*=\s*\d+', b) is not None
        if not has_start and not has_cap:
            no_cap.append('%s (%s) 没有 start 却也没限制在首都' % (nm, f))
        if has_start and has_cap:
            bad_cap.append('%s (%s) 有 start 却被限制在首都（不应有）' % (nm, f))
        # AI 分支检查
        m_else = re.search(r'(?m)^[ \t]*else[ \t]*=[ \t]*\{', bt)
        if not m_else:
            # ★ 例外：start 写成 event_target 之类非法值的奇观，生成器会把它
            #   【重定向到首都】并新建 build_trigger（仅首都 + 仅玩家 + 年份闸
            #   + 禁重复）。那种本来就不该做 if/else 拆分，不要误报。
            if not has_cap:
                no_split.append('%s (%s) 没有 if/else 拆分' % (nm, f))
        else:
            q2 = bt.index('{', m_else.start())
            e2 = brace_close(bt, q2)
            if e2 > q2:
                seg = bt[q2:e2 + 1]
                if re.search(r'owner\s*=\s*\{\s*ai\s*=\s*no', seg):
                    ai_dead.append('%s (%s) AI 分支里残留 ai = no（AI 会永远建不了）'
                                   % (nm, f))
    check('建造条件含 owner = { ai = no }（玩家分支）', no_human)
    check('AI 分支里没有残留 ai = no（AI 仍能自己建）', ai_dead)
    check('每件奇观的建造条件都做了 if/else 拆分', no_split)
    check('没有 start 的奇观限制在首都（is_capital = yes）', no_cap)
    check('有 start 的奇观【没有】被限制在首都', bad_cap)

    # ①b ★ 用户 2026-10-04 定的口径：
    #   「有 start 就算条件留空，也让他在本省建；没有 start 的就在玩家首都」
    # 所以"条件留空但有 start"的奇观必须有 `province_id = <它自己的 start>`。
    # 少了这条它们会在【任何】自己的省份都能建 —— 实测大运河那 8 段在明朝
    # 100 个省里全都能建（用 src\\amr_plan.py 求值验出来的）。
    nopin = []
    for nm, f, b in mons:
        sm = re.search(r'(?m)^[ \t]*start[ \t]*=\s*(\d+)', b)
        if not sm:
            continue                      # 没有 start 的由上一条 is_capital 管
        bt = sub_block(b, 'build_trigger')
        if bt is None:
            continue
        # 作者原条件留空 = 去掉注释后没有 if/else 之类的真判断
        body = re.sub(r'#[^\n]*', '', bt[1:-1])
        if 'if = {' in body or 'else = {' in body:
            continue                      # 有真条件的（圣索菲亚那类）：不动
        pm = re.search(r'province_id\s*=\s*(\d+)', bt)
        if not pm:
            nopin.append('%s 条件留空但没钉省份（会到处建）' % nm)
        elif pm.group(1) != sm.group(1):
            nopin.append('%s province_id=%s 与 start=%s 不一致'
                         % (nm, pm.group(1), sm.group(1)))
    check('条件留空但有 start 的奇观钉回了自己的省份（province_id）', nopin)
    check('每件奇观都有 build_trigger', no_bt)

    # ② 升级/加成条件【不该】被加地域限制，也不该被加 ai=no
    polluted = []
    for nm, f, b in mons:
        for k in ('can_upgrade_trigger', 'can_use_modifiers_trigger'):
            s = sub_block(b, k)
            if not s:
                continue
            if re.search(r'(?m)^[ \t]*is_capital\s*=\s*yes', s):
                polluted.append('%s.%s 被加了 is_capital' % (nm, k))
    check('升级/加成条件没有被加地域限制', polluted)

    # ③ 玩家旁路（奖励解锁）：有实条件就必须有门禁；空块才该没有
    ungated, needless = [], []
    for nm, f, b in mons:
        for k in ('can_upgrade_trigger', 'can_use_modifiers_trigger'):
            s = sub_block(b, k)
            if s is None:
                continue
            body = re.sub(r'#[^\n]*', '', s[1:-1]).strip()
            # 玩家门禁有两种形态，都要认：
            #   B) 外层 custom_trigger_tooltip 带 AMR 标记（没有作者 tooltip）
            #   A) if = { limit = { owner = { ai = no } }
            #          custom_trigger_tooltip = { tooltip = <作者的> ... } }
            #      玩家悬停能看到作者那句条件说明（形态 A 里没有 AMR 标记）
            has_gate = (
                'AMR_monument_bypass_tt' in s
                or bool(re.search(
                    r'(?m)^[ \t]*if[ \t]*=[ \t]*\{[^}]*limit[ \t]*=[ \t]*\{'
                    r'[^}]*owner[ \t]*=[ \t]*\{[^}]*ai[ \t]*=[ \t]*no', s)))
            if body and not has_gate:
                ungated.append('%s.%s 有条件但没有玩家旁路' % (nm, k))
            if not body and has_gate:
                needless.append('%s.%s 空条件却插了门禁' % (nm, k))
    check('有条件的升级/加成触发器都带玩家旁路（奖励解锁）', ungated)
    check('空触发器没有被多插门禁', needless)

    # ④ 玩家旁路的写法：有实条件 -> "外层 if/else"；空条件 -> 只需一条 ai=no
    #    ★ 2026-10-03 用户定的最终做法（比"把原内容展开成 AND/OR"安全得多）：
    #        custom_trigger_tooltip = {
    #            tooltip = AMR_monument_bypass_tt
    #            if   = { limit = { owner = { ai = no } }  <原触发器内容> }  ← 玩家直通
    #            else = { <原触发器内容> }                                  ← AI 走原条件
    #        }
    #      语义：玩家必过；AI 在 if 里不满足 -> 落到 else -> 作者原条件照旧。
    #      （custom_trigger_tooltip 里带真条件是合法写法，全机 20215 处先例，
    #        原版 common/achievements.txt 就是这么用的。）
    #    ★ 空触发器（can_use_modifiers_trigger = { }）本来就"谁都能用"，
    #      只需要一条 owner = { ai = no }，不需要 if/else。
    # ★ 2026-10-04 起，旁路统一改成照抄 mod 3050177747（All Monuments for
    #   Player）的 OR 结构，不再用 if/else：
    #
    #     OR = {
    #         custom_trigger_tooltip = { tooltip = AMR_monument_bypass_tt
    #                                    owner = { ai = no } }        <- 恒真
    #         AND = { custom_trigger_tooltip = { tooltip = <作者的>
    #                                           <作者原条件> } }
    #     }
    #
    #   要点：作者条件必须在 custom_trigger_tooltip 里（生效但玩家看不到），
    #        绝不能裸放 —— 裸条件会被真求值，作者条件不满足就卡死奇观效果。
    leftover, lost = [], []
    for nm, f, b in mons:
        for k in ('can_upgrade_trigger', 'can_use_modifiers_trigger'):
            s = sub_block(b, k)
            if not s or 'AMR_monument_bypass_tt' not in s:
                continue
            body = re.sub(r'#[^\n]*', '', s[1:-1])
            if not re.search(r'tooltip[ \t]*=[ \t]*AMR_monument_bypass_tt', body):
                leftover.append('%s.%s 旁路里缺 tooltip 键' % (nm, k))
                continue
            # 旁路项必须自带恒真条件
            if not re.search(r'owner\s*=\s*\{\s*ai\s*=\s*no', body):
                leftover.append('%s.%s 旁路里缺 owner = { ai = no }' % (nm, k))
                continue
            # 作者条件必须被 custom_trigger_tooltip 包住（数一下壳的数量：
            # 至少 2 个 —— 一个是我们自己的旁路壳，一个是作者的）
            # ★ 只在【有作者条件】时才要求 2 个壳。
            #   源条件为空的（can_use_modifiers_trigger = { }）只需要一个旁路壳，
            #   壳数 1 是正确的（实测这类 146 件：himeji_castle / alhambra ...）。
            n_shell = len(re.findall(r'custom_trigger_tooltip\s*=\s*\{', body))
            # 判定"有没有作者条件"：去掉我们旁路壳之后还剩不剩东西
            _after = re.sub(r'custom_trigger_tooltip\s*=\s*\{\s*tooltip\s*=\s*'
                            r'AMR_monument_bypass_tt\s*owner\s*=\s*\{\s*ai\s*=\s*no'
                            r'\s*\}\s*\}', '', body)
            _after = re.sub(r'[{}#\s]', '', _after)
    # 注：原来这里有一条『作者条件都包在 custom_trigger_tooltip 里』的检查，
    # 2026-10-04 删除。口径反了 —— custom_trigger_tooltip 会【遮住】里面的条件、
    # 只显示 tooltip= 那句文本（EU4 Wiki 原文）。把作者条件包进壳里恰恰会让
    # 玩家看不到条件。正确做法：作者写了 tooltip 才套壳；没写就裸放让 EU4
    # 自己渲染文字。

    # ⑤ 每距离基础搬运时间 = 1
    # keep：搬运限制原样保留，不能断言统一成 1。
    if (val_of(cfg, 'move') or 'keep').strip().lower() == 'keep':
        check('move=keep：move_days_per_unit_distance 保持作者原样', [])
    else:
        md = val_of(cfg, 'movedays') or '1'
        want = md.strip()
        bad_md = []
        if want.lower() not in ('no', 'off', ''):
            for nm, f, b in mons:
                v = val_of(b, 'move_days_per_unit_distance')
                if v != want:
                    bad_md.append('%s = %s（应为 %s）' % (nm, v, want))
        check('move_days_per_unit_distance 全部 = %s' % want, bad_md)

    # ⑥ 括号平衡 + 顶层块完整
    bad_brace, bad_block = [], []
    for f in files:
        t = io.open(os.path.join(gp, f), 'rb').read().decode('latin-1')
        if t.count('{') != t.count('}'):
            bad_brace.append('%s  %d / %d' % (f, t.count('{'), t.count('}')))
        # 每个顶层块必须能配对
        for m in re.finditer(r'(?m)^([A-Za-z_0-9.\-]+)[ \t]*=[ \t]*\{', t):
            q = t.index('{', m.start())
            if brace_close(t, q) < 0:
                bad_block.append('%s: %s 花括号不配对' % (f, m.group(1)))
    check('每个文件的 { } 数量平衡', bad_brace)
    check('每个顶层块的花括号都能配对', bad_block)


    # ⑥b ★ 用户 2026-10-04：「打省标记改成打全局标记，不然在其他省或者其他国家
    #   也能建造」—— 所以"建过就不再建"必须用【全局标记】：
    #     守卫里  NOT = { has_global_flag = <键名>_AMR_built_g }
    #     on_built 里  set_global_flag = <键名>_AMR_built_g
    #   省标记挡不住"别的省 / 别的国家再建一个"，全局标记是一整个世界只此一份。
    flagbad = []
    for nm, f, b in mons:
        bt = sub_block(b, 'build_trigger')
        ob = sub_block(b, 'on_built')
        if bt is None:
            continue
        want = nm + '_AMR_built_g'
        if not re.search(r'has_great_project', bt):
            continue                      # 没加禁重复守卫的（理论上不该有）
        if ('has_global_flag' not in bt) or (want not in bt):
            flagbad.append('%s 守卫里没有全局标记 %s' % (nm, want))
        if ob is None or 'set_global_flag' not in ob or want not in ob:
            flagbad.append('%s 的 on_built 里没有 set_global_flag = %s' % (nm, want))
    check('禁重复建用的是【全局标记】（跨省跨国家只此一份）', flagbad)

    # ⑦ 键不重复（同名奇观只定义一次）
    seen, dup = {}, []
    for nm, f, b in mons:
        if nm in seen:
            dup.append('%s 同时出现在 %s 和 %s' % (nm, seen[nm], f))
        else:
            seen[nm] = f
    check('奇观定义没有重名', dup)

    # ⑧ 决议 + 修正器 + 本地化
    dec = os.path.join(moddir, 'decisions', 'AMR_upgrade_discount.txt')
    dec2 = os.path.join(moddir, 'common', 'decisions', 'AMR_upgrade_discount.txt')
    mod_f = os.path.join(moddir, 'common', 'event_modifiers',
                         'AMR_upgrade_discount.txt')
    loc_en = os.path.join(moddir, 'localisation',
                          'AMR_monument_l_english.yml')
    loc_cn = os.path.join(moddir, 'localisation',
                          'AMR_monument_l_simp_chinese.yml')

    prob = []
    if os.path.isfile(dec) and os.path.isfile(dec2):
        a = io.open(dec, 'rb').read()
        c = io.open(dec2, 'rb').read()
        if a != c:
            prob.append('两处 decisions 副本内容不一致')
    else:
        prob.append('缺少 decisions/AMR_upgrade_discount.txt')
    if not os.path.isfile(mod_f):
        prob.append('缺少 common/event_modifiers/AMR_upgrade_discount.txt')
    else:
        s = io.open(mod_f, encoding='latin-1').read()
        if 'global_unrest' in s:
            prob.append('修正器里还有 global_unrest（应已删掉）')
    check('升级打折决议 / 修正器文件齐全且正确', prob)

    # ⑨ 决议：扣 50 杜卡特、allow 里不检查钱、文件以 country_decisions 开头
    prob = []
    if os.path.isfile(dec):
        raw = io.open(dec, 'rb').read()
        s = raw.decode('latin-1')
        if not raw.startswith(b'country_decisions'):
            prob.append('文件不是以 country_decisions 开头（决议不会出现）')
        if 'add_treasury' not in s:
            prob.append('决议里没有扣钱（add_treasury）')
        if re.search(r'allow\s*=\s*\{[^}]*treasury', s):
            prob.append('allow 里检查了 treasury（不该检查，没钱应自动贷款）')
        if 'ai = no' not in s:
            prob.append('potential 里没有 ai = no（AI 也会点）')
    check('决议：扣钱 / 不检查钱 / 仅玩家 / 文件头正确', prob)

    # ⑩ 本地化：英文 ASCII、中文含中文、键名以 _title/_desc 结尾
    #    ★ BOM 是【必须】的：实测原版 localisation 抽查 12/12 全带 BOM，
    #      参照 mod（3050177747）也带 —— 以前这里写成"不该有 BOM"是错的。
    prob = []
    for p, label, want_cn in ((loc_en, 'english', False),
                              (loc_cn, 'simp_chinese', True)):
        if not os.path.isfile(p):
            prob.append('缺少 %s 本地化' % label)
            continue
        b = io.open(p, 'rb').read()
        s = b.decode('utf-8', 'replace')
        has_cn = any('\u4e00' <= c <= '\u9fff' for c in s)
        if want_cn and not has_cn:
            prob.append('%s 那份没有中文（应该是中文）' % label)
        if not want_cn and has_cn:
            prob.append('%s 那份混进了中文（l_english 只收 Latin-1，会变问号）'
                        % label)
        if b[:3] != b'\xef\xbb\xbf':
            prob.append('%s 缺 UTF-8 BOM（原版全都有，缺了可能读不到）' % label)
        if 'AMR_toggle_upgrade_discount_title' not in s:
            prob.append('%s 缺 _title 键（决议会显示为空）' % label)
    check('本地化：英文 ASCII / 中文含中文 / 有 BOM / 键名正确', prob)
    # ★ 用户 2026-10-04 澄清：游戏本体【没有中文语言】。汉化是「覆盖 l_english
    #   + 自定义单字节编码 + 自带位图字体」实现的（汉化包 2976470733 里
    #   zh-hans-*.fnt/.dds + 魔改 core.gfx）。所以 l_simp_chinese 那份
    #   游戏【读不到】，它只是给汉化组做编码用的素材 —— 这里只提示不改判。
    if os.path.isfile(loc_cn):
        print('%s[说明]%s l_simp_chinese 那份游戏读不到（本体无中文语言）；'
              '它是给汉化组编码用的素材' % (DIM, END))

    # ⑪ 同名文件冲突：别的启用 mod 也在 common/great_projects 放同名文件
    #    ★ 交接文档 说明.txt「v3.3/v3.4」实测结论：
    #      本 mod 的 replace_path="common/great_projects" 能顶掉【原版】那一份，
    #      但【顶不掉别的 mod】放在这个目录里的同名文件 —— 谁生效由引擎自己决定，
    #      位置/版本号/文件大小都不影响结果。当时的实测：
    #        梗类 HL_geng_monuments.txt       -> 读的是我们那份（8/8 命中）
    #        原神 gs_monuments_*.txt          -> 读的是我们那份
    #        增加全球奇观 02/03_monuments.txt -> 读的是【它自己】那份（8/8、1/1）
    #      所以一旦撞名，我们的改动可能整份失效。这条查的就是"有没有撞名"。
    clash = []
    for other in enabled_mods():
        if os.path.abspath(other) == os.path.abspath(moddir):
            continue
        ogp = os.path.join(other, 'common', 'great_projects')
        if not os.path.isdir(ogp):
            continue
        for f in files:
            p = os.path.join(ogp, f)
            if not os.path.isfile(p):
                continue
            t = io.open(p, 'rb').read().decode('latin-1')
            n = sum(1 for _nm, b in top_blocks(t) if is_monument(b))
            if n:
                clash.append('%s 的同名文件 %s（%d 件奇观）—— 谁生效由引擎决定，'
                             '我们的改动可能整份失效，建议只勾一份'
                             % (os.path.basename(other), f, n))
    check('没有别的启用 mod 放同名奇观文件（同名覆盖风险）', clash)

    # ⑫ 年份闸：有 date 的奇观，build_trigger 里必须有 owner = { is_year = <date年> }
    #    ★ 2026-10-03 加的规则。用户定案「以后默认全部关闭」= lockopen=date。
    #      date 的语义：剧本开始年份 < date 时，这件奇观开局【不在图上】，
    #      于是变成"可手动建" —— 条件里只要没有年份限制，它就能在满足条件的
    #      任何省份建出来（例：CE_chongwu_city 的条件是东亚文化组，明朝全境都满足
    #      -> 1368 剧本里到处能建）。补一道 owner = { is_year = 年份 } 就堵死了。
    #    没写 date 的（原版 inukshuk / 摩索拉斯陵墓那类"自古就在"的）不需要闸。
    nogate = []
    if (val_of(cfg, 'lockopen') or 'date').strip().lower() == 'date':
        for nm, f, b in mons:
            dm = re.search(r'(?m)^[ \t]*date[ \t]*=[ \t]*(\d+)', b)
            if not dm:
                continue
            bt = sub_block(b, 'build_trigger') or ''
            if 'is_year' not in bt:
                nogate.append('%s 有 date=%s 但建造条件没有年份闸' % (nm, dm.group(1)))
    check('有 date 的奇观都带了年份闸（lockopen=date）', nogate)

    # ---- 总结 ----
    print('-' * 74)
    if fails:
        print('%s总结：%d 项不通过%s' % (RED, len(fails), END))
        for x in fails:
            print('   ✗ %s' % x)
        return 1
    print('%s总结：全部通过（奇观 %d 件）%s' % (GREEN, len(mons), END))
    print('%s提示：这只查"生成结果对不对"，游戏里的实际手感仍需你自己看一眼。%s'
          % (DIM, END))
    return 0


if __name__ == '__main__':
    m = find_mod()
    if not m:
        print('%s找不到要体检的 mod。用法：python src\\amr_check.py <mod文件夹>%s'
              % (RED, END))
        sys.exit(2)
    sys.exit(run(m))
