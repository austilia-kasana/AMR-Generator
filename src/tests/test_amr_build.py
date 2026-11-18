import os
import re
import tempfile
import unittest

import amr_build as B
import amr_rules as R
import amr_script as S


SRC = """kiel_canal = {
	type = monument
	start = 1
	can_be_moved = yes
	build_trigger = { always = yes }
}
normal = {
	type = monument
	start = 2
	can_be_moved = no
	build_trigger = { always = yes }
}
can_be_moved = no
"""


class TestProcessFileMoveFallback(unittest.TestCase):
    """构建层回归：全文件兜底不能把 KEEP_UNMOVABLE 的保护改回 yes。

    只测 make_movable() 不够：process_file() 后面还有一次全文件
    can_be_moved 兜底替换，早先会连块内刚锁好的名单奇观一起改成 yes。
    """

    def setUp(self):
        self._old = {
            'S_move': S.MAKE_MOVE, 'R_move': R.MAKE_MOVE, 'B_move': B.MAKE_MOVE,
            'S_keep': S.MAKE_KEEP_UNMOVABLE, 'S_set': S.KEEP_UNMOVABLE,
            'R_md': R.MAKE_MOVEDAYS,
        }
        S.MAKE_MOVE = R.MAKE_MOVE = B.MAKE_MOVE = 'raw'
        S.MAKE_KEEP_UNMOVABLE = True
        S.KEEP_UNMOVABLE = frozenset(('kiel_canal',))
        R.MAKE_MOVEDAYS = '1'

    def tearDown(self):
        S.MAKE_MOVE = self._old['S_move']
        R.MAKE_MOVE = self._old['R_move']
        B.MAKE_MOVE = self._old['B_move']
        S.MAKE_KEEP_UNMOVABLE = self._old['S_keep']
        S.KEEP_UNMOVABLE = self._old['S_set']
        R.MAKE_MOVEDAYS = self._old['R_md']

    def test_protected_stays_no_after_process_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'in.txt')
            dst = os.path.join(d, 'out.txt')
            with open(src, 'w', encoding='latin-1', newline='') as f:
                f.write(SRC)
            B.process_file(src, dst, 'test')
            with open(dst, encoding='latin-1') as f:
                out = f.read()

        # 名单内：块内必须是 no（不能被全文件兜底改回 yes）
        m = re.search(r'kiel_canal\s*=\s*\{.*?\n\}', out, re.S)
        self.assertIsNotNone(m, out)
        self.assertIn('can_be_moved = no', m.group(0))
        self.assertNotIn('can_be_moved = yes', m.group(0))

        # 名单外：raw 仍应放开
        m2 = re.search(r'normal\s*=\s*\{.*?\n\}', out, re.S)
        self.assertIsNotNone(m2, out)
        self.assertIn('can_be_moved = yes', m2.group(0))

        # 块外漏网字段：raw 仍按 yes 修
        self.assertTrue(re.search(r'(?m)^\s*can_be_moved\s*=\s*yes\s*$', out), out)


if __name__ == '__main__':
    unittest.main()
