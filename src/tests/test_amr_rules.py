# -*- coding: utf-8 -*-
"""奇观规则单测：无 start 的隐藏奇观、解锁模式下恢复被注释的 start、人类独占放宽。

关键点：fix_no_start 依赖磁盘（applied_markers / map_province_ids）和开关，
测试里把这三样都钉住，保证结果与本机 config.txt、本机播放集无关。
"""
import unittest

import amr_testenv
import amr_rules as R
import amr_state as ST

amr_testenv.prepare()

st = amr_testenv.stats


class TestKeyAndStart(unittest.TestCase):
    def test_mon_key(self):
        self.assertEqual(R._mon_key('mon = {\n}\n'), 'mon')

    def test_mon_key_ignores_indented(self):
        self.assertEqual(R._mon_key('\tmon={}'), '')

    def test_has_start(self):
        self.assertTrue(R.has_start('start = 151'))
        self.assertTrue(R.has_start('\tstart=1822'))

    def test_commented_start_counts_as_missing(self):
        self.assertFalse(R.has_start('#start = 691'))
        self.assertFalse(R.has_start('\t# start = 691  - doesnt need this'))

    def test_start_not_at_line_start_is_ignored(self):
        self.assertFalse(R.has_start('build_trigger = { start = 1 }'))


class TestNoStartIsHidden(unittest.TestCase):
    def test_no_start_and_no_build_trigger_is_hidden(self):
        self.assertTrue(R.no_start_is_hidden('m = {\n\ttype = monument\n}\n'))

    def test_empty_build_trigger_is_hidden(self):
        self.assertTrue(R.no_start_is_hidden(
            'm = {\n\tbuild_trigger = {\n\t}\n}\n'))

    def test_province_flag_anchor_is_not_hidden(self):
        # 安本纳尔那类：#start 注释掉、改用省份标记定位，是正常奇观，一律不动
        self.assertFalse(R.no_start_is_hidden(
            'm = {\n\tbuild_trigger = {\n\t\thas_province_flag = h35_x\n\t}\n}\n'))

    def test_visible_start_is_not_hidden(self):
        self.assertFalse(R.no_start_is_hidden('m = {\n\tstart = 151\n}\n'))


class _RulesCase(unittest.TestCase):
    """统一保存/恢复被测试改动的全局：开关、磁盘桩、NOSTART_KEYS。"""

    def setUp(self):
        self._old_nostartfix = R.MAKE_NOSTARTFIX
        self._am = R.applied_markers
        self._mp = R.map_province_ids
        self._keys = list(ST.NOSTART_KEYS)

    def tearDown(self):
        R.MAKE_NOSTARTFIX = self._old_nostartfix
        R.applied_markers = self._am
        R.map_province_ids = self._mp
        del ST.NOSTART_KEYS[:]
        ST.NOSTART_KEYS.extend(self._keys)


class TestFixNoStartDefault(_RulesCase):
    """默认模式（nostart=yes）：没 start 的隐藏奇观加"建过就不再显示"的守卫。

    用户 2026-10-01 复述的原始设计：没有 start 的奇观【建造完后不再显示可建】。
    所以这里补的不是 always = no（那是"根本不能建"），而是
        NOT = { has_great_project = { type = <这件奇观> } }
    它和原 build_trigger 是 AND 关系：原来能建的省照旧能建，建完就不再显示。
    """

    HIDDEN_EMPTY_BT = 'm = {\n\ttype = monument\n\tbuild_trigger = {\n\t}\n}\n'
    HIDDEN_NO_BT = 'm = {\n\ttype = monument\n}\n'
    ANCHORED = ('m = {\n\ttype = monument\n\tbuild_trigger = {\n'
                '\t\thas_province_flag = h35_x\n\t}\n}\n')
    NORMAL = 'm = {\n\tstart = 151\n\ttype = monument\n}\n'
    GUARD = 'NOT = { has_great_project = { type = m } }'

    def setUp(self):
        _RulesCase.setUp(self)
        R.MAKE_NOSTARTFIX = True

    def test_guards_empty_build_trigger(self):
        d = st()
        out = R.fix_no_start(self.HIDDEN_EMPTY_BT, d, 'm')
        self.assertIn(self.GUARD, out)
        self.assertNotIn('always = no', out)      # 不能把"能建"改成"不能建"
        self.assertEqual(d['nostart_fixed'], 1)
        self.assertEqual(d['nostart_guarded'], 1)
        self.assertEqual(d['nostart_bt'], 0)
        self.assertIn('m', ST.NOSTART_KEYS)

    def test_adds_guarded_build_trigger_when_absent(self):
        d = st()
        out = R.fix_no_start(self.HIDDEN_NO_BT, d, 'm')
        self.assertIn('build_trigger = {', out)
        self.assertIn(self.GUARD, out)
        self.assertNotIn('always = no', out)
        self.assertEqual(d['nostart_bt'], 1)
        self.assertEqual(d['nostart_guarded'], 1)

    def test_guard_uses_the_real_monument_key(self):
        # type = 必须是这件奇观自己的键名（引擎不接受 THIS）
        d = st()
        out = R.fix_no_start(self.HIDDEN_EMPTY_BT, d, 'some_other_monument')
        self.assertIn('has_great_project = { type = some_other_monument }', out)

    def test_anchored_monument_untouched(self):
        d = st()
        self.assertEqual(R.fix_no_start(self.ANCHORED, d, 'm'), self.ANCHORED)
        self.assertEqual(d['nostart_fixed'], 0)

    def test_normal_monument_untouched(self):
        d = st()
        self.assertEqual(R.fix_no_start(self.NORMAL, d, 'm'), self.NORMAL)
        self.assertEqual(d['nostart_fixed'], 0)


class TestFixNoStartUnlock(_RulesCase):
    """解锁模式（nostart=no）：恢复被注释掉的 start，并放宽人类独占。"""

    BLOCK = ('m = {\n'
             '\t#start = 1822\n'
             '\ttype = monument\n'
             '\tbuild_trigger = {\n'
             '\t\thas_province_flag = h35_crimson_cathedral\n'
             '\t}\n'
             '\tcan_use_modifiers_trigger = {\n'
             '\t\towner = { ai = no }\n'
             '\t}\n'
             '}\n')

    def setUp(self):
        _RulesCase.setUp(self)
        R.MAKE_NOSTARTFIX = False

    def test_restores_when_marker_unused_and_province_exists(self):
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_no_start(self.BLOCK, d, 'm')
        self.assertIn('start = 1822', out)
        self.assertNotIn('#start', out)
        self.assertEqual(d['nostart_fixed'], 1)
        self.assertIn('m', ST.NOSTART_KEYS)

    def test_relaxes_human_only_limit(self):
        # AI 持有省份时引擎会清掉"人类独占"的奇观，所以解锁模式要连带放宽
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        out = R.fix_no_start(self.BLOCK, st(), 'm')
        self.assertIn('always = yes', out)
        self.assertNotIn('ai = no', out)

    def test_protected_when_marker_is_in_use(self):
        R.applied_markers = lambda: {'h35_crimson_cathedral'}
        R.map_province_ids = lambda: {'1822'}
        d = st()
        self.assertEqual(R.fix_no_start(self.BLOCK, d, 'm'), self.BLOCK)
        self.assertEqual(d['nostart_fixed'], 0)

    def test_protected_when_province_missing_from_map(self):
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'999'}
        d = st()
        self.assertEqual(R.fix_no_start(self.BLOCK, d, 'm'), self.BLOCK)
        self.assertEqual(d['nostart_fixed'], 0)

    def test_restores_when_map_ids_unavailable(self):
        # 读不到地图定义时按"通过"处理（源码：not ids or ...），不因为查不到就放弃
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: set()
        out = R.fix_no_start(self.BLOCK, st(), 'm')
        self.assertIn('start = 1822', out)

    def test_visible_start_is_left_alone(self):
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'151'}
        block = 'm = {\n\tstart = 151\n\ttype = monument\n}\n'
        self.assertEqual(R.fix_no_start(block, st(), 'm'), block)


class TestFixNoStartNegationFilter(_RulesCase):
    """1.3 新增：注释里作者明说"不需要 start"时，解锁模式必须【跳过】不恢复。

    真实写法样例（安本纳尔等 mod）：
        #start = 2807 - doesnt need this
        #start = 1234  # no need
        #start = 5678  # 不需要
    1.2 之前不看注释内容，一律恢复成真 start —— 那会把作者的玩法设计弄坏。
    """

    def setUp(self):
        _RulesCase.setUp(self)
        R.MAKE_NOSTARTFIX = False        # 解锁模式（恢复注释掉的 start）
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'2807', '1234', '5678'}

    def _block(self, comment):
        return ('m = {\n'
                '\t%s\n'
                '\ttype = monument\n'
                '\tbuild_trigger = {\n'
                '\t\thas_province_flag = some_flag\n'
                '\t}\n'
                '}\n' % comment)

    def test_english_doesnt_need_is_skipped(self):
        d = st()
        out = R.fix_no_start(self._block('#start = 2807 - doesnt need this'), d, 'm')
        self.assertIn('#start = 2807', out)        # 原样保留，没被恢复
        self.assertNotIn('\n\tstart = ', out)
        self.assertEqual(d['nostart_skipped'], 1)
        self.assertEqual(d['nostart_fixed'], 0)

    def test_english_no_need_is_skipped(self):
        d = st()
        out = R.fix_no_start(self._block('#start = 1234  # no need'), d, 'm')
        self.assertIn('#start = 1234', out)
        self.assertEqual(d['nostart_skipped'], 1)

    def test_english_dont_is_skipped(self):
        d = st()
        out = R.fix_no_start(self._block("#start = 1234  # don't need"), d, 'm')
        self.assertIn('#start = 1234', out)
        self.assertEqual(d['nostart_skipped'], 1)

    def test_chinese_negation_is_skipped(self):
        d = st()
        out = R.fix_no_start(self._block('#start = 5678  # 不需要'), d, 'm')
        self.assertIn('#start = 5678', out)
        self.assertEqual(d['nostart_skipped'], 1)

    def test_plain_comment_is_still_restored(self):
        # 没有否定词 -> 照旧恢复（不能因为加了过滤器就全都不恢复了）
        d = st()
        out = R.fix_no_start(self._block('#start = 2807  # AMR test'), d, 'm')
        self.assertIn('start = 2807', out)
        self.assertNotIn('#start', out)
        self.assertEqual(d['nostart_fixed'], 1)
        self.assertEqual(d['nostart_skipped'], 0)

    def test_bare_comment_is_still_restored(self):
        d = st()
        out = R.fix_no_start(self._block('#start = 2807'), d, 'm')
        self.assertIn('start = 2807', out)
        self.assertEqual(d['nostart_fixed'], 1)


class TestPct(unittest.TestCase):
    def test_ninety_means_keep_a_tenth(self):
        self.assertAlmostEqual(R._pct('90'), 0.1)

    def test_hundred_means_free(self):
        self.assertEqual(R._pct('100'), 0.0)

    def test_zero_and_junk_mean_no_change(self):
        for v in ('0', '', 'no', None, 'abc'):
            self.assertIsNone(R._pct(v), v)

    def test_over_hundred_clamped(self):
        self.assertEqual(R._pct('250'), 0.0)

    def test_percent_sign_and_spaces_ok(self):
        self.assertAlmostEqual(R._pct(' 50% '), 0.5)

    def test_fraction_allowed(self):
        self.assertAlmostEqual(R._pct('12.5'), 0.875)


class TestDiscountProjects(_RulesCase):
    BLOCK = ('m = {\n'
             '\tcan_be_moved = yes\n'
             '\tbuild_cost = 1000\t# 原版注释要留着\n'
             '\ttime = { months = 120 }\n'
             '\ttype = monument\n'
             '}\n')

    def setUp(self):
        _RulesCase.setUp(self)
        self._bc, self._bt = R.MAKE_BUILDCOST, R.MAKE_BUILDTIME

    def tearDown(self):
        R.MAKE_BUILDCOST, R.MAKE_BUILDTIME = self._bc, self._bt
        _RulesCase.tearDown(self)

    def test_ninety_percent_off(self):
        R.MAKE_BUILDCOST = R.MAKE_BUILDTIME = '90'
        d = st()
        out = R.discount_projects(self.BLOCK, d)
        self.assertIn('build_cost = 100', out)
        self.assertIn('months = 12', out)
        self.assertIn('# 原版注释要留着', out)      # 行尾注释不能丢
        self.assertEqual(d['dc_cost'], 1)
        self.assertEqual(d['dc_time'], 1)
        self.assertEqual(d['dc_cost_1000_100'], 1)
        self.assertEqual(d['dc_time_120_12'], 1)

    def test_zero_cost_is_left_alone(self):
        # 原版 621 件本来就 build_cost = 0，把 0 写成 0 没意义还白改文件
        R.MAKE_BUILDCOST = R.MAKE_BUILDTIME = '90'
        src = 'm = {\n\tbuild_cost = 0\n\ttime = { months = 0 }\n}\n'
        d = st()
        self.assertEqual(R.discount_projects(src, d), src)
        self.assertEqual(d['dc_cost'], 0)
        self.assertEqual(d['dc_time'], 0)

    def test_hundred_percent_makes_it_free(self):
        R.MAKE_BUILDCOST = R.MAKE_BUILDTIME = '100'
        d = st()
        out = R.discount_projects(self.BLOCK, d)
        self.assertIn('build_cost = 0', out)
        self.assertIn('months = 0', out)

    def test_multiline_time_block(self):
        R.MAKE_BUILDTIME = '90'
        src = 'm = {\n\ttime = {\n\t\tmonths = 120\n\t}\n}\n'
        d = st()
        out = R.discount_projects(src, d)
        self.assertIn('months = 12', out)
        self.assertEqual(d['dc_time_120_12'], 1)

    def test_tenth_rounds_up_not_to_901(self):
        # 1000 * 0.9 在浮点下是 900.0000000000001，向上取整会变 901 —— 必须整数运算
        R.MAKE_BUILDCOST = '90'
        R.MAKE_BUILDTIME = '0'
        d = st()
        out = R.discount_projects('m = {\n\tbuild_cost = 1000\n}\n', d)
        self.assertIn('build_cost = 100', out)
        self.assertNotIn('901', out)

    def test_disabled_returns_unchanged(self):
        R.MAKE_BUILDCOST = R.MAKE_BUILDTIME = '0'
        d = st()
        self.assertEqual(R.discount_projects(self.BLOCK, d), self.BLOCK)
        self.assertEqual(d['dc_cost'] + d['dc_time'], 0)

    def test_does_not_touch_other_numbers(self):
        # 只该动 build_cost / time 的那两个数字，别的数值一个都不许变
        R.MAKE_BUILDCOST = R.MAKE_BUILDTIME = '90'
        src = ('m = {\n\tbuild_cost = 1000\n\tstarting_tier = 2\n'
               '\tdate = 1444.11.11\n\tstart = 151\n'
               '\ttier_1 = { cost_to_upgrade = { factor = 1000 } }\n}\n')
        d = st()
        out = R.discount_projects(src, d)
        self.assertIn('starting_tier = 2', out)
        self.assertIn('date = 1444.11.11', out)
        self.assertIn('start = 151', out)
        self.assertIn('factor = 1000', out)        # 升级费是另一套修正器管的，不动
        self.assertEqual(d['dc_cost'], 1)


class TestNeedsFields(_RulesCase):
    def setUp(self):
        _RulesCase.setUp(self)
        self._bc, self._bt = R.MAKE_BUILDCOST, R.MAKE_BUILDTIME

    def tearDown(self):
        R.MAKE_BUILDCOST, R.MAKE_BUILDTIME = self._bc, self._bt
        _RulesCase.tearDown(self)

    def test_positive_cost_needs_work(self):
        R.MAKE_BUILDCOST, R.MAKE_BUILDTIME = '90', '0'
        self.assertTrue(R._needs_fields('build_cost = 1000\n'))

    def test_zero_cost_needs_nothing(self):
        R.MAKE_BUILDCOST, R.MAKE_BUILDTIME = '90', '0'
        self.assertFalse(R._needs_fields('build_cost = 0\n'))

    def test_positive_months_needs_work(self):
        R.MAKE_BUILDCOST, R.MAKE_BUILDTIME = '0', '90'
        self.assertTrue(R._needs_fields('time = { months = 120 }\n'))

    def test_disabled_never_needs_work(self):
        R.MAKE_BUILDCOST, R.MAKE_BUILDTIME = '0', '0'
        self.assertFalse(R._needs_fields('build_cost = 1000\ntime = { months = 120 }\n'))


class TestFixBadStart(_RulesCase):
    """start 写成 event_target 之类的奇观。

    用户 2026-10-01 复述的原始设计与机制：
      引擎只认 start = <省份号>；写成 event_target:XXX 解析失败
      （error.log: Malformed token ... Last good read: type=monument），
      这件奇观就【没有所属省份】→ 每个满足 build_trigger 的省份都能建它
      （"遍地米兰大教堂/崇武城"）。
    处理：能从注释里恢复出省份号就恢复；否则加"建过就不再显示"的守卫。
    """

    # 有 build_trigger 的坏 start（作者靠省份标记定位）：
    # 事件给某个省 set_province_flag -> 那个省就能建它。所以只能加守卫，不能锁死。
    BAD = ('m = {\n'
           '\tstart = event_target:m_MB\n'
           '\ttype = monument\n'
           '\tbuild_trigger = {\n'
           '\t\talways = yes\n'
           '\t}\n'
           '}\n')
    # 连 build_trigger 都没有的坏 start：谁也建不了它 -> 只能锁死
    BAD_NO_BT = ('m = {\n'
                 '\tstart = event_target:m_MB\n'
                 '\ttype = monument\n'
                 '}\n')
    BAD_WITH_COMMENTED = ('m = {\n'
                          '\t#start = 1822\n'
                          '\tstart = event_target:m_MB\n'
                          '\ttype = monument\n'
                          '\tbuild_trigger = {\n'
                          '\t\talways = yes\n'
                          '\t}\n'
                          '}\n')
    # 靠省份标记定位、而且标记有人在用：按设计放它一马
    BAD_ANCHORED = ('m = {\n'
                    '\tstart = event_target:m_MB\n'
                    '\ttype = monument\n'
                    '\tbuild_trigger = {\n'
                    '\t\thas_province_flag = m_flag\n'
                    '\t}\n'
                    '}\n')
    GOOD = 'm = {\n\tstart = 151\n\ttype = monument\n}\n'

    def setUp(self):
        _RulesCase.setUp(self)
        self._bs = R.MAKE_BADSTART
        R.MAKE_BADSTART = True

    def tearDown(self):
        R.MAKE_BADSTART = self._bs
        del ST.BADSTART_KEYS[:]
        _RulesCase.tearDown(self)

    def test_detects_non_numeric_start(self):
        self.assertEqual(R.bad_start_key(self.BAD), 'event_target:m_MB')

    def test_numeric_start_is_fine(self):
        self.assertEqual(R.bad_start_key(self.GOOD), '')
        self.assertEqual(R.bad_start_key('m = {\n\tstart = 151\n}\n'), '')

    def test_guards_when_it_cannot_be_restored(self):
        # 没有可恢复的注释，但靠的省份标记【有人在应用】-> 加"建过就不再显示"
        R.applied_markers = lambda: {'m_flag'}
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD_ANCHORED, d, 'm')
        self.assertIn('has_great_project = { type = m }', out)
        self.assertIn('has_province_flag = m_flag', out)   # 原条件保留
        self.assertNotIn('always = no', out)
        self.assertEqual(d['badstart_guarded'], 1)
        self.assertIn(('m', 'event_target:m_MB', 'guarded'), ST.BADSTART_KEYS)

    def test_no_build_trigger_gets_human_only(self):
        # 连 build_trigger 都没有的：不再锁死 always = no，
        # 改为【仅人类玩家 + 仅首都】——用户 2026-10-03 的最终定案。
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD_NO_BT, d, 'm')
        self.assertIn('owner = { ai = no }', out)
        self.assertIn('is_capital = yes', out)   # 用户定案：仅人类玩家 + 仅首都
        self.assertNotIn('always = no', out)
        self.assertEqual(d['badstart_bt'], 1)
        self.assertIn(('m', 'event_target:m_MB', 'capital'), ST.BADSTART_KEYS)

    def test_with_build_trigger_gets_guard_and_human_only(self):
        # 有 build_trigger 的：守卫 + 仅人类玩家 + 仅首都（它同样没有可用 start）
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD, d, 'm')
        self.assertIn('has_great_project = { type = m }', out)
        self.assertIn('owner = { ai = no }', out)
        self.assertIn('is_capital = yes', out)   # 用户定案：仅人类玩家 + 仅首都
        self.assertIn('always = yes', out)      # 原来的可建条件保留
        self.assertNotIn('always = no', out)
        self.assertEqual(d['badstart_guarded'], 1)

    def test_guards_when_it_has_a_build_trigger(self):
        # 有 build_trigger（作者靠它限制可建的省）-> 只加守卫，不锁死
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD, d, 'm')
        self.assertIn('has_great_project = { type = m }', out)
        self.assertIn('always = yes', out)      # 原来的可建条件保留
        self.assertNotIn('always = no', out)
        self.assertEqual(d['badstart_guarded'], 1)
        self.assertEqual(d['badstart_dead'], 0)

    def test_guards_when_anchored_even_if_marker_not_applied_yet(self):
        # ★ 用户要求：这 11 件只在事件里被 set_province_flag 引用、没有
        #   add_great_project 调用 —— 作者的玩法是"事件设标记 -> 那个省可以建"。
        #   所以【不能锁死】（会打死作者玩法），只加"建过就不再显示"。
        #   标记当前没人应用也要加守卫，不能放行成"到处可建"。
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD_ANCHORED, d, 'm')
        self.assertIn('has_great_project = { type = m }', out)
        self.assertIn('has_province_flag = m_flag', out)   # 可建性原样保留
        self.assertNotIn('always = no', out)
        self.assertEqual(d['badstart_guarded'], 1)
        self.assertEqual(d['badstart_dead'], 0)

    def test_restores_from_commented_start_when_possible(self):
        R.applied_markers = lambda: set()
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD_WITH_COMMENTED, d, 'm')
        self.assertIn('start = 1822', out)
        # 写坏的那行必须被删掉：不能有【以 start = 开头】的行再指向 event_target
        # （注释里提到 event_target 是说明文字，不算问题）
        for ln in out.split('\n'):
            head = ln.split('#')[0]          # 只看代码部分，注释不算
            if head.strip().startswith('start'):
                self.assertNotIn('event_target', head, ln)
        self.assertEqual(out.count('\tstart ='), 1, out)
        self.assertEqual(d['badstart_restored'], 1)
        self.assertIn(('m', 'event_target:m_MB', 'restored'), ST.BADSTART_KEYS)

    def test_anchored_and_marker_in_use_is_left_alone(self):
        R.applied_markers = lambda: {'m_flag'}
        R.map_province_ids = lambda: {'1822'}
        d = st()
        out = R.fix_bad_start(self.BAD_ANCHORED, d, 'm')
        self.assertIn('has_great_project = { type = m }', out)   # 加守卫，不是放行
        self.assertEqual(d['badstart_guarded'], 1)
        self.assertEqual(d['badstart_dead'], 0)

    def test_disabled_returns_unchanged(self):
        R.MAKE_BADSTART = False
        d = st()
        self.assertEqual(R.fix_bad_start(self.BAD, d, 'm'), self.BAD)
        self.assertEqual(d['badstart_guarded'], 0)
        self.assertEqual(d['badstart_restored'], 0)


class TestMarkBuilt(unittest.TestCase):
    """on_built 里打"已建成"【全局】标记 —— 防"卡时间建多个"。
    ★ 用户 2026-10-04：「打省标记改成打全局标记，不然在其他省或者其他国家也能建造」
      -> set_global_flag / has_global_flag，一整个世界只此一份。

    用户实测："如果卡时间甚至能建造多个，虽然并不生效"。
    根因：NOT = { has_great_project } 只管【已建成】的奇观，施工中的不算，
    一个省的建设队列被取消/切换后就能再开一个。
    所以建成时打个省标记（标记会存档），永远挡住第二次。
    ★ 标记必须写在 on_built（效果块）里 —— build_trigger 是触发器块，
      set_global_flag 放进去会被引擎丢掉。
    """

    WITH_ON_BUILT = ('m = {\n'
                     '\ttype = monument\n'
                     '\ton_built = { }\n'
                     '\ton_destroyed = { }\n'
                     '}\n')
    WITHOUT = 'm = {\n\ttype = monument\n}\n'

    def test_injects_into_existing_on_built(self):
        d = st()
        out = R._mark_built(self.WITH_ON_BUILT, 'k_AMR_built', d)
        self.assertIn('set_global_flag = k_AMR_built', out)
        self.assertEqual(d['mark_built'], 1)
        self.assertEqual(d['mark_built_new'], 0)     # 没新建 on_built
        # 必须落在 on_built 块里，不能落进 on_destroyed
        self.assertLess(out.index('set_global_flag'), out.index('on_destroyed'))
        self.assertGreater(out.index('set_global_flag'), out.index('on_built'))

    def test_creates_on_built_when_absent(self):
        d = st()
        out = R._mark_built(self.WITHOUT, 'k_AMR_built', d)
        self.assertIn('on_built = {', out)
        self.assertIn('set_global_flag = k_AMR_built', out)
        self.assertEqual(d['mark_built_new'], 1)

    def test_guard_branch_emits_two_guards_and_marker(self):
        # 端到端：guard 分支必须【同时】产出两条 NOT 和 on_built 标记
        old = R.MAKE_NOSTARTFIX
        R.MAKE_NOSTARTFIX = True
        try:
            d = st()
            out = R.fix_no_start(
                'm = {\n\ttype = monument\n\tbuild_trigger = {\n\t}\n'
                '\ton_built = { }\n}\n', d, 'm')
            self.assertIn('has_great_project = { type = m }', out)
            self.assertIn('has_global_flag = m_AMR_built_g', out)
            self.assertIn('set_global_flag = m_AMR_built_g', out)
            self.assertNotIn('always = no', out)
        finally:
            R.MAKE_NOSTARTFIX = old


class TestApplyMoveDays(unittest.TestCase):
    """每距离基础搬运时间统一覆盖成 MAKE_MOVEDAYS（默认 1）。

    用户 2026-10-03 定的 1.2 功能："把所有奇观每距离基础搬运时间改成 1"。
    官方公式（EU4 Wiki · Great project § Relocation）：
        搬迁耗时 = 两省距离 × move_days_per_unit_distance
        搬迁费用 = 耗时（天） × 3 杜卡特/天
    所以改成 1 = 搬迁最快最便宜（费用与耗时同方向，引擎算法改不了）。
    这是【定义层】字段，游戏内没有修正器能改 -> 只能生成器统一覆盖。
    最安全的改法：纯数值替换，不动任何结构。
    """

    HAS10 = ('m = {\n'
             '\ttype = monument\n'
             '\tmove_days_per_unit_distance = 10\n'
             '\tstart = 151\n'
             '}\n')
    HAS1 = HAS10.replace('= 10', '= 1')
    NOKEY = 'm = {\n\ttype = monument\n\tstart = 151\n}\n'

    def setUp(self):
        self._md = R.MAKE_MOVEDAYS
        self._mv = R.MAKE_MOVE
        R.MAKE_MOVEDAYS = '1'
        R.MAKE_MOVE = 'raw'      # 这些用例覆盖 1.2 的 raw 行为

    def tearDown(self):
        R.MAKE_MOVEDAYS = self._md
        R.MAKE_MOVE = self._mv

    def test_replaces_value(self):
        d = st()
        out = R.apply_move_days(self.HAS10, d, 'm')
        self.assertIn('move_days_per_unit_distance = 1', out)
        self.assertNotIn('= 10', out)
        self.assertEqual(d['movedays_set'], 1)
        # 结构没动：其它字段原样
        self.assertIn('start = 151', out)
        self.assertIn('type = monument', out)

    def test_already_target_is_noop(self):
        d = st()
        self.assertEqual(R.apply_move_days(self.HAS1, d, 'm'), self.HAS1)
        self.assertEqual(d['movedays_set'], 0)
        self.assertEqual(d['movedays_add'], 0)

    def test_adds_key_when_absent(self):
        d = st()
        out = R.apply_move_days(self.NOKEY, d, 'm')
        self.assertIn('move_days_per_unit_distance = 1', out)
        self.assertEqual(d['movedays_add'], 1)

    def test_empty_setting_leaves_block_alone(self):
        R.MAKE_MOVEDAYS = ''
        d = st()
        self.assertEqual(R.apply_move_days(self.HAS10, d, 'm'), self.HAS10)

    def test_non_numeric_is_ignored(self):
        # 写错值（不是纯数字）就原样放过，绝不写坏定义
        R.MAKE_MOVEDAYS = 'abc'
        d = st()
        self.assertEqual(R.apply_move_days(self.HAS10, d, 'm'), self.HAS10)
        self.assertEqual(d['movedays_set'], 0)

    def test_keep_leaves_block_alone(self):
        R.MAKE_MOVE = 'keep'
        d = st()
        self.assertEqual(R.apply_move_days(self.HAS10, d, 'm'), self.HAS10)
        self.assertEqual(d['movedays_set'], 0)


if __name__ == '__main__':
    unittest.main()
