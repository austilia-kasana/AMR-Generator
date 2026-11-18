"""AMR 生成器 · 跨模块共享的可变状态

这些容器由流程填充、被多个模块读写，所以单独放一份 —— 谁 import 谁拿到同一个对象。
只做原地改（append / update / []=），【不要】重新赋值，否则别人看不到。
"""

import os

from amr_env import VAN


NOSTART_KEYS = []

OPEN_KEYS = []

HIDDEN_KEYS = []

KNOWN_KEYS = set('''
build_cost build_trigger can_be_moved can_upgrade_trigger can_use_modifiers_trigger
date keep_trigger move_days_per_unit_distance on_built on_destroyed start starting_tier
time type tier_0 tier_1 tier_2 tier_3 tier_4 tier_5'''.split())
AGP_KEYS = set()

VAN_GP = os.path.join(VAN, 'common', 'great_projects') if VAN else ''

VAN_LABEL = '游戏本体（原版）'

ALIAS_PREFIX = '00_amr_'

MONUMENT_ONLY_OK = ('descriptor.mod',)

SOURCES = {}

GP_TAKEOVER = []       # 声明接管 common/great_projects 的 mod 名

MOD_GP_FILES = {}      # mod 显示名 -> {奇观文件名: 路径}（用来复核有没有带全）

SKIPPED_MODS = []      # 路径读不出来/目录不存在而跳过的 mod（它们的奇观会全漏）

SUBS = []              # common/great_projects 下有子目录的 mod（子目录里的 txt 不带）

FILLS = {}

VGT = os.path.join(VAN, 'common', 'great_projects') if VAN else ''

VERBATIM = ['00_great_projects.txt']

SKIP = set(VERBATIM)

PACKS = []

# start 写成 event_target 之类非法值的奇观：(键名, 写成了什么, 处理方式)
# 处理方式 'locked' = 已补 always = no 挡掉到处可建；
#          'marker-in-use' = 它靠的省份标记真的有人应用，放它一马（只记录）
BADSTART_KEYS = []

# 被重定向到首都的奇观（capital only）
CAPONLY_KEYS = []
