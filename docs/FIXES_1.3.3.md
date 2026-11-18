# 1.3.3 修复：一键三级决议变成“加发展度”

## 现象

点「奇观全部升到三级」后：

- 决议不消失，可以继续点
- 已经三级（或更高）的奇观会**增加发展度**

## 根因

原版脚本效果 `set_great_project_tier_3` 在 **tier=3** 时不是空操作：

```text
if has_great_project { type=X tier=3 }:
    random_list = {
        1 = { add_base_tax = 6 }
        1 = { add_base_production = 6 }
        1 = { add_base_manpower = 6 }
    }
```

我们的决议原本只判断“有这件奇观”，没有判断“是否已满三级”，所以每次点都会对已三级奇观触发这段随机发展度。

## 修复

生成决议的每个 if 增加：

```text
limit = {
    has_great_project = { type = X }
    NOT = { has_great_project = { type = X tier = 3 } }
}
```

并且决议加了一次性国家标记：

```text
potential = {
    ai = no
    NOT = { has_country_flag = AMR_max_all_monuments_done }
}
effect = {
    set_country_flag = AMR_max_all_monuments_done
    ...
}
```

所以：

- 每局只能点一次，点完决议消失
- 只升级未满三级的奇观
- 已三级奇观不会再增加发展度

## 验证

- 构建里 995 个 `set_great_project_tier_3`，995 个 `tier = 3` 守卫，2 处一次性标记
- 单元/集成测试 117 例全过
- 决议文件开头已人工核对

## 注意

旧存档里如果已经点过旧版决议，**旧版已经加过的发展度不会回退**；新版本只保证以后不再加。需要重新生成构建并重启游戏。
