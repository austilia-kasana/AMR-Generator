# 1.3 游戏内测试报告

> 执行者：有 computeruse 的会话
> 时间：2026-11-18 23:30–00:00
> 对应指南：`19_1.3游戏内测试指南.md`

## 0. 测试环境

| 项 | 值 |
|---|---|
| 游戏 | EU4 v1.37.5.0（Steam 版） |
| 构建 | `mod\!AMR_all_monuments_relocatable_pa7f39d02` |
| 播放集 | 24 个 mod，其中 `!AMR` **只有这一份**（已核实 `dlc_load.json`） |
| 存档 | `威尼斯1582_01_01.eu4`（14,539 KB，2026-11-09 18:03） |
| 配置 | `move=keep`、`aimove=yes` |
| 分辨率 | 2560×1440 全屏 |
| 原始 error.log 基线 | 19,615,452 字节 / 208,299 行 |

**defines 是否生效**：eu4 进程启动 23:23:43，`00_amr_ai_move.lua` 写入 23:16:30，进程晚 7.2 分钟 → **本次加载已读取，无需重启**。

---

## 1. 结果总表

| 测试 | 结果 | 证据 |
|---|---|---|
| 进图/读档 | ✅ | 正常进入威尼斯 1582-01-01 暂停态 |
| **A 一键三级决议** | ✅ | `game.log` 有执行记录；名下 2 座奇观 0→3 |
| B keep：作者锁住的仍锁 | ✅（数据层） | `can_be_moved = no` = **984** 条 |
| B keep：作者允许的可搬 | ✅（数据层） | `can_be_moved = yes` = **19** 条（预期约 19） |
| B keep：耗时非 1 | ✅（数据层） | `AMR: move time` = **0** 条 |
| C defines 文件 4 行正确 | ✅ | 3 行注释 + 4 行 `NDefines.NAI.* = 0` |
| C 启动无 defines 报错 | ✅ | 新增 19,307 行日志中，AMR/defines/GreatProject 命中 **0** |
| D 跑 3 个月不崩 | ✅ | 实跑 **1582-01-01 → 1584-01-01（两年）** |
| 回归：两个决议都在 | ✅ | 三个决议文件均在，列表可点 |

**未覆盖项**（本会话没做）：
- B 的**游戏内移动按钮**外观（作者允许的可搬/运河类灰掉）——只做了数据层
- C 的**可选观察**（`observe` 跑 3~5 年看 AI 是否还搬奇观）

---

## 2. 测试 A 详细证据

### 2.1 执行确认

`logs\game.log` 末尾：

```
[effectimplementation.cpp:25375]: EVENT [1583.09.01]:AMR: all owned monuments set to tier 3
```

> ⚠️ 注意：`log = "..."` 写的是 **`game.log`**，不是 `error.log`。排查决议有没有执行请看 game.log。

### 2.2 存档级比对

方法：解包 `.eu4`（实为 ZIP）→ 读 `gamestate` → 解析 `great_projects` 块 → 取每个奇观的 `development_tier`。

| | tier0 | tier1 | tier2 | tier3 |
|---|---|---|---|---|
| 点击前（1582-01-01 存档） | 388 | 66 | 13 | 105 |
| 点击后（1584-01-01 autosave） | 386 | 66 | 13 | 107 |

**变化明细（2 座）**：

```
al_azhar_university    0 → 3
pyramid_of_cheops      0 → 3
```

### 2.3 为什么只有 2 座

威尼斯此存档已吞并埃及，名下只有这 2 座奇观。其余 570 座属于别的国家，按设计不该动。**这是正确行为，不是缺陷。**

### 2.4 附加验证

两个奇观都是 **0 → 3 直接跳级**，验证了 `19` 号文档之外的另一条技术事实：
`set_great_project_tier_3` 一次调用即可从 0 级直达 3 级，**不需要**连着调 tier_1/tier_2。

---

## 3. 测试 B 详细证据（数据层）

构建目录 `mod\!AMR_all_monuments_relocatable_pa7f39d02\`：

```
common\defines\00_amr_ai_move.lua        存在，3 行注释 + 4 行赋值
  NDefines.NAI.GREAT_PROJECT_DESIRE_MOVE_FROM_SUBJECT_MODIFIER = 0
  NDefines.NAI.GREAT_PROJECT_DESIRE_CAPITAL_MODIFIER = 0
  NDefines.NAI.GREAT_PROJECT_DESIRE_CAPITAL_BASE = 0
  NDefines.NAI.GREAT_PROJECT_DESIRE_CAPITAL_AREA_MODIFIER = 0

common\great_projects\*.txt（22 个文件）
  can_be_moved = yes : 19
  can_be_moved = no  : 984
  AMR: move time     : 0
```

结论：`move=keep` 正确保留了作者原值——19 个允许、984 个锁定，且**没有**把搬运耗时统一改写成 1。

---

## 4. 测试 C 详细证据

- `00_amr_ai_move.lua` 存在且内容正确（见上）
- error.log 新增 19,307 行，其中 `00_amr_ai_move` / `NDefines` / `Great Project` **全部 0 命中**
- 新增日志的错误主体与本次 mod 无关：
  - `spritetype.cpp` 8,928 条（UI mod 缺贴图）
  - `scriptable_gui.cpp` 5,955 条（缺 scripted icon）
  - `province.cpp` / `triggerimplementation.cpp` / `gamestate.cpp` 若干（其他 mod 的作用域/事件目标问题，如 `economic_ideas`、`IW_third_party`、`superflag`）

---

## 5. 测试 D 详细证据

- 解除暂停后从 1582-01-01 跑到 **1584-01-01**（两年，远超 3 个月要求）
- eu4 进程全程存活（PID 4136，运行 31 分钟，内存 1.88 GB）
- 期间触发并处理了多个事件（卖官鬻爵、咖啡关税、教士不满、城市要求大议会席位、殖民地商标等），无崩溃/黑屏
- 两个决议在测试结束时仍在列表中可点

---

## 6. 本次踩到的坑（排查用，非 mod 问题）

1. **`major = yes` 的决议排在决议列表最底部**。只翻前 15 行会误判"决议不存在"。
2. 每行右侧三个控件：**金盘=执行 / ?=帮助 / 信封=通知开关**（tooltip 明写"点击更改通知状态"）。
3. **比对存档必须确认存档时间晚于操作时间**。第一次比对用了执行前的 autosave（23:44:28 vs 执行 23:51:43），得出"零变化"的错误结论。
4. `log = "..."` 进 **game.log**，不进 error.log。

完整操作细节见 `21_EU4_游戏内自动化操作指南.md`。

---

## 7. 结论

**1.3 版三项改动全部通过游戏内/数据层验证。**

- 一键三级决议：可用、生效、名下奇观全部到 III
- `move=keep`：作者锁定仍锁、作者允许仍可搬、耗时未被改写
- `aimove=yes`：defines 正确加载、无解析报错、两年内无崩溃

建议下一步（可选）：
- 补测 B 的游戏内移动按钮外观
- 补测 C 的 observe 观察
