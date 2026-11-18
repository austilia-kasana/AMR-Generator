"""AMR 生成器 · 脚本文本解析与改写

最底层：brace_close() 配对花括号（跳过 # 注释和 "字符串"）、find_blocks() 顶层
name = { 块、is_monument() 判断是不是奇观。
再往上：把触发条件包一层"只有玩家生效"、搬运开关、白名单与漏行修复。
以纯函数为主，靠传入的 stats 字典累计统计。
"""
import collections
import os
import re

from amr_config import *
from amr_env import log, write_text
from amr_state import KNOWN_KEYS


def brace_close(s, i):
    """i points at '{'; index of the matching '}' (skips # comments and "strings")"""
    depth, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '#':
            j = s.find('\n', i)
            if j == -1:
                return -1
            i = j
            continue
        if c == '"':
            j = s.find('"', i + 1)
            if j != -1:
                i = j
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _drop_commented_blocks(text):
    """删掉【整段注释掉】的块（形如连续多行以 # 开头、并且里面有括号的行）。

    ★ 为什么要删（2026-10-04，edinburgh_castle 丢旁路的根因）：
      作者常把旧版条件整段 # 掉，里面有 { }。EU4 引擎会把注释里的括号
      当真括号（会带歪后面的定义），所以 amr_scan.strip_comment_braces 会把
      它们换成 ( )。但换完这些注释会：
        · 打乱括号平衡判断 -> wrap_span 误判"写坏了" -> 回滚 -> 丢旁路
        · 让 _author_tt_key / _strip_ctt 在注释里找到 tooltip 键 -> 逻辑走歪
      这些是死代码，直接删掉最干净（顺带让产物更短）。
    """
    out = []
    for ln in text.split('\n'):
        st = ln.strip()
        # 注释行、且带括号 -> 属于被注释掉的代码 / 括号备注，删
        if st.startswith('#') and ('{' in st or '}' in st):
            continue
        out.append(ln)
    return '\n'.join(out)


def _brace_balance(s):
    """返回 { } 的净差（0 = 平衡）。跳注释和字符串。"""
    depth, n, i = 0, len(s), 0
    while i < n:
        c = s[i]
        if c == '#':
            j = s.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '"':
            j = s.find('"', i + 1)
            i = (j + 1) if j > 0 else (i + 1)
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return depth


def find_blocks(text):
    """top level 'name = {' blocks"""
    out = []
    for m in re.finditer(r'(?m)^([a-zA-Z_0-9._\-]+)[ \t]*=[ \t]*\{', text):
        j = text.index('{', m.start())
        out.append((m.group(1), m.start(), j, brace_close(text, j)))
    return out


def is_monument(block):
    return bool(re.search(r'(?m)^\s*type\s*=\s*monument\s*$', block))


WRAP_KEYS = ['can_use_modifiers_trigger', 'can_upgrade_trigger', 'keep_trigger']

TT = 'AMR_monument_bypass_tt'

TT_LOCK = 'AMR_hidden_locked_tt'


def find_spans(text, key, line_start_only=True):
    """all '<indent>key = {' spans -> [(indent, open_idx, close_idx)]"""
    pat = (r'(?m)^([\t ]*)' + key + r'[ \t]*=[ \t]*\{' if line_start_only
           else r'([\t ]*)' + key + r'[ \t]*=[ \t]*\{')
    out = []
    for m in re.finditer(pat, text):
        bo = text.index('{', m.start())
        bc = brace_close(text, bo)
        if bc > bo:
            out.append((m.group(1), bo, bc))
    return out


def non_nested(spans):
    """keep only the outermost spans (spans are in ascending order)"""
    out = []
    for sp in spans:
        if out and sp[1] <= out[-1][2]:
            continue
        out.append(sp)
    return out


def depth1_span(block, key):
    """first '<key> = {' that sits at depth 1 inside block"""
    depth, pos = 0, 0
    for ln in block.split('\n'):
        code = re.sub(r'#[^\n]*', '', ln)
        if depth == 1:
            m = re.match(r'([\t ]*)' + key + r'\s*=\s*\{', ln)
            if m:
                bo = pos + ln.index('{', m.start())
                return m.group(1), bo, brace_close(block, bo)
        depth += code.count('{') - code.count('}')
        pos += len(ln) + 1
    return None


def empty_inner(inner):
    t = re.sub(r'#[^\n]*', '', inner)
    return re.sub(r'[{}\s]', '', t) == ''


def bypass_branch(indent):
    """玩家专属旁路：这件奇观的主人是玩家（ai = no）-> 判断直接通过。
    没有任何开关、不需要点任何决议，装上就生效；AI 永远不满足。"""
    return (indent + '\tcustom_trigger_tooltip = {\n'
            + indent + '\t\ttooltip = ' + TT + '\n'
            + indent + '\t\towner = { ai = no }\n'
            + indent + '\t}\n')


def _depth1_if(inner):
    """在触发器文本里找【第一层】的 `if = {`，返回 (start, brace_open, brace_close)。

    只认第 1 层的（不在任何子块里）——嵌套的 if 由递归处理。
    """
    i, n, depth = 0, len(inner), 0
    while i < n:
        c = inner[i]
        if c == '#':
            j = inner.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '"':
            j = inner.find('"', i + 1)
            if j > 0:
                i = j + 1
                continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and c == 'i' and inner.startswith('if', i):
            k = i + 2
            while k < n and inner[k] in ' \t':
                k += 1
            if k < n and inner[k] == '=':
                k += 1
                while k < n and inner[k] in ' \t':
                    k += 1
                if k < n and inner[k] == '{':
                    bo = k
                    d, j = 0, k
                    while j < n:
                        if inner[j] == '{':
                            d += 1
                        elif inner[j] == '}':
                            d -= 1
                            if d == 0:
                                return i, bo, j
                        j += 1
                    return None
        i += 1
    return None


def _child(block, key):
    """取块里第一层的 `key = { ... }` 内容（不含花括号）；没有返回 None。"""
    i, n, depth = 0, len(block), 0
    while i < n:
        c = block[i]
        if c == '#':
            j = block.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and block.startswith(key, i):
            k = i + len(key)
            while k < n and block[k] in ' \t':
                k += 1
            if k < n and block[k] == '=':
                k += 1
                while k < n and block[k] in ' \t':
                    k += 1
                if k < n and block[k] == '{':
                    d, j = 0, k
                    while j < n:
                        if block[j] == '{':
                            d += 1
                        elif block[j] == '}':
                            d -= 1
                            if d == 0:
                                return block[k + 1:j]
                        j += 1
                    return None
        i += 1
    return None


def _match_brace(text, open_pos):
    """返回 text[open_pos] 那个 '{' 对应的 '}' 位置；不匹配返回 -1。"""
    d, j, n = 0, open_pos, len(text)
    while j < n:
        c = text[j]
        if c == '#':
            k = text.find('\n', j)
            if k < 0:
                return -1
            j = k
        elif c == '"':
            k = text.find('"', j + 1)
            if k > 0:
                j = k
        elif c == '{':
            d += 1
        elif c == '}':
            d -= 1
            if d == 0:
                return j
        j += 1
    return -1


def _scan_blocks(text, pos):
    """从 pos 起读一个 `{ ... }`，返回 (内容, 开括号位, 结束花括号位)。"""
    n = len(text)
    while pos < n and text[pos] in ' \t\r\n':
        pos += 1
    if pos >= n or text[pos] != '{':
        return None, -1, -1
    d, j = 0, pos
    while j < n:
        if text[j] == '{':
            d += 1
        elif text[j] == '}':
            d -= 1
            if d == 0:
                return text[pos + 1:j], pos, j
        j += 1
    return None, -1, -1


def _find_keyword(text, kw, start=0, any_depth=False):
    """找 `kw =`，返回 (键名起点, 开括号位, 结束花括号位)；找不到返回 (-1, -1, -1)。

    any_depth=False（默认）：只找第一层（不在任何花括号内）。
    any_depth=True：任意深度都算 —— **必须是这个**才能展开嵌套 if。
      以前只找第一层，嵌套 if（外层 else 里又套一个 if，bran_castle 就是）
      永远找不到 -> 反复展开也展不开 -> 那几件的"奖励解锁"永久丢失。
      找到的是【最左边】的那个，所以配外层循环逐层剥掉。
    """
    i, n, depth = start, len(text), 0
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            i = n if j < 0 else j
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
            if depth < 0:
                return -1, -1, -1
        elif (any_depth or depth == 0) and text.startswith(kw, i):
            k = i + len(kw)
            if k < n and text[k] not in ' \t=\r\n':
                i += 1
                continue
            while k < n and text[k] in ' \t':
                k += 1
            if k < n and text[k] == '=':
                body, bo, bc_ = _scan_blocks(text, k + 1)
                if body is not None:
                    return i, bo, bc_
        i += 1
    return -1, -1, -1


def flatten_if(inner, _d=0):
    """把触发器里的 `if = { limit = L  然后 T }  else = { E }` 展开成等价布尔式。

    ★ 语义（EU4 触发器里的 if）：
        if = { limit = L  T }              ≡  AND = { L  T }
        if = { limit = L  T } else = { E } ≡  OR = { AND = { L  T }
                                                     AND = { NOT = { L }  E } }
      原版自己就这么写（common/great_projects/01_monuments.txt:11225、12818）。

    ★ 为什么必须展开：要给触发器套
        OR = { <原内容>  custom_trigger_tooltip = { ... owner = { ai = no } } }
      加"玩家无条件通过"的旁路（也就是"奖励解锁"）。
      if/else **不能**直接并进 OR —— 直接并会让整个条件对玩家恒成立，
      把作者的地域/条件限制全抹掉（用户 2026-10-03 报的"随处可建 + 升到三级还能升"）。
      展开成 AND/OR/NOT 之后，旁路并进去才安全，奖励解锁也回来了。

    ★ L / T / E 三段【原文照搬】，只做位置拼接，不重新排版
      （重排过一次，缩进和括号全乱，不再犯）。
    limit 是普通键、不是控制流，绝不递归进去改。
    展开不了就原样返回，绝不写坏。
    """
    if _d > 8 or not inner.strip():
        return inner
    ii, ibo, ibc = _find_keyword(inner, 'if', any_depth=True)
    if ii < 0:
        return inner
    body = inner[ibo + 1:ibc]
    li, lbo, lbc = _find_keyword(body, 'limit')
    if li < 0:
        return inner                      # 没有 limit 的 if 不认，原样放过
    L = body[lbo + 1:lbc].strip()
    T = (body[:li] + body[lbc + 1:]).strip()
    if not L or not T:
        return inner
    # if 之后紧跟的 else
    tail = inner[ibc + 1:]
    m = re.match(r'[ \t\r\n]*else[ \t]*=', tail)
    Etxt = None
    after = tail
    if m:
        eb, ebo, ebc = _scan_blocks(tail, m.end())
        if eb is not None:
            Etxt = eb.strip()
            after = tail[ebc + 1:]
    if Etxt:
        rep = ('OR = {\n'
               'AND = {\n' + L + '\n' + T + '\n}\n'
               'AND = {\nNOT = {\n' + L + '\n}\n' + Etxt + '\n}\n'
               '}')
    else:
        rep = 'AND = {\n' + L + '\n' + T + '\n}'
    return inner[:ii] + rep + after


def _has_if(inner):
    """原触发器内容里有没有 if / else。

    ★★ 2026-10-03 定位到的严重 bug ★★
    很多 mod 的 build_trigger / can_upgrade_trigger / can_use_modifiers_trigger
    是用 `if = { limit = {...} ... } else = { ... }` 写的（源 mod 全机 590 处、
    我们生成的 200 件里 146 件）。
    **if / else 是【效果】语法，在触发器里不成立** —— 引擎不把它当真触发器。

    原来的 wrap_span 把整段原内容塞进 `OR = { <原内容> <玩家旁路> }`，
    结果 OR 里只剩 `custom_trigger_tooltip = { owner = { ai = no } }` 一个
    真触发器 -> **对玩家【恒成立】**：
      · build_trigger 恒成立  -> 任意省份都能建（"到处崇武城"）
      · can_upgrade_trigger 恒成立 -> 升级条件失效（"升到三级还能升、升级完不成"）
    实际受害：CE_chongwu_city / CE_amber_palace 等 146 件。

    所以：**原内容里有 if 的，一律不套 OR**，保持作者原样（少一个 tooltip 换正确性）。
    """
    return re.search(r'(?m)^[ \t]*if[ \t]*=', inner) is not None


def _author_tt_key(body):
    """从作者原内容里提出他用的 tooltip 键（第一个 custom_trigger_tooltip 的 tooltip=）。

    用途：把它放进玩家分支当【显示文本】，这样玩家悬停时能看到作者写的条件说明，
    而不是只剩我们那句 "not ai"。
    （wiki: custom_trigger_tooltip 会把内部触发器对玩家隐藏，只显示 tooltip= 那句。）
    取不到就返回 None，调用方退回 always = yes。
    """
    m = re.search(r'custom_trigger_tooltip\s*=\s*\{[^}]*?tooltip\s*=\s*([A-Za-z_0-9.\-]+)',
                  body, re.S)
    if not m:
        return None
    key = m.group(1)
    # 别把我们的旁路键再套一层
    if key == TT or key.startswith('AMR_'):
        return None
    return key


def _unwrap_author_tt(body):
    """把作者的 custom_trigger_tooltip 外壳剥掉，只留里面的条件。

        custom_trigger_tooltip = { tooltip = X   <条件> }   ->   <条件>

    反复剥（可能嵌套）。tooltip= 那行是显示文字，不是条件，丢掉。
    """
    for _ in range(8):
        m = re.search(r'custom_trigger_tooltip\s*=\s*\{', body)
        if not m:
            break
        q = body.index('{', m.start())
        e = brace_close(body, q)
        if e < q:
            break
        inner = body[q + 1:e]
        # 去掉 tooltip = X 那一行（含行尾空白）
        inner = re.sub(r'(?m)^[ \t]*tooltip[ \t]*=[ \t]*[A-Za-z_0-9.\-]+[ \t]*\r?$',
                       '', inner)
        body = body[:m.start()] + inner + body[e + 1:]
    return body


def _strip_ctt(body):
    """去掉作者内容里所有 custom_trigger_tooltip 的【壳】，只留里面的条件。

    我们的新写法会统一在外面再包一层 custom_trigger_tooltip，
    所以必须先剥掉作者原有的壳，否则会套成 tooltip 里再套 tooltip。

    壳里只有 tooltip 没有其他条件的（纯显示对象）：剥完剩下空字符串，
    调用处会保留一个空 body 的壳（结构不变、不影响判定）。
    """
    out = body
    for _ in range(12):
        m = re.search(r'custom_trigger_tooltip\s*=\s*\{', out)
        if not m:
            break
        q = out.index('{', m.start())
        e = brace_close(out, q)
        if e < q:
            break
        inner = out[q + 1:e]
        inner = re.sub(r'(?m)^[ \t]*tooltip[ \t]*=[ \t]*[A-Za-z_0-9.\-]+[ \t]*\r?$',
                       '', inner)
        out = out[:m.start()] + inner + out[e + 1:]
    return out


def _visible_condition(body):
    """提一段【给玩家看】的作者原条件（会渲染成本地化文字）。

    三种情况：
      · 作者写了 if/else：取 if 分支里除 limit 之外的部分（那是"达成条件"）
      · 纯裸条件：整段就是
      · 作者用了 custom_trigger_tooltip：返回 None（由 _author_tt_key 那条路处理，
        他自己那句 tooltip 已接管显示，外面再挂原文会重复且误导）
    """
    # ★ 选项 B：先把作者的 custom_trigger_tooltip 外壳剥掉。
    #   作者写 custom_trigger_tooltip = { tooltip = X  <条件> }，本意是"条件藏起来、
    #   只显示一句提示"。用户要求看到【实际条件】，所以这里把壳剥了、只留条件
    #   （tooltip= 那行丢掉，它是显示文字不是条件）。
    #   对玩家分支做这件事是安全的：玩家分支里已有恒真旁路项，摊开的条件只负责显示。
    # ★ 去掉注释行：作者常把旧版条件整段 # 掉，注释里还带 custom_trigger_tooltip
    #   和括号，留着会让正则误判、玩家也只看到一堆注释。注释是给作者看的。
    #   （AI 分支仍保留原文含注释，一个字节不动。）
    body = re.sub(r'(?m)^[ \t]*#[^\n]*\r?$', '', body)
    body = _unwrap_author_tt(body)
    if not body.strip():
        return None
    m = re.search(r'(?m)^([ \t]*)if[ \t]*=[ \t]*\{', body)
    if not m:
        t = body.strip()
        return t or None
    q = body.index('{', m.start())
    e = brace_close(body, q)
    if e < q:
        return None
    inner = body[q + 1:e]
    # 去掉 limit = { ... }
    ml = re.search(r'(?m)^([ \t]*)limit[ \t]*=[ \t]*\{', inner)
    if ml:
        lq = inner.index('{', ml.start())
        le = brace_close(inner, lq)
        if le > lq:
            inner = inner[:ml.start()] + inner[le + 1:]
    return inner.strip() or None


def wrap_span(text, key, bo, bc, indent, stats, tag):
    """给触发器加"玩家无条件通过"的旁路（= 奖励解锁）。

    ★ 用户 2026-10-03 定的最终做法：**在最外面套一层 if/else**，不动原内容一个字节。

        ORIG = { <原触发器内容> }        （无论里面是 if/else 还是纯 AND/OR）

        结果 = {
            if   = { limit = { owner = { ai = no } }   <原触发器内容> }   ← 人类玩家：直通
            else = { <原触发器内容> }                                    ← AI：走作者原条件
        }

      工具提示放在外面（custom_trigger_tooltip），保证悬停能看到"不是 AI"。

    ★ 为什么换成这个（血的教训）：
      以前的做法是"把原内容展开成 AND/OR/NOT，再套 OR = { 原内容 玩家旁路 }"。
      展开这条路我写坏了三次：
        · 括号失配（8175/8438）—— 展开改变长度却用旧位置切，把后面的键整段削掉
        · 拼接少补一个 } —— _match_brace 永远找不到匹配，整批放弃
        · 嵌套 if 展不开（bran_castle 那种 else 里又套 if）—— 那几件的奖励解锁永久丢失
      外层套 if/else 只动一处、原内容原样搬运，没有这些问题。
      （两种写法语义等价：玩家必过；AI 在 if 里不满足 -> 落到 else -> 原条件。）

    ★ build_trigger 不走这里 —— 它由 amr_rules.human_only_build() 处理
      （那条是"仅人类玩家 + 仅首都"两条硬条件，不是旁路）。
    """
    inner = text[bo + 1:bc]
    # ★ 作者的 tooltip 键要在【删注释之前】就取出来。
    #   作者那句 tooltip 常常写在被注释掉的旧条件里（#tooltip = xxx），
    #   删注释后再取就取不到了，会退化成我们自己的 AMR 键 ->
    #   玩家在游戏里看到 "not ai" 而不是作者那句条件说明
    #   （实测 parthenon / Athens_Vouli / Buckingham_Palace 等一大批）。
    _auth_key_early = _author_tt_key(inner)
    # ★ 再删掉整段注释掉的代码（死代码；且 EU4 会把注释里的括号当真括号，
    #   留着会打乱平衡判断）。
    inner = _drop_commented_blocks(inner)
    if empty_inner(inner):
        stats['empty_' + tag] += 1
        return text
    # ★ 幂等：已经加过玩家分支的直接返回。
    #   三种形态都可能出现：
    #     B) 外层 custom_trigger_tooltip 带 TT
    #     A) if = { limit = { owner = { ai = no } } custom_trigger_tooltip ... }
    #     C) if = { limit = { owner = { ai = no } } owner = { ai = no } <作者条件> }
    #   A/C 里【没有 TT】，只查 TT 会重复处理（第二次跑把分支再套一层）。
    if re.search(r'limit\s*=\s*\{\s*owner\s*=\s*\{\s*ai\s*=\s*no\s*\}\s*\}', inner):
        stats['dup_' + tag] += 1
        return text
    if TT in inner:
        stats['dup_' + tag] += 1
        return text
    body = inner.strip('\n')
    if not body:
        stats['empty_' + tag] += 1
        return text
    # 原内容缩进一级；空行保持空
    lines = body.split('\n')
    body_i = '\n'.join((indent + '\t\t' + l) if l.strip() else l for l in lines)
    i1 = indent + '\t'
    i2 = indent + '\t\t'
    # == 2026-10-04 修：玩家分支必须【无条件通过】 ==
    # 以前这里把 body_i（作者原条件）也塞进了 if 分支，语义变成
    # "是玩家【而且】满足作者条件" -> 作者条件不满足的奇观对玩家完全失效。
    # 实测：威尼斯 1444 档，君士坦丁堡（省 151）的 hagia_sophia 等
    # 宗教条件不满足 -> 加成全没了。
    # 正确语义：if（是玩家）-> always = yes 直通；else（AI）-> 作者原条件。
    # == 2026-10-04 修（第二轮）：玩家分支要保留作者那句 tooltip 的【显示】 ==
    # wiki: custom_trigger_tooltip "Hides the enclosed trigger ... cannot be
    # seen by human players and displays the specified tooltip in its place."
    # 也就是玩家看到什么，完全由 tooltip= 那句本地化文本决定。
    # 上一版玩家分支写 always = yes -> 恒真 -> EU4 认为无条件可显示 ->
    # 提示空白，只剩最外层那句 "not ai"，作者写的条件说明（如
    # hagia_sophia_tt "本省宗教必须是天主教/东正教/科普特或穆斯林组"）全丢。
    # 这里把作者的 tooltip 提进玩家分支当显示用，判定仍无条件通过。
    # ══════════════════════════════════════════════════════════════════
    # 照抄 mod 3050177747（All Monuments for Player）的写法。
    # 它的 OR 结构保证：
    #   · 第 1 项 custom_trigger_tooltip 里是【恒真】条件（玩家不是 AI）
    #     -> 整个 OR 立即为真 -> 效果必生效
    #   · 作者原条件放在第 2 项 AND 里的【单一 custom_trigger_tooltip】中
    #     -> 它的语义是"包住的条件生效但玩家看不到、改显示那句子"
    #     -> 作者条件【不会】被裸求值，不会卡死效果（我之前就是踩这里）
    #   · OR 的两项都会渲染，玩家看得到解锁提示 + 作者那句提示
    # 我们的唯一改动：把 has_country_flag = Harmony_enabled_... 去掉，
    # 只用 ai = no（不需要玩家再点一次决议开关）。
    # ══════════════════════════════════════════════════════════════════
    # 去掉作者内容里已有的 custom_trigger_tooltip 壳（后面统一重新包一层），
    # 免得套出"tooltip 里再套 tooltip"。壳里若没有条件（纯 tooltip 对象），
    # 那句文本保留在一个空 body 的壳里，结构不变、不影响判定。
    _key2 = _auth_key_early
    _body2 = _strip_ctt(body)
    _body2_i = '\n'.join((i2 + '\t\t' + l) if l.strip() else l
                        for l in _body2.strip('\n').split('\n'))
    # ── 作者分支：分两种情况 ────────────────────────────────────────
    # 作者写了 tooltip -> 套壳显示他那句（尊重作者原意）
    # 作者没写（裸条件）-> 不套壳，让条件自己渲染成本地化文字
    if _key2:
        _author_branch = (i2 + 'AND = {\n'
                          + i2 + '\tcustom_trigger_tooltip = {\n'
                          + i2 + '\t\ttooltip = ' + _key2 + '\n'
                          + _body2_i + '\n'
                          + i2 + '\t}\n'
                          + i2 + '}\n')
    else:
        _author_branch = (i2 + 'AND = {   # AMR: author condition (display only)\n'
                          + _body2_i + '\n'
                          + i2 + '}\n')
    new = ('\n'
           + i1 + 'OR = {\n'
           + i2 + 'custom_trigger_tooltip = {\n'
           + i2 + '\ttooltip = ' + TT + '\n'
           + i2 + '\towner = { ai = no }'
           + '   # AMR: player bypass (not AI)\n'
           + i2 + '}\n'
           + _author_branch
           + i1 + '}\n' + indent)
    stats['wrapped_' + tag] += 1
    out = text[:bo + 1] + new + text[bc:]
    # ★★ 2026-10-04 修：平衡检查要【跳注释和字符串】再数。
    #   朴素计数不跳注释 —— 源文件里只要有一行注释带 }（实测：
    #   `has_owner_accepted_culture = yes\t#已接受当地文化}`），
    #   左右就不相等 -> 被误判成"我写坏了" -> 回滚 -> 玩家旁路丢失。
    #   后果：[1.34]增加全球奇观 的 Ali_Qapu_Palace 加成对玩家完全失效。
    if _brace_balance(out) != 0:
        stats['wrap_bad_' + tag] += 1
        return text
    return out
def wrap_top_level(block, key, stats):
    span = depth1_span(block, key)
    if span is None:
        stats[key + '_absent'] += 1
        return block
    indent, bo, bc = span
    return wrap_span(block, key, bo, bc, indent, stats, key)


def inject_gate_at(text, bo, bc, indent, stats):
    """把 text[bo..bc] 的里面（空块）直接写成玩家门禁"""
    stats['inj_empty'] += 1
    return text[:bo + 1] + '\n' + bypass_branch(indent) + indent + text[bc:]


def inject_gate(block, key, stats):
    """这个奇观在源文件里【没有】要求判断 —— 键不存在，或者块是空的。
    原版含义就是"谁都能用"，所以 AI 也照样吃得到，这正是"其他国家也生效"的来源。
    这里给它补一道玩家门禁；有内容的块返回 None，交给正常的 OR 套法。"""
    span = depth1_span(block, key)
    if span is not None:
        indent, bo, bc = span
        if not empty_inner(block[bo + 1:bc]):
            return None
        return inject_gate_at(block, bo, bc, indent, stats)
    m = re.search(r'(?m)^([\t ]*)type[ \t]*=[ \t]*monument[ \t]*$', block)
    if not m:
        return None
    indent = m.group(1)
    ins = ('\n' + indent + key + ' = {\n' + bypass_branch(indent) + indent + '}')
    stats['inj_new'] += 1
    return block[:m.end()] + ins + block[m.end():]


def wrap_or_inject(block, key, stats):
    """有要求判断 -> 外面套 OR 加一条玩家分支；没有要求判断 -> 补一道玩家门禁"""
    r = inject_gate(block, key, stats)
    if r is not None:
        return r
    return wrap_top_level(block, key, stats)


def wrap_conditional_modifiers(block, stats):
    """conditional_modifier 的 trigger = "达成奖励"的触发条件。
    有内容就套 OR 加玩家分支；空的 trigger = 永远成立 = 奖励对所有人生效，
    所以也换成玩家门禁。"""
    outer = non_nested(find_spans(block, 'conditional_modifier'))
    stats['cm_found'] += len(outer)
    for indent, bo, bc in reversed(outer):
        sub = block[bo:bc + 1]
        trig = non_nested(find_spans(sub, 'trigger'))
        if not trig:
            stats['cm_no_trigger'] += 1
            continue
        newsub = sub
        for t_indent, tbo, tbc in reversed(trig):
            inner = newsub[tbo + 1:tbc]
            if empty_inner(inner):
                stats['cm_empty_trigger'] += 1
                if TT not in inner:
                    newsub = inject_gate_at(newsub, tbo, tbc, t_indent, stats)
                continue
            if TT in inner:
                continue
            newsub = wrap_span(newsub, 'trigger', tbo, tbc, t_indent, stats, 'conditional_modifier')
        block = block[:bo] + newsub + block[bc + 1:]
    return block


def _move_locked():
    """move=ai 时 can_be_moved 一律锁 no；keep 由 make_movable 提前原样返回。"""
    return str(MAKE_MOVE).lower() == 'ai'


def make_movable(block, stats, name=''):
    """搬运开关。can_be_moved 是【定义层】，而且引擎不读里面的条件 ——
    没有任何写法能做到"只有玩家能搬、AI 不能"，所以只有三档：

      keep（1.3 默认）can_be_moved / move_days 原样返回
        只解除使用限制，不解除作者写好的搬运限制。

      raw（老行为）can_be_moved = no -> yes
        谁都能在省份面板里按「移动」把奇观搬走，含 AI。

      ai can_be_moved 一律写死 no
        谁都按不了那个按钮（AI 也就搬不动了）；1.3 不再生成额外搬迁决议。

    三种模式都由 config.txt 的 move= 选（keep / raw / ai）。

    ★ 2026-11-18（1.3）：通路 / 地下城类（KEEP_UNMOVABLE 名单）**永远锁 no**，
      不受 move= 影响 —— 矮人隧道、升降机、妖精传送门、地下城入口、原版三条运河
      搬了会把地图通路断开或让地牢探索失效。想放开：config.txt 写 keepunmovable=no。
    """
    # 键名优先用 transform_block 传进来的 name；直接调用的测试块可能带 `key = {` 前缀。
    # keep 只对名单外的奇观原样返回；名单内仍然强制 no（1.3 的“永远不可搬”）。
    _km = re.match(r'\s*([A-Za-z_0-9.\-]+)\s*=\s*\{', block)
    _key = name or (_km.group(1) if _km else '')
    _keep_still = bool(MAKE_KEEP_UNMOVABLE) and _key in KEEP_UNMOVABLE
    _mode = str(MAKE_MOVE).lower()
    if _mode == 'keep' and not _keep_still:
        return block        # keep：名单外，can_be_moved 原样保留
    locked = _keep_still or _mode != 'raw'
    pat = r'(?m)^([\t ]*can_be_moved[ \t]*=[ \t]*)(yes|no)(?=[ \t]*(?:#|\r|$))'
    want = 'no' if locked else 'yes'
    other = 'yes' if locked else 'no'

    def _sub(m):
        if m.group(2) == want:
            return m.group(0)
        stats['cbm_yes' if not locked else 'cbm_locked'] += 1
        return m.group(1) + want

    new, n = re.subn(pat, _sub, block)
    if n:
        return new
    if re.search(r'(?m)^[\t ]*can_be_moved[ \t]*=', block):
        return block
    m = re.search(r'(?m)^([\t ]*)type[ \t]*=[ \t]*monument[ \t]*$', block)
    if m:
        stats['cbm_added' if not locked else 'cbm_locked'] += 1
        return (block[:m.end()] + '\n' + m.group(1) + 'can_be_moved = ' + want
                + block[m.end():])
    return block

# ---------------------------------------------------- 奇观块内合法的键（白名单）



def _clean(ln):
    return re.sub(r'#[^\n]*', '', ln)


def _leaked_at(ln):
    """这一行是不是"掉在块外的判断语句"：深度 1 的位置出现了不是奇观键的名字"""
    if not ln.strip():
        return False
    m = re.match(r'[\t ]*([A-Za-z_0-9.\-]+)[ \t]*[={]', ln)
    return bool(m) and m.group(1) not in KNOWN_KEYS


def scan_leaked(block):
    """列出这个奇观块里"掉在块外"的判断语句行号（块内行号）"""
    out, depth = [], 0
    for n, ln in enumerate(block.split('\n')):
        if depth == 1 and _leaked_at(ln):
            out.append((n, ln.strip()))
        depth += _clean(ln).count('{') - _clean(ln).count('}')
    return out


def repair_leaked_lines(block, stats):
    """有的作者把 can_upgrade_trigger = { 提前闭合了，紧跟其后的判断语句就掉到
    块外面 —— 游戏会报 "Unexpected token: culture_group ... Last good read:
    can_upgrade_trigger={" 并把它们丢掉（[1.34]增加全球奇观 的
    The_Towns_of_Edinburgh 就是这样）。这里把这种行搬回前面那个空块里。

    这是整个脚本里唯一一处"搬移行"的改动，所以改完会和源文件逐行核对。"""
    lines = block.split('\n')
    out, i, depth = [], 0, 0
    while i < len(lines):
        if depth == 1 and _leaked_at(lines[i]):
            run, j = [], i
            while j < len(lines) and _leaked_at(lines[j]):
                run.append(lines[j])
                j += 1
            k = len(out) - 1
            while k >= 0 and not out[k].strip():
                k -= 1
            if (len(run) and k >= 1
                    and re.match(r'[\t ]*\}[\t ]*$', out[k])
                    and re.match(r'[\t ]*[A-Za-z_0-9.\-]+[ \t]*=[ \t]*\{[ \t]*$', out[k - 1])
                    and not out[k - 1].lstrip().startswith('#')):
                out = out[:k] + run + [out[k]]
                stats['moved_in'] += len(run)
                i = j
                continue
            stats['leaked_left'] += len(run)
        out.append(lines[i])
        depth += _clean(lines[i]).count('{') - _clean(lines[i]).count('}')
        i += 1
    return '\n'.join(out)

TOKEN_RE = re.compile(r'"[^"]*"|[{}]|=|[^\s{}=]+')


def tokens(text):
    return collections.Counter(TOKEN_RE.findall(re.sub(r'#[^\n]*', '', text)))
