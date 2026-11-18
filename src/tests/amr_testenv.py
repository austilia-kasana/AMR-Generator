# -*- coding: utf-8 -*-
"""测试垫片：把 src 加进 sys.path、静音日志、避开对真实文件的副作用。

用法（必须在导入任何 amr_* 模块之后立刻调用 prepare()）：
    import amr_testenv
    import amr_script as S
    amr_testenv.prepare()
"""
import collections
import os
import sys

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def silence_logs():
    """把各模块里的 log 换成空函数。

    amr_* 之间是 `from amr_env import log` 逐个拷贝的，所以要按模块逐个换，
    不能只改 amr_env.log。否则测试会把真实的 生成日志.txt 覆盖掉。
    """
    for name, mod in list(sys.modules.items()):
        if name.startswith('amr_') and hasattr(mod, 'log'):
            setattr(mod, 'log', lambda *a, **k: None)


def prepare():
    """导入 amr_* 之后调用一次：关掉异常兜底、静音全部日志。"""
    # amr_env 会装一个把异常写进 生成日志.txt 的钩子，测试里必须禁掉。
    sys.excepthook = sys.__excepthook__
    silence_logs()


def stats():
    """测试用统计字典：允许 stats['x'] += 1 而不必预先初始化每个键。"""
    return collections.defaultdict(int)
