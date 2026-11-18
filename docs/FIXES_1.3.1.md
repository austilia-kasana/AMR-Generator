# 1.3.1 P0 修复记录（2026-11-19）

本轮针对代码审查指出的两个 P0 逻辑缺口，以及构建层校验问题：

## 1. keep 不能绕过 KEEP_UNMOVABLE 名单

- 原实现：`make_movable()` 在识别键名之前直接对 keep 返回，名单失效。
- 修复：先取键名；keep 只对名单外原样返回，名单内仍强制 `can_be_moved = no`。
- 测试：`TestMakeMovableKeepListed` 3 例。

## 2. process_file 的块内键名丢失

- 更底层的问题：`transform_block()` 传给 `make_movable()` 的 block 从 `{` 开始，
  没有 `key = {` 前缀，导致 `_key` 为空，KEEP_UNMOVABLE 在最终产物里完全失效。
- 修复：`make_movable(block, stats, name='')`，由 `transform_block()` 传入奇观键名；
  直接调用时仍兼容带键名前缀的测试块。
- 测试：`test_amr_build.py` 完整 `process_file()` 集成测试。

## 3. 全文件 can_be_moved 兜底覆盖名单

- 原实现：`process_file()` 后面按模式全文件替换 `can_be_moved`，会把块内刚锁好的名单奇观改回 yes。
- 修复：先收集全部 monument block 的字符区间；兜底只改块外字段。
- raw 模式的构建校验也改为：普通奇观必须 yes，名单内必须 no。

## 4. 默认值与示例配置同步

- `MAKE_MOVE = 'keep'`
- `MAKE_AI_MOVE = True`
- 与 `config.example.txt` 一致；无 config.txt 时也按 1.3 推荐设置运行。

## 5. AI defines 第四项核实

本机 EU4 1.37.5 的 `common/defines.lua` 确实包含：

```lua
GREAT_PROJECT_DESIRE_CAPITAL_AREA_MODIFIER = 3,
```

四项均存在于 1.37.5；旧版公开镜像缺第四项不能作为 1.37.5 的判断依据。

## 验证

- 单元/集成测试：117 例全过
- 当前构建 `can_be_moved` 统计仍为 19 yes / 981 no
- 当前播放集没有 KEEP_UNMOVABLE 奇观，因此保护逻辑由合成集成测试覆盖
