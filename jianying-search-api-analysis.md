# 剪映搜索接口抓包分析（整理版）

说明：
- 本文对照 `jianying-material-api-cache-analysis.md` 的结构重新整理，专门描述“搜索”相关接口。
- 本文不是替代总接口说明，而是把新增搜索抓包单独抽出来，作为总文档的补充卷。
- 如果后面继续补搜索抓包，建议继续沿用本文结构，不要再零散追加。

分析时间：2026-05-13

## 1. 这份文档怎么用

本文范围：
- 覆盖当前已经抓到的搜索类样本：
  - 综合素材搜索
  - 音效搜索
  - 花字搜索
  - 贴纸搜索
  - 普通特效搜索
  - 人物特效搜索
  - 转场搜索
  - 花字模板搜索
  - 滤镜搜索
  - 音乐搜索
  - 模板搜索
  - 字幕模板搜索联想词
- 核心目标是判断：
  - 搜索接口分成几类
  - 每类请求走哪个业务地址
  - 返回结构如何分页
  - 能复用本地哪条 crawler 逻辑
  - 哪些链路已经跑透，哪些还只是半条链路

证据等级：
- `已抓到请求`：当前样本里有原始请求，通常来自 `.saz` 的 `raw/1_c.txt`
- `已抓到响应`：当前样本里有原始响应，通常来自 `.json` 或 `.saz` 的 `raw/1_s.txt`
- `关系推断`：当前没有完整补抓，但可以从结构、字段、现有 crawler 关系中稳定推出

推荐阅读顺序：
1. 先看 `2. 一页速览`，快速建立搜索接口的整体结构。
2. 再看 `3. 接口总索引`，确定某个搜索请求属于哪条接口族。
3. 然后用 `4. 文件索引` 回查对应抓包文件。
4. 最后进入 `5. 分类型详解` 看每条搜索链路的细节。

## 2. 一页速览

### 2.1 整体结构

从这批新增抓包里看，剪映搜索接口基本可以稳定拆成 4 组：

```text
通用素材搜索
-> 音乐搜索
-> 模板搜索
-> 搜索词推荐
```

目前已确认的典型分工：
- 通用素材搜索：`artist/v1/effect/search`
- 音乐搜索：`lv/v1/search/songs`
- 模板搜索：`lv/v1/pc/search/templates`
- 搜索词推荐：`artist/v1/effect/get_search_words`

### 2.2 列表结构分工

| 搜索接口 | 当前已确认主列表字段 | 当前已确认分页字段 | 当前已确认备注 |
|---|---|---|---|
| `artist/v1/effect/search` | `data.effect_item_list` | `data.has_more`、`data.next_offset` | 大多数素材搜索共用这一套 |
| `lv/v1/search/songs` | `response` 二次解析后的 `songs` | `has_more`、`next_offset` | 真正结果在顶层字符串字段 `response` 中 |
| `lv/v1/pc/search/templates` | `data.template_list` | `data.has_more`、`data.next_cursor` | 不走现有 collection 模板列表结构 |
| `artist/v1/effect/get_search_words` | 无素材列表 | 无 | 只是联想词，不是搜索结果页 |

### 2.3 搜索类型对照表

| 搜索类型 | 请求接口 | 关键区分字段 | 当前结果结构 | 本地最适合映射 |
|---|---|---|---|---|
| 综合素材搜索 | `effect/search` | `effect_type=201`、`scene=material_lib_c_v2` | `effect_item_list`，实际返回 `effect_type=5/9` 混合 | `official_material.py` |
| 音效搜索 | `effect/search` | `effect_type=3` | `effect_item_list` + `audio_effect` | `sound_effect.py` |
| 花字搜索 | `effect/search` | `effect_type=1` | `effect_item_list` + `word_art` | `flower.py` |
| 贴纸搜索 | `effect/search` | `effect_type=2` | `effect_item_list` + `sticker` | `sticker.py` |
| 普通特效搜索 | `effect/search` | `effect_type=7` | `effect_item_list` + `special_effect` | `effect.py` |
| 人物特效 / 任务特效搜索 | `effect/search` | 已确认存在 `effect_type=7 / 8` 两条分支 | `effect_item_list` + `special_effect` | `task_effect.py` / `effect.py` |
| 转场搜索 | `effect/search` | `effect_type=19` | `effect_item_list` | `transition.py` |
| 花字模板搜索 | `effect/search` | `effect_type=6`、`scene=vimo_text-template` | `effect_item_list` + `text_template` | `text_template.py` |
| 滤镜搜索 | `effect/search` | `effect_type=12` | `effect_item_list` + `filter` | `filter.py` |
| 音乐搜索 | `search/songs` | `keyword` | `songs` | `music.py` |
| 模板搜索 | `pc/search/templates` | `channels=["lv_template"]` | `template_list` | `template.py` / `marketing_template.py` |
| 字幕模板联想词 | `get_search_words` | `effect_type=48` | `recommend_words` / `hot_words` | 暂无直接素材抓取复用 |

### 2.4 当前最重要的结构结论

| 结论 | 证据等级 | 说明 |
|---|---|---|
| 大多数素材搜索共用 `artist/v1/effect/search` | `已抓到请求` | `search-effect`、`search-fllower`、`search-huazimuban`、`search-lvjing` 等都已证实 |
| 音乐搜索是独立接口族 | `已抓到请求` | `search-song.saz` 明确走 `lv/v1/search/songs` |
| 模板搜索是独立接口族 | `已抓到请求` | `search-muban.saz` 明确走 `lv/v1/pc/search/templates` |
| 字幕模板真实搜索结果页已经抓到 | `已抓到请求` | `search-zimu.saz` 已明确走 `artist/v1/effect/search`，并返回 `subtitle_template` 结果 |
| 搜索翻页会回填首屏 `search_id` | `已抓到请求 + 在线验证` | 贴纸、字幕模板、花字模板，以及 `effect_type=7 / 8` 的人物 / 任务相关特效都已实锤 |

### 2.5 与本地解析逻辑的复用速查

| 本地公共函数 | 是否可直接复用 | 适用范围 |
|---|---|---|
| `unwrap_response_payload` | 是 | 通用素材搜索、音乐搜索 |
| `iter_effect_items` | 是 | 所有 `effect/search` 结果 |
| `iter_song_items` | 是 | `search/songs` |
| `extract_common_attr` | 是 | 所有 `effect_item_list` 结果 |
| `get_effect_item_identity` | 是 | 所有 `effect_item_list` 结果 |
| `iter_template_items` | 否 | 当前只识别 `item_list` / `templates`，不识别 `template_list` |
| `get_new_cursor` | 否 | 当前只识别 `new_cursor`，不识别 `next_cursor` |

### 2.6 公共 query 参数

除模板搜索外，大多数搜索请求都带一套很长的设备 query 参数。

当前重复出现的核心参数包括：

```text
effect_sdk_version=21.2.0
channel=jianyingpro_0
aid=3704
device_id=7012563561417
version_name=10.5.0
language=zh-Hans
region=CN
device_platform=windows
biz_id=2
version_code_num=656640
device_type=x86_64
```

如果需要 1:1 回放请求，请直接回查对应 `.saz` 的 `raw/1_c.txt`。

## 3. 接口总索引

说明：
- 下表列的是当前已经确认的业务主地址。
- 完整 query、完整 body 以 `.saz` 原文为准。
- 同一个搜索接口可以服务多种素材，最终要结合 `effect_type`、`scene`、结果项子对象一起判断。

| 接口名 | 完整业务地址 | 主要作用 | 当前已确认搜索类型 | 出处文件 |
|---|---|---|---|---|
| `effect/search` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/search` | 通用素材搜索结果列表 | 综合素材、音效、花字、贴纸、普通特效、人物特效、转场、花字模板、滤镜 | `search.saz`、`search-effect.saz`、`search-fllower.saz`、`search-teizhi.saz`、`search-texiao.saz`、`search-rengwutexiao.saz`、`search-zhuanchang.saz`、`search-huazimuban.saz`、`search-lvjing.saz` |
| `search/songs` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/search/songs` | 音乐搜索结果列表 | 音乐 | `search-song.saz` |
| `pc/search/templates` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/search/templates` | 模板搜索结果列表 | 模板 | `search-muban.saz` |
| `get_search_words` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_search_words` | 搜索联想词 / 热词 | 字幕模板搜索联想词 | `search-zimumuban.saz` |

## 4. 文件索引

说明：
- `角色` 站在抓包证据角度填写，表示该文件主要证明什么。
- 如果你想回放完整请求，优先看 `.saz`
- 如果你想直接看结果结构，优先看 `.json`

### 4.1 综合素材搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search.saz` | `已抓到请求` | `effect/search`，综合素材搜索，请求里 `effect_type=201`、`scene=material_lib_c_v2` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search.json` | `已抓到响应` | 综合素材搜索结果，实际返回 `effect_type=5/9` 混合 |

### 4.2 音效搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-effect.saz` | `已抓到请求` | `effect/search`，音效搜索，请求里 `effect_type=3` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-effect.json` | `已抓到响应` | 音效搜索结果，结果项带 `audio_effect` |

### 4.3 花字搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-fllower.saz` | `已抓到请求` | `effect/search`，花字搜索，请求里 `effect_type=1` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-fllower.json` | `已抓到响应` | 花字搜索结果，结果项带 `word_art` |

### 4.4 贴纸搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-teizhi.saz` | `已抓到请求` | `effect/search`，贴纸搜索，请求里 `effect_type=2` |
| `C:\Users\wu\Documents\Fiddler2\Captures\tiezhi.json` | `已抓到响应` | 贴纸搜索结果，结果项带 `sticker` |

### 4.5 普通特效搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-texiao.saz` | `已抓到请求` | `effect/search`，普通特效搜索，请求里 `effect_type=7` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-texiao.json` | `已抓到响应` | 普通特效搜索结果，结果项带 `special_effect` |

### 4.6 人物 / 任务特效搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-rengwutexiao.saz` | `已抓到请求` | `effect/search`，人物特效搜索样本，请求体仍表现为 `effect_type=7` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-rengwutexiao.json` | `已抓到响应` | 人物特效搜索结果，结构与普通特效搜索同构 |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao1.saz` | `已抓到请求` | `effect/search`，第 1 页，`effect_type=7`，`query=闪烁` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao5.saz` | `已抓到请求` | `effect/search`，第 2 页，`effect_type=7`，`offset=50`，回填 `search_id` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao2.saz` | `已抓到请求` | `effect/search`，第 1 页，`effect_type=8`，`query=闪烁` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao4.saz` | `已抓到请求` | `effect/search`，第 2 页，`effect_type=8`，`offset=50`，回填 `search_id` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao6.saz` | `已抓到请求` | `effect/search`，第 3 页，`effect_type=8`，`offset=100`，继续沿用同一个 `search_id` |

### 4.7 转场搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zhuanchang.saz` | `已抓到请求` | `effect/search`，转场搜索，请求里 `effect_type=19` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zhuanchang.json` | `已抓到响应` | 转场搜索结果 |

### 4.8 花字模板搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-huazimuban.saz` | `已抓到请求` | `effect/search`，花字模板搜索，请求里 `effect_type=6`、`scene=vimo_text-template` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-huazimuban.json` | `已抓到响应` | 花字模板搜索结果，结果项带 `text_template` 和依赖信息 |

### 4.9 滤镜搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-lvjing.saz` | `已抓到请求` | `effect/search`，滤镜搜索，请求里 `effect_type=12` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-lvjing.json` | `已抓到响应` | 滤镜搜索结果，结果项带 `filter` |

### 4.10 音乐搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-song.saz` | `已抓到请求` | `search/songs`，音乐搜索，请求体含 `keyword`、`offset`、`count` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-song.json` | `已抓到响应` | 音乐搜索结果，真正列表在顶层 `response` 字符串中 |

### 4.11 模板搜索

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-muban.saz` | `已抓到请求` | `pc/search/templates`，模板搜索 |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-muban.json` | `已抓到响应` | 模板搜索结果，主列表字段是 `template_list` |

### 4.12 字幕模板搜索联想词

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zimumuban.saz` | `已抓到请求` | `get_search_words(effect_type=48)` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zimumuban.json` | `已抓到响应` | 只返回推荐词、热词、默认词，不返回素材结果列表 |

## 5. 分类型详解

### 5.1 通用素材搜索

#### 5.1.1 接口形态

完整业务地址：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/search
```

这一组请求的共性：
- 都是 `POST`
- 都有统一设备 query 参数
- body 中固定会有：
  - `app_id`
  - `count`
  - `offset`
  - `query`
  - `search_id`
  - `search_option`

#### 5.1.2 统一响应结构

响应顶层基本是：

```json
{
  "ret": 0,
  "errmsg": "",
  "data": {
    "effect_item_list": [],
    "has_more": true,
    "next_offset": 50,
    "search_id": "2026..."
  }
}
```

本地当前可以直接复用：
- `unwrap_response_payload`
- `iter_effect_items`
- `extract_common_attr`
- `get_effect_item_identity`

#### 5.1.3 已实锤的分类变体

| 搜索方向 | 请求 `effect_type` | 额外特征 | 结果项主子对象 |
|---|---:|---|---|
| 音效 | 3 | 无特殊 `scene` | `audio_effect` |
| 花字 | 1 | 无特殊 `scene` | `word_art` |
| 贴纸 | 2 | 无特殊 `scene` | `sticker` |
| 普通特效 | 7 | 无特殊 `scene` | `special_effect` |
| 人物特效 | 7 | 当前抓包没体现独立协议区分 | `special_effect` |
| 转场 | 19 | 无特殊 `scene` | 无稳定专属子对象 |
| 花字模板 | 6 | `scene=vimo_text-template` | `text_template` |
| 字幕模板 | 48 | `scene=vimo_subtitle-template` | `subtitle_template` |
| 滤镜 | 12 | 无特殊 `scene` | `filter` |
| 综合素材 | 201 | `scene=material_lib_c_v2` | `video` / `image` |

#### 5.1.4 当前结论

- `effect/search` 是当前搜索体系里最重要的一条总入口
- 大多数素材链路都能在这一条里表达
- 对项目来说，这条接口族最值得先接入

### 5.2 综合素材搜索

#### 5.2.1 请求特征

样本：`search.saz`

关键 body：

```json
{
  "effect_type": 201,
  "query": "天空",
  "search_option": {
    "scene": "material_lib_c_v2"
  }
}
```

#### 5.2.2 返回结构

样本：`search.json`

结果项并不是 `effect_type=201`，而是：
- `effect_type=5` 共 44 条
- `effect_type=9` 共 5 条

结果项结构：
- 视频素材项通常带 `video`
- 图片素材项通常带 `image`

#### 5.2.3 当前结论

- `201` 更像“素材库综合搜索域”
- 它不是最终资源类型
- 本地最适合映射到 `official_material.py`

### 5.3 音效搜索

#### 5.3.1 请求

样本：`search-effect.saz`

关键 body：

```json
{
  "effect_type": 3,
  "query": "欢呼",
  "offset": 0,
  "count": 50
}
```

#### 5.3.2 返回结构

样本：`search-effect.json`

结果项结构：
- `author`
- `common_attr`
- `audio_effect`

#### 5.3.3 当前结论

- 可直接映射到 `sound_effect.py`
- 后续详情仍建议复用 `mget_item`

### 5.4 花字搜索

#### 5.4.1 请求

样本：`search-fllower.saz`

关键 body：

```json
{
  "effect_type": 1,
  "query": "粉色"
}
```

#### 5.4.2 返回结构

样本：`search-fllower.json`

结果项结构：
- `author`
- `common_attr`
- `word_art`

#### 5.4.3 当前结论

- 与本地 `flower.py` 高度一致
- 入库和详情补全都可直接复用花字链路

### 5.5 贴纸搜索

#### 5.5.1 请求

样本：`search-teizhi.saz`

关键 body：

```json
{
  "effect_type": 2,
  "query": "春天"
}
```

#### 5.5.2 返回结构

样本：`tiezhi.json`

结果项结构：
- `author`
- `common_attr`
- `sticker`

#### 5.5.3 当前结论

- 结构上就是普通贴纸搜索结果
- 可直接映射到 `sticker.py`

### 5.6 普通特效搜索

#### 5.6.1 请求

样本：`search-texiao.saz`

关键 body：

```json
{
  "effect_type": 7,
  "query": "心形"
}
```

#### 5.6.2 返回结构

样本：`search-texiao.json`

结果项结构：
- `author`
- `common_attr`
- `special_effect`

#### 5.6.3 当前结论

- 与本地 `effect.py` 对齐度很高
- 属于最容易接进现有系统的一条搜索线

### 5.7 人物特效搜索

#### 5.7.1 请求

老样本：`search-rengwutexiao.saz`

老样本关键 body 仍表现为：

```json
{
  "effect_type": 7,
  "query": "马赛克"
}
```

#### 5.7.2 返回结构

样本：
- `search-rengwutexiao.json`
- `renwutexiao1.saz`
- `renwutexiao2.saz`

新增样本已经把分页关系补出来了：
- `renwutexiao1.saz` / `renwutexiao5.saz`：`effect_type=7`，`offset=0/50`，翻页回填 `search_id`
- `renwutexiao2.saz` / `renwutexiao4.saz` / `renwutexiao6.saz`：`effect_type=8`，`offset=0/50/100`，多页沿用同一个 `search_id`

两条分支的结果项结构都与普通特效搜索同构：
- `author`
- `common_attr`
- `special_effect`

#### 5.7.3 当前结论

- 之前“人物特效搜索只是 `effect_type=7` 展示口径差异”的判断已经不够用了
- 至少在搜索协议层，`effect_type=7` 和 `effect_type=8` 两条人物 / 任务相关搜索分支都真实存在
- `effect/search` 的翻页机制在这两条分支上也已经坐实：
  - 首屏 `search_id=""`
  - 后续页回填首屏 `search_id`
  - `offset -> next_offset`
- 我又在线对照了面板与分类链路：
  - `effects2` 面板的热门分类 `39654/rm` 拉出来的结果全部是 `effect_type=7`
  - `face-prop` 面板的热门分类 `38389/hot` 拉出来的结果全部是 `effect_type=8`
  - `face-prop` 的分类名也明显偏人物处理：`情绪 / 身体 / 挡脸 / 头饰 / 手部 / 形象 / 环绕 / 表情`
- 因此当前已经可以基本锁定：
  - 普通特效 UI 面板对应 `effects2` / `effect_type=7`
  - 人物 / 任务特效 UI 面板对应 `face-prop` / `effect_type=8`
  - 还不能百分百静态证明的，只剩“人物特效”和“任务特效”是否只是同一面板在不同版本下的中文命名差异

### 5.8 转场搜索

#### 5.8.1 请求

样本：`search-zhuanchang.saz`

关键 body：

```json
{
  "effect_type": 19,
  "query": "旋转"
}
```

#### 5.8.2 返回结构

样本：`search-zhuanchang.json`

结果项结构没有非常稳定的专属顶层子对象，但 `common_attr.effect_type=19` 很稳定。

#### 5.8.3 当前结论

- 可直接映射到 `transition.py`

### 5.9 花字模板搜索

#### 5.9.1 请求

样本：`search-huazimuban.saz`

关键 body：

```json
{
  "effect_type": 6,
  "query": "划重点",
  "search_option": {
    "scene": "vimo_text-template"
  }
}
```

#### 5.9.2 返回结构

样本：`search-huazimuban.json`

结果项结构：
- `author`
- `common_attr`
- `text_template`

`common_attr.sdk_extra` 中已经能看到：
- `depend_resource_list`

#### 5.9.3 当前结论

- 这已经不是单纯平铺素材，而是组合类模板搜索
- 后续依赖展开建议直接复用 `text_template.py`

### 5.10 滤镜搜索

#### 5.10.1 请求

样本：`search-lvjing.saz`

关键 body：

```json
{
  "effect_type": 12,
  "query": "天空"
}
```

#### 5.10.2 返回结构

样本：`search-lvjing.json`

结果项结构：
- `author`
- `common_attr`
- `filter`

#### 5.10.3 当前结论

- 与本地 `filter.py` 的数据形态一致

### 5.11 音乐搜索

#### 5.11.1 请求

完整业务地址：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/search/songs
```

样本：`search-song.saz`

关键 body：

```json
{
  "count": 50,
  "filter_paid_type": [],
  "keyword": "安静",
  "offset": 0,
  "scene": 0
}
```

#### 5.11.2 返回结构

样本：`search-song.json`

真正结果在顶层字符串字段 `response` 中，二次解析后得到：
- `songs`
- `has_more`
- `next_offset`
- `search_id`
- `source`

单项字段和本地音乐链路高度一致：
- `id`
- `web_id`
- `title`
- `author`
- `preview_url`
- `cover_url`
- `beats`
- `business_info`
- `strategy_info`

#### 5.11.3 当前结论

- 可直接复用 `music.py` 的主入库思路
- 不应和通用素材搜索混成一种解析器

### 5.12 模板搜索

#### 5.12.1 请求

完整业务地址：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/search/templates
```

样本：`search-muban.saz`

关键 body：

```json
{
  "channels": ["lv_template"],
  "count": 32,
  "cursor": 0,
  "keyword": "当年",
  "search_id": "",
  "search_source": "input",
  "sort_type": 0
}
```

#### 5.12.2 返回结构

样本：`search-muban.json`

主字段：
- `data.template_list`
- `data.has_more`
- `data.next_cursor`
- `data.search_id`
- `data.channel`
- `data.filter_options`

结果项中已经能直接看到：
- `template_url`
- `video_url`
- `draft_package_url`
- `template_json`
- `origin_video_info`

#### 5.12.3 与本地代码的差异

当前项目不能直接无改动复用，主要因为：
- `iter_template_items` 只认 `item_list`、`templates`
- `get_new_cursor` 只认 `new_cursor`

而模板搜索实际是：
- 列表字段 `template_list`
- 分页字段 `next_cursor`

但这一点现在已经补上：
- `iter_template_items` 已扩展支持 `template_list`
- `get_new_cursor` 已扩展兼容 `next_cursor`
- 项目里已经新增独立 `search_service.py` 作为搜索适配层

#### 5.12.4 当前结论

- 模板搜索已抓透到“可明确实现”的程度
- 项目代码现在已经补上模板搜索解析适配层
- 当前模板搜索已可作为实时搜索链路直接调用
- 最新 `E:/sucai/crawler_project/fiddler-v2rayn-10808/yingxiao.saz` 也已经证明：
  - 营销入口的一份真实搜索样本同样走 `pc/search/templates`
  - 请求体仍是 `channels=["lv_template"]`
  - 响应里的 `data.channel` 也仍是 `lv_template`
  - 目前可以视为已经确认：营销模板搜索没有独立 `lv_marketing_template` channel

### 5.13 字幕模板搜索联想词

#### 5.13.1 请求

完整业务地址：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_search_words
```

样本：`search-zimumuban.saz`

关键 body：

```json
{
  "app_id": 3704,
  "effect_type": 48
}
```

#### 5.13.2 返回结构

样本：`search-zimumuban.json`

返回内容只有：
- `default_word`
- `recommend_words`
- `hot_words`
- `grey_words`
- `word_source`
- `task_id`

#### 5.13.3 当前结论

- 这不是字幕模板搜索结果页
- 这只是搜索联想词 / 热词接口
- 但现在已经有新的补抓样本证明：字幕模板真实搜索结果页实际走的是 `artist/v1/effect/search`

## 6. 对本地项目的直接影响

当前最值得落地的改造顺序：

1. 已接 `effect/search`
   - 已覆盖绝大多数素材搜索
2. 已接 `search/songs`
   - 与 `music.py` 基本天然对齐
3. 已接 `pc/search/templates`
   - 已通过独立搜索适配层打通
4. `get_search_words` 仍建议后置
   - 这更偏前端搜索辅助，不是主抓取链路

当前项目内已经落地：

- 新增 CLI 命令：
  - `python -m jianying_crawler.cli search <关键词>`
- 新增搜索服务层：
  - `jianying_crawler/search_service.py`
- 当前搜索策略：
  - 先调用剪映实时搜索接口
  - 如果实时结果为空，再回退本地 SQL
  - 如果传 `--downloaded-only`，则直接查询本地数据库

当前已接入实时搜索的链路：

- `sound_effect`
- `music`
- `sticker`
- `flower`
- `effect`
- `task_effect`
- `transition`
- `filter`
- `text_template`
- `subtitle_template`
- `template`
- `marketing_template`
- `official_material`

当前统一输出结果格式：

```json
{
  "crawler_name": "task_effect",
  "resource_id": "7399497918765436195",
  "title": "卡通脸",
  "effect_type": "8",
  "panel": "face-prop",
  "category_id": "5913857",
  "collection_id": "",
  "source_kind": "live_search",
  "parent_resource_id": "",
  "updated_at": "",
  "downloaded": false,
  "primary_downloaded": false,
  "primary_target_path": "",
  "material_type": "effect"
}
```

搜索返回还会补：

- `search_mode`
  - `live_only`
  - `sql_fallback`
  - `sql_downloaded_only`
- `source`
  - `live_search`
  - `sql`

## 7. 当前还没有完全跑透的点

- `普通特效 = effects2 = effect_type=7`、`人物 / 任务特效 = face-prop = effect_type=8` 现在已经可以基本视为锁定
- 剩余未完全跑透的只剩 UI 中文名“人物特效 / 任务特效”之间是否是同一面板的命名差异
- 营销模板搜索没有独立 `lv_marketing_template` / `marketing_template` channel
- `material_pack` 目前仍没有接入实时搜索
- `get_search_words` 仍未并入 CLI 搜索主流程
