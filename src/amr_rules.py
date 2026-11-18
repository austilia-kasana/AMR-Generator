"""AMR 生成器 · 奇观规则

没有所属省份的隐藏奇观、建造条件留空的按各自 date 解锁、白板化、钉回自己的省份，
以及总入口 transform_block()：按顺序把这些规则套到一个奇观块上。
"""

import re

from amr_config import *
from amr_config import MAKE_BUILDCOST, MAKE_BUILDTIME, MAKE_MOVE
from amr_env import log, write_text
from amr_scan import applied_markers, map_province_ids
from amr_script import *
from amr_script import _clean, _leaked_at
from amr_state import (NOSTART_KEYS, OPEN_KEYS, HIDDEN_KEYS, AGP_KEYS,
                       BADSTART_KEYS, CAPONLY_KEYS)

# ★ 2026-11-18（1.3）：`#start = 2807 - doesnt need this` 这种注释里，
#   作者是在说"我不需要 start"。解锁模式恢复注释掉的 start 时必须跳过这些，
#   否则会把作者的玩法设计弄坏（例如靠省份标记定位、故意不给固定省份的奇观）。
#   匹配英文缩写/全写 + 中文三种说法；大小写不敏感。
_START_NOT_WANTED = re.compile(
    r"(?:don'?t|do\s+not|doesn'?t|doesnt|not\s+define[ds]?"
    r"|no\s+need|not\s+needed|needn'?t"
    r"|不需要|无需|不用|不必)",
    re.I)


def _mon_key(block):
    m = re.search(r'(?m)^([A-Za-z_0-9.\-]+)[ \t]*=[ \t]*\{', block)
    return m.group(1) if m else ''




def has_start(block):
    """奇观块里有没有生效的 start = <省份>。
    注意 mod 作者会把 start 注释掉（'#start = 1822'），那种算【没有】。"""
    return bool(re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*[0-9]', block))


def no_start_is_hidden(block):
    """没有 start 时，判断它是不是那种"到处都能建"的隐藏奇观。

    只有 build_trigger 里【一个条件都没写】（或者根本没这个键）才算 —— 那种写法
    等于"谁占着这个省谁就能建"，才会在每个省都冒出来。
    Anbennar 那类 mod 是【故意】把 start 注释掉、改用省份标记定位的：
        #start = 2807 - doesnt need this
        build_trigger = { has_province_flag = h35_crimson_cathedral }
    这种有省份锚点，是正常奇观，一律不动（否则会把它的加成和建造一起打死）。"""
    if has_start(block):
        return False
    m = re.search(r'(?m)^[ \t]*build_trigger[ \t]*=[ \t]*\{', block)
    if not m:
        return True
    q = block.index('{', m.start())
    e = brace_close(block, q)
    if e < 0 or e < q:
        return True
    return not re.sub(r'#[^\n]*', '', block[q + 1:e]).strip()


def fix_no_start(block, stats, name=''):
    """EU4 里 start = <省份> 才是"这个奇观属于哪个省"。
    有的 mod 把 start 注释掉了（或者压根没写），游戏就不知道该把它放在哪，
    于是会在【每一个】满足条件的省份都给出建造选项 —— 这些"隐藏奇观"就到处冒。
    这些奇观本来就是靠决议/事件用 add_great_project 塞进去的（不受 build_trigger 影响），
    所以这里给它们补一句 always = no，只是不让玩家手动到处建，不影响原 mod 的发放。
    想保持原样：config.txt 里加一行 nostart=no"""
    if not MAKE_NOSTARTFIX:
        # 解锁模式（nostart=no）：作者把 start 注释掉的那类奇观（#start = 691）
        # 在游戏里根本没有所属省份 —— 存档里查得到它们，但地图上不出现、也点不到，
        # 所以"解开限制"对它们等于没做。这里把注释掉的那行恢复成真正的 start，
        # 它就会出现在作者指定的省份上；加成照常（can_use_modifiers_trigger 里
        # 已经有玩家旁路）。默认（nostart=yes）不动它们。
        m = re.search(r'(?m)^([\t ]*)#[ \t]*start[ \t]*=[ \t]*(\d+)([^\n]*)$', block)
        if m and not has_start(block):
            # ★ 2026-11-18（1.3）新增：先看注释里作者有没有说"不需要"。
            #   作者常见的写法是  #start = 2807 - doesnt need this / #start = X  # no need
            #   —— 他明说不需要，我们就**不能**把它恢复回来（会破坏作者的玩法设计）。
            #   1.2 之前这里不看注释内容，一律恢复，是错的。
            if _START_NOT_WANTED.search(m.group(3)):
                stats['nostart_skipped'] += 1
                return block
            # 两个前提都满足才恢复，避免误伤"作者故意注释掉、改用省份标记定位"的
            # 正常奇观（安本纳尔那 27 件就是这样，它们的标记是有人在应用的）：
            #   ① 它靠的省份标记在整个播放集里没人应用 ⇒ 它本来注定不出现
            #   ② 注释里那个省份号在当前地图上真实存在 ⇒ 放下去不会指到空白地
            marks = re.findall(r'(?m)^[ \t]*has_province_'
                               r'(?:modifier|flag|trigger)[ \t]*=[ \t]*'
                               r'([A-Za-z0-9_.\-]+)', block)
            applied = applied_markers()
            ids = map_province_ids()
            if (not any(x in applied for x in marks)
                    and (not ids or m.group(2) in ids)):
                stats['nostart_fixed'] += 1
                NOSTART_KEYS.append(name or _mon_key(block))
                out = (block[:m.start()] + m.group(1) + 'start = ' + m.group(2)
                       + '   # AMR: restored commented-out start (unlock mode)'
                       + block[m.end():])
                # 这类奇观被作者写成"只有人类持有才算"（owner = { ai = no }）。
                # 我们把它们放到了 AI 的省份上，AI 一持有引擎就把它们清掉 ——
                # 所以解锁模式下连带把这条人类独占放宽成"任何持有者都算"，
                # 这样 AI 拿在手里不会消失，你打下来之后它还在、加成归你。
                # 写法有两种：单行 owner = { ai = no } 和跨行的 owner = {\n ai = no \n}，
                # 所以这里用 \s 让空白（含换行）都能吃住。
                out, n_relax = re.subn(
                    r'owner\s*=\s*\{\s*ai\s*=\s*no\s*\}',
                    'always = yes   # AMR: unlock mode, no human-only limit', out)
                if n_relax:
                    log('  放宽人类独占 %-14s（%d 处 owner = { ai = no }）'
                        % (name or _mon_key(block), n_relax))
                return out
        return block
    if not no_start_is_hidden(block):
        return block          # 有 start，或者用省份标记定位：正常奇观，不动它
    # ★ 用户 2026-10-01 复述的原始设计意图（本轮按它改）：
    #   「#start 注释掉的 → 恢复回来（见上面解锁模式）；
    #     没有 start 的 → 【建造完后不再显示可建】；
    #     没有日期的、以及两个都没有的 → 同理」
    # 之前这里一律补 always = no，那是"根本不能手建"，和设计意图不符。
    # 正确写法：在 build_trigger 里加两条 ——
    #   ① NOT = { has_great_project = { type = <键名> } }
    #      "这个省已经有这件奇观了就不再显示"
    #      引擎只认 has_great_project 的 type = any 或【写死的奇观键名】，
    #      不接受 THIS（全机 26 处 type= 用法核对过：只有 any 和实名）。
    #   ② NOT = { has_province_flag = <键名>_AMR_built }
    #      这条是【正在施工 / 已建成】用的。用户实测反馈："如果卡时间甚至能建造多个"——
    #      原因是 ① 判断的是【已建成】的奇观，施工中的不算；一个省同时在造的东西
    #      一旦被取消/切换，就能再开一个，于是同一件奇观在一个省能刷出好几个。
    #      所以一建成就在 on_built 里打个省标记（标记会存档），永远挡住第二次。
    #      ★ on_built 是【效果】块，set_province_flag 只能放这里 ——
    #        build_trigger 是触发器块，里面放效果会被引擎丢掉。
    # 注意必须写在这件奇观自己的块里、且处于省份域 —— build_trigger 就是省份域。
    _key = name or _mon_key(block)
    _flag = _key + '_AMR_built_g'
    _need = ('NOT = { has_great_project = { type = ' + _key + ' } }'
             '   # AMR: hide once this province already has it\n'
             'NOT = { has_global_flag = ' + _flag + ' }'
             '   # AMR: hide if it was already built here\n')
    b = re.search(r'(?m)^([\t ]*)build_trigger[\t ]*=[\t ]*\{', block)
    if b:
        ind = b.group(1)
        guard = ind + '\t' + _need.replace('\n', '\n' + ind + '\t')[:-len(ind) - 1]
        b2 = block.index('{', b.start())
        stats['nostart_fixed'] += 1
        stats['nostart_guarded'] += 1
        NOSTART_KEYS.append(_key)
        out = _mark_built(block[:b2 + 1] + '\n' + guard + block[b2 + 1:],
                          _flag, stats)
        # ★ 用户 2026-10-03 最终方案：没有 start 的（注释也恢复不出来的）
        #   交给人类玩家。走到这里就说明本体没有 start。
        return _capital_redirect(out, stats)
    tm = re.search(r'(?m)^([\t ]*)type[\t ]*=[\t ]*monument[\t ]*\r?$', block)
    if not tm:
        return block
    ind = tm.group(1)
    stats['nostart_fixed'] += 1
    stats['nostart_bt'] += 1
    stats['nostart_guarded'] += 1
    NOSTART_KEYS.append(_key)
    guard = ind + '\t' + _need.replace('\n', '\n' + ind + '\t')[:-len(ind) - 1]
    add = (ind + 'build_trigger = {\n' + guard
           + ind + '\tis_capital = yes   # AMR: capital only\n'
           + ind + '\towner = { ai = no }'
           '   # AMR: human player only (the AI never builds it)\n'
           + ind + '}')
    stats['cap_only'] += 1
    return block[:tm.end()] + '\n' + add + block[tm.end():]


def bad_start_key(block):
    """start 写成了非数字（例如 `start = event_target:XXX_MB`）时返回那个字符串。

    引擎只认 `start = <省份号>`。写成 event_target 之类的，error.log 会报
    "Malformed token: event_target:XXX_MB, Last good read: type=monument"，
    这件奇观就等于【没有所属省份】—— 每个满足 build_trigger 的省份都能建它。
    Anbennar 那类"改用 has_province_flag 定位"的写法是作者【故意】的，
    而且标记真的有人应用；这里只负责把"写坏了"的情况识别出来。

    注意【不能】先用 has_start() 短路：has_start() 只认数字，
    写坏的 start 会让它返回 False，于是这类奇观会掉进"没有 start"那条分支。
    """
    m = re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*([^\s#]+)', block)
    if not m:
        return ''
    v = m.group(1)
    # 数字（含负数 / 带引号）都是合法的，直接放过
    if v.strip('"').lstrip('-').isdigit():
        return ''
    return v


def fix_bad_start(block, stats, name=''):
    """start 写成 event_target 之类的奇观：挡掉"到处可建"。

    用户 2026-10-01 复述的原始设计意图：
      · 能从注释里恢复出省份号 -> 恢复（奇观回到作者本来想放的那个省）
      · 恢复不出来 -> 加"建过就不再显示"的守卫
        NOT = { has_great_project = { type = <这件奇观> } }
    例外：如果它靠的 has_province_flag 在整个播放集里【真的有人应用】，
    就放它一马（那是作者有意的定位方式，安本纳尔那 27 件就是这种）。
    """
    if not MAKE_BADSTART:
        return block
    v = bad_start_key(block)
    if not v:
        return block
    marks = re.findall(r'(?m)^[ \t]*has_province_'
                       r'(?:modifier|flag|trigger)[ \t]*=[ \t]*'
                       r'([A-Za-z0-9_.\-]+)', block)
    # 注意：这里【不能】在"标记有人应用"时提前 return。
    # 作者写 start = event_target 本身仍然是引擎不认的，奇观照样没有所属省份；
    # 只是"标记有人应用"意味着事件会把它放到某个省 —— 那种情况下给守卫就够，
    # 不必锁死。两种情况下面分别处理。
    note = ' (source wrote start = ' + v + ', not a province id)'
    # ① 能从注释里恢复出真正的省份号就恢复（这是最好的结果：
    #    奇观回到作者本来想放的那个省，不再到处冒）
    cm = re.search(r'(?m)^([\t ]*)#[ \t]*start[ \t]*=[ \t]*(\d+)', block)
    ids = map_province_ids()
    if cm and (not ids or cm.group(2) in ids):
        stats['badstart_restored'] += 1
        BADSTART_KEYS.append((name or _mon_key(block), v, 'restored'))
        # 替换注释行 -> 真正的 start，并把【原来那行写坏的 start 整行删掉】。
        # 只替换注释行会留下两个 start，游戏会取后面那个（还是坏的）。
        # 说明性注释就写在 start 那一行【行尾】，不要挂到块外面去
        # （挂到块外的话，如果这是文件最后一件奇观，注释会掉在文件末尾空白处）。
        out = (block[:cm.start()] + cm.group(1) + 'start = ' + cm.group(2)
               + '   # AMR: restored start' + note)
        tail = block[cm.end():]
        bad_line = re.compile(r'[ \t]*start[ \t]*=[ \t]*' + re.escape(v)
                              + r'[^\n]*\n?')
        tail, n_del = bad_line.subn('', tail, count=1)
        if not n_del:
            # 兜底：万一那行在注释行之前，回头从整块里删
            out = bad_line.sub('', out, count=1)
        return out + tail
    # ② 恢复不出来。
    #    ★ 用户 2026-10-01 的要求：「如果奇观后续有被调用过，那就不要解禁」，
    #      并且实测这 11 件【没有任何 add_great_project 调用】—— 它们只在事件里
    #      被 set_province_flag / save_global_event_target_as 引用。
    #      也就是说作者的玩法是："事件给某个省设标记 -> 奇观在那个省【可以建】"
    #      （build_trigger = { has_province_flag = ... } 就是为这个写的）。
    #      所以【不能锁死】（锁死会把作者的玩法打死 —— 我上一轮就是这么错的），
    #      正确做法只是加"建过就不再显示"的守卫，让它不要到处可建、也不要重复建。
    #    只有连 build_trigger 都没有（从来没人能建它）时，才轮到锁死。
    key = name or _mon_key(block)
    _fl = key + '_AMR_built_g'
    b = re.search(r'(?m)^([\t ]*)build_trigger[\t ]*=[\t ]*\{', block)
    _need = ('NOT = { has_great_project = { type = ' + key + ' } }'
             '   # AMR: hide once this province already has it' + note + '\n'
             'NOT = { has_global_flag = ' + _fl + ' }'
             '   # AMR: hide if it was already built here\n')
    if b:
        # 有 build_trigger：不改它的可建性，只加"建过就不再显示"的守卫；
        # ★ 再加"只给人类玩家"——这是用户定的最终方案
        #   （"没有 start 的，就算注释回来也没有 start 的，才只给人类玩家"）。
        #   走到这里就说明：本体 start 非法、注释里也恢复不出省份号。
        ind = b.group(1)
        guard = ind + '\t' + _need.replace('\n', '\n' + ind + '\t')[:-len(ind) - 1]
        b2 = block.index('{', b.start())
        stats['badstart_guarded'] += 1
        BADSTART_KEYS.append((key, v, 'guarded'))
        out = _mark_built(block[:b2 + 1] + '\n' + guard + block[b2 + 1:],
                          _fl, stats)
        return _capital_redirect(out, stats)
    # 连 build_trigger 都没有：谁也建不了它。
    # ★ 改为只给人类玩家（而不是锁死 always = no）——用户 2026-10-03 的方案。
    #   这样玩家能在自己首都把它建出来，而不是永远看不见。
    out = _capital_redirect_or_new(block, stats)
    if out is not block:
        stats['badstart_bt'] += 1
        BADSTART_KEYS.append((key, v, 'capital'))
        return out
    return block


def _mark_built(block, flag, stats):
    """在奇观自己的 on_built 里加一句 set_province_flag = <flag>。

    为什么要它：用户实测"卡时间能建造多个"。守卫 NOT = { has_great_project } 只管
    【已建成】的奇观，施工中的不算；一个省的建设队列被取消/切换后就能再开一个，
    于是同一件奇观在一个省刷出好几个。建成时打个省标记（标记会存档）就永远挡住了。

    ★ 必须放在 on_built（效果块）里。build_trigger 是【触发器】块，
      set_province_flag 放进去会被引擎丢掉（触发器里不允许效果）。
      原版 01_monuments.txt 里每件奇观都有 on_built = { }，所以路径稳定。
    """
    line = 'set_global_flag = ' + flag + '   # AMR: built somewhere once\n'
    m = re.search(r'(?m)^([\t ]*)on_built[ \t]*=[ \t]*\{', block)
    if m:
        ind = m.group(1)
        b2 = block.index('{', m.start())
        stats['mark_built'] += 1
        return block[:b2 + 1] + '\n' + ind + '\t' + line + block[b2 + 1:]
    # 没有 on_built：跟 fix_build_place 一样，挂在 type = monument 后面新建一个
    tm = re.search(r'(?m)^([\t ]*)type[ \t]*=[ \t]*monument[ \t]*\r?$', block)
    if not tm:
        return block
    ind = tm.group(1)
    stats['mark_built'] += 1
    stats['mark_built_new'] += 1
    add = '\n' + ind + 'on_built = {\n' + ind + '\t' + line + ind + '}'
    return block[:tm.end()] + add + block[tm.end():]


def _empty_bt(block):
    """build_trigger 存在但里面【一个条件都没有】时返回它的 (缩进, 开括号位置)。

    引擎语义：build_trigger 留空 = "谁占着这个省谁就能建"，而且【不限省份】。
    ★ 这就是"同一件奇观被重复建造"的真凶（2026-10-03 实测）：
      cartagena_de_indias / fuerte_del_morro / salvador_da_bahia /
      royal_palace_caserta 这几件都有正常 start，但 build_trigger = { }，
      于是能在自己省份以外的地方也建 —— 法兰西存档里 cartagena_de_indias
      出现在 4 个省、versailles 3 个。
    """
    m = re.search(r'(?m)^([\t ]*)build_trigger[ \t]*=[ \t]*\{', block)
    if not m:
        return None
    b2 = block.index('{', m.start())
    e2 = brace_close(block, b2)
    if e2 < b2:
        return None
    if re.sub(r'#[^\n]*', '', block[b2 + 1:e2]).strip():
        return None          # 有真条件 -> 作者有意，不动
    return m.group(1), b2


def _capital_redirect(block, stats):
    """★ 用户 2026-10-03 的方案（我先前说"做不到"是错的）：
    把【解禁之后依然没有 start】的奇观交给人类玩家。

    判据（用户原话）："没有 start 的，就算注释回来也没有 start 的，才只给人类玩家"。
    也就是：本体没有 start = <省份号>，而且从注释里也恢复不出省份号。

    做法：在它的 build_trigger 里追加两条硬条件
        owner = { ai = no }    只有人类玩家能建（AI 永远不建）
        owner = { ai = no }    只有玩家能建
    这样这件奇观全局只出现一份（玩家的首都），不会到处铺。
    ★ append 而不是 wrap —— 硬条件对所有分支生效，if/else 也绕不开。
    ★ 只动 build_trigger；升级/加成条件绝不加地域限制。

    为什么可行：`build_trigger` 是省份域触发器，`owner = { ai = no }` 在省份域
    合法，所以能表达"这件奇观只对玩家开放"。
    ★ 用户 2026-10-03 的最终定案：「buildtrigger 改成仅人类玩家生效不就行了」——
    确实更简单：AI 完全不参与建造，就不会有"很多国家各建一个"的重复；
    比限定首都更好，因为不牺牲玩家自己的选址自由。
    """
    b = re.search(r'(?m)^([\t ]*)build_trigger[ \t]*=[ \t]*\{', block)
    if not b:
        return block
    q = block.index('{', b.start())
    e = brace_close(block, q)
    if e < q:
        return block
    inner = block[q + 1:e]
    if 'AMR: human player only' in inner:
        return block                    # 已经加过
    ind = b.group(1)
    extra = (ind + '\tis_capital = yes   # AMR: capital only\n'
             + ind + '\towner = { ai = no }'
             '   # AMR: human player only (the AI never builds it)\n')
    stats['cap_only'] += 1
    return block[:q + 1] + '\n' + extra + inner.lstrip('\n') + block[e:]


def _capital_redirect_or_new(block, stats):
    """没有 build_trigger 的：新建一个只含首都条件的块。"""
    tm = re.search(r'(?m)^([\t ]*)type[\t ]*=[\t ]*monument[\t ]*\r?$', block)
    if not tm:
        return block
    ind = tm.group(1)
    stats['cap_only'] += 1
    stats['cap_new_bt'] += 1
    add = ('\n' + ind + 'build_trigger = {\n'
           + ind + '\tis_capital = yes   # AMR: capital only\n'
           + ind + '\towner = { ai = no }'
           '   # AMR: human player only (the AI never builds it)\n'
           + ind + '}')
    return block[:tm.end()] + add + block[tm.end():]


def human_only_build(block, stats, name=''):
    """把 build_trigger 拆成"玩家"和"AI"两条，用 if/else 区分开。

    ★ 用户 2026-10-04 的定案（我上一版做错了）：
      「按你的意思是，现在 ai 完全不能建吗自己满足条件的奇观吗，
        你就不能直接 ifelse 区分开来吗」

    我上一版给【所有】奇观硬加一条 `owner = { ai = no }`，等于把 AI 的建造
    也一并堵死。用户要的是**区分**：

        build_trigger = {
            if   = { limit = { owner = { ai = no } }   <玩家：我们的规则> }
            else = { <AI：作者原来的条件> }
        }

    玩家分支（我们说了算）：
      · 条件留空的（作者没写）    -> province_id = 自己的 start（只在本省）+ 年份闸 + 禁重复
      · 作者写了条件的            -> 作者条件 + 年份闸 + 禁重复
      · 没有 start 的             -> 仅首都（is_capital，在 fix_no_start/fix_bad_start 里加）
    AI 分支（作者说了算）：
      · 原样保留作者的条件 —— AI 在自己满足条件的省份照旧能建（用户明确要这个）
      · **但"条件留空"的除外**：那种作者本意就是"这件奇观已经在那儿了"
        （实测：存档里 56 件空条件奇观全部只出现在自己 start 的那一个省，
         AI 从来不建它们）。若把空条件原样交给 AI，那 AI 就能在【任何】自己的
         省份免费瞬建 —— 那正是用户最初报的"到处铺"。所以 AI 分支也带上
         province_id + 年份闸 + 禁重复，和玩家一致。

    ★ 实测背景（为什么相信这个划分）：
      · 空条件那 56 件：两个存档里各出现【1 处】，没有一件是多处。
      · 真正被 AI 铺开的是【有作者条件】的：CE_amber_palace 在 106 个省
        （条件是"接受当地文化"，明朝全境都满足）。
      → 所以"让 AI 走作者条件"不会重新引入重复，重复的根源是作者条件太宽，
        而那属于原作者的设定，不该由我们替它改。

    注意：只动 build_trigger；can_upgrade_trigger / can_use_modifiers_trigger
    一个字节都不动 —— 那两类加限制会把 AI 既有的奇观升级也锁死。
    """
    b = re.search(r'(?m)^([\t ]*)build_trigger[ \t]*=[ \t]*\{', block)
    if not b:
        return _capital_redirect_or_new(block, stats)
    q = block.index('{', b.start())
    e = brace_close(block, q)
    if e < q:
        return block
    inner = block[q + 1:e]
    if 'AMR: human player only' in inner or 'AMR: player branch' in inner:
        return block                       # 已经加过
    # 作者有没有写条件？去掉注释后看有没有真判断（if/else/各种触发器）
    stripped = re.sub(r'#[^\n]*', '', inner)
    for _tag in ('AMR: human only', 'AMR: pin to its own province',
                 'AMR: not before its historical year', 'AMR: no second one',
                 'AMR: already built here', 'AMR: capital only'):
        stripped = stripped.replace(_tag, '')
    author_cond = bool(re.search(r'[a-z_]', stripped))
    has_start = re.search(r'(?m)^[ \t]*start[ \t]*=\s*\d+', block) is not None

    ind = b.group(1)
    i1 = ind + '\t'
    i2 = ind + '\t\t'

    def _emit(txt):
        t = txt.strip('\n')
        return '\n'.join((i2 + l) if l.strip() else l for l in t.split('\n'))

    body_i = _emit(inner)
    # ★ AI 分支不能带 `owner = { ai = no }`（那是"只给玩家"的标记）——
    #   带着它的话 AI 分支永远不成立，等于白写。把它整行删掉。
    if author_cond or not has_start:
        ai_txt = re.sub(r'(?m)^[ \t]*owner[ \t]*=[ \t]*\{[ \t]*ai[ \t]*=[ \t]*no'
                        r'[ \t]*\}[^\n]*\n?', '', inner)
        ai_body = _emit(ai_txt)
    else:
        # 作者没写条件（build_trigger 留空）。
        # ★ 用户 2026-10-04：「那 56 件有自己 start，那就放他自己 start 上啊」
        #   —— 所以 AI 分支【不写 always = yes】（作者本来就没写条件），
        #   只靠下面的省份钉 + 年份闸 + 禁重复，让它在自己 start 那个省成立。
        #   实测：这 56 件开局就已经在自己 start 的省（存档里 56/56 都只出现一处），
        #   AI 不会去建它们；而如果放开成"空条件"，AI 就能在任何自己的省免费瞬建
        #   （build_cost = 0、time = 0），那正是最初报的"到处铺"。
        ai_body = (i2 + '# AMR: the author left the build condition empty;\n'
                   + i2 + '# this monument sits on its own start province\n')
    new = ('\n'
           + i1 + 'if = {   # AMR: player branch\n'
           + i2 + 'limit = { owner = { ai = no } }\n'
           + body_i + '\n'
           + i1 + '}\n'
           + i1 + 'else = {   # AMR: AI branch (author conditions)\n'
           + ai_body + '\n'
           + i1 + '}\n' + ind)
    stats['human_only'] += 1
    return block[:q + 1] + new + block[e:]


def apply_move_days(block, stats, name=''):
    """把所有奇观的【每距离基础搬运时间】统一覆盖成 MAKE_MOVEDAYS（默认 1）。

    ★ 用户 2026-10-03 定的 1.2 功能。官方公式（EU4 Wiki · Great project § Relocation）：
        搬迁耗时 = 两省距离 × move_days_per_unit_distance
        搬迁费用 = 耗时（天） × 3 杜卡特/天
      改成 1 -> 搬迁最快、最便宜（费用和耗时同方向，这是引擎的算法，改不了）。

    ★ 为什么必须在这里做：这是【定义层】字段，游戏内没有任何修正器/效果能改它
      （exe 里跟奇观搬迁有关的标识符只有 can_be_moved 和 move_days_per_unit_distance，
       没有费用类修正器）。所以只能生成器统一覆盖。
    ★ 最安全的一种改法：纯数值替换，不动任何结构。
    ★ 只动奇观块自己的这一行；原键不存在时补一行。
    """
    if str(MAKE_MOVE).lower() == 'keep':
        return block                    # keep：完全保留作者的搬运限制/耗时
    if not MAKE_MOVEDAYS:
        return block
    val = str(MAKE_MOVEDAYS).strip()
    if not re.match(r'^\d+$', val):
        return block                    # 只接受纯数字，写错就原样放过
    m = re.search(r'(?m)^([\t ]*)move_days_per_unit_distance[ \t]*=[ \t]*(\d+)',
                  block)
    if m:
        if m.group(2) == val:
            return block                # 已经是目标值
        stats['movedays_set'] += 1
        return (block[:m.start(2)] + val
                + '   # AMR: move time per distance (was ' + m.group(2) + ')'
                + block[m.end(2):])
    tm = re.search(r'(?m)^([\t ]*)type[\t ]*=[\t ]*monument[\t ]*\r?$', block)
    if not tm:
        return block
    ind = tm.group(1)
    stats['movedays_add'] += 1
    add = ('\n' + ind + 'move_days_per_unit_distance = ' + val
           + '   # AMR: added')
    return block[:tm.end()] + add + block[tm.end():]


def guard_one_per_province(block, stats, name=''):
    """空 build_trigger 的奇观：重定向到【拥有者的首都】+ 禁止重复建。

    ★ 用户 2026-10-03 的方案（我先前说"做不到"是错的）：
      `build_trigger` 里可以写 `owner = { ai = no }`，把建造权收到人类玩家。
      用户原话："这种你直接重定向到玩家首都，不行吗"——可以，这就是实现。

    加三条：
      owner = { ai = no }             —— 只有人类玩家能建（AI 永远不建）
      owner = { ai = no }             —— 只有玩家能建（AI 不参与，避免 AI 到处铺）
      NOT = { has_great_project = { type = <键名> } }
      NOT = { has_province_flag = <键名>_AMR_built }   （on_built 里打标记）
    效果：这件奇观【全局只会出现一份】（玩家的首都），玩家的领土再也刷不出第二个。
    比钉回固定的 start 省份更符合"奇观该是独一无二的"这个直觉。

    与 MAKE_STRICTBUILD（strictbuild=）的区别：那个是【所有】奇观一律钉回，
    会把"有真 build_trigger 的"也一起限制住；这里【只动 build_trigger 留空的】。
    """
    if not MAKE_EMPTYBT_GUARD:
        return block, 0
    hit = _empty_bt(block)
    if not hit:
        return block, 0
    sm = re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*(\d+)', block)
    if not sm:
        return block, 0          # 没有 start 的由 fix_no_start / fix_bad_start 管
    ind, b2 = hit
    key = name or _mon_key(block)
    flag = key + '_AMR_built_g'
    pid = sm.group(1)
    add = ''
    # ★★ 用户 2026-10-04 明确的口径：
    #   「有 start 就算条件留空，也让他在本省建；没有 start 的就在玩家首都」
    # 所以这批"条件留空但有 start"的（运河分段、姬路城、布兰登堡门…共 56 件）
    # 钉回它自己的省份 —— 用 `province_id = <start>`。
    #   · 这是 Anbennar 的既有写法：province_id 写在 build_trigger 里 = 只能在这个省建
    #     （anb_great_projects.txt:330，作者注释还专门写了
    #      "putting no start entry allows the canal to be put in multiple places"）
    #   · 实测（src\\amr_plan.py）：不钉的话，大运河那 8 段在明朝 100 个省里【全都能建】。
    #   · 为什么不是 is_capital：这批有历史定位，赶到首都是错的（用户已纠正过一次）。
    if 'AMR: pin to its own province' not in block:
        add += (ind + '\tprovince_id = ' + pid
                + '   # AMR: pin to its own province (start)\n')
        stats['place_pinned'] += 1
    # ★ 用户 2026-10-03 定案：建造权只归人类玩家（AI 不参与建造）。
    if 'AMR: human only' not in block:
        add += (ind + '\towner = { ai = no }'
                '   # AMR: human only (the AI never builds it)\n')
        stats['human_only'] += 1
    if 'AMR_built' not in block:
        add += (ind + '\tNOT = { has_great_project = { type = ' + key + ' } }'
                '   # AMR: no second one of these\n')
        add += (ind + '\tNOT = { has_global_flag = ' + flag + ' }'
                '   # AMR: already built here\n')
        stats['guard_empty_bt'] += 1
    if not add:
        return block, 0
    out = block[:b2 + 1] + '\n' + add + block[b2 + 1:]
    if 'AMR_built' not in block:
        out = _mark_built(out, flag, stats)
    return out, 1


def _has_top_level(text, key):
    """text 里有没有【第一层】的 `key =`（不在任何花括号内）。

    ★ 为什么需要它：判断"这个触发器是不是已经被锁过了"时不能整块搜字符串。
      实测踩到的坑：el_escorial 的 else 分支里有个【嵌套的】`always = no`
      （那是"奇观被永久摧毁过"的判定），整块搜 'always = no' 会命中它，
      于是被误判成"已经锁过了" -> 年份闸不加 -> 1368 剧本里它照样到处能建。
    """
    i, n, depth = 0, len(text), 0
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            if j < 0:
                return False
            i = j
            continue
        if c == '"':
            j = text.find('"', i + 1)
            if j > 0:
                i = j + 1
                continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and text.startswith(key, i):
            k = i + len(key)
            if k < n and text[k] not in ' \t=\r\n':
                i += 1
                continue
            while k < n and text[k] in ' \t':
                k += 1
            if k < n and text[k] == '=':
                return True
        i += 1
    return False


def lock_open_build(block, stats, name=''):
    """把"建造条件被写成空的"奇观按年份锁上。

    背景（EU4 官方 wiki · Great project modding）：
      date          = 历史上建成的年份（开局早于它 ⇒ 这件奇观开局就不该在图上）
      build_trigger = 能不能【手动】建；留空 = 谁占着这个省谁就能建
    两条凑一起就是"隐藏奇观大放送"：玩家开局就能一口气手建几十件本来看不到的奇观。
    原版 1444 开局没这个问题（原版 52 个空条件奇观的 date 全在 1444 之前，开局就已经在了）。

    默认做法（lockopen=yes）= 按各自 date 解锁，插一句
        custom_trigger_tooltip = { tooltip = AMR_hidden_locked_tt
                                  owner = { is_year = <date 年份> } }
    年份没到就建不了，年份到了自动能建 —— 与开局年份无关，风云那种两千多年跨度
    （公元 2 年开局到近代开局）都自动对得上。is_year 是原版触发器，语义是
    "当前年份 ≥ N"（原版 common\\buildings\\00_buildings.txt 在省份 scope 用它当
    AI 权重条件；风云自己的 SMB_TNG_monuments.txt 就在 build_trigger 里写
    owner = { is_year = 626 ... }）。
    lockopen=all 用 always = no 永远锁死；lockopen=<年份> 是老的静态写法。
    锁上只是【不能手动建】，事件/决议/任务（add_great_project 等）照样能正常发放。"""
    if not MAKE_LOCKOPEN:
        return block
    b = re.search(r'(?m)^([\t ]*)build_trigger[\t ]*=[\t ]*\{', block)
    if not b:
        return block          # 没有这个键的奇观交给 fix_no_start 处理
    q = block.index('{', b.start())
    e = brace_close(block, q)
    if e < 0 or e < q:
        return block
    inner = re.sub(r'#[^\n]*', '', block[q + 1:e]).strip()
    if inner:
        # ★ 2026-10-03 扩展：以前这里直接 return（只处理"空条件"的奇观）。
        #   但"有真条件"的一样会到处建 —— 例：CE_chongwu_city 的条件是
        #   culture_group = east_asian，而明朝全境都是东亚文化组，于是到处能建。
        #   现在只要【有 date】就补一道年份闸（隐式 AND，作者原条件一字不动）：
        #       owner = { is_year = <date 年份> }
        #   语义：年份没到就建不了；年份到了（date 之后开局的剧本它本来就已在图上）
        #   这道闸自动成立，不影响任何东西。
        #   注意：只对【有 date】的做 —— 没写 date 的是"自古就在"那类，不该加闸。
        if MAKE_LOCKOPEN != 'date':
            return block
        if _has_top_level(block[q + 1:e], 'always'):
            return block
        dm2 = re.search(r'(?m)^[ \t]*date[ \t]*=[ \t]*(\d+)', block)
        if not dm2:
            return block
        yr = int(dm2.group(1))
        ind2 = b.group(1)
        ins2 = (ind2 + '\towner = { is_year = %d }   '
                '# AMR: not before its historical year\n' % yr)
        stats['open_locked'] += 1
        stats['dategate'] += 1
        stats['lky_' + str(yr)] = stats.get('lky_' + str(yr), 0) + 1
        return block[:q + 1] + '\n' + ins2 + block[q + 1:]
    if 'always = no' in block[q:e] or 'is_year' in block[q:e]:
        return block
    ind = b.group(1)
    dm = re.search(r'(?m)^[ \t]*date[ \t]*=[ \t]*(\d+)', block)
    if not dm:
        # 没写 date 的（原版 inukshuk / 摩索拉斯陵墓这类"自古就在"的）不算隐藏奇观。
        # 只有 lockopen=all 才连它们一起锁。
        if MAKE_LOCKOPEN != 'all':
            return block
        ins = ind + '\talways = no   # AMR: source mod left build_trigger empty\n'
        stats['open_locked'] += 1
        stats['open_locked_hard'] += 1
    elif MAKE_LOCKOPEN == 'date':
        year = int(dm.group(1))
        # is_year = N 的语义是"当前年份 ≥ N"（原版 buildings/00_buildings.txt 用它当
        # AI 权重条件、风云自己的 SMB_TNG_monuments.txt 就在 build_trigger 里写
        # owner = { is_year = 626 ... }），所以直接写 is_year = <date 年份> 即可：
        # 年份没到 → 条件不成立 → 建不了；年份到了 → 自动能建。
        ins = (ind + '\tcustom_trigger_tooltip = {\n'
               + ind + '\t\ttooltip = ' + TT_LOCK + '\n'
               + ind + '\t\towner = { is_year = %d }   '
               '# AMR: buildable from %d on (source mod left build_trigger empty)\n'
               % (year, year)
               + ind + '\t}\n')
        stats['open_locked'] += 1
        # ★ 这里必须同时记 open_locked_date：校验器用 n_lkd 算 is_year 的期望值。
        #   漏了它 -> 期望 is_year=0，而产物里有 356 处 -> 假报 problems。
        stats['open_locked_date'] += 1
        stats['dategate'] += 1
        stats['lky_' + str(year)] = stats.get('lky_' + str(year), 0) + 1
    else:
        year = int(dm.group(1))
        if year <= int(MAKE_LOCKOPEN):
            return block      # 开局（界线年份）时它已经在地图上了，空条件不算问题
        ins = ind + '\talways = no   # AMR: source mod left build_trigger empty\n'
        stats['open_locked'] += 1
        stats['open_locked_hard'] += 1
    OPEN_KEYS.append(name or _mon_key(block))
    return block[:q + 1] + '\n' + ins + block[q + 1:]




def kill_hidden_bonus(block, stats, name=''):
    """把"隐藏奇观"（没有 start 的那类）的加成整块关掉。

    这些奇观（原神的新艾利都 / 星穹列车 / NXX 基地、更多决议与修正的"伟大奇观"等）
    本来就是原 mod 用事件/决议的 add_great_project 塞给玩家的，很多数值是爆炸级的。
    默认（hiddenbonus=no）给它们的 can_use_modifiers_trigger 里塞一句 always = no：
    这件奇观对谁都不产生效果，同时【不做】玩家无条件生效的旁路，
    conditional_modifier 也保持原样（否则"达成奖励"还会漏出来）。
    奇观本体、原 mod 的事件都照旧，地图上照样看得见，只是白板。
    返回 None = 这件不归本函数管，交给原来的 wrap_or_inject 流程。"""
    if MAKE_HIDDENBONUS == 'yes':
        return None
    if not no_start_is_hidden(block):
        return None                      # 有 start（或用省份标记定位）的是正常奇观，一律不动
    if MAKE_HIDDENBONUS == 'agp' and (name or _mon_key(block)) not in AGP_KEYS:
        return None
    note = '   # AMR: hidden monument (no start) - bonuses off'
    b = re.search(r'(?m)^([\t ]*)can_use_modifiers_trigger[\t ]*=[\t ]*\{', block)
    if b:
        q = block.index('{', b.start())
        e = brace_close(block, q)
        if e < 0 or e < q:
            return None
        if 'always = no' in block[q:e]:
            return None
        if re.sub(r'#[^\n]*', '', block[q + 1:e]).strip():
            # 本来有内容：在最前面插一行 always = no —— 触发器是隐式 AND，
            # 整块因此永远不成立，原内容一个字节都不动。
            stats['hb_ins'] += 1
            out = block[:q + 1] + '\n' + b.group(1) + '\talways = no' + note + '\n' + block[q + 1:]
        else:
            # 空体（原 mod 写成 { } 或 { #anyone }）：直接换成 always = no
            ind = b.group(1)
            stats['hb_empty'] += 1
            out = block[:q + 1] + '\n' + ind + '\talways = no' + note + '\n' + ind + block[e:]
    else:
        tm = re.search(r'(?m)^([\t ]*)type[\t ]*=[\t ]*monument[\t ]*\r?$', block)
        if not tm:
            return None
        ind = tm.group(1)
        stats['hb_new'] += 1
        add = (ind + 'can_use_modifiers_trigger = {\n' + ind + '\talways = no'
               + note + '\n' + ind + '}')
        out = block[:tm.end()] + '\n' + add + block[tm.end():]
    stats['hidden_blank'] += 1
    HIDDEN_KEYS.append(name or _mon_key(block))
    return out




def fix_build_place(block, stats):
    """把奇观钉回"只在自己所属的那个省份能建"。
    有的 mod（例如 CE 王朝）在 build_trigger 里写了
      if = { limit = { owner = { full_idea_group = great_project_ideas } } ... }
    这样的分支 —— 带着那个理念组的国家就可以【在任意省份】建造这件奇观。
    结果那些还没建成的奇观（开局日期在后面的）在每个省的建造列表里都出现，
    看着就是"隐藏奇观到处都是"。建过一件之后它会固定下来，也是这个原因。
    这里给 build_trigger 补一句 province_id = <start>，钉回它自己的省。
    没有所属省份的奇观由 fix_no_start 处理（补 always = no），这里会跳过。
    想保持原样：config.txt 里加一行 strictbuild=no"""
    if not MAKE_STRICTBUILD:
        return block
    m = re.search(r'(?m)^[ \t]*start[ \t]*=[ \t]*([0-9]+)', block)
    if not m:
        return block
    pid = m.group(1)
    if re.search(r'(?m)^[ \t]*province_id[ \t]*=[ \t]*' + pid + r'\b', block):
        return block
    b = re.search(r'(?m)^([\t ]*)build_trigger[\t ]*=[\t ]*\{', block)
    if b:
        ind = b.group(1)
        stats['place_pinned'] += 1
        stats['pid_' + pid] += 1
        return (block[:b.end()] + '\n' + ind + '\tprovince_id = ' + pid
                + '   # AMR: buildable only in its own province\n'
                + block[b.end():])
    tm = re.search(r'(?m)^([\t ]*)type[\t ]*=[\t ]*monument[\t ]*\r?$', block)
    if not tm:
        return block
    ind = tm.group(1)
    stats['place_pinned'] += 1
    stats['place_bt'] += 1
    stats['pid_' + pid] += 1
    add = (ind + 'build_trigger = {\n' + ind + '\tprovince_id = ' + pid
           + '   # AMR: buildable only in its own province\n' + ind + '}')
    return block[:tm.end()] + '\n' + add + block[tm.end():]

def _pct(s):
    """'90' -> 0.9（保留的比例）；认不出来或 0 -> None（表示不改动）"""
    try:
        n = float(str(s).strip().rstrip('%'))
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if n > 100:
        n = 100.0
    return (100.0 - n) / 100.0


def discount_projects(text, stats):
    """把每件奇观的【建造花费】和【建造时间】打折。

    这两个字段是定义层，引擎只在加载时读一次，决议/事件/修正器都改不了
    （EU4 只有【升级】有 great_project_upgrade_cost / upgrade_time 修正器，
    【建造】一个都没有），所以折扣只能在生成时写进定义里。

      build_cost = 1000            ->  build_cost = 100        （打一折）
      time = { months = 120 }      ->  time = { months = 12 }

    只动原值大于 0 的：原版 187 件里 621 件本来就 build_cost = 0、683 件本来
    就是 months = 0，把 0 写成 0 没有意义，还会白改一遍文件。
    写法上只替换那个数字本身，行尾注释、缩进、换行风格一律原样保留；
    同一行里如果有两处（理论上不会有），只认第一处。

    返回改过的文本；折扣关掉时原样返回。统计写进 stats：
      dc_cost / dc_time       改动的件数
      dc_cost_{旧}_{新}       每个具体改动（供 token 校验用）
      dc_time_{旧}_{新}
    """
    kc, kt = _pct(MAKE_BUILDCOST), _pct(MAKE_BUILDTIME)
    if kc is None and kt is None:
        return text
    cost_re = re.compile(r'(?m)^([\t ]*build_cost[ \t]*=[ \t]*)([0-9]+)(?=[ \t]*(?:#|\r|$))')
    time_re = re.compile(r'(?m)^([\t ]*time[ \t]*=[ \t]*\{[^}]*?months[ \t]*=[ \t]*)'
                         r'([0-9]+)(?![0-9.])')
    edits = []          # (开, 止, 新文本, 统计键, 旧值, 新值)
    for m in cost_re.finditer(text):
        old = int(m.group(2))
        if old <= 0:
            continue
        # 整数运算：1000 * 0.9 在浮点下是 900.0000000000001，向上取整会变 901。
        new = -((-old * int(round(kc * 1000))) // 1000)
        if new == old:
            continue
        edits.append((m.start(2), m.end(2), str(new), 'dc_cost', old, new))
    for m in time_re.finditer(text):
        old = int(m.group(2))
        if old <= 0:
            continue
        new = -((-old * int(round(kt * 1000))) // 1000) if kt is not None else old
        if new == old:
            continue
        edits.append((m.start(2), m.end(2), str(new), 'dc_time', old, new))
    if not edits:
        return text
    out = text
    for a, b, new, key, old, _n in sorted(edits, key=lambda e: -e[0]):
        out = out[:a] + new + out[b:]
    for _a, _b, _new, key, old, new in edits:
        stats[key] += 1
        stats['%s_%d_%d' % (key, old, new)] += 1
    return out


TUNE_MARK = 'AMR: build cost'


def _needs_fields(block):
    """这个奇观块要不要由 discount_projects 改写（要 = 里面有正的花费/时间）"""
    if _pct(MAKE_BUILDCOST) is not None:
        for m in re.finditer(r'(?m)^[ \t]*build_cost[ \t]*=[ \t]*([0-9]+)', block):
            if int(m.group(1)) > 0:
                return True
    if _pct(MAKE_BUILDTIME) is not None:
        for m in re.finditer(r'(?m)^[ \t]*time[ \t]*=[ \t]*\{[^}]*?months[ \t]*=[ \t]*([0-9]+)',
                             block):
            if int(m.group(1)) > 0:
                return True
    return False


def _discounted(old, what):
    """按配置算出 old 该变成多少（what='cost' / 'time'）。用于校验"确实改对了"。"""
    keep = _pct(MAKE_BUILDCOST if what == 'cost' else MAKE_BUILDTIME)
    if keep is None:
        return old
    return -((-int(old) * int(round(keep * 1000))) // 1000)


def _field_values(text):
    """{奇观键: (build_cost, time 月数)}，没有这个键的记 None。校验用。"""
    out = {}
    for m in re.finditer(r'(?m)^([A-Za-z_0-9._\-]+)[ \t]*=[ \t]*\{', text):
        bo = text.index('{', m.start())
        bc = brace_close(text, bo)
        if bc < bo:
            continue
        blk = text[bo:bc + 1]
        if not re.search(r'(?m)^\s*type\s*=\s*monument\s*$', blk):
            continue
        cm = re.search(r'(?m)^[ \t]*build_cost[ \t]*=[ \t]*([0-9]+)', blk)
        tm = re.search(r'(?m)^[ \t]*time[ \t]*=[ \t]*\{[^}]*?months[ \t]*=[ \t]*([0-9]+)',
                       blk)
        out[m.group(1)] = (int(cm.group(1)) if cm else None,
                           int(tm.group(1)) if tm else None)
    return out


def transform_block(block, stats, name=''):
    """对每个奇观只做三件事：
       0) 把"掉在块外"的判断语句搬回它本来所属的块里
          （源文件自己写坏了才会发生；不修的话游戏会报 Unexpected token）
       1) can_use_modifiers_trigger（加成总闸门）——有要求判断就套
          OR = { 原内容  玩家分支 }；本来没有要求判断（空的/不存在）就补一道
          玩家门禁，否则 AI 也会吃到。
          can_upgrade_trigger / keep_trigger 有内容才套，空的保持原样
          （尤其 keep_trigger：给它加条件会让 AI 抢到奇观时把奇观销毁）。
          conditional_modifier 的 trigger（= 达成奖励）同样处理。
       2) can_be_moved = no -> yes（手工搬运）
       3) 奇观没有 start（没有所属省份）时，给 build_trigger 加一句 always = no，
          免得这类"隐藏奇观"在每个省份都能建。有 start 的一律不动 build_trigger，
          也不改写 if/else。
       4) 没有 start 的隐藏奇观（多半是原 mod 用 add_great_project 塞给玩家的），
          默认连加成一起关掉（kill_hidden_bonus），不像正常奇观那样加玩家旁路。"""
    block = apply_move_days(block, stats, name)
    block = repair_leaked_lines(block, stats)
    block = fix_bad_start(block, stats, name)
    block = fix_no_start(block, stats, name)
    # ★★ 顺序很重要，两步都【只认"体是空的" build_trigger】，必须排在
    #    "往 build_trigger 里插任何东西"之前：
    #      · guard_one_per_province  给"条件留空但有 start"的钉 province_id
    #      · lock_open_build         给空条件的加年份闸
    #    反过来（先插了年份闸）体就非空了，两个都会被静默跳过。
    #    实测踩过两次：先插 is_capital 时年份锁全丢；先插年份闸时 province_id 全丢
    #    （表现就是"大运河那 8 段在明朝 100 个省里都能建"）。
    block, _ = guard_one_per_province(block, stats, name)
    block = lock_open_build(block, stats, name)
    block = fix_build_place(block, stats)
    # ★ 最后一步：所有奇观的 build_trigger 一律"仅人类玩家"（用户 2026-10-03 定案）
    block = human_only_build(block, stats, name)
    _killed = kill_hidden_bonus(block, stats, name)
    if _killed is None:
        block = wrap_or_inject(block, 'can_use_modifiers_trigger', stats)
        block = wrap_conditional_modifiers(block, stats)
    else:
        block = _killed            # 白板：不加旁路，conditional_modifier 也不动
    for key in ('can_upgrade_trigger', 'keep_trigger'):
        block = wrap_top_level(block, key, stats)
    block = make_movable(block, stats, name)
    return block
