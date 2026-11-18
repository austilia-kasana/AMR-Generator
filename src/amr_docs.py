"""AMR 生成器 · 四份说明文本

改文案只改这个文件，不用碰任何逻辑：
  README_TPL  生成出来的 mod 里的 README_说明.txt
  WS_TPL      生成出来的 mod 里的 创意工坊简介.txt
  SHUOMING    生成器文件夹里的 说明.txt
  TOOL_README 上传包里的 README_工具说明.txt
README_TPL / WS_TPL 里用 %(name)s 这类占位符，由 generate.py 填值。

注意：模板是按 %(name)s 这种字典格式化的，正文里不要出现单独的 %% 号。
"""
README_TPL = '''%(name)s
（本 mod 文件夹里的说明 · readme inside this mod folder）

这个 mod 让播放集里的所有奇观（Great Project）对你（玩家）无条件生效；搬运按 config.txt 的 move= 设置处理。
This mod makes every Great Project in your playset work unconditionally for you (the player); relocation follows the move= setting in config.txt.

【怎么用】 How to use
1) 启动器里勾选名字以「!AMR」开头的这一条，拖到已启用列表【最前面】。
   Enable the entry whose name starts with "!AMR" and drag it to the top of your playset.
2) 重启游戏。
   Restart the game.
3) %(move_cn)s
   %(move_en)s

【这一份覆盖什么】 What this build covers
本版本：%(total)d 件奇观 / %(files)d 个文件。
This build: %(total)d Great Projects in %(files)d files.
%(notes)s

【注意】 Notes
- 只有玩家受益，AI 和 AI 附庸照旧。搬运限制由 config.txt 的 move= 决定（raw / ai / keep）。
  Only the player benefits; AI and AI subjects are unaffected. Relocation rules
  depend on move= in config.txt (raw / ai / keep).
- %(tune_cn)s
  %(tune_en)s
- 一个播放集里只勾【一份】本 mod。
  Enable only ONE build of this mod per playset.
- 以后新装了加奇观的 mod，要重跑一次生成器。
  After adding a new monument mod, re-run the generator.
'''


WS_TPL = '''%(name)s

最重要的两条问题放前面
Q1. 为什么做成工具形式，而不是游戏内决议开关？

A1.最初就是决议模式，但决议改不了定义层（start、date、can_be_moved），而且照样要在每条定义里插判定，等于一样要接管 common/great_projects，兼容性一点没省。所以改成工具。
It started as a decision mod, but a decision cannot touch the definition layer (start, date, can_be_moved) and still needs a flag check inside every definition, so it takes over common/great_projects anyway and saves nothing. That is why it became a generator.

Q2. 为什么不直接发布成品 submod？

A2.最关键的是，成品里带着其他 mod 的定义和图标，等于分发他人内容，会被 Steam 判定并下架。其次各 mod 对 submod 的态度不同，作者没精力逐个求证；而且成品一样要接管奇观目录，装两个照样互相顶掉。后续可能针对授权允许的 mod 单独上传。
The main reason is that a finished build carries other mods' definitions and icons, which counts as redistributing someone else's content and gets taken down once Steam rules on it. On top of that, submod policies differ and the author has no time to ask every one, and a finished submod still takes over the monument folder, so two of them override each other anyway. Builds for the mods that explicitly allow it may follow later.

V1.3.5
「奇观全部升到三级」改成【可以重复点】：玩家名下的奇观会一直增加（打下来、搬过来），一次性决议用掉之后，新到手的奇观就再也升不上去了。同时不再调用原版 set_great_project_tier_3，改成用它那三条分支、只提升等级 —— 原版在 2→3 时送 +4 发展度、1→3 时送 +2，而且没有 Leviathan 时会退化成“等级不涨、只加税基/生产/人力”，重复点等于无限刷。现在点多少次都只改等级，一点发展度都不给。另有两项调整：一键三级已经免费直达 III 之后，“升级打折”（50 杜卡特）就只剩花钱，所以两者默认互斥（想都要：config.txt 里写 upgdec=force）；aimove 的 defines 文件改名 zzzz_amr_ai_move.lua —— 不同名的 defines 文件是各执行一遍、后赋值的赢，原来叫 00_ 等于永远第一个被别的 mod 改回去；生成时还会扫一遍播放集，发现别的 mod 也改这几个键就预警。
V1.3.5
The "set every owned monument to tier 3" decision is now repeatable: players keep acquiring monuments (conquest, relocation), so a one-shot decision stopped helping with the ones you get later. It also no longer calls vanilla set_great_project_tier_3 - that effect hands out +4 development on 2->3 and +2 on 1->3, and without Leviathan it falls back to adding tax/production/manpower without ever changing the tier, which a repeatable click would farm forever. The decision now uses vanilla's three tier branches and only raises the tier: no development, ever. Two smaller changes: once the free tier-3 decision exists the 50-ducat upgrade discount is pointless, so the two are mutually exclusive by default (write upgdec=force to get both); and the aimove defines file is now zzzz_amr_ai_move.lua, because defines files with different names all run and the last assignment wins, so a 00_ prefix guaranteed everyone else overwrote it. The generator now also scans the playset and warns when another mod touches the same keys.

V1.3
新增决议「奇观全部升到三级」：免费、无冷却，点一次你名下所有已拥有的奇观直接升到三级（用的是原版自带效果，0/1/2 级都能一次到位）。通路/地下城类奇观（矮人隧道、升降机、妖精传送门、地下城入口，加原版三条运河，共 38 件）现在【永远不可搬】，不会被"一键放开搬运"顺手放开 —— 搬了会断地图通路或让地牢探索失效。新增 `move=keep`：只解除使用限制，can_be_moved 和搬运耗时完全保留作者原样，不解除搬运限制。新增 `aimove=yes`：生成 common/defines/zzzz_amr_ai_move.lua，把 AI 的奇观搬运倾向四项归零（不影响玩家）。修正"恢复被注释掉的 start"的逻辑：作者在注释里写明"doesnt need this / 不需要"的，不再被误恢复成真 start。
A "set every owned monument to tier 3" decision: free, no cooldown, one click takes all monuments you own straight to tier 3. Tunnel/dungeon monuments (38 of them - dwarven tunnels, lifts, fey portals, dungeon entrances plus the three vanilla canals) now always stay unmovable, because moving them would break map passages or dungeon exploration. New `move=keep`: only the use restrictions are lifted; can_be_moved and move time stay exactly as the author wrote them, so movement is still restricted. New `aimove=yes`: writes common/defines/zzzz_amr_ai_move.lua, zeroing the four AI Great Project relocation desire values (the player is unaffected). Fixed the restoration of commented-out start lines: when the author's comment says the start is not needed, it is no longer restored.

V1.2
省份面板可搬运，且又快又便宜（每距离基础搬运时间统一为 1）；新增决议「奇观升级更便宜、更快」（扣 50 杜卡特，升级花费/时间 −90%%）；建造规则重做，玩家与 AI 用 if/else 分开，AI 照旧按作者原本的条件自己建；年份没到的建不了，同一件建不出第二个（全局标记）；有 start 的钉回它自己那个省，没有 start 的隐藏奇观改在玩家首都建；修掉 146 件奇观条件失效的老 bug。
Fast, cheap relocation from the province panel; a "cheaper and faster upgrades" decision (50 ducats, -90%%); a rebuilt build rule splitting player and AI with if/else, so the AI keeps building on the author's own conditions; no building before the historical date or twice (global flag); monuments with a start province stay there, hidden ones without a start go to your capital; fixed the bug that had broken 146 monuments.

V1.1
新增老存档检验（通过检验的老存档即可使用）；优化部分代码；针对原神奇观 mod 的隐藏奇观做了专项处理。
Added the old-save check (a passing old save now works), cleaned up part of the code, and gave the hidden Great Projects in the Genshin mod dedicated handling.
---------------
由某不知名蓝色大肥鱼制作 Made By Deepseek
全奇观解锁并搬迁 All Monuments Unlocked & Movable (Generator)V1.3
（这是工具版：生成器本身，游戏里不起作用；游戏内容在它生成出来的那个 mod 里）
(This is the generator tool itself - it does nothing in game; the actual game content is in the mod it generates.)

包里有什么 / What is in this folder
AMR_Generator.exe 双击就能跑，不用装 Python / double-click, no Python needed
一键生成-源码版.bat 用 Python 跑的等价入口（需要装 Python）/ Python entry point
解禁无省份奇观.bat / 解禁年份未到奇观.bat 两个解禁开关 / two unlock helpers
存档体检.bat 老存档体检：会掉多少件、缺谁的 / old-save check (see below)
体检.bat 生成结果自检（22 项；脚本是 src\\amr_check.py）/ self-check (22 rules; script: src\\amr_check.py)
amr_plan.py 拿存档离线算"哪些奇观、哪些省、能不能建"（在 src 里） / offline planner over a save
amr_*.py 生成器的功能模块（源码版跑的时候需要，别单独删）
config.txt 开关设置 / the switches
说明.txt 完整说明（中文 + English）/ full manual (Chinese + English)

它做什么 / What it does
读你当前播放集里【已启用】的奇观 mod，生成一个 mod：其中每件奇观（Great Project）对玩家无条件生效，并且都能搬运。
It reads the monument mods enabled in your playset and generates a mod where every Great Project always works for the player, and can be moved.
奇观的名字、图片、定义仍来自原 mod，本工具只改规则。
Names, pictures and definitions still come from the original mods; this tool only changes the rules.

怎么用 / How to use
1) 双击 AMR_Generator.exe（或 一键生成-源码版.bat）。
Double-click AMR_Generator.exe (or 一键生成-源码版.bat).
2) 启动器里勾选生成出来的、名字以「!AMR」开头的 mod，并拖到已启用列表【最前面】。
In the launcher enable the generated mod whose name starts with "!AMR" and drag it to the top.
3) 重启游戏。
Restart the game.

结果写到哪 / Where the result goes
文档 / Paradox Interactive / Europa Universalis IV / mod / 下面，文件夹名以 !AMR_ 开头。
Under Documents / Paradox Interactive / Europa Universalis IV / mod/, in a folder starting with "!AMR_".

老存档 / Old saves
存档记着每件奇观在哪个省、几级、哪年建的。这次生成如果少勾了某个加奇观的 mod，它的奇观在旧存档里会永久消失，救不回来。所以只有一条规则：生成时勾的 mod 不能比存档当时少。
双击 存档体检.bat（或把 .eu4 拖上去）会列出这份存档会少几件、缺哪个 mod，写 0 就放心开档。回车 = 查"继续游戏"那份存档，输入 a = 查全部；按 y 可先把缺的临时补回来应急（能看能用，不能搬）。
A save stores each monument's province, level and date. Miss a monument mod when generating and its monuments are gone from the old save for good, so keep at least the mods the save had. Double-click 存档体检.bat (or drop a .eu4 onto it): it lists the losses and the missing mod; 0 means safe. Enter = the "Continue" save, a = all saves, y = restore the missing ones as a stopgap (usable, not movable).

注意 / Notes
- 收录的是【运行那一刻】已启用的奇观 mod；新装了加奇观的 mod 要重跑一次。
It covers the monument mods enabled at that moment; re-run it after adding a new one.
- 生成的完整版含别人 mod 的定义副本，建议自己用，别公开转发。要公开分享就分享这个工具本身，或"原版奇观版"（config.txt 里写 generic=yes 生成）。
The generated "full" version contains copies of other mods' definitions - keep it for yourself; share this tool itself, or build the vanilla-only version (generic=yes in config.txt).
- 会关掉铁人成就（改了游戏规则）。
Disables ironman achievements (it changes the game rules).

【常见问题】 FAQ
Q1 出问题了该看哪里？
A1 生成器文件夹里的 生成日志.txt。开头写着这次读的 config.txt 和生效值，读不进来的 mod 会以 !! 开头单独列出。
Q2 AI 也会吃到加成吗？奇观会被 AI 弄没吗？
A2 AI 照旧按作者原本的条件自己建自己的奇观；"对玩家无条件生效"只对你生效，所以奇观在 AI 手里不会消失。用了 解禁无省份奇观.bat 之后，那批隐藏奇观才改成谁占谁享，AI 也吃得到。
Q3 我只想要搬迁，不想要全解锁，行吗？
A3 不行，本工具是"对玩家全生效 + 全可搬迁"打包好的。能单独调的只有隐藏奇观那一批的边界，用两个解禁 bat。
Q4 EU4 已停止更新，以后还要重跑吗？
A4 游戏本体不会再动，会动的是各个奇观 mod。哪个 mod 更新了、或者你换了播放集，重跑一次就行。
Q5 为什么有两个同名奇观，图标还不一样？
A5 那是源 mod 自己定义重了（同名两件、图不同），不是本工具造成的，当成两件独立奇观即可。
Q6 建造按钮是灰的 / 某件奇观不让我建？
A6 三种原因：① 还没到它的历史年份（每件按自己的 date 解锁）；② 它已经建过了（同一件全世界只此一份）；③ 有历史定位的只能建在它自己那个省，没有所属省份的隐藏奇观只能建在你的首都。想放开年份就用 解禁年份未到奇观.bat。

【FAQ】 English
Q1 Where do I look if something goes wrong? — At 生成日志.txt in the generator folder; it prints which config.txt was read and the effective values, and lists any unreadable mod with a "!!" prefix.
Q2 Does the AI get the bonuses? Can the AI take monuments away? — The AI keeps building on the author's own conditions, and "always works for the player" applies to you only, so AI-held monuments do not disappear. After 解禁无省份奇观.bat those hidden ones become "whoever holds it", AI included.
Q3 I only want relocation, not a full unlock? — No; the tool always unlocks use. Relocation is controlled separately by move= (keep / raw / ai), and aimove=yes can stop the AI from relocating without changing the player's rules.
Q4 Do I need to re-run it later? — The base game will not change any more, the monument mods will. Re-run whenever one updates or you switch playsets.
Q5 Two monuments share a name but have different icons? — The source mod defines that name twice with different art; not from this tool.
Q6 Why is the build button greyed out? — (1) its historical date has not arrived; (2) it has already been built - only one of each exists; (3) it has a start province, or is a hidden one with no start (capital only). Use 解禁年份未到奇观.bat to lift the date lock.
'''
SHUOMING = '''全奇观解锁并搬迁 · 生成器 / All Monuments Unlocked & Movable - Generator

它做什么 / What it does
读你当前播放集里【已启用】的奇观 mod，生成一个 mod：其中每件奇观（Great Project）对玩家无条件生效，并且都能搬运。
It reads the monument mods enabled in your playset and generates a mod where every Great Project always works for the player, and can be moved.
奇观的名字、图片、定义仍来自原 mod，本生成器只改规则。
Names, pictures and definitions still come from the original mods; the generator only changes the rules.

怎么用 / How to use
1) 双击 一键生成-源码版.bat（需要装 Python，装法见文末）；不想装 Python 就双击 AMR_Generator.exe。
   Double-click 一键生成-源码版.bat (needs Python, see the end); or AMR_Generator.exe if you have no Python.
2) 启动器里勾选名字以「!AMR」开头的 mod，并拖到已启用列表【最前面】（名字里的 !AMR 不能去掉）。
   In the launcher enable the mod whose name starts with "!AMR" and drag it to the top of the playset (keep the "!AMR" prefix).
3) 重启游戏。
   Restart the game.
4) 想搬奇观：省份面板里点奇观，会看到「移动」按钮，自己挑目标省份。
   搬迁【又快又便宜】：所有奇观的"每距离基础搬运时间"都被统一设成 1
   （原版公式：搬迁耗时 = 两省距离 × 这个值；搬迁费用 = 耗时天数 × 3 杜卡特）。
   To move a Great Project use the Move button in the province panel and pick a target.
   Relocation is fast and cheap: every monument's move_days_per_unit_distance is set to 1
   (vanilla formula: days = distance × that value, cost = days × 3 ducats).
5) 升级打折：决议面板里有「奇观升级更便宜、更快」，点一次开、再点一次关，
   每次【扣 50 杜卡特】（没钱会自动贷款）。它把升级花费和升级时间各降 90%。
   Upgrade discount: the decision "Cheaper and faster monument upgrades" toggles a −90%
   UPGRADE cost/time modifier for 50 ducats each time you click it.

建造规则（生成时就写进定义，游戏里改不了）/ Build rules baked into the definitions
  · 建造条件拆成 if/else 两条：玩家一条、AI 一条
  · 玩家：按下面的规则建；AI：照旧按【作者原本的条件】自己建
  · 有 start + 作者写了条件的：照旧只在它自己那个省（作者条件不动）
  · 有 start + 作者把条件留空的：就放它自己 start 那个省（province_id = start）
  · 【没有所属省份】的隐藏奇观：建在你的首都（is_capital = yes）
  · 年份没到建不了（有写 date 的都有年份闸）
  · 同一件奇观建不出第二个（建过就打标记）
  · The build condition is split with if/else: one branch for the player, one for the AI.
  · The AI keeps building on the author's own conditions; the player follows the rules below.
    condition applies, or - if the author left the build condition empty -
    it simply sits on its own start province (province_id = start province).
  · Hidden monuments WITHOUT a start province are built in your capital.
    Never before its historical date, and never twice.

两个解禁小工具 / Two unlock helpers（双击即可，改完再跑一次生成器 / double-click, then re-run the generator）
  解禁无省份奇观.bat    没有所属省份的隐藏奇观（原神那类）：加成 + 可手动建 一起开/关
  解禁年份未到奇观.bat  还没到历史年份的奇观：放开（开局就能建）/ 锁回（按各自 date）
  解禁无省份奇观.bat    hidden monuments without a start province (Genshin-like): bonuses + manual building, on/off
  解禁年份未到奇观.bat  monuments whose date has not arrived: unlock / lock back by date
  它们只改 config.txt 里自己管的键，其余开关不动。
  Each one only touches its own keys in config.txt.

老存档能不能用 / Using it on an old save（双击 存档体检.bat）
  存档里每件奇观是按【定义里的键名】记账的（省份 / 等级 / 建成年份）。读档时引擎拿这本账
  和当前加载的定义对号：账上有、定义里没有的那件会被【永久清掉】。所以规则只有一条：
    · 生成时的播放集 盖得住 存档当时的播放集  ->  安全（多出来的只会按定义新建出来）
    · 少了某条 mod（当时开着、现在没开）      ->  那条 mod 的奇观被永久清掉
  存档体检.bat 会把一份存档和 mod 目录里每一份生成结果对一遍：缺多少件、缺的是谁的，
  直接列出来；0 就是安全，放心开档。提示里按 y 还能把缺的键从你订阅的 mod 里原文搬回来应急
  （搬来的是原样定义，不能搬、加成按原条件，只当保命用）。
  双击后【直接回车】= 体检主菜单上『继续』会读的那个存档（游戏记在 continue_game.json 里）；
  输入 a = 把存档全部体检一遍（每份一行结论）；也可以输入序号单独体检某一个。
  The engine stores every Great Project in a save by its definition key (province / tier / built
  date). On load it matches that ledger against the currently loaded definitions, and any key
  without a definition is deleted for good. So there is exactly one rule: the playset you generate
  with must cover the playset the save was made with. 存档体检.bat compares a save against every
  build in your mod folder and lists how many (and whose) monuments would be lost; 0 means safe.
  Pressing Enter checks the save the main menu's "Continue" would load; typing "a" checks all saves
  (one line each); a number checks that single save. Answering "y" at its prompt copies the missing
  definitions over from the subscribed mods as a stopgap (verbatim copies: not movable, bonuses on
  the original conditions).

开关一览 / Switches（exe 版改 config.txt；源码版改 generate.py 顶部那一块 / exe: config.txt, source: the block at the top of generate.py）
  generic=yes      顺便生成"原版奇观版" / also build the vanilla-only version（默认 no）
  only=generic     只做"原版奇观版" / build only that version
  multi=yes        每个播放集各生成一份 / one build per playset（默认）
  nostart=yes      没有所属省份、也没写建造条件的隐藏奇观：禁止手动建 / lock them out of manual building（默认）
  hiddenbonus=no   同一批隐藏奇观：连加成一起关掉 / their bonuses off too（默认）
  lockopen=date    建造条件留空的奇观：按各自 date 解锁 / unlock by each one's own date（默认）
  strictbuild=yes  把奇观钉回它自己的省份 / pin each Great Project to its own province
  buildcost=90     建造花费打几折（90 = 打一折，100 = 完全免费，0/no = 不动）/ build cost discount
  buildtime=90     建造时间打几折（同上）/ build time discount
  move=raw         全部放开搬运（谁都能搬）—— 默认 / unlock the Move button for everyone (default)
  move=ai          全部锁死搬运（谁都不能搬）= 关掉搬迁功能 / lock the Move button for everyone
  move=keep        只解除使用限制，can_be_moved / 搬运耗时保持作者原样 / unlock use only, keep the author's movement rules
  aimove=yes       生成外部 defines，把 AI 搬运倾向归零（默认）/ write external defines to zero AI relocation desire (default)
  movedays=1       仅 raw/ai 模式：每距离基础搬运时间统一成这个值（keep 模式不动）/ only raw/ai: move_days_per_unit_distance
  upgdec=yes       生成"升级打折"决议 / build the upgrade-discount decision
                   （默认与一键三级互斥：maxtierdec 开着就不发它；要两个都要写 upgdec=force）
  upgcost=-0.9     该决议给多少升级花费折扣 / upgrade cost discount it grants
  upgtime=-0.9     该决议给多少升级时间折扣 / upgrade time discount it grants
  badstart=yes     start 写成 event_target 之类的奇观：自动修/挡掉（默认）
  emptybt=yes      建造条件留空的奇观：禁止重复建（默认）

  【为什么花费和时间只能这样改】build_cost 和 time 是"定义层"字段，引擎只在加载时读一次；
  EU4 的修正器列表里只有【升级】有 great_project_upgrade_cost / great_project_upgrade_time，
  【建造】一个都没有（在 eu4.exe 里搜过）。所以决议、事件、修正器都改不了它们，
  只能在生成时写进定义里 —— 这也是本工具必须存在的原因。
  【为什么搬运要二选一】can_be_moved 同样是定义层，而且引擎【不读它里面的条件】，
  没有任何写法能做到"只有玩家能按那个按钮"。所以要么全放开（AI 也搬），
  要么全锁上、玩家改走决议（决议里 ai_will_do = 0，AI 不会点）。
  Why cost/time cannot be changed by a decision: build_cost and time are definition-layer
  fields read once at load time, and EU4 only has upgrade modifiers (great_project_upgrade_cost /
  _time) - there are none for building. Why moving is all-or-nothing: can_be_moved is
  definition-layer too and the engine does not evaluate conditions inside it, so there is no way
  to give the button to the player only. Either leave it open (the AI moves too) or lock it and
  let the player use a decision whose ai_will_do is 0.

  【打折对哪个播放集有用 / where the discount actually bites】
  原版自己几乎全是免费的：01_monuments 里 138 件只有 1 件要钱、1 件要时间。
  所以"打一折"在只开原版的档里几乎看不出变化 —— 这是数据本来就这样，不是开关没生效。
  要钱要时间的奇观集中在这些 mod 里（实测 件数 / 要钱 / 要时间）：
    Anbennar 1385440355     187 / 100 / 178
    2803976184              305 / 104 /  65
    2935149060              242 / 152 /  17
    3577957498（青沼威尼斯） 32 /  23 /   0
  Vanilla is almost entirely free already: of its 138 monuments only 1 costs money and 1 takes
  time. So the discount is invisible in a vanilla-only playset - that is the data, not a broken
  switch. The monuments that do cost money and time live in the mods listed above.

怎么判断成功 / How to tell it worked
日志里每个文件那一行 PROBLEMS 都是 0，最后一行 问题=0，并且"输出里的奇观"没有重复。
Every file line in the log must read PROBLEMS=0, the summary line must read 问题=0, and no duplicate keys may be reported.
出问题就把 生成日志.txt 发给我（在生成器目录下）。
If something is off, send me 生成日志.txt (it sits next to the generator).

装 Python（只在要用 bat 时）/ Installing Python (only needed for the .bat)
到 https://www.python.org/downloads/ 下载安装，安装时务必勾选 "Add python.exe to PATH"，然后双击 src 文件夹里的 一键生成-源码版.bat。
Download it from the link above, tick "Add python.exe to PATH" during setup, then run 一键生成-源码版.bat inside the src subfolder.
（嫌麻烦就不用它：双击上一层的 AMR_Generator.exe 效果一样，只是源码版永远是最新版。）
(The exe one level up does the same thing and needs no Python - the source version is simply always the newest.)

【常见问题】 FAQ
Q1 生成器日志在哪？
A1 就在生成器文件夹里：生成日志.txt（脚本崩溃时也会写到那里）。
Q2 游戏里奇观变少了或没了？
A2 先看日志里有没有 !! 开头的行：某个 mod 没被读进来时会写明，把日志发我。
Q3 为什么我这一份和别人的不一样？
A3 它按你当前播放集生成；换播放集、或新装了加奇观的 mod，都要重跑一次。
Q4 要关掉别的奇观 mod 吗？
A4 不用，保持订阅。本 mod 只改规则，名字和图片仍来自它们。
Q5 为什么有些奇观没有加成？
A5 没有所属省份的隐藏奇观默认不给加成（那类数值往往爆炸）；想放开就用 解禁无省份奇观.bat 重做一份。
Q6 建造按钮是灰的？
A6 还没到它的历史年份（按各自 date 解锁）；想放开就用 解禁年份未到奇观.bat 重做一份。
Q7 老存档（玩了很久那种）能直接用吗？
A7 能，前提是生成时的播放集盖得住存档当时的播放集。先双击 存档体检.bat 照一下：写"安全"就直接开档；写着"会掉 N 件"就先把缺的那几条 mod 勾上、重跑一次生成器。少开 mod 才会掉，多开只是多冒出来。
Q8 省份面板里的「移动」按钮怎么用？
A8 看 config.txt 的 move=：
· keep（默认）：完全不碰 can_be_moved 和 move_days，作者让搬的才能搬，只解除使用限制。
· raw：全部 can_be_moved = yes，且每距离基础搬运时间统一成 1（又快又便宜）。
· ai：全部 can_be_moved = no，谁都不能搬。
（说明：can_be_moved 是定义层字段，引擎不读它里面的条件，所以做不到"只有玩家能按这个按钮"；
想只限制 AI，用 aimove=yes 的 defines 文件。通路/地下城类 38 件在 raw 下也保持锁死。）
Q8b 哪些奇观不能搬？
A8b 通路 / 地下城类，共 38 件：安本纳尔的矮人地下城（11）、隧道与升降机（17）、
妖精传送门与季节门（7），加上原版三条运河（基尔 / 苏伊士 / 巴拿马）。
它们搬走会断地图通路或让地牢探索失效，所以无论怎么设都锁死。
想放开某一件：把它的键名从 src\amr_config.py 的 KEEP_UNMOVABLE 里删掉；
想全部放开：config.txt 里写 keepunmovable=no 再跑一次。
Q9 花费和时间是怎么改的？
A9 分两种，因为引擎给的能力不一样：
  · 【建造】花费 / 时间：必须【在生成时写进定义里】。build_cost 和 time 是定义层字段，
    加载时读一次就定死；EU4 的修正器里【建造】一个都没有（great_project_upgrade_cost /
    _time 都是给【升级】的）。所以只能生成时写死 —— config.txt 的 buildcost= / buildtime= 选打几折。
  · 【升级】花费 / 时间：可以直接用 buff 改，所以我们做成了决议
    「Cheaper and faster monument upgrades」:点一次开、再点一次关，每次扣 50 杜卡特，
    升级花费和时间各降 90%（config.txt 里 upgdec / upgcost / upgtime 可调）。
  · 【升到几级】同样能用决议直接改：决议「奇观全部升到三级」，免费、无冷却，
    点一次你名下所有奇观直接三级（config.txt 里 maxtierdec=no 可以关掉它）。
Q10 搬迁费用能改吗？
A10 只能通过"每距离基础搬运时间"间接改。原版公式是 耗时 = 两省距离 × move_days_per_unit_distance，费用 = 耗时天数 × 3 杜卡特；eu4.exe 里【没有任何搬迁费用类修正器】（只有 can_be_moved 和 move_days_per_unit_distance 两个跟搬迁有关的字段）。所以本工具把每距离基础搬运时间统一设成 1，搬迁就变得又快又便宜。开关：config.txt 里 movedays=。
Q11 为什么我不能在别的省建某件奇观？
A11 因为每件奇观的建造条件被拆成了 if/else 两条：你走一条、AI 走另一条。
  · 你（人类玩家）：有历史定位的奇观（作者写了 start 的）只能建在它自己那个省份 ——
    作者本来就把条件留空的，我们补一句 province_id 把它钉回去；作者自己写了条件的，条件不动。
    只有【没有所属省份】的隐藏奇观才改成建在你的首都。
  · AI：照旧按【作者原本的条件】自己建自己的，我们不动它那份条件。
另外：年份没到的建不了；同一件奇观全世界只此一份（建成时打全局标记）。
Q12 为什么有件奇观现在建不了、以前能建？
A12 它的历史年份还没到（每件按自己的 date 解锁）。这是本版的默认行为（lockopen=date）。想放开就双击 解禁年份未到奇观.bat 选 1。
Q13 某件奇观为什么只能在一个省建？
A13 那是它的历史定位省。作者写了 start 就表示"这件奇观属于这个省"：条件留空的会被自动钉回该省（province_id），有条件的按作者条件。只有【完全没有所属省份】的隐藏奇观才改成建在你的首都。

【FAQ】 English
Q1 Where is the generator log?
A1 Right next to the generator: 生成日志.txt (a crash writes its traceback there too).
Q2 Some monuments are missing in game?
A2 Look for lines starting with "!!" in the log - they name any mod that could not be read. Send me the log.
Q3 Why is my build different from someone else's?
A3 It is generated from YOUR playset; re-run it after switching playsets or adding a new monument mod.
Q4 Should I switch off the other monument mods?
A4 No, keep them subscribed. This mod only changes the rules; names and pictures still come from them.
Q5 Why do some Great Projects give no bonus?
A5 Hidden monuments without a start province give no bonus by default (their numbers are often extreme). Use 解禁无省份奇观.bat to rebuild with them unlocked.
Q6 Why is the build button greyed out?
A6 Its historical date has not arrived yet (each one unlocks by its own date). Use 解禁年份未到奇观.bat to rebuild unlocked.
Q7 Can I use it on an old save (a long campaign)?
A7 Yes, as long as the playset you generated with covers the one the save was made with. Double-click 存档体检.bat first: if it says safe, just load the save; if it lists losses, enable the missing mods and re-run the generator. Only removing a mod costs you monuments - adding one just makes new ones appear.
Q8 How do I use the province-panel "Move" button?
A8 Depends on move= in config.txt:
- keep (default): can_be_moved and move_days are left untouched; only use restrictions are lifted.
- raw: every monument gets can_be_moved = yes and move_days_per_unit_distance = 1 (fast and cheap).
- ai: every monument gets can_be_moved = no; nobody can move them.
(Note: can_be_moved is a definition-layer flag and the engine does not evaluate conditions inside it,
so there is no way to give the button to the player only. To restrict only the AI, use aimove=yes,
which writes external defines. The 38 tunnel/dungeon monuments stay locked even under raw.)
Q8b Which monuments cannot be moved?
A8b Tunnel / dungeon monuments, 38 in total: Anbennar's dwarven dungeons (11), tunnels and lifts (17),
fey portals and season gates (7), plus the three vanilla canals (Kiel, Suez, Panama). Moving them
would cut map passages or break dungeon exploration, so they stay locked no matter what.
To unlock one, delete its key from KEEP_UNMOVABLE in src\amr_config.py; to unlock all of them,
put keepunmovable=no in config.txt and re-run.
Q9 How are cost and time actually changed?
A9 Two different ways, because the engine allows different things:
  - BUILD cost / time must be baked into the definition at generation time. build_cost and time are
    definition-layer fields read once at load, and EU4 has no modifiers at all for building
    (great_project_upgrade_cost / _time are for UPGRADES). So config.txt buildcost= / buildtime=
    decide the discount, applied when the mod is generated.
  - UPGRADE cost / time can be changed by a modifier, so they are handled by the decision
    "Cheaper and faster monument upgrades": toggle on/off, 50 ducats each time, -90% upgrade cost
    and time (tunable via upgdec / upgcost / upgtime in config.txt).
  - The TIER itself can be set by a decision too: "Set every owned monument to tier 3" - free,
    no cooldown, one click takes all your monuments straight to tier 3
    (turn it off with maxtierdec=no in config.txt).
Q10 Can relocation cost be changed?
A10 Only indirectly, through the per-distance move time. Vanilla formula: days = distance × move_days_per_unit_distance, cost = days × 3 ducats, and eu4.exe contains no relocation-cost modifier at all. So this tool sets move_days_per_unit_distance to 1 for every monument, making relocation both fast and cheap. Switch: movedays= in config.txt.
Q11 Why can I not build a certain monument in other provinces?
A11 Because every monument's build condition is split with if/else into two branches: one for you, one for the AI.
  - You (the human player): a monument with a historical location (the author wrote start) can only be
    built in that province - if the author left the build condition empty we pin it back with
    province_id; if the author wrote their own condition it is left untouched. Only hidden monuments
    WITHOUT a start province are moved to your capital.
  - The AI: keeps building its own on the AUTHOR'S OWN conditions (it is not "the AI never builds").
Also: nothing can be built before its historical date, and there is only one of each monument in the
whole world (a global flag is set when it is built).
Q12 Why can a monument no longer be built although it used to work?
A12 Its historical date has not arrived yet (each one unlocks by its own date) - the default behaviour (lockopen=date). Use 解禁年份未到奇观.bat option 1 to unlock them.
Q13 Why can a monument only be built in a single province?
A13 That is its historical location. A start province means the monument belongs there: if the author left the build condition empty it is pinned back to that province (province_id), otherwise the author's own condition applies. Only hidden monuments with NO start province at all are moved to your capital.
'''


TOOL_README = '''全奇观解锁并搬迁 All Monuments Unlocked & Movable (Generator)
（这是工具版：生成器本身，游戏里不起作用；游戏内容在它生成出来的那个 mod 里）
(This is the generator tool itself - it does nothing in game; the actual game content is in the mod it generates.)

包里有什么 / What is in this folder
  AMR_Generator.exe   双击就能跑，不用装 Python / double-click, no Python needed
  一键生成-源码版.bat  用 Python 跑的等价入口（需要装 Python）/ the Python entry point (needs Python)
  解禁无省份奇观.bat / 解禁年份未到奇观.bat   两个解禁开关 / two unlock helpers
  存档体检.bat        老存档体检：会掉多少件、缺谁的 / old-save check (see below)
  体检.bat            生成结果自检：22 项规则逐条核对 / self-check for a generated build (22 rules)
  amr_*.py            生成器的功能模块（源码版跑的时候需要，别单独删）
  config.txt          开关设置 / the switches
  说明.txt            完整说明（中文 + English）/ full manual (Chinese + English)

本版（1.2）改了什么 / What changed in 1.2
  · 搬迁费用/时间：所有奇观的"每距离基础搬运时间"统一成 1（又快又便宜）
  · 新增决议「奇观升级更便宜、更快」：扣 50 杜卡特，升级花费/时间 −90%
  · 建造规则重做：每件奇观的建造条件拆成 if/else 两条 ——
      玩家一条（我们的规则）、AI 一条（照旧按作者原本的条件自己建）
  · 年份闸：有写 date 的奇观，年份没到就建不了（默认）
  · 禁重复建：建成时打一个【全局标记】，跨省跨国家都只此一份
  · 有 start + 作者条件留空的：钉回它自己那个省（province_id = start）
    有 start + 作者写了条件的：只在它自己那个省（作者条件不动）
    没有 start 的隐藏奇观：改在【玩家首都】建（is_capital）
    type = canal 的原版三条运河：完全不动
  · 修掉"把 if/else 触发器错误地包进 OR"导致 146 件奇观条件失效的老 bug

它做什么 / What it does
读你当前播放集里【已启用】的奇观 mod，生成一个 mod：其中每件奇观（Great Project）对玩家无条件生效，并且都能搬运。
It reads the monument mods enabled in your playset and generates a mod where every Great Project always works for the player, and can be moved.
奇观的名字、图片、定义仍来自原 mod，本工具只改规则。
Names, pictures and definitions still come from the original mods; this tool only changes the rules.

怎么用 / How to use
1) 双击 AMR_Generator.exe（或 一键生成-源码版.bat）。
   Double-click AMR_Generator.exe (or 一键生成-源码版.bat).
2) 启动器里勾选生成出来的、名字以「!AMR」开头的 mod，并拖到已启用列表【最前面】。
   In the launcher enable the generated mod whose name starts with "!AMR" and drag it to the top.
3) 重启游戏。
   Restart the game.

结果写到哪 / Where the result goes
文档 / Paradox Interactive / Europa Universalis IV / mod / 下面，文件夹名以 !AMR_ 开头。
Under Documents / Paradox Interactive / Europa Universalis IV / mod/, in a folder starting with "!AMR_".

老存档 / Old saves
存档里每件奇观是按【定义里的键名】记账的（省份 / 等级 / 建成年份）。读档时引擎拿这本账和当前
加载的定义对号：账上有、定义里没有的那件会被【永久清掉】。所以只有一条规则：生成时的播放集
要盖得住存档当时的播放集；少了某条 mod，那条 mod 的奇观就会掉。
双击 存档体检.bat（或把 .eu4 文件拖到它上面），它会告诉你这份存档对每一份生成结果会掉多少件、
缺的是哪条 mod 的 —— 写着 0 就放心开档。提示里按 y 还能把缺的定义从你订阅的 mod 里原文搬回来
应急（原样搬来：不能搬、加成按原条件，只当保命用）。
双击后【直接回车】= 体检主菜单上『继续』会读的那个存档；输入 a = 把存档全部体检一遍（每份一行结论）。
The engine stores every monument in the save by its definition key (province / tier / built date);
on load, any key without a definition is deleted for good. So generate with a playset that covers
the one the save was made with - only removing a mod costs you monuments.
双击 存档体检.bat (or drop a .eu4 onto it) and it lists, for every build you have, how many
monuments would be lost and which mod they belong to; 0 means safe to load. Answering "y" copies
the missing definitions over from the subscribed mods as a stopgap.
Press Enter to check the save the main menu's "Continue" would load; type "a" to check all saves.

注意 / Notes
- 收录的是【运行那一刻】已启用的奇观 mod；新装了加奇观的 mod 要重跑一次。
  It covers the monument mods enabled at that moment; re-run it after adding a new one.
- 生成的完整版含别人 mod 的定义副本，建议自己用，别公开转发。
  The generated "full" version contains copies of other mods' definitions - keep it for yourself.
- 要公开分享就分享这个工具本身，或"原版奇观版"（config.txt 里写 generic=yes 生成）。
  To share publicly, share this tool itself, or build the vanilla-only version (generic=yes in config.txt).

【常见问题】 FAQ
Q1 生成器日志在哪？
A1 就在生成器文件夹里：生成日志.txt。
Q2 游戏里奇观变少了或没了？
A2 先看日志里有没有 !! 开头的行：某个 mod 没被读进来时会写明，把日志发作者。
Q3 为什么每个人生成出来的不一样？
A3 它按各自的播放集生成，所以内容不同；换播放集或加了新奇观 mod 都要重跑。
Q4 要关掉别的奇观 mod 吗？
A4 不用，保持订阅。本工具只改规则，名字和图片仍来自它们。
Q5 为什么有些奇观没有加成？
A5 没有所属省份的隐藏奇观默认不给加成（那类数值往往爆炸）；想放开就用 解禁无省份奇观.bat 重做一份。
Q6 建造按钮是灰的？
A6 还没到它的历史年份（按各自 date 解锁）；想放开就用 解禁年份未到奇观.bat 重做一份。
Q7 老存档（玩了很久那种）能直接用吗？
A7 能，前提是生成时的播放集盖得住存档当时的播放集。先双击 存档体检.bat 照一下：写"安全"就直接开档；写着"会掉 N 件"就先把缺的那几条 mod 勾上、重跑一次生成器。

【FAQ】 English
Q1 Where is the generator log?
A1 Right here in the generator folder: 生成日志.txt.
Q2 Some monuments are missing in game?
A2 Look for lines starting with "!!" in the log - they name any mod that could not be read. Send the log to the author.
Q3 Why is everyone's build different?
A3 It is generated from each player's own playset. Re-run it after switching playsets or adding a monument mod.
Q4 Should I switch off the other monument mods?
A4 No, keep them subscribed. This tool only changes the rules; names and pictures still come from them.
Q5 Why do some Great Projects give no bonus?
A5 Hidden monuments without a start province give no bonus by default (their numbers are often extreme). Use 解禁无省份奇观.bat to rebuild with them unlocked.
Q6 Why is the build button greyed out?
A6 Its historical date has not arrived yet (each one unlocks by its own date). Use 解禁年份未到奇观.bat to rebuild unlocked.
Q7 Can I use it on an old save (a long campaign)?
A7 Yes, as long as the playset you generated with covers the one the save was made with. Double-click 存档体检.bat first: if it says safe, just load the save; if it lists losses, enable the missing mods and re-run the generator.
'''
