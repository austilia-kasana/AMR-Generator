# -*- coding: utf-8 -*-
"""纯函数单测：括号扫描、块与键定位、OR 包裹、门禁注入、搬运开关、漏行修复。

只吃内存里的字符串，不碰磁盘。每条用例都能对应到一次真实踩过的坑。
"""
import unittest

import amr_testenv
import amr_script as S

amr_testenv.prepare()

st = amr_testenv.stats


class TestBraceClose(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(S.brace_close('a {b} c', 2), 4)

    def test_nested(self):
        s = 'x = { a = { b } }'
        self.assertEqual(S.brace_close(s, 4), len(s) - 1)

    def test_brace_in_comment_ignored(self):
        s = 'a = {\n# }\nb = 1\n}'
        self.assertEqual(S.brace_close(s, 4), s.rindex('}'))

    def test_brace_in_string_ignored(self):
        s = 'a = { b = "}" }'
        self.assertEqual(S.brace_close(s, 4), s.rindex('}'))

    def test_unbalanced_returns_minus_one(self):
        self.assertEqual(S.brace_close('a = { b = 1', 4), -1)

    def test_comment_without_newline_returns_minus_one(self):
        self.assertEqual(S.brace_close('a = { # }', 4), -1)


class TestFindBlocks(unittest.TestCase):
    def test_two_top_level_blocks(self):
        t = 'foo = {\n}\nbar = {\n}\n'
        got = S.find_blocks(t)
        self.assertEqual([g[0] for g in got], ['foo', 'bar'])
        self.assertEqual(got[0][1], 0)
        self.assertEqual(got[0][3], t.index('}'))
        self.assertEqual(got[1][3], t.rindex('}'))

    def test_indented_block_is_not_top_level(self):
        t = 'foo = {\n\tbar = {\n\t}\n}\n'
        self.assertEqual([g[0] for g in S.find_blocks(t)], ['foo'])

    def test_key_character_set(self):
        self.assertEqual(S.find_blocks('a_b-c.d = {\n}\n')[0][0], 'a_b-c.d')


class TestIsMonument(unittest.TestCase):
    def test_plain(self):
        self.assertTrue(S.is_monument('m = {\n\ttype = monument\n}\n'))

    def test_indented(self):
        self.assertTrue(S.is_monument('\ttype = monument\n'))

    def test_prefix_does_not_match(self):
        self.assertFalse(S.is_monument('\ttype = monument_foo\n'))

    def test_commented_out_does_not_match(self):
        self.assertFalse(S.is_monument('\t#type = monument\n'))


class TestSpans(unittest.TestCase):
    def test_find_spans_indent_and_bounds(self):
        t = 'm = {\n\tcan_upgrade_trigger = {\n\t\ta = 1\n\t}\n}\n'
        spans = S.find_spans(t, 'can_upgrade_trigger')
        self.assertEqual(len(spans), 1)
        ind, bo, bc = spans[0]
        self.assertEqual(ind, '\t')
        self.assertEqual(t[bo], '{')
        self.assertEqual(t[bc], '}')

    def test_non_nested_keeps_only_outermost(self):
        t = 'm = {\n\ttrigger = {\n\t\ttrigger = {\n\t\t}\n\t}\n}\n'
        spans = S.find_spans(t, 'trigger')
        self.assertEqual(len(spans), 2)
        self.assertEqual(len(S.non_nested(spans)), 1)

    def test_depth1_span(self):
        t = 'm = {\n\ttype = monument\n\tcan_use_modifiers_trigger = {\n\t\tx = 1\n\t}\n}\n'
        ind, bo, bc = S.depth1_span(t, 'can_use_modifiers_trigger')
        self.assertEqual(ind, '\t')
        self.assertEqual(t[bc], '}')

    def test_depth1_ignores_nested_same_name(self):
        t = 'm = {\n\touter = {\n\t\tinner = {\n\t\t}\n\t}\n}\n'
        self.assertIsNone(S.depth1_span(t, 'inner'))


class TestEmptyInner(unittest.TestCase):
    def test_empty(self):
        self.assertTrue(S.empty_inner(''))

    def test_comment_only(self):
        self.assertTrue(S.empty_inner('# nothing here\n'))

    def test_braces_and_space_only(self):
        self.assertTrue(S.empty_inner('  \n{ }'))

    def test_has_content(self):
        self.assertFalse(S.empty_inner('a = 1'))

    def test_comment_then_content(self):
        self.assertFalse(S.empty_inner('# c\nreligion = catholic'))


class TestBypassBranch(unittest.TestCase):
    def test_contains_player_only_condition(self):
        txt = S.bypass_branch('\t')
        self.assertIn('owner = { ai = no }', txt)
        self.assertIn(S.TT, txt)
        self.assertIn('custom_trigger_tooltip', txt)


class TestWrapTopLevel(unittest.TestCase):
    """玩家旁路（= 奖励解锁）的写法。

    ★ 2026-10-03 用户定案：**在最外面套一层 if/else**，原内容一个字节不动。

        custom_trigger_tooltip = {
            tooltip = AMR_monument_bypass_tt
            if   = { limit = { owner = { ai = no } }  <原触发器内容> }   ← 玩家直通
            else = { <原触发器内容> }                                   ← AI 走原条件
        }

    以前是把原内容展开成 AND/OR/NOT 再套 OR —— 那条路写坏了三次
    （括号失配、少补 }、嵌套 if 展不开），已废弃。
    """

    BLOCK = ('m = {\n'
             '\ttype = monument\n'
             '\tcan_upgrade_trigger = {\n'
             '\t\treligion = catholic\n'
             '\t}\n'
             '}\n')
    IF_ELSE = ('m = {\n'
               '\ttype = monument\n'
               '\tcan_upgrade_trigger = {\n'
               '\t\tif = {\n'
               '\t\t\tlimit = { owner = { full_idea_group = gp_ideas } }\n'
               '\t\t\towner = { full_idea_group = gp_ideas }\n'
               '\t\t}\n'
               '\t\telse = {\n'
               '\t\t\tculture_group = east_asian\n'
               '\t\t}\n'
               '\t}\n'
               '}\n')

    def test_uses_harmony_or_pattern(self):
        # ★ 照抄 mod 3050177747（All Monuments for Player）的成熟写法：
        #     OR = {
        #         custom_trigger_tooltip = { tooltip = <解锁提示>
        #                                    owner = { ai = no } }   <- 恒真
        #         AND = { custom_trigger_tooltip = { tooltip = <作者的>
        #                                           <作者原条件> } }
        #     }
        #   关键：作者条件【包在 custom_trigger_tooltip 里】-> 生效但玩家看不到、
        #   不会和旁路项混在一起被裸求值（那是我之前卡死效果的根因）。
        d = st()
        out = S.wrap_top_level(self.BLOCK, 'can_upgrade_trigger', d)
        self.assertIn('owner = { ai = no }', out)          # 恒真旁路项
        self.assertIn('OR = {', out)                       # OR 结构
        self.assertIn('custom_trigger_tooltip', out)       # 作者条件被 tooltip 包住
        self.assertIn('religion = catholic', out)          # 原内容保留
        self.assertEqual(d['wrapped_can_upgrade_trigger'], 1)
        self.assertEqual(out.count('{'), out.count('}'))
    def test_bypass_is_not_raw_condition(self):
        # ★★ 血教训：玩家旁路【绝不能】和作者条件裸放在一起 ——
        #   触发器里裸条件会被真求值，作者条件不满足就卡死奇观效果。
        #   Harmony 写法把作者条件包进 custom_trigger_tooltip 里，所以安全。
        d = st()
        out = S.wrap_top_level(self.IF_ELSE, 'can_upgrade_trigger', d)
        # 恒真旁路项必须在，且不在作者的 tooltip 壳里面
        self.assertIn('owner = { ai = no }', out)
        # 作者原条件必须在（保留）
        self.assertIn('east_asian', out)
        self.assertIn('gp_ideas', out)
        # 作者内容必须被 custom_trigger_tooltip 包住（不能裸放）
        idx = out.index('gp_ideas')
        head = out[:idx]
        self.assertIn('custom_trigger_tooltip', head)
        self.assertEqual(out.count('{'), out.count('}'))
    def test_second_pass_is_noop(self):
        d = st()
        once = S.wrap_top_level(self.BLOCK, 'can_upgrade_trigger', d)
        twice = S.wrap_top_level(once, 'can_upgrade_trigger', d)
        self.assertEqual(once, twice)
        self.assertEqual(d['dup_can_upgrade_trigger'], 1)

    def test_empty_block_is_untouched(self):
        blk = ('m = {\n\ttype = monument\n'
               '\tcan_upgrade_trigger = {\n\t}\n}\n')
        d = st()
        self.assertEqual(S.wrap_top_level(blk, 'can_upgrade_trigger', d), blk)
        self.assertEqual(d['empty_can_upgrade_trigger'], 1)


class TestInjectGate(unittest.TestCase):
    def test_key_absent_gets_new_gate(self):
        d = st()
        out = S.inject_gate('m = {\n\ttype = monument\n}\n',
                            'can_use_modifiers_trigger', d)
        self.assertIsNotNone(out)
        self.assertIn('can_use_modifiers_trigger = {', out)
        self.assertIn(S.TT, out)
        self.assertEqual(d['inj_new'], 1)

    def test_empty_key_becomes_gate(self):
        d = st()
        out = S.inject_gate('m = {\n\ttype = monument\n\tcan_use_modifiers_trigger = {\n\t}\n}\n',
                            'can_use_modifiers_trigger', d)
        self.assertIsNotNone(out)
        self.assertIn(S.TT, out)
        self.assertEqual(d['inj_empty'], 1)

    def test_key_with_content_defers_to_wrap(self):
        d = st()
        block = ('m = {\n\ttype = monument\n\tcan_use_modifiers_trigger = {\n'
                 '\t\towner = { ai = no }\n\t}\n}\n')
        self.assertIsNone(S.inject_gate(block, 'can_use_modifiers_trigger', d))


class TestMakeMovableRaw(unittest.TestCase):
    """move=raw（老行为）：can_be_moved 一律改成 yes，谁都能在面板里搬。"""

    def setUp(self):
        self._old = S.MAKE_MOVE
        S.MAKE_MOVE = 'raw'

    def tearDown(self):
        S.MAKE_MOVE = self._old

    def test_no_becomes_yes(self):
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = no\n}\n', d)
        self.assertIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_yes'], 1)

    def test_no_with_trailing_comment(self):
        # 回归：源 mod 里写成 "can_be_moved = no<TAB>#注释"，早先会漏掉
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = no\t# why not\n}\n', d)
        self.assertIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_yes'], 1)

    def test_crlf_file(self):
        # 回归：CRLF 文件里 no 后面是 \r，早先会漏掉
        d = st()
        out = S.make_movable('m = {\r\n\tcan_be_moved = no\r\n}\r\n', d)
        self.assertIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_yes'], 1)

    def test_already_yes_untouched(self):
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = yes\n}\n', d)
        self.assertIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_yes'], 0)
        self.assertEqual(d['cbm_added'], 0)

    def test_absent_key_is_added(self):
        d = st()
        out = S.make_movable('m = {\n\ttype = monument\n}\n', d)
        self.assertIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_added'], 1)
        self.assertFalse(d['cbm_locked'])


class TestMakeMovableKeepUnmovable(unittest.TestCase):
    """1.3 新增：通路/地下城类（KEEP_UNMOVABLE 名单）永远锁 no，即使 move=raw。

    矮人隧道、升降机、妖精传送门、地下城入口、原版三条运河搬了会断地图通路
    或让地牢探索失效，所以这几件不能用"一键放开搬运"顺手放开。
    """

    def setUp(self):
        self._old_move = S.MAKE_MOVE
        self._old_keep = S.MAKE_KEEP_UNMOVABLE
        self._old_set = S.KEEP_UNMOVABLE
        S.MAKE_MOVE = 'raw'
        S.MAKE_KEEP_UNMOVABLE = True
        S.KEEP_UNMOVABLE = frozenset(('dd_stramolgiv', 'kiel_canal'))

    def tearDown(self):
        S.MAKE_MOVE = self._old_move
        S.MAKE_KEEP_UNMOVABLE = self._old_keep
        S.KEEP_UNMOVABLE = self._old_set

    def test_listed_monument_stays_locked(self):
        d = st()
        out = S.make_movable('dd_stramolgiv = {\n\tcan_be_moved = yes\n}\n', d)
        self.assertIn('can_be_moved = no', out)
        self.assertNotIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_locked'], 1)

    def test_listed_monument_locked_when_field_absent(self):
        # 源文件里没写 can_be_moved 时，补进去的必须是 no（不是 yes）
        d = st()
        out = S.make_movable('kiel_canal = {\n\ttype = monument\n}\n', d)
        self.assertIn('can_be_moved = no', out)
        self.assertEqual(d['cbm_locked'], 1)

    def test_listed_monument_crlf(self):
        d = st()
        out = S.make_movable('kiel_canal = {\r\n\tcan_be_moved = yes\r\n}\r\n', d)
        self.assertIn('can_be_moved = no', out)

    def test_unlisted_monument_still_opens(self):
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = no\n}\n', d)
        self.assertIn('can_be_moved = yes', out)

    def test_switch_off_disables_lock(self):
        # config.txt 写 keepunmovable=no 时回到 1.2 行为：一律放开
        S.MAKE_KEEP_UNMOVABLE = False
        d = st()
        out = S.make_movable('dd_stramolgiv = {\n\tcan_be_moved = no\n}\n', d)
        self.assertIn('can_be_moved = yes', out)

    def test_real_config_list_contains_the_known_tunnels(self):
        # 名单本身别被误删：抽查几个关键键名还在
        import amr_config as C
        for k in ('kiel_canal', 'suez_canal', 'panama_canal',
                  'dd_stramolgiv', 'the_wormway', 'domandrod_fey_portal'):
            self.assertIn(k, C.KEEP_UNMOVABLE)


class TestMakeMovableLocked(unittest.TestCase):
    """move=ai（默认）：can_be_moved 一律锁成 no —— AI 再也搬不动，
    玩家的搬运改走 generate.py 生成的搬迁决议。"""

    def setUp(self):
        self._old = S.MAKE_MOVE
        S.MAKE_MOVE = 'ai'

    def tearDown(self):
        S.MAKE_MOVE = self._old

    def test_yes_becomes_no(self):
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = yes\n}\n', d)
        self.assertIn('can_be_moved = no', out)
        self.assertNotIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_locked'], 1)
        self.assertEqual(d['cbm_yes'], 0)

    def test_yes_with_trailing_comment(self):
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = yes\t# movable in source\n}\n', d)
        self.assertIn('can_be_moved = no', out)
        self.assertIn('# movable in source', out)     # 行尾注释不能被吃掉
        self.assertEqual(d['cbm_locked'], 1)

    def test_crlf_file(self):
        d = st()
        out = S.make_movable('m = {\r\n\tcan_be_moved = yes\r\n}\r\n', d)
        self.assertIn('can_be_moved = no', out)
        self.assertEqual(d['cbm_locked'], 1)

    def test_already_no_untouched(self):
        d = st()
        out = S.make_movable('m = {\n\tcan_be_moved = no\n}\n', d)
        self.assertEqual(out, 'm = {\n\tcan_be_moved = no\n}\n')
        self.assertEqual(d['cbm_locked'], 0)
        self.assertEqual(d['cbm_added'], 0)

    def test_absent_key_is_added_as_no(self):
        d = st()
        out = S.make_movable('m = {\n\ttype = monument\n}\n', d)
        self.assertIn('can_be_moved = no', out)
        self.assertNotIn('can_be_moved = yes', out)
        self.assertEqual(d['cbm_locked'], 1)



class TestLeakedLines(unittest.TestCase):
    # 真实案例：[1.34]增加全球奇观 的 The_Towns_of_Edinburgh 提前闭合了
    # can_upgrade_trigger，紧随其后的判断语句掉到块外面。
    BLOCK = ('m = {\n'
             '\ttype = monument\n'
             '\tcan_upgrade_trigger = {\n'
             '\t}\n'
             '\tculture_group = latin\n'
             '}\n')

    def test_scan_finds_leaked_line(self):
        got = S.scan_leaked(self.BLOCK)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1], 'culture_group = latin')

    def test_scan_ignores_known_keys(self):
        self.assertEqual(S.scan_leaked('m = {\n\ttype = monument\n}\n'), [])

    def test_repair_moves_line_inside(self):
        d = st()
        out = S.repair_leaked_lines(self.BLOCK, d)
        self.assertEqual(d['moved_in'], 1)
        self.assertLess(out.index('culture_group = latin'), out.rindex('}'))

    def test_repair_leaves_clean_block_unchanged(self):
        d = st()
        block = 'm = {\n\ttype = monument\n\tcan_be_moved = yes\n}\n'
        self.assertEqual(S.repair_leaked_lines(block, d), block)
        self.assertEqual(d['moved_in'], 0)


class TestTokens(unittest.TestCase):
    def test_counts_and_strips_comments(self):
        c = S.tokens('a = { b = 1 }  # c = 2')
        self.assertEqual(c['='], 2)
        self.assertEqual(c['{'], 1)
        self.assertEqual(c['}'], 1)
        self.assertNotIn('c', c)


if __name__ == '__main__':
    unittest.main()
