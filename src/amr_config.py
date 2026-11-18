"""AMR 生成器 · 小开关与 config.txt

开关默认值 + config.txt 覆盖（两个"解禁"bat 改的就是这里）。
别的模块用 from amr_config import * 取开关值。
"""

import os
import re
import sys

from amr_env import CFGDIR, HERE, _cfg_path


# ======================================================================
# ==================== 小 开 关（这里只是默认值）======================
# ======================================================================
# 三种改法，优先级从低到高：
#   1) 什么都不动  -> 就用下面这些默认值
#   2) 双击 解禁无省份奇观.bat / 解禁年份未到奇观.bat
#      -> 各改自己管的键，结果写进同目录的 config.txt（推荐，最省事）
#   3) 直接编辑 config.txt -> 一行一个 名字=值；写了的键会盖掉这里的默认值
# 也就是说：某个键在 config.txt 里【有】，就以它为准；没有就用这里的值。
# 每次跑生成器，日志第一段会写明"小开关: config.txt（N 项…）"还是"脚本默认值"。
# 手改 config.txt 记得按 UTF-8 存（生成器也认 BOM）。
# ======================================================================

# 游戏升级大版本后，如果启动器提示版本不匹配，把这里改成 '1.38.*'
SUPPORTED = '1.37.*'
TOOL_NAME = '全奇观解锁并搬迁 All Monuments Unlocked & Movable (Generator)'
# 是否顺便生成"原版奇观版"（只含游戏本体奇观、可公开分享给没装奇观 mod 的人）。
# 默认 False：只用生成器做按播放集定制的那一份就够了，mod 文件夹里也少一个容易搞混的文件夹。
MAKE_GENERIC = False
# 只做"原版奇观版"，完全不去动按播放集定制的那一份（True 时上面那项自动生效）
MAKE_ONLY_GENERIC = False
# 也更新 mod/AMR_generator 那个"生成器自己"的上传包（平时保持 False）
MAKE_PKG = False
# 默认修"奇观没写所属省份(start)"的问题（否则这类隐藏奇观会到处都能建）。
# 想保持原样：False
MAKE_NOSTARTFIX = True
# 是否把奇观钉回"只在自己所属的省份能建"。
# 默认【关】：CE 王朝这类 mod 是故意允许"有 great_project_ideas 理念组的国家
# 在任意省份建造"的，属于作者设计，生成器不去动它。
MAKE_STRICTBUILD = False
# 【隐藏奇观锁】把"建造条件被作者写成空的"奇观按年份锁上。
# 背景（EU4 官方 wiki · Great project modding）：
#   date = 历史上建成的年份 —— 开局日期早于它，这件奇观就还不该在图上；
#   build_trigger 才是"能不能手动建"的开关，留空 = 谁占着这个省谁就能建。
# 两者碰上就是：风云世纪两千年那种 1460~1788 年才该出现、开局却已经能建的"隐藏奇观"。
# 原版 1444 开局没有这个问题：原版 52 个空条件奇观的 date 全都在 1444 之前，开局就已经在了。
#
# 【默认做法 = 按各自 date 解锁】给这类奇观补一句
#     custom_trigger_tooltip = { tooltip = ... owner = { is_year = <它自己的 date 年份> } }
# 也就是"年份没到就建不了，年份到了就自动能建"。好处是【与开局年份无关】：
# 风云的时间跨度两千多年（能开局于公元 2 年，也能开局于 1392 / 1444 / 近代），
# 写死一个年份（比如 1444）在早期开局里会漏掉一大批，写太早又会把本该有的也锁掉；
# 按 date 走则由引擎按当前年份自己判断，任何开局都自动对得上。
# 被锁期间只是【不能手动建】，原 mod 用事件/决议/任务发放的照旧不受影响。
#
# 取值（写在上面那个等号右边）：
#   'date'  = 按各自 date 解锁（默认，推荐；风云这种长跨度 mod 就靠它）
#   'all'   = 永远锁死（always = no，任何年份都建不了，连没写 date 的也锁）
#   '1392'  = 老做法：把 date 晚于 1392 的那些写死成 always = no
#   ''      = 不锁，完全按原 mod 来（尊重作者原样）
MAKE_LOCKOPEN = 'date'
# 【隐藏奇观的加成】没有 start 的那些"隐藏奇观"（原神的新艾利都 / 星穹列车 / NXX 基地、
# 更多决议与修正的"伟大奇观"等）本来就是靠原 mod 的事件/决议用 add_great_project
# 塞给你的，而且不少数值是爆炸级的。这一档让它们【默认不给加成】：
#   can_use_modifiers_trigger 里塞一句 always = no ⇒ 这件奇观对谁都不产生效果，
#   同时也不再给它加"玩家无条件生效"的旁路（conditional_modifier 也不动）。
#   奇观本体还在，原 mod 的事件照跑，地图上照样看得见，只是白板。
# 想恢复（玩家吃满 + 可搬运）：改成 'yes'，再跑一次生成器。
#   'no'  = 关掉全部"没有 start 的隐藏奇观"的加成（默认）
#   'agp' = 只关"确实是靠 add_great_project 发放"的那些（最保守）
#   'yes' = 都不关（保持原样 / 以前的行为）
# 注：原版只有三条运河用 add_great_project，而运河都有 start，天生不在这批里。
MAKE_HIDDENBONUS = 'no'     # 'no' / 'agp' / 'yes'
# 默认每个奇观文件都用【和源 mod 完全相同的文件名】。
# 依据 EU4 官方 wiki（Mod structure 页）：同一个文件路径只加载一份，谁赢看 mod
# 名字的字母序（名字靠前的覆盖靠后的），启动器里排第几没用。同名 ⇒ 源 mod 那份
# 不被加载 ⇒ 每件奇观只有一个定义，不会出现"两个一样的/建完就消失"。
# 所以本 mod 的显示名和文件夹都带一个靠前的 ASCII 前缀（见 NAME_PREFIX），
# 靠"名字排最前"取胜，而不是靠改文件名。
# 想退回"改名副本"的老做法排错：SAME_NAME = False、ALIAS_ONLY = True（只带 00_amr_ 副本，
# 会和源 mod 重复）；两个都 False 是两种都带（重复得更厉害）。
SAME_NAME = True
ALIAS_ONLY = False
# 默认：每个播放集各生成一份独立 mod（互不覆盖），文件夹带播放集后缀。
# 想退回"只有一份、每次按当前播放集覆盖"：False
MAKE_MULTI = True

# --- 建造花费 / 建造时间 折扣 ------------------------------------------------
# 这两个字段（build_cost、time = { months = N }）是【定义层】：
# 引擎只在加载 common/great_projects 时读一次，之后改不了 —— EU4 的修正器列表里
# 只有【升级】有 great_project_upgrade_cost / great_project_upgrade_time，
# 【建造】没有任何修正器（exe 里搜 build_cost 只有建筑/单位那套）。
# 所以决议、事件、修正器都改不了它们，只能在这里生成时写进去。
# 取值 = 打掉百分之几：'90' = 打一折，'100' = 完全免费/瞬间，'0'/''/'no' = 不动。
# 只影响【原值大于 0】的那些：原版 187 件里 621 件本来就是 build_cost = 0、
# 683 件本来就是 months = 0，那些不动（动了也只是把 0 写成 0）。
# 现在是 90：1000 杜卡特 -> 100，120 个月 -> 12 个月。
MAKE_BUILDCOST = '90'       # '0'~'100'，或 'no' 表示保持原样
MAKE_BUILDTIME = '90'       # 同上

# --- 奇观搬运 ----------------------------------------------------------------
# 2026-11-18 1.3 默认改成 'keep'：只解除使用限制，保留作者原本的搬运限制。
# can_be_moved 是定义层，引擎不读它里面的条件，**没有"只锁 AI"的写法**
# （引擎自己的 subject_types 里 can_have_great_projects_moved_by_overlord
#  就是给朝贡设的，跟玩家/AI 无关）；要单独限制 AI 用 aimove=yes 的外部 defines。
#   'raw' = 全部 can_be_moved = yes，谁都能在省份面板里搬（含 AI）
#   'ai'  = 全部锁 no（AI 搬不了，玩家也按不了按钮）
#   'keep'= 只解除使用限制：can_be_moved / move_days 原样保留，不解除搬运限制
# 注：曾经做过"玩家专属搬迁决议"（move_great_project），实测点了没反应；
#     也试过 destroy + add_great_project 重建，实测只摧毁成功、重建没成功。
#     两条路都已放弃，见 _交接\10_第二轮交接说明.md 第 4.9/4.10 节。
MAKE_MOVE = 'raw'           # 默认旧行为；要“只解使用限制、不解除搬运限制”就显式写 move=keep
# AI 搬运奇观倾向（定义层外部文件）。aimove=yes 时在产物里写
# common/defines/00_amr_ai_move.lua，把 NAI 的四个 GREAT_PROJECT_DESIRE_*
# 归零：AI 不再想把奇观搬去首都/从附庸搬走。
# 不影响玩家的 can_be_moved；想连玩家一起锁，用 move=ai。
# 本 mod 名以 !AMR 开头，按名字排序在最前，defines 覆盖优先。
MAKE_AI_MOVE = False        # 可选开关：aimove=yes 才写外部 defines，把 AI 搬运倾向归零
# ★ 2026-11-18（1.3）：通路 / 地下城类奇观【永远不可搬】，不受 move= 影响。
#   理由：这些是"地图通路"机制（矮人隧道、升降机、妖精传送门、地下城入口），
#   搬走会把通路断开或让地牢探索失效。原版三条运河（基尔/苏伊士/巴拿马）同理。
#   这份名单来自安本纳尔成品（当年在那里手工改的 35 件，生成器里一直没有）。
#   只在 move=raw（放开搬运）时生效 —— move=ai 本来就全锁。
#   想放开某一件：把它从下面删掉。想全放开：config.txt 里写 keepunmovable=no
MAKE_KEEP_UNMOVABLE = True
KEEP_UNMOVABLE = frozenset((
    # 安本纳尔矮人地下城（anb_dwarovar_dungeons.txt，11 件）
    'runefather_maw',
    'dd_stramolgiv', 'dd_frogarsalforn', 'dd_stunveigryorth', 'dd_wytlramvar',
    'dd_dimlherd', 'dd_grumhardhum', 'dd_leforn', 'dd_rizvambrethar',
    'dd_ofralglarf', 'dd_yidablaerun',
    # 隧道 / 升降机 / 隘道（anb_great_projects.txt 等，18 件）
    'marrhold_dwarovar_tunnel', 'dwarovar_marrhold_tunnel',
    'redrushes_climb', 'spoorland_lift', 'walkway_of_thorns',
    'arca_noruin', 'arca_venaan', 'arbeloch_ascensor', 'the_wormway',
    'godswall_tunnel', 'dwarovar_valley_tunnel', 'valley_dwarovar_tunnel',
    'great_merfolk_canal',
    'zabyostlar_canal', 'kozuurigur_canal', 'stormwall_canal', 'budanphre_canal',
    # 妖精传送门 / 季节门（anb_great_projects.txt，6 件）
    'deepwoods_fey_portal', 'domandrod_fey_portal',
    'domandrod_summer_gate', 'domandrod_spring_gate',
    'domandrod_autumn_gate', 'domandrod_winter_gate', 'domandrod_winter_gate2',
    # 原版三条运河：位置写死，搬了就断海路（原本它们就没有 can_be_moved）
    'kiel_canal', 'suez_canal', 'panama_canal',
))
# 搬迁决议的冷却（天），防止一口气全搬空。
# 决议是【免费】的：没法在生效前可靠判断"到底有没有奇观可搬"
# （has_great_project 是省份域触发器，放进 potential / allow 会报域错误、
#  结果是决议永远不出现），收费的话会出现"点了扣钱但什么都没搬"。
DECISION_MOVE_COOLDOWN = 365
# --- 升级花费 / 升级时间 打折决议（纯 buff，不碰定义层）--------------------
# 奇观的【升级】有修正器：【建造】没有。
#   脚本里实际出现过的 great_project* 修正器只有 6 个：
#     great_project_upgrade_cost / great_project_upgrade_time
#     local_great_project_upgrade_cost / local_great_project_upgrade_time
#     great_project_can_be_built / great_project_can_be_upgraded
#   （exe 里 122 个 great_project* 标识符全扫过；build_cost / build_time 那套
#     属于建筑和单位，跟奇观无关。）
# 所以：升级折扣用决议发 buff（本项）；建造折扣只能在生成时写进定义里
# （见上面 MAKE_BUILDCOST / MAKE_BUILDTIME 和 amr_rules.discount_projects）。
# 原版范本：common\event_modifiers\00_event_modifiers.txt
#   monument_boost     = { great_project_upgrade_cost = -0.25 }
#   talented_architect = { build_time = -0.1  great_project_upgrade_time = -0.1 }
MAKE_UPGRADE_DEC = True
# ★ 1.3.5：默认与一键三级互斥（互斥逻辑在文件末尾）。想要两个都发：config.txt 写 upgdec=force。
UPGRADE_DEC_OFF_BY_TIERDEC = False   # True = 被"一键三级"默认关掉的，不是玩家自己写的 upgdec=no
# ★ 2026-11-18（1.3）新增：**一键三级决议** —— 点一次，你名下所有奇观立刻升到三级。
#   用户 2026-11-18 定的：免费 + 全自动（不收费、无冷却）。
#   实现：原版自带脚本效果 set_great_project_tier_3 = { type = <键名> }，
#   它内部对 tier 0/1/2 都有级联分支，所以【一次调用就能从 0 级直达 3 级】。
#   决议效果体：every_owned_province 里逐个奇观 if 一下（668 个 if 块，约 100 KB）。
#   不想要：config.txt 里写 maxtierdec=no 再跑一次。
MAKE_MAX_TIER_DEC = True
MAKE_UPGRADE_COST = '-0.9'   # 修正器写法：'0' 不动、'-0.9' = 打一折、'-1' = 免费
MAKE_UPGRADE_TIME = '-0.9'   # 同上
# 【start 写法非法】有的 mod 把 start 写成 `start = event_target:XXX_MB`。
# 引擎只认 `start = <省份号>`，解析失败 = 这件奇观【没有所属省份】，
# 于是每个满足 build_trigger 的省份都能建它 —— 这就是"遍地米兰大教堂/
# 崇武城"那一类 bug 的机制（2026-10-01 实查：全机 3196 件里只有
# 「更多决议与修正」的 11 件是这样）。
# 默认 True：给这类奇观补 always = no 挡掉到处可建（不影响 mod 自己用
# add_great_project 发放），并在生成日志里点名。
# 但它靠的省份标记如果真有人应用，就放它一马（那是有意的定位方式）。
# 想保持原样：False
MAKE_BADSTART = True
# 【空 build_trigger 的奇观】build_trigger = { } 的引擎语义是"谁占着这个省谁就能建"，
# 而且【不限省份】。2026-10-03 实测这几件就是这样：
#   cartagena_de_indias / fuerte_del_morro / salvador_da_bahia /
#   royal_palace_caserta / versailles …
# 结果法兰西存档里 cartagena_de_indias 出现在 4 个省、versailles 3 个 ——
# 用户反馈的"卡时间能建造多个"就是它。
# 默认 True：给这类奇观钉回自己的 start 省份，并禁止在一个省建第二件。
# ★ 只动 build_trigger【留空】的；有任何条件的（CE 王朝那类作者有意允许的）不动 ——
#   那个是 MAKE_STRICTBUILD 管的，两者不要混。
MAKE_EMPTYBT_GUARD = True
# 【每距离基础搬运时间】move_days_per_unit_distance。
# ★ 用户 2026-10-03 定的 1.2 功能："把所有奇观每距离基础搬运时间改成 1"。
# 官方公式（EU4 Wiki · Great project § Relocation）：
#     搬迁耗时 = 两省距离 × move_days_per_unit_distance
#     搬迁费用 = 耗时（天） × 3 杜卡特/天
# 所以改成 1 会同时让搬迁【最快、最便宜】（费用与耗时同方向）。
# 这是定义层字段，在游戏内【没法】用事件/决议改 —— 只能生成器统一覆盖。
# 填 '' 或 no = 不动原值；填数字 = 所有奇观统一成那个值。默认 '1'。
MAKE_MOVEDAYS = '1'
# 【重定向到首都】临时奇观（build_trigger 满足条件的省很多 -> 到处重复建）：
#   加 is_capital = yes + owner = { ai = no }，让这件奇观全局只在玩家首都出现一份。
# 用户 2026-10-03 的方案（我先前说"做不到"是错的：build_trigger 里可以用 is_capital）。
# 作用范围：
#   · build_trigger 留空的奇观（那 56 件）        -> guard_one_per_province
#   · build_trigger 用 if/else 写的奇观（那 146 件）-> amr_script.wrap_span
# ★ 只动 build_trigger；升级/加成条件绝对不加地域限制（那会把作者的设计弄坏）。
# ★ 代价：这些奇观变成"只有玩家能在首都建"，AI 不会再建它们。
MAKE_CAPITAL_ONLY = True


# 顺便写调试探针（AMR_probe.txt 傻瓜决议 + ZZ_amr_readtest.txt 故意写坏的文件）。
# 用途是排查"游戏到底有没有读本 mod 的 decisions 目录"：
# 它们会在 logs\error.log / logs\game.log 里留下痕迹，是唯一不依赖猜测的证据。
# 平常保持 False（别让用户看到没用的决议）；
# 要排查时在 config.txt 里写 probe=yes 再跑一次。
MAKE_PROBE = False

# --- config.txt（两个"解禁"bat 改的就是它）------------------------------------
# 优先级：config.txt 里【写了】的键 > 上面那一块的默认值。
#   · 想省事：双击 解禁无省份奇观.bat / 解禁年份未到奇观.bat，它们会把结果写进 config.txt。
#     注意 hiddenbonus 和 nostart 是同进同退的一对（只放开一半会出怪问题），
#     "解禁无省份奇观.bat" 会两个一起改。
#   · 想手改：直接编辑 config.txt，一行一个 名字=值。
#   · 什么都不动（或删掉 config.txt）：就用上面那一块的默认值。
_CFG_KEYS = ('version', 'generic', 'only', 'package', 'multi', 'single', 'nostart',
             'strictbuild', 'lockopen', 'hiddenbonus', 'alias',
             'buildcost', 'buildtime', 'move', 'aimove', 'probe', 'upgdec',
             'upgcost', 'upgtime', 'badstart', 'emptybt', 'movedays',
             'keepunmovable', 'maxtierdec')


def _cfg_pct(v, dflt):
    """'90' / '90%' -> '90'；'no' / '' / 认不出来的 -> 保持默认。

    顺手挡掉越界和负数：只接受 0~100（100 = 完全免费）。"""
    s = v.strip().strip('"').rstrip('%').strip()
    if s.lower() in ('', 'no', 'off', 'false', 'keep'):
        return dflt
    try:
        n = float(s)
    except ValueError:
        return dflt
    if n < 0:
        n = 0.0
    if n > 100:
        n = 100.0
    # 整数就写成整数，免得 config.txt 里出现 "90.0" 这种怪东西
    return str(int(n)) if n == int(n) else str(n)


_cfgfile = _cfg_path()
_CFG_SET = []
if _cfgfile:
    # utf-8-sig：记事本存 config.txt 会带 BOM，用 utf-8 读会让第一行的
    # "package=yes" 变成 "\ufeffpackage=yes"，开关就失效了。
    for _ln in open(_cfgfile, encoding='utf-8-sig', errors='ignore'):
        _k, _, _v = _ln.strip().partition('=')
        _k = _k.strip().lower()
        if _k not in _CFG_KEYS:
            continue            # 注释行 / 空行 / 不认识的键，一律忽略
        _CFG_SET.append(_k)
        if _k == 'version':
            SUPPORTED = _v.strip().strip('"')
        elif _k == 'generic':
            MAKE_GENERIC = _v.strip().lower() in ('yes', '1', 'true', 'on')
        elif _k == 'package':
            MAKE_PKG = _v.strip().lower() in ('yes', '1', 'true', 'on')
        elif _k == 'multi':
            MAKE_MULTI = _v.strip().lower() in ('yes', '1', 'true', 'on')
        elif _k == 'single':
            MAKE_MULTI = not _v.strip().lower() in ('yes', '1', 'true', 'on')
        elif _k == 'nostart':
            MAKE_NOSTARTFIX = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'lockopen':
            _v2 = _v.strip().lower().strip('"')
            if _v2 in ('', 'no', '0', 'false', 'off'):
                MAKE_LOCKOPEN = ''
            elif _v2 in ('yes', 'true', 'on', '1', 'date', 'year'):
                MAKE_LOCKOPEN = 'date'
            elif _v2 in ('all', 'hard', 'everything', 'any'):
                MAKE_LOCKOPEN = 'all'
            else:
                _m2 = re.match(r'(\d{1,4})', _v2)
                MAKE_LOCKOPEN = _m2.group(1) if _m2 else ''
        elif _k == 'hiddenbonus':
            _v3 = _v.strip().lower().strip('"')
            if _v3 in ('agp', 'add_great_project'):
                MAKE_HIDDENBONUS = 'agp'
            elif _v3 in ('yes', 'true', 'on', '1', 'keep', 'all'):
                MAKE_HIDDENBONUS = 'yes'
            else:
                MAKE_HIDDENBONUS = 'no'
        elif _k == 'strictbuild':
            MAKE_STRICTBUILD = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'buildcost':
            MAKE_BUILDCOST = _cfg_pct(_v, MAKE_BUILDCOST)
        elif _k == 'buildtime':
            MAKE_BUILDTIME = _cfg_pct(_v, MAKE_BUILDTIME)
        elif _k == 'move':
            _mv = _v.strip().lower().strip('"')
            if _mv in ('keep', 'source', 'original', 'nochange', 'lockuse'):
                MAKE_MOVE = 'keep'
            elif _mv in ('raw', 'yes', 'true', 'on', '1', 'open', 'any', 'all'):
                MAKE_MOVE = 'raw'
            else:
                MAKE_MOVE = 'ai'
        elif _k == 'aimove':
            MAKE_AI_MOVE = _v.strip().lower() in ('yes', 'true', 'on', '1', 'zero')

        elif _k == 'probe':
            MAKE_PROBE = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'upgdec':
            MAKE_UPGRADE_DEC = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'upgcost':
            _u = _v.strip().strip('"')
            MAKE_UPGRADE_COST = _u if re.match(r'^-?[0-9.]+$', _u) else MAKE_UPGRADE_COST
        elif _k == 'upgtime':
            _u = _v.strip().strip('"')
            MAKE_UPGRADE_TIME = _u if re.match(r'^-?[0-9.]+$', _u) else MAKE_UPGRADE_TIME
        elif _k == 'badstart':
            MAKE_BADSTART = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'emptybt':
            MAKE_EMPTYBT_GUARD = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'movedays':
            _mv = _v.strip()
            MAKE_MOVEDAYS = '' if _mv.lower() in ('no', 'off', '') else _mv
        elif _k == 'keepunmovable':
            MAKE_KEEP_UNMOVABLE = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'maxtierdec':
            MAKE_MAX_TIER_DEC = not _v.strip().lower() in ('no', '0', 'false', 'off')
        elif _k == 'alias':
            _av = _v.strip().lower()
            if _av in ('rename', 'amr'):
                SAME_NAME, ALIAS_ONLY = False, True
            elif _av in ('both', 'two', 'yes', '1', 'true', 'on'):
                SAME_NAME, ALIAS_ONLY = False, False
            else:
                SAME_NAME, ALIAS_ONLY = True, False
        elif _k == 'only':
            MAKE_ONLY_GENERIC = _v.strip().lower() in ('generic', 'vanilla', 'g')
if MAKE_ONLY_GENERIC:
    MAKE_GENERIC = True

# ★ 1.3.5：一键三级 与 升级打折 默认【互斥】。
#   一键三级一旦能用（免费直达 III），"升级花费 -90%"" 的收益就是 0，
#   而且玩家还得先花 50 杜卡特才知道有免费按钮 —— 等于花钱陷阱。
#   所以：config.txt 里【没有明确写 upgdec】时，只要 maxtierdec 开着，就不生成打折决议。
#   想两个都要：config.txt 写 upgdec=force（写了的键在 _CFG_SET 里，下面不会关掉它）。
if MAKE_MAX_TIER_DEC and MAKE_UPGRADE_DEC and 'upgdec' not in _CFG_SET:
    MAKE_UPGRADE_DEC = False
    UPGRADE_DEC_OFF_BY_TIERDEC = True
