# 1.3.5：「一键三级」决议改成可重复点（并且不再附带任何其他效果）

## 背景

玩家反馈两件事：

1. 决议点一次就消失（一次性国家标记），但玩家名下的奇观会**持续增加**（打下来、搬过来、事件给），
   后来拿到的奇观再也升不上去；
2. 要求"可重复点，但**不要**出其他效果"——不能变成加发展度的按钮。

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

效果：等级照样一次到 III，**一点发展度都不给**；已经 III 级的省份三条 `limit` 全不成立，
重复点不会发生任何事。

### ③ `tier` 是增量不是绝对值

`add_great_project_tier = { tier = N }` 的 `N` 是"加减几级"，不是"设成第几级"。
反证：原版 `events/flavorZIM.txt:50` 用 `tier = -1` 做文明衰败降级，负数只可能是增量。

### ④ 其他

- 决议文案（中/英）从"每局只能用一次"改成"免费、可重复点"；
- `TOOL_VERSION` → `1.3.5`；
- 生成器自检：断言产物里**没有** `AMR_max_all_monuments_done`，且每件奇观都有 `tier = 0 → +3` 直达分支。

## 验证

- `python -m py_compile` 通过；
- 测试 117 例全过（`src/tests`）；
- 干跑决议生成（不写 mod 目录）：首字节 `country_decisions`、大括号 43/43 平衡、
  无 `random_list` / `add_base_tax` / 一次性标记、每件奇观正好三条分支；
- **尚未做游戏内复测**。

## 已知待定（评审请重点看这几条）

1. 决议仍为 `major = yes`，可重复之后会常驻"重大决议"高亮，是否改普通决议未定；
2. 升级打折决议（50 杜卡特，-90% 升级花费/时间）与一键三级强度重叠：
   一键三级免费直达 III 之后，打折收益为 0，默认是否只发其中一个还没定；
3. `aimove` 那条注释"本 mod 名以 `!AMR` 开头，按名字排序最前，defines 覆盖优先"是**推断**，
   没有区分度实验证据：`00_` 系列验证过的是"同名文件只加载一份、名字靠前赢"，
   而两个**不同名**的 `common/defines/*.lua` 会各执行一遍，理论上后赋值者生效；
4. 决议文件体积：668 件奇观 × 3 分支 ≈ 1.4 万行 / 约 400 KB，一次点击约 40 万次触发器求值，
   未在低配机上测过卡顿。
