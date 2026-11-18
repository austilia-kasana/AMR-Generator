# 1.3.5：「一键三级」决议改成可重复点（脚本层不再附带任何其他效果）

> 状态：**未游戏内复测**。文档里凡"已经证明"的说法都标注了证据等级，"推断"就是推断。

## 背景

玩家反馈两件事：

1. 决议点一次就消失（一次性国家标记），但玩家名下的奇观会**持续增加**（打下来、搬过来、事件给），
   后来拿到的奇观再也升不上去；
2. 要求"可重复点，但**不要**出其他效果"——不能变成加发展度的按钮。

## ★ 另修一个更大的 bug：中文标点在游戏里显示成 `?`

1.3.4 把"决议文本乱码"归因为 `0x1A`（"会"字的编码），**这个归因是错的**。

游戏内实测（截图）：决议标题显示为 **`奇观升级更便宜?更快`**，原文是 `奇观升级更便宜、更快` ——
乱码点是**顿号**，不是"会"。

根因在 `amr_font_codec.encode()`：

```python
if "\u4e00" <= ch <= "\u9fff":   # 只把汉字送去查表
    ...
else:
    out.append(ch)               # ← 中文标点走这里：原样写进文件
```

而汉化字库根本没有 `，、。；：` 这些**码位**的字形（它们的字形挂在三字节编码空间里，
`charmap.json` 里其实【有】这些标点的三字节编码，只是 encode 从来没去查）。
原样写出来的标点游戏找不到字形，就显示成 `?`。

修复：

- `encode()` 改成**只要 `charmap` 里有就编码**（标点全部命中），不再限制在汉字区间；
- `missing_chars()` 从"只查汉字"改成"查所有非 ASCII 且不在 charmap 里的字符"
  （`§` 引擎标记除外），这样真缺字时是**整条退回英文**，而不是显示 `?`。

另外更正 1.3.4 的归因：**`0x1A` 不是问题**。
主汉化包 `Chinese Language Mod for 1.37` 的 146 个 yml 里共有 **33,075** 个 `0x1A` 字节，
游戏里显示完全正常；所以 `_zh()` 的守卫改成只拦 `0x0A` / `0x0D`（这两个才真的会断行）。

## 改动

### ① 去掉一次性标记

`AMR_max_all_monuments` 的 `potential` 里的 `NOT = { has_country_flag = AMR_max_all_monuments_done }`
和 `effect` 里的 `set_country_flag = AMR_max_all_monuments_done` 都删掉，决议永久可用。

### ② 不再调用原版 `set_great_project_tier_3`

只去掉标记是不够的，原版这个脚本效果有两个副作用：

- **2 级→3 级送 +4 发展度、1 级→3 级送 +2**（0 级→3 级不送），
  依据 `common/scripted_effects/00_scripted_effects.txt:1387-1475` 里每条分支的
  `random_list = { add_base_tax 4 / add_base_production 4 / add_base_manpower 4 }`；
- **没有 Leviathan 时**它走 `else = { add_base_tax = 2 ... }`，等级**完全不涨**，
  于是 `NOT = { has_great_project = { tier = 3 } }` 的守卫永远成立 → 可以无限刷税基/生产/人力。

改成照抄它的三条分支、只保留等级提升：

```text
tier = 0  ->  add_great_project_tier = { type = X tier = 3 }    # 0 -> 3
tier = 1  ->  add_great_project_tier = { type = X tier = 2 }    # 1 -> 3
tier = 2  ->  add_great_project_tier = { type = X tier = 1 }    # 2 -> 3
```

效果：等级照样一次到 III，**脚本层一点发展度都不给**；已经 III 级的省份三条 `limit` 全不成立，
重复点不会发生任何事。

### ③ `tier` 是增量不是绝对值（评审确认）

`add_great_project_tier = { tier = N }` 的 `N` 是"加减几级"，不是"设成第几级"。两条独立证据：

- 原版 `events/flavorZIM.txt:50` 用 `tier = -1` 做文明衰败降级，负数只可能是增量；
- 印加国家形成相关脚本里，马丘比丘 1 级时写 `tier = 1`、否则写 `tier = 2`，只有增量解释才自洽。

所以上面三条分支的数学是对的，不会把 2 级奇观降到 1 级。

### ④ 升级打折决议默认与一键三级互斥

一键三级免费直达 III 之后，"升级打折"（50 杜卡特，`great_project_upgrade_cost/time = -0.9`）
收益为 0，玩家还会白花 50 块。所以：`config.txt` 里**没有明确写 `upgdec`** 时，
只要 `maxtierdec` 开着，就不生成打折决议；想两个都要写 `upgdec=force`。

### ⑤ `aimove` 的 defines 文件改名 + 冲突预警

- 文件名 `00_amr_ai_move.lua` → `zzzz_amr_ai_move.lua`。
  不同名的 defines 文件不是"谁覆盖谁"，而是**各执行一遍、后赋值的赢**，顺序按文件名排序；
  `00_` 前缀等于永远第一个被赋值，别人写个 `10_`/`zz_` 就把归零改回去了。
- 生成时扫一遍播放集里其他 mod 的 `common/defines/*.lua`，命中 `GREAT_PROJECT_DESIRE_*`
  就在日志里点名预警（不致命，只影响 AI 搬运倾向，玩家侧不受影响）。
- 1.37.5 的 `common/defines.lua` 里确认这四个键都存在：
  `GREAT_PROJECT_DESIRE_MOVE_FROM_SUBJECT_MODIFIER`(1625)、`_CAPITAL_MODIFIER`(1630)、
  `_CAPITAL_BASE`(1631)、`_CAPITAL_AREA_MODIFIER`(1632)。

## ★ 还没排除的副作用：`on_upgraded`

奇观定义的 `tier_N` 里可以有 `on_upgraded = { ... }`，语义是"升级完成时执行"。
**`add_great_project_tier` 会不会触发它，尚未验证**（wiki 的 Great project modding 页没说，
本仓库没有实测记录）。

播放集实测量（脚本 `_交接` 里的一次性统计，数据来源：原版 + 播放集 8 个目录 / 48 个文件）：

| 项 | 数量 |
|---|---|
| `on_upgraded` 块总数 | 8,975 |
| 其中**空块** | 5,230 |
| 其中**非空** | **3,745** |
| 非空里出现最多的效果 | `add_base_tax` 2144、`add_base_manpower` 2013、`add_base_production` 1953、`add_prosperity` 580、`add_estate_loyalty` 252 |
| 原版样例 | `owner = { add_prestige = 30 }` |

**如果它会触发**，一次点击会给 600+ 座奇观各发一份升级奖励（发展度/繁荣/威望），
那"零副作用"就不成立。验法（不用改代码）：在游戏里点决议前后看**某座奇观所在省的发展度**，
或看**威望**——一次跳一大截就是触发了，纹丝不动就是没触发。

## 验证

- `python -m py_compile` 通过；
- 测试 117 例全过（`src/tests`）；
- 干跑决议生成（不写 mod 目录）：首字节 `country_decisions`、大括号 43/43 平衡、
  无 `random_list` / `add_base_tax` / `一次性标记`、每件奇观正好三条分支；
- **尚未做游戏内复测**（游戏还开着，旧输出目录删不掉）。

## 已知待定

1. `on_upgraded`（见上）——**发布前应实测**；
2. 决议仍为 `major = yes`（评审建议保留：它只是视觉上突出，不产生弹窗/AI 行为）；
3. 构建时对"没有 `tier_3` 定义的奇观"没有预警（评审建议加，尚未做）；
4. 决议文件体积：668 件奇观 × 3 分支 ≈ 1.4 万行 / 约 400 KB，一次点击约 40 万次触发器求值，
   没在 300 省以上的大档实测过卡顿。
