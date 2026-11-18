# AMR Generator / EU4 全奇观解锁并搬迁生成器

EU4（Europa Universalis IV）1.37 的奇观（Great Project）规则生成器。读取当前播放集里已启用的奇观 mod，生成一个玩家专用的 mod：

- 奇观加成/升级条件对玩家生效
- 搬迁默认开启：全部奇观都能搬（`move=raw`）
- 可选：只解除使用限制（`move=keep`），保留作者写的搬运限制
- 可选：关掉搬迁功能（`move=ai`，谁的“移动”按钮都锁上）
- 可选：一键把所有已拥有奇观升到 III 级（可重复点，只改等级、不给发展度）
- 可选：外部 defines 降低 AI 搬运奇观的倾向
- 可选：隐藏奇观处理、年份闸、建造折扣、升级折扣等

生成器本身不包含任何游戏素材；生成的 mod 才会引用对应源 mod 的定义。

## 环境

- Python 3.10+（仅标准库即可运行生成器）
- 打包 exe 需要：`pip install pyinstaller pillow`
- EU4 1.37.x，用户目录默认在 `Documents/Paradox Interactive/Europa Universalis IV`

## 运行

```bash
python src/generate.py
```

首次运行前把 `config.example.txt` 复制为 `config.txt`，按需修改。

配置示例：

```ini
# 搬运：raw=全部放开（默认）；ai=全部锁死（关掉搬迁功能）；keep=只解使用限制，保留作者限制
move=raw
# 想要“只解使用限制、不解除搬运限制”就改成：
# move=keep
# 想关掉搬迁功能就改成：
# move=ai
# AI 搬运倾向：yes=写外部 defines 归零；no=不动
aimove=yes
# 一键三级决议（可重复点）
maxtierdec=yes
# 升级打折决议：默认与一键三级互斥；想两个都要写 upgdec=force
upgdec=no
```

完整开关见 `src/amr_config.py` 顶部注释。

## 测试

```bash
python -m unittest discover -s src/tests -v
```

当前 117 例测试。游戏内测试记录见 [docs/TEST_REPORT_1.3.md](docs/TEST_REPORT_1.3.md)，P0 修复记录见 [docs/FIXES_1.3.1.md](docs/FIXES_1.3.1.md)，一键三级决议修复见 [docs/FIXES_1.3.3.md](docs/FIXES_1.3.3.md)，决议文本乱码修复见 [docs/FIXES_1.3.4.md](docs/FIXES_1.3.4.md)。

## 打包 exe

```bash
python -m PyInstaller --noconfirm --onefile --name AMR_Generator \
  --add-data "src/charmap.json;." src/generate.py
```

Windows 下把 `;` 换成 PyInstaller 的分隔符；输出在 `dist/AMR_Generator.exe`。

## 结构

```
src/
  generate.py          入口 / 主流程
  amr_config.py        开关默认值与 config.txt 解析
  amr_rules.py         奇观规则改写
  amr_script.py        括号/块解析与触发条件改写
  amr_build.py         输出构建与校验
  amr_docs.py          说明文本模板
  amr_scan.py          播放集/素材扫描
  amr_saves.py         存档体检 / 救援
  amr_check.py         生成结果自检
  amr_font_codec.py    汉化字库编解码
  charmap.json         字库映射
  tests/               单元测试
docs/
  TEST_REPORT_1.3.md   1.3 游戏内测试报告
```

## 已知边界

- `can_be_moved` 是定义层字段，引擎不读其中的条件：**不能做到“只锁 AI、不锁玩家”**。`aimove` 改的是 AI 倾向（外部 defines），不是硬锁。
- `move=keep` 下作者锁住的奇观仍然不能搬，这是正确行为。
- 生成器不包含游戏本体或任何 mod 的素材；请只分享生成器本身，不要公开分发包含他人定义的完整构建。

## English

A rule generator for EU4 Great Projects (v1.37). It scans the enabled monument mods in the current playset and writes a player-focused mod. It contains no game assets. See `src/amr_config.py` for options and `docs/TEST_REPORT_1.3.md` for the in-game test report.
