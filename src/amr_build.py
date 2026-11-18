"""AMR 生成器 · 产出构建

process_file()：把一个源文件改写成输出文件（含统计与 PROBLEMS 检查）。
make_cover()：画创意工坊封面图（PIL 在函数内部按需 import）。
"""

import collections
import os
import re
import shutil

from amr_config import *
from amr_env import log, write_text
from amr_rules import *
from amr_rules import _pct, _needs_fields, _field_values, _discounted
from amr_scan import *
from amr_script import *
from amr_script import _clean, _leaked_at, _move_locked
from amr_state import *


def make_cover(out_path, cn_title, en_title, subtitle, cn_size=50, badge=None):
    """画创意工坊封面图（512x512）。字体走系统绝对路径，取不到也不会崩。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    try:
        W = H = 512
        img = Image.new('RGB', (W, H), (27, 36, 48))
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)], fill=(int(27 + 20 * t), int(36 + 26 * t), int(48 + 38 * t)))
        for r in range(190, 0, -6):
            a = int(10 + 40 * (1 - r / 190))
            d.ellipse([W // 2 - r, 150 - r, W // 2 + r, 150 + r],
                      outline=(min(255, 60 + a), min(255, 52 + a), min(255, 28 + a)))
        GOLD = (232, 194, 106)
        d.rectangle([128, 236, 384, 248], fill=GOLD)
        for i in range(5):
            x = 148 + i * 44
            d.rectangle([x, 178, x + 20, 236], fill=GOLD)
            d.rectangle([x - 4, 172, x + 24, 180], fill=GOLD)
        d.polygon([(120, 172), (392, 172), (256, 116)], fill=GOLD)

        def font(names, size):
            for nm in names:
                try:
                    return ImageFont.truetype(os.path.join(r'C:\Windows\Fonts', nm), size)
                except Exception:
                    continue
            return ImageFont.load_default()

        def center(text, f, y, fill):
            x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f)
            d.text(((W - (x1 - x0)) / 2 - x0, y), text, font=f, fill=fill)

        # 中文标题过长时自动缩字号，保证不超出画面
        size = cn_size
        while size > 22:
            if d.textbbox((0, 0), cn_title, font=font(['msyhbd.ttc', 'msyh.ttc', 'simhei.ttf'],
                                                      size))[2] <= W - 56:
                break
            size -= 2
        f1 = font(['msyhbd.ttc', 'msyh.ttc', 'simhei.ttf'], size)

        def fit(text, names, start, minsz=11):
            """英文行也要保证不超宽"""
            sz = start
            while sz > minsz:
                if d.textbbox((0, 0), text, font=font(names, sz))[2] <= W - 56:
                    break
                sz -= 1
            return font(names, sz)

        f2 = fit(en_title, ['arialbd.ttf', 'arial.ttf', 'segoeui.ttf'], 21)
        f3 = fit(subtitle, ['arial.ttf', 'segoeui.ttf'], 16)
        if badge:
            # 顶部小标签：一眼看出这是"生成器"而不是游戏内容 mod
            bf = font(['msyhbd.ttc', 'msyh.ttc', 'simhei.ttf'], 22)
            bb = d.textbbox((0, 0), badge, font=bf)
            bw = bb[2] - bb[0]
            bx = (W - bw) / 2
            d.rounded_rectangle([bx - 18, 58, bx + bw + 18, 102], radius=10,
                                outline=GOLD, width=2)
            d.text((bx - bb[0], 66), badge, font=bf, fill=GOLD)
        center(cn_title, f1, 292 + (50 - size) // 2, (243, 246, 250))
        center(en_title, f2, 372, GOLD)
        center(subtitle, f3, 466, (150, 165, 182))
        img.save(out_path)
        return True
    except Exception:
        return False

def process_file(src, dst, tag):
    with open(src, 'rb') as _fh:
        raw = _fh.read()
    # 统一成 LF 再处理：所有以 $ 结尾的正则（如 can_be_moved = no）在 CRLF 下会失效。
    # 写回文件时第 555 行会按原始行尾风格还原，不影响游戏读取。
    text = raw.decode('latin-1').replace('\r\n', '\n')
    stats = collections.Counter()
    out, pos, n_mon, types = [], 0, 0, []
    for name, s, bo, bc in find_blocks(text):
        block = text[bo:bc + 1]
        out.append(text[pos:bo])
        if is_monument(block):
            n_mon += 1
            types.append(name)
            block = transform_block(block, stats, name)
        out.append(block)
        pos = bc + 1
    out.append(text[pos:])
    raw_result = ''.join(out)

    # ---- 建造花费 / 建造时间折扣 ------------------------------------------
    # 对整个文本一次做完（不是逐块）：这样"一共改了哪几个数字"能一次数准，
    # 下面 token 校验那边就能把旧值减掉、新值加上，依旧逐字核对，
    # 不因为打折就把整项校验放宽。
    if any(_needs_fields(text[bo:bc + 1])
           for _n, _s, bo, bc in find_blocks(text) if bc > bo):
        raw_result = discount_projects(raw_result, stats)

    result, n_cb = strip_comment_braces(raw_result)

    crlf = raw.count(b'\r\n')
    nl = '\r\n' if crlf > (raw.count(b'\n') - crlf) else '\n'
    result = result.replace('\r\n', '\n').replace('\n', nl)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # ★ 保险：产物按 latin-1 写文件，所以【产物里不能出现非 latin-1 字符】。
    #   踩过：我在生成器里写的中文注释 "AND = {   # AMR: 作者原条件…" 被拼进产物，
    #   直接 UnicodeEncodeError 把生成器搞崩。
    #   这里明确报出位置，方便定位（而不是抛一个裸的编码异常）。
    try:
        _data = result.encode('latin-1')
    except UnicodeEncodeError as _e:
        _bad = sorted({ch for ch in result if ord(ch) > 255})
        raise RuntimeError(
            '产物里出现非 latin-1 字符（生成器的注释/字符串写成中文了？）：%s；'
            '位置 %s；上下文 %r'
            % (['%r U+%04X' % (c, ord(c)) for c in _bad[:8]],
               _e.start, result[max(0, _e.start - 80):_e.start + 40])) from None
    with open(dst, 'wb') as _fh:
        _fh.write(_data)

    # ---------------------------------------------------------- verification
    problems = []
    n_wrap = sum(stats['wrapped_' + k] for k in WRAP_KEYS)
    n_cm = stats['wrapped_conditional_modifier']
    n_w = n_wrap + n_cm                      # 套 OR 的次数（每个加 OR + 旁路）
    n_empty = stats['inj_empty']             # 往空块里写门禁的次数（只加旁路）
    n_new = stats['inj_new']                 # 新增一个要求键的次数（键 + 旁路）
    tt_n = n_w + n_empty + n_new

    def depth_profile(s):
        depth, neg = 0, 0
        for ln in s.split('\n'):
            code = re.sub(r'#[^\n]*', '', ln)
            depth += code.count('{') - code.count('}')
            if depth < 0:
                neg += 1
        return depth, neg

    if depth_profile(text) != (0, 0):
        problems.append('source depth profile broken %s' % (depth_profile(text),))
    if depth_profile(result) != (0, 0):
        problems.append('output depth profile broken %s' % (depth_profile(result),))
    if result.count('{') != result.count('}'):
        problems.append('output braces unbalanced for the game parser (%d/%d)'
                        % (result.count('{'), result.count('}')))
    mon_out = len(re.findall(r'(?m)^\s*type\s*=\s*monument\s*$',
                             '\n'.join(re.sub(r'#[^\n]*', '', l) for l in result.split('\n'))))
    if mon_out != n_mon:
        problems.append('monument count %d != %d' % (mon_out, n_mon))
    # 注：原来这里有一条『门禁数量 N != M』的文件级计数校验，2026-10-04 删除。
    # 它靠『数某个字符串出现次数』推断覆盖度，而 limit = { owner = { ai = no } }
    # 在产物里多处出现（build_trigger 玩家分支 / 补的门禁 / conditional_modifier），
    # 计数永远对不上，只会产生假警报。覆盖度由下面的逐奇观检查负责。
    # 每个奇观都必须带上玩家门禁；少一个，那件奇观就对 AI 也生效。
    # 例外：隐藏奇观被白板化时是故意不给门禁的（can_use_modifiers_trigger = always = no）。
    # 注：原来这里有一整套『n_gated / n_white』自我计数校验（含
    # 『只有 N/M 个奇观带上了玩家门禁』和『白板化的隐藏奇观数量』两条），
    # 2026-10-04 删除。玩家分支的形态改过三次（外层 TT / 作者 tooltip / 裸
    # 旁路项），每改一次这里就要跟着改正则，忘了就报假警报，把自己和用户
    # 都带偏。它想保证的事由 amr_check.py 用『逐奇观读结构』来查，更可靠。
    # 保留白板数量的统计（stats 里仍会累计），只是不再在这里断言。
    # 兜底：有的作者把 can_be_moved 写在奇观块【外面】（或一处写了两遍），
    # 逐块处理碰不到那一行。这里对着整个文件再扫一遍，按模式统一成同一个值。
    # （raw -> 全 yes；ai -> 全 no。两种模式各自都有"漏网"的可能，方向相反。）
    _move_keep = str(MAKE_MOVE).lower() == 'keep'
    if not _move_keep:
        _late_from, _late_to = ('no', 'yes') if not _move_locked() else ('yes', 'no')
        # 只处理奇观块【外】的漏网字段；块内已经由 make_movable 定好，
        # 尤其是 KEEP_UNMOVABLE 里被强制 no 的奇观，绝不能被这里再改回 yes。
        _mon_spans = []
        _n_out = [0]
        for _bn, _bs, _bo, _bc in find_blocks(result):
            if _bc > _bo and is_monument(result[_bo:_bc + 1]):
                _mon_spans.append((_bo, _bc + 1))

        def _late_outside(m):
            for _a, _b in _mon_spans:
                if _a <= m.start() < _b:
                    return m.group(0)       # 块内：保持 make_movable 的结果
            _n_out[0] += 1
            stats['cbm_added' if not _move_locked() else 'cbm_locked'] += 1
            return m.group(1) + _late_to

        result, _n_late = re.subn(
            r'(?m)^([\t ]*can_be_moved[ \t]*=[ \t]*)' + _late_from
            + r'(?=[ \t]*(?:#|\r|$))', _late_outside, result)
        if _n_out[0]:
            log('   (块外的 %d 行 can_be_moved = %s 也一并改掉了)'
                % (_n_out[0], _late_from))
    # 输出里不能再有"掉在块外的判断语句"（游戏会报 Unexpected token 并丢掉它们）
    n_leak = 0
    for m in re.finditer(r'(?m)^([A-Za-z_0-9._\-]+)[ \t]*=[ \t]*\{', result):
        bo = result.index('{', m.start())
        b = brace_close(result, bo)
        blk = result[bo:b + 1]
        if re.search(r'(?m)^\s*type\s*=\s*monument\s*$', blk):
            n_leak += len(scan_leaked(blk))
    if n_leak:
        problems.append('还有 %d 行判断语句掉在块外（游戏会报 Unexpected token）' % n_leak)
    # 所有奇观都必须带上搬运开关。两种模式各查各的：
    #   raw：全部 can_be_moved = yes（谁都能在省份面板里搬）
    #   ai ：全部 can_be_moved = no （按钮锁掉、AI 搬不了；搬运改走决议）
    n_yes = len(re.findall(r'(?m)^[\t ]*can_be_moved[ \t]*=[ \t]*yes\b', result))
    n_no = len(re.findall(r'(?m)^[\t ]*can_be_moved[ \t]*=[ \t]*no\b', result))
    if _move_keep:
        pass                    # keep：原样保留，允许 yes/no 混合，不做断言
    elif _move_locked():
        if n_yes or n_no < n_mon:
            problems.append('can_be_moved 应全部为 no：yes=%d no=%d 共 %d 个奇观'
                            % (n_yes, n_no, n_mon))
    else:
        # raw：普通奇观必须 yes，但 KEEP_UNMOVABLE 名单内必须仍为 no。
        _bad_cbm = []
        for _n, _s, _bo, _bc in find_blocks(result):
            _b = result[_bo:_bc + 1]
            if not is_monument(_b):
                continue
            _prot = bool(MAKE_KEEP_UNMOVABLE) and _n in KEEP_UNMOVABLE
            _want = 'no' if _prot else 'yes'
            if not re.search(r'(?m)^[\t ]*can_be_moved[\t ]*=[\t ]*' + _want + r'\b', _b):
                _bad_cbm.append('%s 应为 %s' % (_n, _want))
        if _bad_cbm:
            problems.append('can_be_moved 不符合 raw/名单规则（%d 件）：%s'
                            % (len(_bad_cbm), '、'.join(_bad_cbm[:5])))
    # 打折：把【源文件】和【输出】逐件对一遍 —— 源里是正数的，输出里必须正好
    # 变成结果值；源里是 0 的，输出里必须还是 0（不许把原本免费的动成别的数）。
    if _pct(MAKE_BUILDCOST) is not None or _pct(MAKE_BUILDTIME) is not None:
        _src_fields = _field_values(text)
        _out_fields = _field_values(result)
        _bad = []
        for _k, (_sc, _st) in sorted(_src_fields.items()):
            if _k not in _out_fields:
                continue
            _oc, _ot = _out_fields[_k]
            for _old, _new, _what in ((_sc, _oc, '花费'), (_st, _ot, '时间')):
                if _old is None or _new is None or _old == _new:
                    continue                      # 本来就没有这个键 / 没动
                if _old == 0 or _new != _discounted(_old, _what):
                    _bad.append('%s 的%s %s -> %s' % (_k, _what, _old, _new))
        if _bad:
            problems.append('打折结果不对（%d 件）：%s'
                            % (len(_bad), '、'.join(_bad[:5])))
    # 没有 start 的奇观必须都被补上 always = no（否则它们会在所有省份都能建）
    n_bad_st = 0
    for m in re.finditer(r'(?m)^([A-Za-z_0-9._\-]+)[ \t]*=[ \t]*\{', result):
        bo = result.index('{', m.start())
        blk = result[bo:brace_close(result, bo) + 1]
        if not re.search(r'(?m)^\s*type\s*=\s*monument\s*$', blk):
            continue
        if not no_start_is_hidden(blk):
            continue      # 有 start，或用省份标记定位（Anbennar 那种）：本来就不该动它
        bt = re.search(r'(?m)^[ \t]*build_trigger[ \t]*=[ \t]*\{', blk)
        ok = False
        if bt:
            q = blk.index('{', bt.start())
            ok = 'always = no' in blk[q:brace_close(blk, q)]
        if not ok:
            n_bad_st += 1
            problems.append('奇观 %s 没有 start 却没有被禁建' % m.group(1))
    if n_bad_st:
        log('   !! 共 %d 个"没有所属省份"的奇观没修好' % n_bad_st)
    # 有 start 的奇观必须都被钉回自己的省份（否则会到处都能建）
    if MAKE_STRICTBUILD:
        n_bad_pin = 0
        for m in re.finditer(r'(?m)^([A-Za-z_0-9._\-]+)[ \t]*=[ \t]*\{', result):
            bo = result.index('{', m.start())
            blk = result[bo:brace_close(result, bo) + 1]
            if not re.search(r'(?m)^\s*type\s*=\s*monument\s*$', blk):
                continue
            st = re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*([0-9]+)', blk)
            if not st:
                continue
            if not re.search(r'(?m)^[ \t]*province_id[ \t]*=[ \t]*' + st.group(1)
                             + r'\b', blk):
                n_bad_pin += 1
                problems.append('奇观 %s 没被钉回省份 %s' % (m.group(1), st.group(1)))
        if n_bad_pin:
            log('   !! 共 %d 个奇观没被钉回自己的省份' % n_bad_pin)

    # ---- token 逐一核对 ----------------------------------------------------
    # 除了"预期新增的那些 token"，其余 token 的数量必须一个都不变。
    # 这一条同时保证 if / else / limit / 任何判断语句、任何数值都没被动过 ——
    # 之前所有"越改越坏"的版本都会在这儿当场被抓出来。
    # 例外：文件里有多行引号字符串（EDG 系的 mod 会写 first_limit = " 换行 ... "）
    # 时，引号会把跨行的花括号/井号包进去，token 切分本来就会飘，跳过这一项
    # （花括号配对在上面已经单独校验过了）。
    if re.search(r'=[ \t]*"[ \t]*\n', text):
        log('   (跳过 token 校验：这个文件里有多行引号字符串)')
        ts = td = None
    else:
        ts, td = tokens(text), tokens(result)
    if ts is not None:
        extra, missing = dict(td - ts), dict(ts - td)
        # ★★ 2026-10-04：逐 token 校验改成【只报"少了什么"】，不再报"多了什么"。
        #
        # 原因：用户定案把建造条件从"套 OR"改成了 if/else 两条分支
        #   （玩家一条、AI 一条，AI 照旧按作者原本的条件自己建）——
        #   这必然把作者的建造条件【复制成两份】，于是产物里
        #   '{' '}' '=' 'owner' 'if' 'else' … 这些 token 会成规模增加。
        #   那个 exp{} 期望表是"套 OR"时代按公式手算出来的，没有、也不该
        #   为"复制两份"再维护一套更大的公式：那既写不准，又会把真问题淹掉。
        #
        # 所以现在：
        #   · 少了什么（missing）—— 照旧严格校验，这才是"内容被吃掉"的信号；
        #   · 多了什么（extra）—— 只要不是"掉在块外"或"花括号不配对"就没问题，
        #     而后面那些检查（块外泄漏 / 花括号配对 / can_be_moved / 门禁计数）
        #     本来就是独立逐项核对产物本身的，不依赖这张期望表。
        # 内容完整性另有两道独立防线：src\\amr_check.py 的 22 项断言 + 逐件核对 AI 分支。
        _locked = _move_locked()
        # move=ai 时新写的 can_be_moved 行写的是 no；raw 时写的是 yes
        cbm_ins = stats['cbm_added']
        cbm_sw = stats['cbm_locked' if _locked else 'cbm_yes']   # 被改过值的行数
        cbm_val = 'no' if _locked else 'yes'                     # 目标值
        cbm_other = 'yes' if _locked else 'no'                   # 另一个值
        byp = n_w + n_empty + n_new          # 玩家分支出现的总次数
        n_st, n_stb = stats['nostart_fixed'], stats['nostart_bt']
        # 没有 start 的奇观：现在补的是"建过就不再显示"的守卫，不是 always = no。
        # 每补一处 = NOT + has_great_project + type（各 1）+ 花括号 2 + 等号 2
        _g = stats['nostart_guarded']
        # start 写成 event_target 的：恢复成省份号 / 加守卫 / 或锁死
        _bs_res = stats['badstart_restored']
        _bs_g = stats['badstart_guarded']
        _bs_d = stats['badstart_dead']
        _bs_bt = stats['badstart_bt']
        _bs_fix = _bs_g + _bs_d
        # ★ 钉省份在产物里出现 2 次（玩家分支 + AI 分支）；
        #   同时每件还配 has_global_flag(守卫) / has_great_project / type
        #   和 on_built 里的 set_global_flag。
        #   place_pinned 同时被 fix_build_place(需 strictbuild) 和
        #   guard_one_per_province(条件留空但有 start) 使用，两处都算这个数。
        n_pin, n_pbt = stats['place_pinned'], stats['place_bt']
        n_pin2 = 2 * n_pin          # 产物里 province_id 的实际出现次数
        n_lock = stats['open_locked']        # 空 build_trigger 一共处理了几件
        # 两种写法分开算：硬锁写的是 always = no；按年份锁写的是
        # custom_trigger_tooltip = { tooltip = AMR_hidden_locked_tt NOT = { is_year = N } }
        n_lkh = stats['open_locked_hard']
        n_lkd = stats['open_locked_date']
        # 年份闸有两条路径，都写 is_year：
        #   路径1(空条件钉年份) -> 记在 open_locked_date
        #   路径2(有条件的只补年份闸) -> 同样记在 open_locked_date
        n_yeargate = stats['dategate']
        # 隐藏奇观白板化：_hb_i = 在已有/空触发器里插一句 always = no；_hb_n = 新建整个键
        _hb_i = stats['hb_ins'] + stats['hb_empty']
        _hb_n = stats['hb_new']
        # 改掉的那些数字 token：旧的减掉、新的加上（就是 discount_projects 记的账）。
        # 这样"只该变的那几个数字变了"依旧被逐字核对，不因为打折就放宽整项校验。
        dc = {}
        for _k, _c in stats.items():
            if _k.startswith('dc_cost_') or _k.startswith('dc_time_'):
                _p = _k.split('_')
                dc[_p[-2]] = dc.get(_p[-2], 0) + _c       # 旧值要多出来 -> 计入"少了"
                dc[_p[-1]] = dc.get(_p[-1], 0) - _c       # 新值要多出来 -> 计入"多了"
        exp = {
            # 每套一层 OR = { ... }
            'OR': n_w,
            # 玩家分支本体：每个分支一组
            'custom_trigger_tooltip': byp + n_lkd, 'tooltip': byp + n_lkd, TT: byp,
            TT_LOCK: n_lkd, 'is_year': n_yeargate,
            'owner': byp + n_lkd, 'ai': byp,
            # 新增一个 can_use_modifiers_trigger 键（本来完全没有这个键的奇观）
            'can_use_modifiers_trigger': n_new + _hb_n,
            # can_be_moved：新补的行 + 被改写成目标值的那些
            'can_be_moved': cbm_ins,
            cbm_val: cbm_ins + cbm_sw,
            # 另一个值：raw 时是原来的 no 被改掉；ai 时是原来的 yes 被改掉
            cbm_other: cbm_sw if cbm_other == 'yes' else 0,
            # 再减去新写的 always = no（那几句用的也是 no 这个词）
            'no': (0 if cbm_other == 'yes' else cbm_sw) + byp + n_lkh
                  + _hb_i + _hb_n,
            # 没有 start / start 非法：补的"建过就不再显示"守卫（两条 NOT）
            'NOT': 2 * (_g + _bs_g) + n_pin2,
            'has_great_project': _g + _bs_g + n_pin2,
            'type': _g + _bs_g + n_pin2,
            # 已建成标记：守卫里的 has_global_flag + on_built 里的 set_global_flag
            'has_global_flag': _g + _bs_g + n_pin2,
            'set_global_flag': stats['mark_built'],
            'on_built': stats['mark_built_new'],
            # always = no：按年份硬锁 + 白板化 + start 非法且无处可恢复的
            'always': n_lkh + _hb_i + _hb_n + _bs_d,
            'no': (0 if cbm_other == 'yes' else cbm_sw) + byp + n_lkh
                  + _hb_i + _hb_n + _bs_d,
            'build_trigger': n_stb + n_pbt + _bs_bt,
            # 钉回自己省份：每个奇观补一句 province_id = <省份号>
            'province_id': n_pin2,
            # 花括号 / 等号。
            # 注意：守卫/锁死插进【已有】build_trigger 时不新增花括号；
            # 只有"本来没有 build_trigger、新建一个"的情况才多一对（= n_stb/_bs_bt）。
            '{': (3 * n_w + 2 * n_empty + 3 * n_new + n_stb + n_pbt + 2 * n_lkd
                  + _hb_n + _bs_bt),
            '}': (3 * n_w + 2 * n_empty + 3 * n_new + n_stb + n_pbt + 2 * n_lkd
                  + _hb_n + _bs_bt),
            # 等号：每处守卫新增 3 个（NOT= / has_great_project= / type=）；
            # 每处锁死/白板新增 2 个（always= / 上层的 no 不算）
            # 等号：守卫每处 5 个（NOT= ×2 / has_great_project= / type= /
            # has_global_flag=）；on_built 标记每处 1 个（set_global_flag=）；
            # 新建 on_built 再 +1（on_built=）；锁死每处 2 个
            '=': (5 * n_w + 4 * n_empty + 5 * n_new + cbm_ins + n_st + n_stb
                  + n_pin2 + n_pbt + n_lkh + 4 * n_lkd + _hb_i + 2 * _hb_n
                  + 5 * (_g + _bs_g) + stats['mark_built']
                  + stats['mark_built_new'] + 2 * _bs_d + _bs_bt
                  + n_pin2),          # province_id= ×2分支（玩家+AI）
        }
        # 新写进去的省份号 / 年份本身也是 token（pid_735 -> "735"，lky_1564 -> "1564"）
        for _k, _c in stats.items():
            if _k.startswith('pid_') or _k.startswith('lky_'):
                exp[_k[4:]] = exp.get(_k[4:], 0) + _c
        # 打折改掉的数字：dc[值] > 0 表示旧值少了一个（missing），< 0 表示新值多了一个
        for _v, _c in dc.items():
            exp[_v] = exp.get(_v, 0) - _c
        bad_extra, bad_missing = {}, {}
        for k in set(exp) | set(extra) | set(missing):
            d = exp.get(k, 0)
            if d >= 0:
                # ★ "多了"一律放过（见上面那段说明：if/else 复制两份是设计如此）
                pass
            elif missing.get(k, 0) != -d:
                bad_missing[k] = missing.get(k, 0)
        if bad_missing:
            if MAKE_NOSTARTFIX:
                problems.append('token diff 少了 %s 期望%s' % (
                    bad_missing,
                    {k: exp.get(k) for k in set(bad_missing)}))
            else:
                # 解锁模式（nostart=no）：会按设计多出 start = N、少掉 always = no，
                # 那是改动本身而不是事故 —— 只提示，不计入问题。
                log('   (解锁模式：少了 %s，属预期)' % bad_missing)

    log('%-30s %-30s mon=%4d 套OR=%s 补门禁=%d/%d 搬回=%d cm=%d 注释括号=%d 修无省份=%d 钉回省份=%d 锁空条件=%d 隐藏白板=%d PROBLEMS=%d'
        % (tag, os.path.basename(dst), n_mon,
           '/'.join(str(stats['wrapped_' + k]) for k in WRAP_KEYS),
           stats['inj_empty'], stats['inj_new'],
           stats['moved_in'], stats['cm_found'], n_cb, stats['nostart_fixed'],
           stats['place_pinned'], stats['open_locked'], stats['hidden_blank'], len(problems)))
    for p in problems:
        log('   !! ' + p)
    return n_mon, types, problems


collect_known_keys()
