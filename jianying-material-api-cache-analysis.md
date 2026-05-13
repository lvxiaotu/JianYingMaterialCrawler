# 剪映素材接口抓包分析（整理版）

说明：
- 本文已整理为更贴切的新文件名：`jianying-material-api-cache-analysis.md`。
- 这版整理的目标不是继续堆抓包事实，而是把“接口是什么、属于哪条链路、对应哪个文件、现在能下什么结论”拆开写清楚。
- 如果后面继续补抓包，建议继续沿用本文的结构补充，不要再往旧位置零散追加。

分析时间：2026-05-11

## 1. 这份文档怎么用

本文范围：
- 覆盖当前已经抓到的音乐、音效、花字、文字模板、贴纸、普通特效、任务特效、官方素材、转场、字幕模板、滤镜、模板库、营销模板、素材包相关样本。
- 核心目标是判断剪映素材接口的分层关系、`effect_type` 分工、详情接口分工、最终资源下载规律。
- 文中凡是写到“完整请求地址”，都指业务主地址；完整 query、header、body 以原始 `.saz` / `.txt` 为准。

证据等级：
- `已抓到请求`：当前样本里有原始请求，通常来自 `.saz` 的 `raw/1_c.txt` 或单独的 `.txt`
- `已抓到响应`：当前样本里有原始响应，通常来自 `.json`、`.txt` 或 `.saz` 的 `raw/1_s.txt`
- `关系推断`：当前没有单独抓到这一跳，但可以从字段、ID、资源地址、上下游接口关系中稳定推出

推荐阅读顺序：
1. 先看 `2. 一页速览`，快速建立整体结构。
2. 再看 `3. 接口总索引`，定位某个请求属于哪一类接口。
3. 然后用 `4. 文件索引` 回查具体抓包文件。
4. 最后进入 `5. 分类型详解` 看每条链路的细节。

## 2. 一页速览

### 2.1 整体结构

从这批样本里看，剪映素材接口基本可以稳定拆成 4 层：

```text
面板 / 分类层
-> 列表层
-> 单项详情层
-> 最终资源层
```

目前已确认的典型分工：
- 面板 / 分类层：`get_panel_info`、`replicate/get_collections`
- 列表层：`get_collection_songs`、`get_resources_by_category_id`、`user_favorite_list`、`user_aigc_list`、`pc/replicate/get_collection_templates`
- 单项详情层：`mget_item`、`mget_artist_item`、`pc/replicate/multi_get_templates`
- 最终资源层：音频文件、ZIP 包、PNG / GIF 预览图、模板 ZIP、模板演示视频

### 2.2 详情接口分工

| 详情接口 | 当前已确认用途 | 当前已确认素材 |
|---|---|---|
| `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item` | 单项详情补全 | 音乐 / BGM、音效 |
| `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item` | 素材包详情补全 | 花字、文字模板、贴纸、普通特效、任务特效、官方素材、转场、字幕模板、滤镜、素材包 |
| `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/multi_get_templates` | 模板详情补全 | 模板库、营销模板 |

### 2.3 `effect_type` 对照表

| `effect_type` | 当前判断 | 说明 | 关键出处 |
|---:|---|---|---|
| `1` | 花字 | 花字面板与详情都能对上 | `huazi.json`、`huazixiangqing.json` |
| `2` | 普通贴纸 / 文字模板子资源 | 文字模板依赖资源会展开成该类型 | `tiezhiremenxiangqing.json`、`wenzimubanxiangqfenye.json` |
| `3` | 音效 | 热门列表与详情都能对上 | `yinxiaokuremen.json`、`yinxiaoxiangqing.json` |
| `4` | 音乐 / BGM | 音乐详情 `mget_item` 样本已确认 | `artist-v1-effect-mget_item.txt` |
| `5` | 官方视频素材 / 插入视频素材 | 当前仅在官方素材列表样本里出现；`item_urls = null`，`download_info.url` 直给 `mp4`，且带 `video.origin_video / transcoded_video` | `guanfangsucai.json` |
| `6` | 文字模板主模板 | 依赖一批子资源 | `wenzimubanxiangqing.json` |
| `7` | 普通特效 | 偏画面特效 / 算法特效 | `rementexiao.json`、`rementexiaoxiangqing.json` |
| `8` | 任务特效 / 人物特效 | 偏人物、人脸、骨骼、抠像任务 | `renwutexiao.json`、`renwutexiaoxiangqing.json` |
| `9` | 官方素材 | 更像图片 / 视频插入素材 | `guanfangsucai.json`、`guanfangsucaixiangqing.json` |
| `12` | 滤镜 | 带 `filter` 字段和滤镜调节参数 | `lvjing.json`、`lvjingxiangqing.json` |
| `19` | 转场 | 带 `transition` 相关配置 | `zhuanchang.json`、`zhuanchangxiangqing.json` |
| `48` | 字幕模板 | 带 `subtitle_template` 依赖信息 | `zimuxiangqing.json` |
| `50` | 素材包 / 组合成片素材 | 带 `recipe.materials`、`recipe.video` | `remensucaibao.json`、`sucaibaoxiangqing.json` |

补充说明：
- `effect_type = 10`、`11` 在当前这批样本中还没有直接命中，暂时不能下可靠结论。

### 2.4 入口、热门分类、样例 ID 对照

| 素材类型 | 面板 / 列表入口 | 热门分类 / 合集 | 样例资源 ID | 当前最稳判断 |
|---|---|---|---|---|
| 推荐音乐 / BGM | `get_collections` + `general_config` + `get_collection_songs` | 合集 `id = 6678556627852856076` | `7492262428060289035` | 列表和详情分离，最终再跳真实音频 |
| 音效 | `get_panel_info(panel=audio)` + `get_resources_by_category_id` | `category_id = 10892` | `6896679799100689672` | 热门列表往往已直接带资源地址 |
| 花字 | `get_panel_info(panel=flower)` | `category_id = 10721` | `7539407429763796249` | 面板响应里直接带首屏资源 |
| 文字模板 | `get_resources_by_category_id(panel=text-template)` | `category_id = 10577` | 主模板 `7590730429486026008` | 主模板是组合结构，不是单一素材 |
| 文字模板子资源 | 主模板依赖展开 | 依赖项，不是独立热门分类结论 | `7590672052688899390` | 已展开到 `effect_type = 2` |
| 贴纸 | 普通贴纸列表未单独抓到；已抓到 AIGC 接口和普通贴纸详情 | 当前未直接抓到普通贴纸热门列表分类 | `7529823016566459672` | 普通贴纸与文字模板子资源共用 `effect_type = 2` |
| 普通特效 | `get_panel_info(panel=effects2)` | `category_id = 39654` | `7399495930849824000` | 面板响应直接带首屏资源 |
| 任务特效 | `get_resources_by_category_id(panel=face-prop)` | `category_id = 38389` | `7399497918765436195` | 直接按分类拉列表，不先走面板首屏 |
| 官方素材 | `get_resources_by_category_id(panel=insert)` | `category_id = 10231` | `6971036278649294115` | 当前样例里同时出现 `effect_type = 9` 图片素材和 `effect_type = 5` 视频素材 |
| 转场 | `get_resources_by_category_id(panel=transitions)` | `category_id = 39663` | `7548386586157813016` | 独立于普通特效，主类型是 `19` |
| 字幕模板 | 当前只抓到 `user_favorite_list(effect_type=48)` 和详情 | 当前未抓到完整分类入口 | `7599874183467699518` | 当前可确认主类型为 `48` |
| 滤镜 | `get_resources_by_category_id(panel=filter)` | `category_id = 11568`，样例 `category_key = chuntian` | `7607867444048317706` | 主类型是 `12`，下载仍是 ZIP |
| 模板库 | `replicate/get_collections(collection_type=1)` + `pc/replicate/get_collection_templates` | 集合 `id = 10804`（推荐） | `7635415980495146264` | 属于 `replicate` 模板体系 |
| 营销模板 | `replicate/get_collections(collection_type=11)` + `pc/replicate/get_collection_templates` | 集合 `id = 11029`（精选） | `7606145866361179416` | 同样属于 `replicate` 模板体系 |
| 素材包 | `get_panel_info(panel=recipe)` + `get_resources_by_category_id(panel=composition)` | 面板热门 `category_id = 10536` | `7230441318567267587` | 主类型是 `50`，内部再依赖多种素材 |

### 2.5 资源域名与格式速查

| 域名 / 地址特征 | 当前常见素材 | 当前常见格式 | 关键出处 |
|---|---|---|---|
| `v9/v11-jianying.vlabvod.com` | 音乐 / BGM | `audio/mp4` | `686_Full.txt` |
| `lf26-faceu-file-sign.bytecdn.com` | 音效、贴纸、部分素材包 | `audio/mpeg`、`application/zip` | `yinxiao.saz`、`tiezhiremenxiangqingxiazai.saz` |
| `p3/p6/p9/p26-artist-file-sign.byteimg.com` | 花字、普通特效、任务特效等素材包 | `application/zip` | `huazixiangqingxiazai.saz`、`rementexiaoxiangqingxiazai.saz`、`renwutexiaoxiangqingxiazai.saz` |
| `p3-heycan-jy-sign.byteimg.com` | 文字模板子资源预览 | `png`、`gif` | `wenzimubanxiangqfenye.json` |
| `v3/v26-jianying.vlabvod.com` | 模板演示视频 / 模板原视频 | `video/mp4` | `tuijianmubanxiangqing.json`、`yingxiaojingxuanxiangqing.json` |

额外说明：
- 对图形类素材来说，`download_info.url` 很多时候只是预览图地址。
- 真正更值得优先盯的是 `item_urls[0]`，它更经常指向最终 ZIP 包。

### 2.6 公共 query 参数

除少数 AIGC 接口外，大部分素材 API 都共用一套很长的 query 参数。为了保证文档可读性，正文不重复展开整段 query，只保留业务主地址和关键 body。

当前样本里反复出现的核心参数包括：

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

如果需要 1:1 回放请求，请直接回查对应 `.saz` / `.txt` 原文件。

### 2.7 搜索接口速览（2026-05-13 新增）

当前新增抓包已经证明：剪映“搜索”并不是单一接口，而是至少分成 4 组：

```text
通用素材搜索
-> 音乐搜索
-> 模板搜索
-> 搜索词推荐
```

当前已确认的分工如下：

| 搜索接口 | 主列表字段 | 分页字段 | 当前说明 |
|---|---|---|---|
| `artist/v1/effect/search` | `data.effect_item_list` | `data.has_more`、`data.next_offset` | 大多数素材搜索共用这一套 |
| `lv/v1/search/songs` | `response` 二次解析后的 `songs` | `has_more`、`next_offset` | 音乐搜索独立接口 |
| `lv/v1/pc/search/templates` | `data.template_list` | `data.has_more`、`data.next_cursor` | 模板搜索独立接口 |
| `artist/v1/effect/get_search_words` | 无素材结果列表 | 无 | 搜索联想词，不是素材结果页 |

当前最重要的搜索结论：

- 大多数素材搜索都走 `artist/v1/effect/search`
- 音乐搜索不走 `effect/search`
- 模板搜索不走 `replicate/get_collection_templates`
- 当前只抓到字幕模板联想词，还没抓到字幕模板真实搜索结果页

## 3. 接口总索引

说明：
- 下表列的是当前已经确认的业务主地址。
- 完整 query、完整 header、完整 body，请以右侧“出处文件”为准。
- 同一个业务地址可能服务多种素材，最终要结合 `panel`、`category_id`、`effect_type` 一起判断。

| 接口名 | 完整业务地址 | 主要作用 | 当前已确认素材 | 出处文件 |
|---|---|---|---|---|
| `get_collections` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collections` | 拉推荐音乐合集 / 歌单列表 | 推荐音乐 / BGM | `yinpincebianl.txt` |
| `replicate/get_collections` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/replicate/get_collections` | 拉模板体系的一级分类 / 合集 | 模板库、营销模板 | `muban.saz`、`yingxiao.saz` |
| `general_config` | `https://lv-pc-api-sinfonlineb.ulikecam.com/artist/v1/effect/general_config` | 拉推荐音乐页配置、推荐词、示例 | 推荐音乐 / BGM | `yinpin.txt` |
| `get_collection_songs` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collection_songs` | 按合集 ID 拉歌曲分页列表 | 推荐音乐 / BGM | `tuijianyinyue.txt`、`yingjiancebian.json` |
| `get_panel_info` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info` | 拉面板分类；某些 panel 直接带首屏资源 | 音效、花字、普通特效、素材包 | `yinxiaoku.saz`、`huazi.saz`、`rementexiao.saz`、`sucaibao.saz` |
| `get_resources_by_category_id` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id` | 按分类 ID 拉素材分页列表 | 音效、文字模板、任务特效、官方素材、转场、滤镜、素材包 | `yinxiaokuremen.saz`、`remenwenzimuban.saz`、`renwutexiao.saz`、`guanfangsucai.saz`、`zhuanchang.saz`、`lvjing.saz`、`remensucaibao.saz` |
| `mget_item` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item` | 补单项详情，常用于音频类资源 | 推荐音乐 / BGM、音效 | `artist-v1-effect-mget_item.txt`、`yinxiaoxiangqing.saz` |
| `mget_artist_item` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item` | 补素材包详情，常用于图形类资源 | 花字、文字模板、贴纸、普通特效、任务特效、官方素材、转场、字幕模板、滤镜、素材包 | `huazixiangqing.saz`、`wenzimubanxiangq.saz`、`tiezhiremenxiangqing.saz`、`rementexiaoxiangqing.saz`、`renwutexiaoxiangqing.saz`、`guanfangsucaixiangqing.saz`、`zhuanchangxiangqing.saz`、`zimuxiangqing.saz`、`lvjingxiangqing.saz`、`remensucaibaoxiangqing.saz` |
| `user_favorite_list` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/user_favorite_list` | 拉用户收藏类素材列表 | 普通特效、字幕模板 | `texiao.saz`、`texiao.json`、`zimu.saz`、`zimu.json` |
| `user_aigc_list` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/user_aigc_list` | 拉用户自己生成的 AIGC 素材列表 | 文字模板、贴纸 | `wenzimoban.saz`、`tiezhiremen.saz` |
| `random_prompt` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/random_prompt` | 拉 AIGC 贴纸提示词推荐 | 贴纸 | `tiezhi.saz`、`tiezhi.json` |
| `pc/replicate/get_collection_templates` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates` | 拉模板合集下的模板分页列表 | 模板库、营销模板 | `tuijianmuban.saz`、`yingxiaojingxuan.saz` |
| `pc/replicate/multi_get_templates` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/multi_get_templates` | 拉单个模板详情 | 模板库、营销模板 | `tuijianmubanxiangqing.saz`、`yingxiaojingxuanxiangqing.saz` |
| `effect/search` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/search` | 通用素材搜索结果列表 | 综合素材、音效、花字、贴纸、普通特效、人物特效、转场、花字模板、滤镜 | `search.saz`、`search-effect.saz`、`search-fllower.saz`、`search-teizhi.saz`、`search-texiao.saz`、`search-rengwutexiao.saz`、`search-zhuanchang.saz`、`search-huazimuban.saz`、`search-lvjing.saz` |
| `search/songs` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/search/songs` | 音乐搜索结果列表 | 音乐搜索 | `search-song.saz` |
| `pc/search/templates` | `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/search/templates` | 模板搜索结果列表 | 模板搜索 | `search-muban.saz` |
| `get_search_words` | `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_search_words` | 搜索联想词 / 热词 | 字幕模板搜索联想词 | `search-zimumuban.saz` |

## 4. 文件索引

说明：
- `角色` 站在抓包证据角度填写，值只表示“这个文件主要证明什么”。
- 如果你想回放完整请求，优先看 `.saz` 或 `.txt`。
- 如果你想直接看字段结构，优先看 `.json`。

### 4.1 推荐音乐 / BGM

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpincebianl.txt` | `已抓到请求` | `get_collections`，推荐音乐合集列表入口 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpin.txt` | `已抓到请求` | `general_config`，推荐音乐页配置接口 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianyinyue.txt` | `已抓到请求` | `get_collection_songs`，按合集拉歌曲列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json` | `已抓到响应` | `get_collection_songs` 解码结果 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/artist-v1-effect-mget_item.txt` | `已抓到请求` | 音乐详情 `mget_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/686_Full.txt` | `已抓到资源 GET` | 最终真实音频资源，`audio/mp4` |

### 4.2 音效

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.saz` | `已抓到请求` | `get_panel_info(panel=audio)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.json` | `已抓到响应` | 音效面板信息 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaokuremen.saz` | `已抓到请求` | `get_resources_by_category_id(panel=audio, category_id=10892)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaokuremen.json` | `已抓到响应` | 热门音效列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.saz` | `已抓到请求` | 音效详情 `mget_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.json` | `已抓到响应` | 单个音效详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiao.saz` | `已抓到资源 GET` | 最终音效 MP3，`audio/mpeg` |

### 4.3 花字

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazi.saz` | `已抓到请求` | `get_panel_info(panel=flower)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazi.json` | `已抓到响应` | 花字面板信息和首屏列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqing.saz` | `已抓到请求` | 花字详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqing.json` | `已抓到响应` | 单个花字详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqingxiazai.saz` | `已抓到资源 GET` | 花字 ZIP 包，`application/zip` |

### 4.4 文字模板

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimoban.saz` | `已抓到请求` | `aigc_effect/user_aigc_list`，用户 AIGC 文字模板列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimuban.json` | `已抓到响应` | 用户 AIGC 文字模板列表响应，当前为空 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remenwenzimuban.saz` | `已抓到请求` | `get_resources_by_category_id(panel=text-template)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remenwenzimuban.json` | `已抓到响应` | 热门文字模板列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangq.saz` | `已抓到请求` | 主模板详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqing.json` | `已抓到响应` | 主文字模板详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqfenye.saz` | `已抓到请求` | 依赖子资源详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqfenye.json` | `已抓到响应` | 主模板依赖子资源详情 |

### 4.5 贴纸

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhi.saz` | `已抓到请求` | `aigc_effect/random_prompt`，AIGC 贴纸提示词推荐 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhi.json` | `已抓到响应` | AIGC 贴纸提示词推荐结果 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremen.saz` | `已抓到请求` | `aigc_effect/user_aigc_list`，用户 AIGC 贴纸列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/teizhiremen.json` | `已抓到响应` | 用户 AIGC 贴纸列表响应，当前为空 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqing.saz` | `已抓到请求` | 普通贴纸详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqing.json` | `已抓到响应` | 普通贴纸详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqingxiazai.saz` | `已抓到资源 GET` | 贴纸 ZIP 包，`application/zip` |

### 4.6 普通特效

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/texiao.saz` | `已抓到请求` | `effect/user_favorite_list`，用户收藏特效 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/texiao.json` | `已抓到响应` | 用户收藏特效列表，当前为空 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiao.saz` | `已抓到请求` | `get_panel_info(panel=effects2)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiao.json` | `已抓到响应` | 特效面板信息 + 热门特效首屏列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqing.saz` | `已抓到请求` | 单个特效详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqing.json` | `已抓到响应` | 单个特效详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqingxiazai.saz` | `已抓到资源 GET` | 特效 ZIP 包，`application/zip` |

### 4.7 任务特效 / 人物特效

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiao.saz` | `已抓到请求` | `get_resources_by_category_id(panel=face-prop, category_key=hot)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiao.json` | `已抓到响应` | 任务特效热门列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqing.saz` | `已抓到请求` | 任务特效详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqing.json` | `已抓到响应` | 单个任务特效详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqingxiazai.saz` | `已抓到资源 GET` | 任务特效 ZIP 包，`application/zip` |

### 4.8 官方素材

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.saz` | `已抓到请求` | `get_resources_by_category_id(panel=insert, category_id=10231)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json` | `已抓到响应` | 官方素材列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqing.saz` | `已抓到请求` | 官方素材详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqing.json` | `已抓到响应` | 单个官方素材详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqingxaizai.saz` | `已抓到资源 GET` | 官方素材下载样例，当前抓到的是 PNG |

### 4.9 转场

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchang.saz` | `已抓到请求` | `get_resources_by_category_id(panel=transitions, category_id=39663)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchang.json` | `已抓到响应` | 转场列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqing.saz` | `已抓到请求` | 转场详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqing.json` | `已抓到响应` | 单个转场详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqingxiazai.saz` | `已抓到资源 GET` | 转场 ZIP 包，`application/zip` |

### 4.10 字幕模板

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimu.saz` | `已抓到请求` | `user_favorite_list(effect_type=48)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimu.json` | `已抓到响应` | 收藏字幕模板列表，当前为空 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqing.saz` | `已抓到请求` | 字幕模板详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqing.json` | `已抓到响应` | 单个字幕模板详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqingxiazai.saz` | `已抓到资源 GET` | 字幕模板 ZIP 包，`application/zip` |

### 4.11 滤镜

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.saz` | `已抓到请求` | `get_resources_by_category_id(panel=filter, category_id=11568)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.json` | `已抓到响应` | 滤镜列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqing.saz` | `已抓到请求` | 滤镜详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqing.json` | `已抓到响应` | 单个滤镜详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqingxiazai.saz` | `已抓到资源 GET` | 滤镜 ZIP 包，`application/zip` |

### 4.12 模板库

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.saz` | `已抓到请求` | `replicate/get_collections(collection_type=1)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.json` | `已抓到响应` | 模板库合集 / 分类列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.saz` | `已抓到请求` | `pc/replicate/get_collection_templates(id=10804)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.json` | `已抓到响应` | 推荐模板列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqing.saz` | `已抓到请求` | `pc/replicate/multi_get_templates` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqing.json` | `已抓到响应` | 模板详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqingxiazai.saz` | `已抓到资源 GET` | 模板 ZIP 包下载 |

### 4.13 营销模板

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiao.saz` | `已抓到请求` | `replicate/get_collections(collection_type=11)`；注意工作区 2026-05-13 新覆盖的同名样本已变成 `pc/search/templates`，见 4.15 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiao.json` | `已抓到响应` | 营销模板合集 / 筛选配置 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.saz` | `已抓到请求` | `pc/replicate/get_collection_templates(id=11029)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.json` | `已抓到响应` | 营销精选模板列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqing.saz` | `已抓到请求` | `pc/replicate/multi_get_templates` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqing.json` | `已抓到响应` | 营销模板详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqingxiazai.saz` | `已抓到资源 GET` | 营销模板 ZIP 包下载 |

### 4.14 素材包

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibao.saz` | `已抓到请求` | `get_panel_info(panel=recipe)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibao.json` | `已抓到响应` | 素材包面板、分类和热门首屏资源 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibao.saz` | `已抓到请求` | `get_resources_by_category_id(panel=composition, category_id=10536)` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibao.json` | `已抓到响应` | 热门素材包列表 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqing.saz` | `已抓到请求` | 素材包详情 `mget_artist_item` |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibaoxiangqing.json` | `已抓到响应` | 单个素材包详情 |
| `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqingxiazai.saz` | `已抓到资源 GET` | 素材包 ZIP 包下载 |

### 4.15 搜索接口补充样本（2026-05-13 新增）

| 文件 | 角色 | 说明 |
|---|---|---|
| `C:\Users\wu\Documents\Fiddler2\Captures\search.saz` | `已抓到请求` | `effect/search`，综合素材搜索，请求里 `effect_type=201`、`scene=material_lib_c_v2` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search.json` | `已抓到响应` | 综合素材搜索结果，实际返回 `effect_type=5/9` 混合 |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-effect.saz` | `已抓到请求` | `effect/search`，音效搜索，请求里 `effect_type=3` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-effect.json` | `已抓到响应` | 音效搜索结果，结果项带 `audio_effect` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-fllower.saz` | `已抓到请求` | `effect/search`，花字搜索，请求里 `effect_type=1` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-fllower.json` | `已抓到响应` | 花字搜索结果，结果项带 `word_art` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-teizhi.saz` | `已抓到请求` | `effect/search`，贴纸搜索，请求里 `effect_type=2` |
| `C:\Users\wu\Documents\Fiddler2\Captures\tiezhi.json` | `已抓到响应` | 贴纸搜索结果，结果项带 `sticker` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-texiao.saz` | `已抓到请求` | `effect/search`，普通特效搜索，请求里 `effect_type=7` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-texiao.json` | `已抓到响应` | 普通特效搜索结果，结果项带 `special_effect` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-rengwutexiao.saz` | `已抓到请求` | `effect/search`，人物特效搜索样本，请求体仍表现为 `effect_type=7` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-rengwutexiao.json` | `已抓到响应` | 人物特效搜索结果，结构与普通特效搜索同构 |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao1.saz` | `已抓到请求` | `effect/search`，相关特效搜索第 1 页，`effect_type=7`，`query=闪烁`，`search_id=""` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao5.saz` | `已抓到请求` | `effect/search`，相关特效搜索第 2 页，`effect_type=7`，`offset=50`，回填首屏 `search_id` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao2.saz` | `已抓到请求` | `effect/search`，相关特效搜索第 1 页，`effect_type=8`，`query=闪烁`，`search_id=""` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao4.saz` | `已抓到请求` | `effect/search`，相关特效搜索第 2 页，`effect_type=8`，`offset=50`，回填首屏 `search_id` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/renwutexiao6.saz` | `已抓到请求` | `effect/search`，相关特效搜索第 3 页，`effect_type=8`，`offset=100`，继续沿用同一个 `search_id` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zhuanchang.saz` | `已抓到请求` | `effect/search`，转场搜索，请求里 `effect_type=19` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zhuanchang.json` | `已抓到响应` | 转场搜索结果 |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-huazimuban.saz` | `已抓到请求` | `effect/search`，花字模板搜索，请求里 `effect_type=6`、`scene=vimo_text-template` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-huazimuban.json` | `已抓到响应` | 花字模板搜索结果，结果项带 `text_template` 和依赖信息 |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-lvjing.saz` | `已抓到请求` | `effect/search`，滤镜搜索，请求里 `effect_type=12` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-lvjing.json` | `已抓到响应` | 滤镜搜索结果，结果项带 `filter` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-song.saz` | `已抓到请求` | `search/songs`，音乐搜索，请求体含 `keyword`、`offset`、`count` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-song.json` | `已抓到响应` | 音乐搜索结果，真正列表在顶层 `response` 字符串中 |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-muban.saz` | `已抓到请求` | `pc/search/templates`，模板搜索 |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-muban.json` | `已抓到响应` | 模板搜索结果，主列表字段是 `template_list` |
| `E:/sucai/crawler_project/fiddler-v2rayn-10808/yingxiao.saz` | `已抓到请求` | 最新模板搜索样本：`pc/search/templates`，`keyword="中秋"`，`channels=["lv_template"]`，响应 `channel=lv_template` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zimumuban.saz` | `已抓到请求` | `get_search_words(effect_type=48)` |
| `C:\Users\wu\Documents\Fiddler2\Captures\search-zimumuban.json` | `已抓到响应` | 只返回推荐词、热词、默认词，不返回素材结果列表 |

## 5. 分类型详解

### 5.1 推荐音乐 / BGM

定位：
- 这是“推荐音乐页”的标准链路
- 核心类型是 `effect_type = 4`
- 入口、配置、列表、单曲详情、真实音频资源五层都抓到了

已确认链路：

```text
打开推荐音乐页
-> /lv/v1/get_collections
-> /artist/v1/effect/general_config
-> /lv/v1/get_collection_songs
-> /artist/v1/effect/mget_item
-> v11-jianying.vlabvod.com 真实音频
```

#### 5.1.1 合集列表

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collections
```

请求体：

```json
{"scene":0}
```

作用：
- 返回推荐音乐页的合集 / 歌单列表
- 后续 `get_collection_songs` 的合集 `id` 很可能从这里来

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpincebianl.txt`

#### 5.1.2 推荐配置

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/artist/v1/effect/general_config
```

请求体：

```json
{"scene":"gen_ai_vocal_songs_rec"}
```

作用：
- 返回推荐词、分类、示例音频等配置
- 更像 UI 配置，不是最终歌曲列表

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpin.txt`

#### 5.1.3 合集歌曲列表

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collection_songs
```

样本请求体：

```json
{
  "count": 50,
  "offset": 0,
  "id": 6678556627852856076,
  "scene": 0
}
```

从解码后的响应可以确认：

```json
{
  "has_more": true,
  "songs": [],
  "next_offset": 50
}
```

作用：
- 按合集 ID 拉歌曲列表
- 这是推荐音乐页真正的“歌曲列表数据源”

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianyinyue.txt`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json`

#### 5.1.4 单曲详情补全

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item
```

已确认的音乐样例 ID：

```text
7492262428060289035
```

作用：
- 用歌曲 `id` 再换一次完整素材详情
- 关键目标是拿到 `item_urls[]`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/artist-v1-effect-mget_item.txt`

#### 5.1.5 真实音乐资源

已确认样例：

```text
https://v11-jianying.vlabvod.com/1b2414873ed0e83bce4d0c777a810eec/6a2914c3/video/tos/cn/tos-cn-ve-2774/oAOg6AfENg9Tn6kDBYBkZwCWDHQ4FytODrf8y3/?a=1775&mime_type=audio_mp4&er=2&ch=0&cr=0&bt=126&btag=c0000e00028000&dr=0&cd=0%7C0%7C0%7C0&br=126&ft=OV.Cu77JWH6BMjB02Jr0PD1IN&qs=6&rc=OTQ7NTo0Z2VkNTpkPDU1M0BpM3c4O285cmh2eTMzNDlkM0AvLWM1My8zX14xNmEvNDE1YSM2ZHNkMmRrZm9gLS1kYTBzcw%3D%3D&dy_q=1778485083&l=202605111538031F2042D6C86CFE8E2EBE
```

响应类型：

```text
audio/mp4
```

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/686_Full.txt`

#### 5.1.6 当前结论

1. 推荐音乐链路完整度最高，五层都抓到了。
2. `get_collection_songs` 明确是分页列表接口。
3. `mget_item` 是音乐链路里把“歌曲 ID”变成“真实资源地址”的关键一步。
4. 最终真实音频不在业务 API 域名上，而是在 `v9/v11-jianying.vlabvod.com` 这类资源域名上。

### 5.2 音效

定位：
- 音效是另一条完整链路
- 核心类型是 `effect_type = 3`
- 与音乐不同，热门列表本身往往已经带 `item_urls` / `download_info.url`

已确认链路：

```text
打开音效面板
-> /artist/v1/panel/get_panel_info (panel=audio)
-> 热门分类 category_id=10892
-> /artist/v1/effect/get_resources_by_category_id (panel=audio)
-> /artist/v1/effect/mget_item
-> lf26-faceu-file-sign.bytecdn.com 真实 MP3
```

#### 5.2.1 音效面板

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info
```

请求体：

```json
{
  "category_status": 1,
  "full_count": false,
  "only_commercial": false,
  "panel": "audio"
}
```

关键结论：
- 返回音效分类元数据
- 热门分类 `category_id = 10892`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.json`

#### 5.2.2 热门音效列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体：

```json
{
  "app_id": 3704,
  "category_id": 10892,
  "count": 50,
  "offset": 0,
  "panel": "audio",
  "panel_source": "heycan"
}
```

关键返回字段：
- `has_more`
- `next_offset`
- `effect_item_list`
- `common_attr.item_urls`
- `common_attr.download_info.url`

关键结论：
- 热门音效列表接口已经直接返回音效项
- 当前样本里很多条目都属于 `category_id = 10892`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaokuremen.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaokuremen.json`

#### 5.2.3 单个音效详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item
```

样本请求体核心：

```json
{
  "app_id": 3704,
  "items": [
    {
      "effect_type": 3,
      "id": "6896679799100689672",
      "source": 1
    }
  ]
}
```

关键结论：
- 音效详情仍走 `mget_item`
- 样例里 `item_urls[0]` 和 `download_info.url` 是同一个真实资源地址

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.json`

#### 5.2.4 真实音效资源

样例：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-v-436d67/72712b436b0445e1ae466cfa4611c3d3?x-expires=1810022050&x-signature=gaSBWtulbscEj%2BZ9USwJ46lifks%3D
```

响应：

```text
Content-Type: audio/mpeg
Content-Length: 7568
```

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiao.saz`

#### 5.2.5 当前结论

1. 音效主类型是 `effect_type = 3`。
2. 热门分类 `category_id = 10892` 已经由请求与响应双向确认。
3. 热门音效列表本身常常已经足够前端展示。
4. 最终真实资源是 MP3。

### 5.3 花字

定位：
- 花字主类型是 `effect_type = 1`
- 入口是 `panel = flower`
- 面板响应里就直接带首屏资源

已确认链路：

```text
打开花字面板
-> /artist/v1/panel/get_panel_info (panel=flower)
-> 热门分类 category_id=10721 直接带首屏列表
-> /artist/v1/effect/mget_artist_item
-> artist-file-sign.byteimg.com
-> application/zip 花字资源包
```

#### 5.3.1 花字面板与首屏列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info
```

请求体关键字段：

```json
{
  "panel": "flower",
  "get_resource": true,
  "resource_count": 50
}
```

关键结论：
- 响应中同时存在 `categories` 和 `category_resources`
- 热门分类 `category_id = 10721`
- `category_resources["10721"]` 里直接就有 `effect_item_list`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazi.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazi.json`

#### 5.3.2 花字列表特征

关键字段：
- `common_attr.id`
- `common_attr.effect_type = 1`
- `common_attr.title`
- `common_attr.cover_url`
- `common_attr.item_urls`
- `common_attr.download_info`
- `common_attr.category_ids`
- `word_art`

关键结论：
- 花字列表阶段就已经带 `item_urls`
- `download_info.url` 在当前样本里通常为空
- 因此最终资源更依赖 `item_urls[0]`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazi.json`

#### 5.3.3 单个花字详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样本详情 ID：

```text
7539407429763796249
```

关键结论：
- 花字详情走 `mget_artist_item`
- 不是 `mget_item`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqing.json`

#### 5.3.4 真实花字资源

样例：

```text
https://p6-artist-file-sign.byteimg.com/tos-cn-i-ik1znaa6ae/f195c11b0f4f4065a43abfc9032e0826?lk3s=43402efa&x-expires=1810022826&x-signature=halNaNpoEBz6akZRdrbK9rqpfZA%3D
```

响应：

```text
Content-Type: application/zip
Content-Length: 613731
```

而且包体中已经能看到：

```text
PK...
1752576790252.png
```

关键结论：
- 花字最终下载的是 ZIP 资源包
- 包里至少包含图片资源

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqingxiazai.saz`

#### 5.3.5 当前结论

1. 花字主类型是 `effect_type = 1`。
2. 花字面板 `panel = flower` 会直接回首屏列表。
3. 花字详情走 `mget_artist_item`。
4. 最终资源是 ZIP 包，不是单图。

### 5.4 文字模板

定位：
- 主模板类型是 `effect_type = 6`
- 依赖子资源里至少已经确认有 `effect_type = 2`
- 这是当前样本里“结构最像组合模板”的一类

已确认链路：

```text
文字模板列表
-> /artist/v1/effect/get_resources_by_category_id (panel=text-template)
-> 选中主模板
-> /artist/v1/effect/mget_artist_item
-> 读取 text_template.depend_resource_list
-> 对依赖 resource_id 再次请求 /artist/v1/effect/mget_artist_item
-> 拿到 effect_type=2 等子资源详情
```

#### 5.4.1 用户 AIGC 文字模板列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/user_aigc_list
```

样本请求体：

```json
{
  "count": 50,
  "effect_type": 116,
  "offset": 0
}
```

样本响应：

```json
{
  "has_more": false,
  "next_offset": 50,
  "aigc_item_list": []
}
```

说明：
- 这是独立的 AIGC 文字模板列表接口
- 当前样本为空

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimoban.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimuban.json`

#### 5.4.2 热门文字模板列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体关键字段：

```json
{
  "category_id": 10577,
  "count": 50,
  "offset": 0,
  "panel": "text-template",
  "panel_source": "heycan"
}
```

关键结论：
- 当前样本里主模板类型是 `effect_type = 6`
- 热门列表本次返回 49 条

说明：
- `category_id = 10577` 对应“热门文字模板”是由文件名和请求体综合判断

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remenwenzimuban.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remenwenzimuban.json`

#### 5.4.3 主模板详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样本主模板：

```text
id = 7590730429486026008
title = 闪光时刻
effect_type = 6
```

已确认依赖数：

```text
11
```

依赖类型示例：
- `default`
- `sticker`
- `fonts`
- `text`
- `flower`

关键结论：
- 主模板不是单一素材
- 它内部依赖一批子资源

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangq.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqing.json`

#### 5.4.4 依赖子资源详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样本依赖资源：

```text
id = 7590672052688899390
title = 闪光时刻-01
effect_type = 2
```

已确认字段：
- `item_urls[0]`
- `download_info.url`
- `download_info.format = png`
- `sticker.sticker_type = 1`
- `track_thumbnail`
- `large_image`

关键结论：
- 这个“分页”文件本质上不是分页接口
- 它是主模板某个依赖资源的详情
- 这个依赖资源已经表现得很像贴纸 / 图层素材

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqfenye.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqfenye.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqing.json`

#### 5.4.5 当前结论

1. 文字模板主模板是 `effect_type = 6`。
2. 文字模板详情走 `mget_artist_item`。
3. `text_template.depend_resource_list` 是这类素材的核心。
4. 至少有一类依赖资源会继续展开为 `effect_type = 2`。
5. 因此文字模板本质上是“主模板 + 多个子资源”的组合结构。

### 5.5 贴纸

定位：
- 当前样本里同时抓到了：
  - AIGC 贴纸提示词接口
  - 用户 AIGC 贴纸列表接口
  - 普通贴纸详情 / 下载链路
- 普通贴纸主类型是 `effect_type = 2`

已确认链路：

```text
AIGC 贴纸提示词
-> /artist/v1/aigc_effect/random_prompt

用户 AIGC 贴纸列表
-> /artist/v1/aigc_effect/user_aigc_list

普通贴纸详情
-> /artist/v1/effect/mget_artist_item
-> item_urls[0]
-> lf26-faceu-file-sign.bytecdn.com
-> application/zip
```

#### 5.5.1 AIGC 贴纸提示词

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/random_prompt
```

样本请求体核心：

```json
{
  "model_list": [
    "high_aes_scheduler_svr:sticker_cartoon_v2.0",
    "high_aes_scheduler_svr:sticker_real_v2.0",
    "text2image_high_aes_sticker_3d",
    "text2image_high_aes_sticker_outline",
    "text2image_high_aes_sticker_pixel",
    "text2image_high_aes_sticker_crayon",
    "text2image_high_aes_sticker_oil"
  ],
  "scene": 1
}
```

关键结论：
- 返回的是 `model2prompt_list`
- 它是提示词推荐，不是普通贴纸素材列表

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhi.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhi.json`

#### 5.5.2 用户 AIGC 贴纸列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/user_aigc_list
```

样本请求体：

```json
{
  "count": 50,
  "effect_type": 2,
  "offset": 0
}
```

样本响应：

```json
{
  "has_more": false,
  "next_offset": 50,
  "aigc_item_list": []
}
```

说明：
- 这是用户自己生成过的 AIGC 贴纸列表
- 当前样本为空

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremen.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/teizhiremen.json`

#### 5.5.3 普通贴纸详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样本：

```text
id = 7529823016566459672
title = 定位坐标
effect_type = 2
```

已确认字段：
- `download_info.url` 是 GIF 预览
- `download_info.format = gif`
- `sticker.sticker_type = 2`
- `sticker.sticker_package.size = 86279`
- `item_urls[0]` 是 ZIP 包地址

关键结论：
- 普通贴纸的预览图和最终资源包是两回事
- 真实资源更依赖 `item_urls[0]`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqing.json`

#### 5.5.4 普通贴纸真实下载

样例响应：

```text
Content-Type: application/zip
Content-Length: 86279
```

ZIP 内已确认文件名：

```text
config.json
ani_info.json
infoSticker.lua
```

关键结论：
- 普通贴纸最终是动画 / 配置资源包
- 不是单张图片

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqingxiazai.saz`

#### 5.5.5 当前结论

1. 普通贴纸主类型是 `effect_type = 2`。
2. AIGC 贴纸链路和普通贴纸链路要分开看。
3. 贴纸详情接口是 `mget_artist_item`。
4. 文字模板里展开出来的 `effect_type = 2` 子资源，和普通贴纸类型完全一致，说明文字模板内部会复用贴纸资源。

### 5.6 普通特效

定位：
- 普通特效主类型是 `effect_type = 7`
- 面板标识是 `panel = effects2`
- 资源包里明显带算法配置

已确认链路：

```text
用户收藏特效
-> /artist/v1/effect/user_favorite_list

热门特效面板
-> /artist/v1/panel/get_panel_info (panel=effects2)
-> 热门分类 category_id=39654
-> /artist/v1/effect/mget_artist_item
-> artist-file-sign.byteimg.com
-> application/zip
```

#### 5.6.1 用户收藏特效列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/user_favorite_list
```

样本请求体：

```json
{
  "effect_types": [7, 47],
  "sub_type_map": {
    "47": [7]
  }
}
```

样本响应为空。

关键结论：
- 这说明 `7` 是普通特效主类型
- `47` 与 `7` 存在映射关系
- 但当前样本不足以完全解释 `47` 的业务名

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/texiao.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/texiao.json`

#### 5.6.2 热门特效面板

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info
```

请求体关键字段：

```json
{
  "panel": "effects2",
  "get_resource": true,
  "resource_count": 50
}
```

关键结论：
- 响应里直接带 `category_resources`
- 热门分类 `category_id = 39654`
- 热门列表项主类型是 `effect_type = 7`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiao.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiao.json`

#### 5.6.3 特效列表项特征

和贴纸 / 花字相比，普通特效更强调这些字段：

- `special_effect.effect_duration`
- `sdk_extra.setting.effect_adjust_params`
- `requirements`
- `sdk_model`
- `model_names`

样本里已经能直接看到：
- `tt_matting`
- `tt_face`
- `tt_face_extra`
- `requirements: ["matting", "blit"]`
- `requirements: ["face", "blit"]`

关键结论：
- 普通特效本质上是“算法 + 配置 + 资源包”
- 它不是简单静态素材

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiao.json`

#### 5.6.4 单个特效详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样本：

```text
id = 7399495930849824000
title = 柔和辉光
effect_type = 7
```

关键结论：
- 详情接口仍然是 `mget_artist_item`
- `item_urls[0]` 指向 ZIP 包
- `download_info.url` 在当前样本里为空

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqing.json`

#### 5.6.5 特效真实下载

响应：

```text
Content-Type: application/zip
Content-Length: 539453
```

ZIP 中已确认文件名：

```text
algorithmConfig.json
config.json
extra.json
AmazingFeature/
AmazingFeature/algorithmConfig.json
AmazingFeature/content.json
AmazingFeature/image/
```

关键结论：
- 特效包里已经明显带算法 / 配置 / 贴图资源

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqingxiazai.saz`

#### 5.6.6 当前结论

1. 普通特效主类型是 `effect_type = 7`。
2. 面板是 `panel = effects2`。
3. 热门特效入口和花字相似，面板响应里就直接带首屏资源。
4. 特效详情接口是 `mget_artist_item`。
5. 最终下载是 ZIP 特效包。

### 5.7 任务特效 / 人物特效

定位：
- 任务特效主类型是 `effect_type = 8`
- 面板标识是 `panel = face-prop`
- 算法依赖明显偏人物、人脸、头部分割、骨骼、表情、avatar drive

已确认链路：

```text
人物特效热门列表
-> /artist/v1/effect/get_resources_by_category_id
-> panel=face-prop, category_key=hot, category_id=38389
-> /artist/v1/effect/mget_artist_item
-> artist-file-sign.byteimg.com
-> application/zip
```

#### 5.7.1 任务特效热门列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体关键字段：

```json
{
  "category_id": 38389,
  "category_key": "hot",
  "count": 50,
  "offset": 0,
  "panel": "face-prop",
  "panel_source": "heycan"
}
```

样本返回：
- `has_more = true`
- `next_offset = 50`
- `effect_item_list`
- 主类型 `effect_type = 8`

关键结论：
- `38389` 在这条链路里就是热门分类
- 入口不是 `get_panel_info`
- 而是直接按分类拉列表

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiao.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiao.json`

#### 5.7.2 任务特效列表项特征

样本里已经直接出现的算法依赖包括：

- `tt_headseg`
- `tt_matting`
- `tt_face`
- `tt_face_extra`
- `tt_freid`
- `tt_skeleton`
- `tt_avatar_drive`

以及对应能力：

- `face`
- `head_seg`
- `matting`
- `skeleton`
- `expression_detect`
- `avatar_drive`
- `texture_blit`

关键结论：
- 任务特效不是普通画面特效
- 它更像人物 / 人脸 / 身体驱动效果

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiao.json`

#### 5.7.3 单个任务特效详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样本：

```text
id = 7399497918765436195
title = 卡通脸
effect_type = 8
```

已确认要求：
- `blit`
- `face`
- `expression_detect`
- `nh_face_align`
- `script`

关键结论：
- 任务特效详情接口虽然还是 `mget_artist_item`
- 但算法依赖比普通特效更集中在人物任务上

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqing.json`

#### 5.7.4 任务特效真实下载

响应：

```text
Content-Type: application/zip
Content-Length: 393818
```

ZIP 中已确认文件名：

```text
algorithmConfig.json
AmazingFeature/
AmazingFeature/mesh/
```

关键结论：
- 任务特效最终也是 ZIP 包
- 但因为出现 `mesh/`，它可能比普通特效更强调几何 / 网格相关资源

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqingxiazai.saz`

#### 5.7.5 当前结论

1. 任务特效主类型是 `effect_type = 8`。
2. 面板是 `panel = face-prop`。
3. 列表入口是 `get_resources_by_category_id`，不是 `get_panel_info`。
4. 最终资源仍是 ZIP 包。
5. 它应当与普通特效 `effect_type = 7` 分开理解。

### 5.8 官方素材

定位：
- 当前样例里的官方素材至少同时出现 `effect_type = 9` 和 `effect_type = 5`
- 列表入口不是 `get_panel_info`
- 而是直接 `get_resources_by_category_id(panel=insert)`

已确认链路：

```text
官方素材列表
-> /artist/v1/effect/get_resources_by_category_id
-> panel=insert, category_id=10231
-> /artist/v1/effect/mget_artist_item
-> p3-heycan-jy-sign.byteimg.com
-> 当前样例下载到 PNG
```

#### 5.8.1 官方素材列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体关键字段：

```json
{
  "category_id": 10231,
  "category_key": "10231",
  "count": 50,
  "offset": 0,
  "panel": "insert",
  "panel_source": "heycan"
}
```

关键结论：
- 列表直接返回 `effect_item_list`
- 样例素材既有纯色 PNG，也有视频素材
- 这类资源更像“插入素材 / 官方图库素材”
- 其中图片类更接近 `effect_type = 9`，视频类更接近 `effect_type = 5`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json`

#### 5.8.2 单个官方素材详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样例：

```text
id = 6971036278649294115
title = 白场
effect_type = 9
```

关键结论：
- 当前样例详情依然走 `mget_artist_item`
- 对纯图片类素材，`item_urls[0]` 直接是图片地址
- `download_info.url` 在当前样例里为空

视频类补充样例：

```text
id = 7024020747794337028
title = 军官笑声 影视经典片段
effect_type = 5
download_info.format = mp4
item_urls = null
```

视频类关键结论：
- `effect_type = 5` 当前出现在官方素材列表内部
- 它和图片型官方素材的最大差异，是下载地址不走 `item_urls[0]`
- 而是直接落在 `download_info.url`
- 响应里同时带 `video.origin_video` 和 `video.transcoded_video`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqing.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json`

#### 5.8.3 当前下载样例

当前已抓到：

```text
Content-Type: image/png
```

关键结论：
- 官方素材不一定落到 ZIP 包
- 至少图片类官方素材会直接下载 PNG
- 当前列表里也看到了 `effect_type = 5` 的视频素材，因此这类资源很可能混合图片 / 视频两种形态

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqingxaizai.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json`

#### 5.8.4 当前结论

1. 官方素材当前样例至少包含两类资源：`effect_type = 9` 图片素材、`effect_type = 5` 视频素材。
2. 列表接口是 `get_resources_by_category_id(panel=insert)`。
3. 详情接口是 `mget_artist_item`。
4. 图片型素材更常见 `item_urls[0] -> PNG / JPEG`。
5. 视频型素材更常见 `download_info.url -> MP4`，并且带 `video` 结构。

### 5.9 转场

定位：
- 转场主类型是 `effect_type = 19`
- 它不是普通特效 `7`
- 也不是人物特效 `8`

已确认链路：

```text
转场列表
-> /artist/v1/effect/get_resources_by_category_id
-> panel=transitions, category_id=39663, category_key=hot
-> /artist/v1/effect/mget_artist_item
-> lf26-faceu-file-sign.bytecdn.com / artist-file-sign.byteimg.com
-> application/zip
```

#### 5.9.1 转场列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体关键字段：

```json
{
  "category_id": 39663,
  "category_key": "hot",
  "count": 50,
  "offset": 0,
  "panel": "transitions",
  "panel_source": "heycan"
}
```

关键结论：
- 当前样例热门分类是 `39663`
- 列表项 `effect_type = 19`
- `sdk_extra` 中可见 `transition.defaultDura`、`transition.isOverlap`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchang.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchang.json`

#### 5.9.2 转场详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样例：

```text
id = 7548386586157813016
title = 螺旋转场
effect_type = 19
```

关键结论：
- 转场详情仍是 `mget_artist_item`
- `item_urls[0]` 指向 ZIP 包
- `download_info.url` 在当前样例里为空

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqing.json`

#### 5.9.3 转场下载

当前已抓到：

```text
Content-Type: application/zip
Content-Length: 52704
```

关键结论：
- 转场最终仍是资源包
- 只是业务语义上应与普通特效拆开理解

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqingxiazai.saz`

#### 5.9.4 当前结论

1. 转场主类型是 `effect_type = 19`。
2. 列表入口是 `get_resources_by_category_id(panel=transitions)`。
3. 详情接口是 `mget_artist_item`。
4. 最终资源是 ZIP 包。

### 5.10 字幕模板

定位：
- 当前样例可稳定确认字幕模板主类型是 `effect_type = 48`
- 但这次没有抓到完整“字幕模板分类列表”
- 只抓到了收藏列表和详情

已确认链路：

```text
收藏字幕模板列表
-> /artist/v1/effect/user_favorite_list (effect_type=48)
-> /artist/v1/effect/mget_artist_item
-> subtitle_template.depend_resource_list
-> application/zip
```

#### 5.10.1 收藏字幕模板列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/user_favorite_list
```

样本请求体：

```json
{
  "count": 50,
  "effect_type": 48,
  "offset": 0
}
```

关键结论：
- 当前样本只说明“字幕模板可以按收藏列表拉”
- 当前响应为空，不能直接推出热门分类入口

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimu.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimu.json`

#### 5.10.2 字幕模板详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样例：

```text
id = 7599874183467699518
title = 综艺-奶茶鼠跟随
effect_type = 48
```

已确认字段：
- `subtitle_template.depend_resource_list`
- `subtitle_template.script_template_version`
- `item_urls[0]`

关键结论：
- 字幕模板不是单一平面素材
- 它至少带自己的字幕模板依赖结构

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqing.json`

#### 5.10.3 字幕模板下载

当前已抓到：

```text
Content-Type: application/zip
Content-Length: 988818
```

关键结论：
- 字幕模板最终仍是 ZIP 包

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqingxiazai.saz`

#### 5.10.4 当前结论

1. 当前样例可确认字幕模板主类型是 `effect_type = 48`。
2. 详情接口是 `mget_artist_item`。
3. 下载结果是 ZIP 包。
4. 当前缺少完整的字幕模板分类 / 热门列表接口。

### 5.11 滤镜

定位：
- 滤镜主类型是 `effect_type = 12`
- 列表走 `panel = filter`
- 字段里会出现 `filter` 和滤镜调节参数

已确认链路：

```text
滤镜列表
-> /artist/v1/effect/get_resources_by_category_id
-> panel=filter, category_id=11568, category_key=chuntian
-> /artist/v1/effect/mget_artist_item
-> lf26-faceu-file-sign.bytecdn.com
-> application/zip
```

#### 5.11.1 滤镜列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体关键字段：

```json
{
  "category_id": 11568,
  "category_key": "chuntian",
  "count": 50,
  "offset": 0,
  "panel": "filter",
  "panel_source": "heycan"
}
```

关键结论：
- 当前样例不是热门，而是某个具体风格分类 `chuntian`
- 列表项主类型是 `effect_type = 12`
- 常见字段包括 `filter.original_image`、`sdk_extra.setting.effect_adjust_params`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.json`

#### 5.11.2 滤镜详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样例：

```text
id = 7607867444048317706
title = 深蓝电影感
effect_type = 12
```

关键结论：
- 详情接口仍然是 `mget_artist_item`
- `item_urls[0]` 指向 ZIP 包
- `filter` 子结构明确说明它是滤镜资源

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqing.json`

#### 5.11.3 滤镜下载

当前已抓到：

```text
Content-Type: application/zip
Content-Length: 165204
```

关键结论：
- 滤镜最终仍是 ZIP 包
- 不只是一个参数值，而是实际滤镜资源包

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqingxiazai.saz`

#### 5.11.4 当前结论

1. 滤镜主类型是 `effect_type = 12`。
2. 列表接口是 `get_resources_by_category_id(panel=filter)`。
3. 详情接口是 `mget_artist_item`。
4. 下载结果是 ZIP 包。

### 5.12 模板库

定位：
- 模板库不走 `artist/v1/effect/*`
- 而是走独立的 `replicate` 体系
- 它和前面的素材包体系要分开理解

已确认链路：

```text
模板库分类
-> /lv/v1/replicate/get_collections (collection_type=1)
-> /lv/v1/pc/replicate/get_collection_templates
-> /lv/v1/pc/replicate/multi_get_templates
-> template_url ZIP
-> video_url / origin_video_info 预览视频
```

#### 5.12.1 模板库分类

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/replicate/get_collections
```

样本请求体：

```json
{
  "collection_type": "1",
  "sdk_version": "167.0.0"
}
```

关键结论：
- 当前样本里 `collection_type = 1` 对应普通模板库
- 返回 `collections`
- 已确认有 `id = 10804` 的“推荐”集合

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.json`

#### 5.12.2 推荐模板列表

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates
```

样本请求体关键字段：

```json
{
  "count": 32,
  "cursor": "0",
  "id": 10804,
  "scene": "edit_page-Template",
  "sdk_version": "167.0.0"
}
```

关键结论：
- 模板列表返回 `item_list`
- 字段明显不同于 `effect_item_list`
- 当前样例里模板项会直接带 `template_url`、`video_url`、`fragment_count`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.json`

#### 5.12.3 模板详情

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/multi_get_templates
```

样例：

```text
id = 7635415980495146264
title = 至今没有找到 驾驭不了的风格｜拿破仑进行曲缩放卡点
```

已确认字段：
- `template_url`
- `video_url`
- `origin_video_info`
- `purchase_info`
- `extra.fragments`
- `tag_list`

关键结论：
- 模板详情不是 `effect_type` 体系
- 模板包和预览视频在详情里直接给出

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqing.json`

#### 5.12.4 模板下载

当前已抓到：

```text
Content-Type: application/zip
Content-Length: 1006079
```

关键结论：
- 模板最终下载是 ZIP 包
- 但详情里同时会带模板演示视频地址

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqingxiazai.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqing.json`

#### 5.12.5 当前结论

1. 模板库属于独立的 `replicate` 接口体系。
2. 分类接口是 `replicate/get_collections(collection_type=1)`。
3. 列表接口是 `pc/replicate/get_collection_templates`。
4. 详情接口是 `pc/replicate/multi_get_templates`。
5. 下载结果是 ZIP，同时详情还会给预览视频。

### 5.13 营销模板

定位：
- 营销模板和普通模板库一样，属于 `replicate` 体系
- 区别主要在 `collection_type`、合集结构和付费信息

已确认链路：

```text
营销模板分类
-> /lv/v1/replicate/get_collections (collection_type=11)
-> /lv/v1/pc/replicate/get_collection_templates
-> /lv/v1/pc/replicate/multi_get_templates
-> template_url ZIP
```

#### 5.13.1 营销模板分类

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/replicate/get_collections
```

样本请求体：

```json
{
  "collection_type": "11",
  "sdk_version": "167.0.0"
}
```

关键结论：
- `collection_type = 11` 对应营销模板体系
- 返回结果中可见更复杂的 `collections` 与 `capsules.filter_list`
- 当前样例里已确认 `id = 11029` 的精选集合

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiao.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiao.json`

#### 5.13.2 营销精选模板列表

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates
```

样本请求体关键字段：

```json
{
  "count": 32,
  "cursor": "0",
  "id": 11029,
  "new_home_page": true,
  "scene": "edit_page-Template",
  "sdk_version": "167.0.0"
}
```

关键结论：
- 返回 `item_list`
- 当前样例与普通模板列表结构高度一致

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.json`

#### 5.13.3 营销模板详情

接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/multi_get_templates
```

样例：

```text
id = 7606145866361179416
title = 新年祝福|拜年|马年|2026|恭贺新年|祝福|新年片头|春节| #马年 #2026 #新年快乐
```

已确认字段：
- `template_url`
- `video_url`
- `purchase_info`
- `origin_video_info`
- `extra.change_type`

关键结论：
- 营销模板详情和普通模板详情结构基本相同
- 但付费、商用、营销场景信息更突出

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqing.json`

#### 5.13.4 营销模板下载

当前已抓到：

```text
Content-Type: application/zip
Content-Length: 62799801
```

关键结论：
- 营销模板最终下载同样是 ZIP
- 当前样例下载体积远大于普通模板，说明模板内容可能更重

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqingxiazai.saz`

#### 5.13.5 当前结论

1. 营销模板属于 `replicate` 模板体系，不属于 `artist effect_type` 体系。
2. 分类接口是 `replicate/get_collections(collection_type=11)`。
3. 列表接口与详情接口和普通模板库一致。
4. 最终下载是 ZIP 包。

### 5.14 素材包

定位：
- 素材包主类型是 `effect_type = 50`
- 这类资源最像“组合成片素材”
- 核心特征是 `recipe.materials` 和 `recipe.video`

已确认链路：

```text
素材包面板
-> /artist/v1/panel/get_panel_info (panel=recipe)
-> 热门 category_resources["10536"]
-> /artist/v1/effect/get_resources_by_category_id (panel=composition)
-> /artist/v1/effect/mget_artist_item
-> recipe.materials
-> application/zip
```

#### 5.14.1 素材包面板

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info
```

样本请求体关键字段：

```json
{
  "panel": "recipe",
  "get_resource": true,
  "resource_count": 50
}
```

关键结论：
- 面板响应包含 `categories`
- 当前样例已有 18 个分类
- 热门分类 `category_id = 10536`
- `category_resources["10536"]` 已直接带首屏列表

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibao.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibao.json`

#### 5.14.2 热门素材包列表

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

样本请求体关键字段：

```json
{
  "category_id": 10536,
  "category_key": "10536",
  "count": 50,
  "offset": 0,
  "panel": "composition",
  "panel_source": "heycan"
}
```

样例列表项：

```text
id = 7239269933702499622
title = 户外运动丨片头
effect_type = 50
```

关键结论：
- 列表和面板的业务名虽然相关，但 `panel` 已从 `recipe` 变成 `composition`
- 列表项主类型稳定是 `50`

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibao.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibao.json`

#### 5.14.3 素材包详情

接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item
```

样例：

```text
id = 7230441318567267587
title = 复古胶片 | 片头
effect_type = 50
```

已确认字段：
- `recipe.material_count`
- `recipe.materials`
- `recipe.video`

关键结论：
- 这类素材包不是单个资源
- 当前样例里 `recipe.materials` 内已经能展开出 `effect_type = 2` 的贴纸类子资源
- 说明素材包本身是组合结构

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibaoxiangqing.json`

#### 5.14.4 素材包下载

当前已抓到：

```text
Content-Type: application/zip
Content-Length: 5048
```

关键结论：
- 当前抓到的是素材包 ZIP 下载
- 但真正完整的组合结构还要结合 `recipe.video` 和 `recipe.materials` 一起理解

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqingxiazai.saz`

#### 5.14.5 当前结论

1. 素材包主类型是 `effect_type = 50`。
2. 面板入口是 `get_panel_info(panel=recipe)`。
3. 列表入口是 `get_resources_by_category_id(panel=composition)`。
4. 详情接口是 `mget_artist_item`。
5. 素材包本质上是“主包 + recipe.materials + recipe.video”的组合结构。

## 6. 现在最稳定的总判断

1. 剪映素材不是“一个接口走到底”，而是明显存在“面板 / 列表 / 详情 / 最终资源”四层结构。
2. `mget_item` 更偏音乐 / 音效。
3. `mget_artist_item` 更偏花字 / 模板 / 贴纸 / 特效 / 官方素材 / 转场 / 滤镜 / 素材包这类“素材包”。
4. `effect_type = 2` 已经可以稳定理解成贴纸类资源，而且会被文字模板复用。
5. `effect_type = 6` 是文字模板主模板，不是普通贴纸。
6. `effect_type = 7` 和 `effect_type = 8` 都是特效，但应当拆成两类：
   - `7`：普通特效 / 画面特效
   - `8`：任务特效 / 人物特效
7. `effect_type = 5` 目前最强的指向是“官方视频素材 / 插入视频素材”。
8. `effect_type = 9`、`12`、`19`、`48`、`50` 也已经有样本支撑，分别对应官方素材、滤镜、转场、字幕模板、素材包。
9. `effect_type = 10`、`11` 目前没有样本命中，先不做业务命名。
10. `replicate` 是独立于 `artist effect_type` 的另一套模板体系，至少覆盖模板库和营销模板。
11. 图形类素材最终大多数都落到 ZIP 包，包里再带配置、图片、脚本、算法目录。
12. 但官方素材中至少已有直接下载 PNG 的样例，同时也已看到直接下载 MP4 的视频型素材。
13. 音频类素材最终落到单独的音频文件。

## 7. 目前仍未直接抓到的环节

1. `effect_type = 47` 的业务含义
   - 在用户收藏特效接口里出现了 `47 -> 7`
   - 但当前样本还不足以完全解释它的准确业务名
2. 官方素材更多分类入口
   - 当前只确认了 `panel=insert, category_id=10231`
   - 还没覆盖更多官方素材分类
3. 滤镜完整分类入口
   - 当前只抓到 `panel=filter, category_id=11568, category_key=chuntian`
   - 还没完整覆盖滤镜的全部分类树
4. 模板库 / 营销模板更多二级分类与筛选组合
   - 当前已确认合集接口与精选列表接口
   - 但还没把所有 `collections` / `capsules.filter_list` 的真实请求组合跑全
5. 某些中文分类名的精确文本
   - 部分原始响应存在终端显示乱码
   - 目前对“热门”等结论，优先使用 `category_id`、`category_key`、文件名、链路位置交叉确认
6. `effect_type = 10`、`11` 的业务含义
   - 当前这批文件里没有直接命中
   - 在没有新样本前，不建议按名称硬映射

### 7.1 我已自行补出的接口

下面这些接口，虽然最初不是直接靠对应页面抓到的，但已经用你现有包里的会话、Cookie、设备参数、请求模板成功在线重放验证：

1. 普通贴纸列表接口
   - 已确认 `panel = sticker`
   - 已确认面板分类接口：
     - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info`
   - 已确认分类样例：
     - `category_id = 2065`, `category_key = ruchang`, `category_name = 入场`
     - `category_id = 2063`, `category_key = chuchang`, `category_name = 出场`
     - `category_id = 2064`, `category_key = xunhuan`, `category_name = 循环`
   - 已确认列表接口：
     - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id`
   - 已在线重放成功的列表样例：
     - `panel = sticker, category_id = 2065, category_key = ruchang`
     - `panel = sticker, category_id = 2063, category_key = chuchang`
     - `panel = sticker, category_id = 11128`
     - `panel = sticker, category_id = 10515`
   - 说明：
     - `2065 / 2063 / 2064` 更像贴纸运动/播放形态分类
     - `11128 / 10515` 是普通贴纸详情样本里反推出来的业务分类

2. 字幕模板完整分类入口
   - 已确认可以通过 `get_panel_info` 探测到多个可用 `panel` 名：
     - `subtitle-template`
     - `subtitle`
     - `captions`
     - `caption`
     - `zimu`
     - `subtitle_template`
   - 已确认列表接口：
     - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id`
   - 已在线重放成功的列表样例：
     - `panel = subtitle-template, category_id = 5913895`
     - `panel = subtitle, category_id = 5913895`
     - `panel = captions, category_id = 5913895`
     - `panel = caption, category_id = 5913895`
     - `panel = zimu, category_id = 5913895`
     - `panel = subtitle_template, category_id = 5913895`
   - 返回样例首项：
     - `title = 综艺-奶茶鼠跟随`
     - `effect_type = 48`
   - 当前最稳判断：
     - 剪映字幕模板至少支持多组同义 `panel` 名，服务端都能返回同一套字幕模板列表

3. 文字模板主模板本体下载地址
   - 虽然还没有“点击使用时的独立下载 GET 包”抓包样本
   - 但已经在线重放确认主模板详情接口会返回新的主包下载地址
   - 已确认接口：
     - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item`
   - 已在线重放成功样例：
     - `id = 7590730429486026008`
     - `title = 闪光时刻`
     - `effect_type = 6`
     - 返回新的 `item_urls[0]`
   - 说明：
     - 这已经足以证明“主模板本体下载地址可刷新拿回”
     - 但如果你还想证明“应用模板时客户端额外发起了哪个最终下载 GET”，那一跳仍然值得继续补抓

### 7.2 下一步最省事的补抓清单

1. 文字模板主模板最终下载 GET
   - 页面：`文本 -> 文字模板`
   - 最容易的动作：进入一个模板详情后，不要只看预览，要真正点一次 `使用 / 应用`
   - 如果第一次没出下载：把模板删掉，再应用一次，或者切另一个模板再切回来
   - 这一步最可能补到：主模板本体最终下载地址，而不只是依赖子资源详情
2. 官方素材更多分类，顺带继续验证 `effect_type = 5`
   - 页面：`官方素材 / 插入素材`
   - 最容易的动作：优先点会动的封面、影视片段类、视频背景类、搞笑片段类
   - 关键词优先级：`影视经典片段`、`视频背景`、`搞笑视频`、`片段`
   - 这一步最可能补到：更多 `effect_type = 5` 视频样本，以及 `panel=insert` 下更多 `category_id`
3. 滤镜完整分类树
   - 页面：`滤镜`
   - 最容易的动作：从 `热门` 切到 `人像 / 风景 / 节日 / 春天` 这类二级分类，每个分类点第一个滤镜
   - 这一步最可能补到：更多 `category_key` 和完整分类层次
4. 模板库 / 营销模板筛选组合
   - 页面：`模板`、`营销模板`
   - 最容易的动作：先点一个合集，再点一个筛选胶囊，再切一次排序或比例
   - 你重点要找：`https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates`
   - 这一步最可能补到：`collections` 和 `capsules.filter_list` 的真实组合请求
5. 为了逼出 `effect_type = 10`、`11`，最值得优先试的未覆盖面板
   - 页面优先级：`背景`、`蒙版`、`动画`、`片头片尾`、`画中画素材`
   - 最容易的动作：每进一个新面板，只做两步，先点顶部第一个分类，再点第一条素材
   - 说明：这条是“补抓优先级建议”，不是对 `10`、`11` 的业务结论

## 8. 最后给你一个最好用的抓包判断法

以后你再看到新请求，可以先按下面方式快速判断：

1. 先看是不是 `mget_item` 还是 `mget_artist_item`
   - `mget_item`：先往音乐 / 音效想
   - `mget_artist_item`：先往花字 / 模板 / 贴纸 / 特效想
2. 再看 `effect_type`
   - `1`：花字
   - `2`：贴纸 / 文字模板子资源
   - `3`：音效
   - `4`：音乐 / BGM
   - `5`：当前最像官方视频素材 / 插入视频素材
   - `6`：文字模板主模板
   - `7`：普通特效
   - `8`：任务特效 / 人物特效
   - `9`：官方素材
   - `12`：滤镜
   - `19`：转场
   - `48`：字幕模板
   - `50`：素材包 / 组合成片素材
   - `10`、`11`：当前样本未命中，先不要硬判
3. 再看最终资源域名和格式
   - `vlabvod.com`：大概率音频
   - `lf26-faceu-file-sign.bytecdn.com`：常见音效、贴纸、部分特效资源
   - `p3/p6/p9/p26-artist-file-sign.byteimg.com`：常见花字、贴纸、特效、任务特效资源
   - `p3-heycan-jy-sign.byteimg.com`：常见图片预览、官方素材图片、部分子资源图
   - `template_url` / `video_url`：优先考虑这是 `replicate` 模板体系，不是 `effect_type` 体系
   - `audio/mp4` / `audio/mpeg`：音频
   - `image/png`：图片素材
   - `application/zip`：素材包 / 模板包

## 9. 关键样例速查

### 音乐 / BGM 样例

- 样例歌曲 ID：`7492262428060289035`
- 最终资源：

```text
https://v11-jianying.vlabvod.com/1b2414873ed0e83bce4d0c777a810eec/6a2914c3/video/tos/cn/tos-cn-ve-2774/oAOg6AfENg9Tn6kDBYBkZwCWDHQ4FytODrf8y3/?a=1775&mime_type=audio_mp4&er=2&ch=0&cr=0&bt=126&btag=c0000e00028000&dr=0&cd=0%7C0%7C0%7C0&br=126&ft=OV.Cu77JWH6BMjB02Jr0PD1IN&qs=6&rc=OTQ7NTo0Z2VkNTpkPDU1M0BpM3c4O285cmh2eTMzNDlkM0AvLWM1My8zX14xNmEvNDE1YSM2ZHNkMmRrZm9gLS1kYTBzcw%3D%3D&dy_q=1778485083&l=202605111538031F2042D6C86CFE8E2EBE
```

### 音效样例

- 样例音效 ID：`6896679799100689672`
- 最终资源：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-v-436d67/72712b436b0445e1ae466cfa4611c3d3?x-expires=1810022050&x-signature=gaSBWtulbscEj%2BZ9USwJ46lifks%3D
```

### 花字样例

- 样例花字 ID：`7539407429763796249`
- 最终资源：

```text
https://p6-artist-file-sign.byteimg.com/tos-cn-i-ik1znaa6ae/f195c11b0f4f4065a43abfc9032e0826?lk3s=43402efa&x-expires=1810022826&x-signature=halNaNpoEBz6akZRdrbK9rqpfZA%3D
```

### 文字模板样例

- 主模板 ID：`7590730429486026008`
- 依赖子资源 ID：`7590672052688899390`
- 子资源预览 PNG：

```text
https://p3-heycan-jy-sign.byteimg.com/tos-cn-i-3jr8j4ixpe/e29e4e1c8d2349c79ff30fb0a13d6520~tplv-3jr8j4ixpe-resize:1920:1920.png?x-expires=1810023245&x-signature=HJjerje5DcXlb%2Br%2BrXqX7ZkHsLk%3D
```

### 贴纸样例

- 样例贴纸 ID：`7529823016566459672`
- 最终资源：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-v-436d67/b3bc8c98c19d0a2762859072e32d862f?x-expires=1810024068&x-signature=6cWpG%2Fvz5UBFoh8%2Bx3lALTc%2B8S8%3D
```

### 普通特效样例

- 样例特效 ID：`7399495930849824000`
- 最终资源：

```text
https://p26-artist-file-sign.byteimg.com/tos-cn-i-ik1znaa6ae/0905f297f5204d5bb93d715cb8466db3?x-expires=1810024389&lk3s=43402efa&x-signature=7KcQmAyEBGggPcEb6CHERrFxVT4%3D
```

### 任务特效样例

- 样例任务特效 ID：`7399497918765436195`
- 最终资源：

```text
https://p6-artist-file-sign.byteimg.com/tos-cn-i-ik1znaa6ae/9c7cfedf30a64dbf943d07dc4f8d2cb5?x-expires=1810024697&lk3s=43402efa&x-signature=VtzchgQlBpQQ43gYGRdXkxKUs3k%3D
```

### 官方素材样例

- 样例官方素材 ID：`6971036278649294115`
- 最终资源：

```text
https://p3-heycan-jy-sign.byteimg.com/tos-cn-i-3jr8j4ixpe/9c33d7d5b46a458cbaeb9cc840ffc157~tplv-3jr8j4ixpe-resize:1920:1920.png?x-expires=1810027015&x-signature=gALXVvWG9NkLFxdcsg08Svz4VmI%3D
```

### 官方视频素材样例

- 样例官方视频素材 ID：`7024020747794337028`
- 标题：`军官笑声 影视经典片段`
- 最终资源：

```text
https://v3-artist.vlabvod.com/854c12eb3a1e16bb9914b6fa60422c96/6a0ad903/video/tos/cn/tos-cn-v-436d67/ccc9a9996602418ba30ec6ec653976e6/?a=4066&ch=0&cr=0&dr=0&er=0&cd=0%7C0%7C0%7C0&br=705&bt=705&cs=0&ds=3&ft=yg8SInYYwAI3XBLxdfuJwFU268aggdY6Y5ThUfogl-3NR7mmXKL9m3kFBfqUxMf&mime_type=video_mp4&qs=0&rc=OWgzNmk2OjZmNzM5OTM8OEBpM3c1NmY6ZmlxODMzNDZlM0A0LTMyYV4vXjAxMzNgXi5eYSNmYGBicjRfbnFgLS1kYC9zcw%3D%3D&btag=c0000e00008000&dy_q=1778491010&l=20260511171649572DD887B0F751B3624E
```

### 转场样例

- 样例转场 ID：`7548386586157813016`
- 最终资源：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-v-436d67/ocANLDoCaUiTYWaBDAEnNwFD2AACfgfoEo8Awt?x-expires=1810026212&x-signature=zdJrXtkBD2K%2F%2F9s%2Bq2QIgQTnS7M%3D
```

### 字幕模板样例

- 样例字幕模板 ID：`7599874183467699518`
- 最终资源：

```text
https://p6-artist-file-sign.byteimg.com/tos-cn-i-ik1znaa6ae/53898b903e3745fbb056d3eb5f972352?lk3s=43402efa&x-expires=1810026280&x-signature=1jR%2FkHRkiDXaElHS5ygM8wA6qKQ%3D
```

### 滤镜样例

- 样例滤镜 ID：`7607867444048317706`
- 最终资源：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-v-436d67/f31c8f7ba639041a53ceb2f3e63b3e72?x-expires=1810026436&x-signature=%2FjuVwQ3WbGt0oavL1chDn836RSQ%3D
```

### 模板库样例

- 样例模板 ID：`7635415980495146264`
- 模板包：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-i-0000c2242/oUUxoAAApDArbGf2CxFEgaDPM9CJj9AIEzfRNs?x-expires=1781082558&x-signature=gf%2FQJirAkM5T5%2BR2iDYBwE134TI%3D
```

### 营销模板样例

- 样例营销模板 ID：`7606145866361179416`
- 模板包：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-o-0000c2242/oIPcieAAIfGRcoeLePRiEM8SoATENhAAI4lLed?x-expires=1781082631&x-signature=s%2F0tiBoTBz%2B9Sij5zHbzI%2Fh3T6U%3D
```

### 素材包样例

- 样例素材包 ID：`7230441318567267587`
- 最终资源：

```text
https://lf26-faceu-file-sign.bytecdn.com/tos-cn-v-436d67/d64d6b153d23423dbea9607673dba548?x-expires=1810026741&x-signature=I%2FxNIuH6nuaMoLK0fVGn2uT1GT8%3D
```

## 10. 链路实测打通结果（2026-05-11）

### 10.1 实测方法

- 这一步不再直接复用旧抓包里的资源直链，因为直链大多带时效签名，过期后会失效。
- 本轮采用的实际方法是：
  1. 先重放原始抓包中的详情接口或列表接口。
  2. 从最新响应里取回新的签名资源 URL。
  3. 再对这个签名 URL 发 `Range: bytes=0-255` 的分片请求。
- 只要底层资源返回 `206 Partial Content`，并且响应头里有明确的 `Content-Type`、`Content-Range`，就说明这条链路已经真实打到底层文件，不只是停留在接口元数据层。
- 本轮用到的刷新接口地址：
  - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item`
  - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id`
  - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item`
- 说明：
  - PowerShell 自带 `Invoke-WebRequest` 对 `Range` 头的处理不稳定，容易报错。
  - 本轮最终以 `curl.exe` 的资源响应头实测结果为准。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/artist-v1-effect-mget_item.txt`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.saz`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.saz`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqing.saz`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibaoxiangqing.json`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/verify_jianying_chain.ps1`

### 10.2 已实测打通的链路

#### 10.2.1 音乐 / BGM

- 刷新接口地址：`https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item`
- 请求样例：`effect_type = 4`，`id = 7492262428060289035`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 叶子域名：`v5-jianying.vlabvod.com`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: video/mp4`
  - `Content-Range: bytes 0-255/1695109`
- 结论：
  - 这条链路可以一直下钻到真实文件。
  - 业务上它是音乐 / BGM，但资源分发层实际给的是 MP4 容器音频流，所以 URL 参数里常见 `mime_type=audio_mp4`，而响应头可能显示 `video/mp4`。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/artist-v1-effect-mget_item.txt`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/686_Full.txt`

#### 10.2.2 音效

- 刷新接口地址：`https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item`
- 请求样例：`effect_type = 3`，`id = 6896679799100689672`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 叶子域名：`lf26-faceu-file-sign.bytecdn.com`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: audio/mpeg`
  - `Content-Range: bytes 0-255/7568`
- 结论：
  - 音效链路也可以一直下钻到底层真实音频文件。
  - 这一类常常直接就是 `mp3 / mpeg`，比音乐链路更直。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.saz`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoxiangqing.json`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiao.saz`

#### 10.2.3 官方视频素材

- 刷新接口地址：`https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id`
- 请求样例：`panel = insert`，`category_id = 10231`
- 命中的视频样例：`effect_type = 5`
- 叶子字段：`common_attr.download_info.url`
- 叶子域名：`v26-artist.vlabvod.com`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: video/mp4`
  - `Content-Range: bytes 0-255/664870`
- 结论：
  - `effect_type = 5` 这一批当前可以高置信度视为官方视频素材 / 插入视频素材。
  - 这条链路不只是“列表里看见视频字段”，而是真的可以继续拿到底层 MP4。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.saz`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json`

#### 10.2.4 素材包主包

- 刷新接口地址：`https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item`
- 请求样例：`id_list = ["7230441318567267587"]`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 叶子域名：`lf26-faceu-file-sign.bytecdn.com`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/5048`
- 结论：
  - 素材包主包本身就是一个可直接获取的 ZIP。
  - 这已经证明“素材包详情 -> 主包下载地址 -> 底层 ZIP”这条链路是通的。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqing.saz`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibaoxiangqing.json`
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/remensucaibaoxiangqingxiazai.saz`

#### 10.2.5 素材包内部依赖

- 刷新接口地址：`https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item`
- 请求样例：`id_list = ["7230441318567267587"]`
- 依赖字段：`data.effect_item_list[0].recipe.materials[0].common_attr.item_urls[0]`
- 首个依赖样例：
  - 标题：`夏天的故事`
  - `effect_type = 2`
- 叶子域名：`lf26-faceu-file-sign.bytecdn.com`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/87638`
- 结论：
  - 素材包不仅主包能拿到，内部依赖素材也能继续下钻到真实 ZIP。
  - 这说明 `recipe.materials[]` 不是纯展示结构，而是真实可下载的依赖链。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibaoxiangqing.json`

#### 10.2.6 素材包演示视频

- 刷新接口地址：`https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item`
- 请求样例：`id_list = ["7230441318567267587"]`
- 视频字段：
  - 原视频：`data.effect_item_list[0].recipe.video.origin_video.video_url`
  - 转码视频：`data.effect_item_list[0].recipe.video.transcoded_video["360p" | "480p" | "720p" | "1080p"].video_url`
- 本轮实测样例：`recipe.video.transcoded_video["720p"].video_url`
- 叶子域名：`v3-artist.vlabvod.com`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: video/mp4`
  - `Content-Range: bytes 0-255/787537`
- 结论：
  - 素材包详情里的 `recipe.video` 也不是摆设，确实能直达演示视频 MP4。
  - 前面一度看起来像“没有视频”，实际只是脚本取字段时取错了，不是接口没有给。
- 来源：
  - `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/sucaibaoxiangqing.json`

### 10.3 本轮实测后的总判断

- 结论一：
  - 仅凭你现在已经给出的抓包数据，至少下面几条链路已经可以确认“从列表 / 详情接口一路走到真实底层文件”：
  - 音乐 / BGM
  - 音效
  - 官方视频素材
  - 素材包主包
  - 素材包内部依赖
  - 素材包演示视频
- 结论二：
  - 最稳定的做法不是长期保存旧的直链，而是保存“刷新直链”的接口请求参数。
  - 也就是优先保存：
    - 请求地址
    - body
    - `Cookie`
    - `X-Helios`
    - `X-Medusa`
    - 设备参数
  - 这样直链过期后，仍可以重新刷出新的签名下载地址。
- 结论三：
  - `mget_item` 更偏音频类资源刷新。
  - `mget_artist_item` 更偏素材包、模板、图形类素材刷新。
  - `get_resources_by_category_id` 则更适合先从分类列表里筛出目标项，再继续下钻。

### 10.4 继续补测结果（2026-05-11）

#### 10.4.1 滤镜

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjingxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/165204`
- 结论：
  - 滤镜主资源可以直接下钻到底层 ZIP。

#### 10.4.2 转场

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zhuanchangxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/52704`
- 结论：
  - 转场主资源可以直接下钻到底层 ZIP。

#### 10.4.3 字幕模板

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/zimuxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/988818`
- 结论：
  - 字幕模板主包可以直接下钻到底层 ZIP。

#### 10.4.4 文字模板

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/982708`
- 结论：
  - 文字模板主包可以直接下钻到底层 ZIP。

#### 10.4.5 花字

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/huazixiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/613731`
- 结论：
  - 花字主包可以直接下钻到底层 ZIP。

#### 10.4.6 贴纸

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tiezhiremenxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/86279`
- 结论：
  - 贴纸主包可以直接下钻到底层 ZIP。

#### 10.4.7 画面特效

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/rementexiaoxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/539453`
- 结论：
  - 画面特效主包可以直接下钻到底层 ZIP。

#### 10.4.8 人物特效

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/renwutexiaoxiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/393818`
- 结论：
  - 人物特效主包可以直接下钻到底层 ZIP。

#### 10.4.9 模板库

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmubanxiangqing.json`
- 主包字段：`data.templates[0].template_url`
- 预览字段：`data.templates[0].video_url`
- 主包分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/1006079`
- 预览视频分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: video/mp4`
  - `Content-Range: bytes 0-255/1260336`
- 结论：
  - 模板库链路可以同时打到底层模板包和预览 MP4。

#### 10.4.10 营销模板

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuanxiangqing.json`
- 主包字段：`data.templates[0].template_url`
- 预览字段：`data.templates[0].video_url`
- 主包分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: application/zip`
  - `Content-Range: bytes 0-255/62799801`
- 预览视频分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: video/mp4`
  - `Content-Range: bytes 0-255/5482388`
- 结论：
  - 营销模板链路也可以同时打到底层模板包和预览 MP4。

#### 10.4.11 官方素材图片

- 详情文件：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucaixiangqing.json`
- 叶子字段：`data.effect_item_list[0].common_attr.item_urls[0]`
- 分片实测结果：
  - `HTTP/1.1 206 Partial Content`
  - `Content-Type: image/png`
  - `Content-Range: bytes 0-255/8575`
- 结论：
  - 官方素材图片型资源可以直接下钻到底层 PNG。
  - 配合前面已经测通的官方视频素材，可以确认官方素材体系里确实混合存在图片与视频两类底层资源。

### 10.5 当前已实锤的底层资源类型汇总

- 音乐 / BGM：
  - 已实测打通到底层音频流，响应头常见 `video/mp4`，业务语义是 `audio_mp4`
- 音效：
  - 已实测打通到底层 `audio/mpeg`
- 官方素材：
  - 已实测打通到底层 `image/png`
  - 已实测打通到底层 `video/mp4`
- 花字：
  - 已实测打通到底层 `application/zip`
- 文字模板：
  - 已实测打通到底层 `application/zip`
- 字幕模板：
  - 已实测打通到底层 `application/zip`
- 贴纸：
  - 已实测打通到底层 `application/zip`
- 画面特效：
  - 已实测打通到底层 `application/zip`
- 人物特效：
  - 已实测打通到底层 `application/zip`
- 滤镜：
  - 已实测打通到底层 `application/zip`
- 转场：
  - 已实测打通到底层 `application/zip`
- 模板库：
  - 已实测打通到底层 `application/zip` + `video/mp4`
- 营销模板：
  - 已实测打通到底层 `application/zip` + `video/mp4`
- 素材包：
  - 已实测打通到底层 `application/zip`
  - 已实测打通内部依赖 `application/zip`
  - 已实测打通演示视频 `video/mp4`

## 11. 横向翻页与分类切换（新增）

### 11.1 先说结论

当前这批样本里，横向查阅基本已经能稳定拆成 3 套模式：

1. `offset` 翻页  
   - 适用于音乐列表 `get_collection_songs`
   - 也适用于大多数 `artist/v1/effect/get_resources_by_category_id` 素材列表
2. `id` / `category_id` / `category_key` 切分类  
   - 音乐更偏 `id`
   - `artist/effect` 素材更偏 `panel + category_id + category_key`
3. `cursor` 翻页  
   - 适用于 `pc/replicate/get_collection_templates`
   - 也就是模板库 / 营销模板这套 `replicate` 体系

当前还没有完全实锤的点：
- “纯音乐”到底是另一套音乐合集 `id`，还是另一个页面入口
- “轻快”到底是音乐合集切换、推荐词下钻，还是单独搜索 / 筛选参数

也就是说：
- “当前推荐音乐第一页之后怎么翻第二页”已经可以明确回答
- “怎么精确切到纯音乐、轻快”还差一条点击对应分类时的抓包

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianyinyue.txt`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpin.txt`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiao.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.json`

### 11.2 音乐 / BGM：怎么翻页，怎么切合集

当前已抓到的音乐列表接口是：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collection_songs
```

当前已抓到的请求体样例是：

```json
{"count":50,"filter_commercial":false,"filter_paid_type":[],"id":6678556627852856076,"offset":0,"only_enterprise_commercial":false,"scene":0}
```

当前已抓到的响应里明确出现：

```json
{"has_more":true,"next_offset":50}
```

所以当前这条推荐音乐链路可以稳定下结论：

- 当前合集第一页：
  - `id = 6678556627852856076`
  - `offset = 0`
- 当前合集第二页：
  - `id` 不变
  - 把 `offset` 改成 `50`
- 第三页：
  - 继续沿用响应返回的 `next_offset`

也就是说，“第一页之后怎么查第二页”这件事，在音乐链路里已经明确是：

```json
{"count":50,"id":6678556627852856076,"offset":50,"scene":0}
```

注意这里真正控制“换一页”的字段是：
- `offset`

真正更像“换一个音乐合集 / 换一个大类”的字段是：
- `id`

出处：
- 请求：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianyinyue.txt`
- 响应：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json`

### 11.3 音乐里的“纯音乐”“轻快”目前能确定到哪一步

当前另一个已抓到的音乐相关接口是：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/artist/v1/effect/general_config
```

当前已抓到的请求体是：

```json
{"scene":"gen_ai_vocal_songs_rec"}
```

这个接口当前能稳定确认的作用是：
- 给推荐音乐页返回配置
- 返回推荐词 / 推荐标签候选

当前已知推荐词样例包括：
- `民谣`
- `流行`
- `嘻哈`
- `国风`
- `R&B`
- `朋克`
- `电子`
- `爵士`
- `雷鬼`
- `DJ`
- `快乐`
- `活力`
- `EMO`
- `鼓舞`
- `怀旧`
- `兴奋`
- `思念`
- `律动`
- `伤感`
- `放松`
- `浪漫`
- `男声`
- `女声`

但当前还不能 100% 直接下结论说：
- “纯音乐”一定对应哪个 `id`
- “轻快”一定对应哪个下游请求参数

当前最稳的判断是：

1. “推荐音乐当前这一个合集的翻页”已经明确是改 `offset`
2. “纯音乐”更像是另一套音乐合集，因此大概率会切到另一个 `id`
3. “轻快”更像是推荐词 / 标签词，可能会触发：
   - 另一套合集 `id`
   - 或者某个搜索 / 筛选参数
   - 或者某个未补到的音乐分类接口

当前只能说“很像”，还不能说“已经实锤”，因为我们还没抓到你点击“纯音乐”或“轻快”之后发出的第一条请求。

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpin.txt`

### 11.4 音乐里目前已经能看到的“轻快风格”痕迹

虽然“轻快”这个筛选动作本身还没实锤，但当前第一页音乐样本里已经能看到明显偏轻快 / 活力的歌曲标题，例如：

- `企业宣传片明亮轻快 成功时刻`
- `愉快欢快的音乐  Be Happy`
- `快乐节奏氛围  Summer Embrace`
- `乐观活力  Upbeat Energetic`

这说明两件事：

1. 当前推荐合集本身就已经混入了“轻快 / 活力 / 欢快”风格歌曲
2. 但这还不足以证明“轻快”是一个独立筛选参数

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json`

### 11.5 `artist/effect` 体系的横向规则：大多数素材都遵循这一套

下面这些素材，当前都已经能确认属于同一类横向模式：

- 音效
- 官方素材
- 任务特效
- 转场
- 滤镜
- 文字模板
- 素材包
- 以及后面继续扩展时的大多数 `artist/effect` 面板素材

它们的列表主接口都是：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

这套接口里，最关键的横向控制字段是：

- `panel`
- `category_id`
- `category_key`
- `offset`
- `count`

通用理解可以写成：

```text
panel 决定素材面板
category_id / category_key 决定当前分类
offset 决定当前页
count 决定每页条数
```

通用请求体骨架大概长这样：

```json
{
  "app_id": 3704,
  "category_id": 10892,
  "category_key": "",
  "count": 50,
  "offset": 0,
  "panel": "audio",
  "panel_source": "heycan"
}
```

也就是说：

- 同分类翻第 2 页：
  - `panel` 不变
  - `category_id` / `category_key` 不变
  - 改 `offset`
- 切到另一分类第一页：
  - `panel` 通常不变
  - 改 `category_id`
  - 如有对应 `category_key`，一起改
  - `offset` 回到 `0`

### 11.6 音效库：已经最适合做横向扩展

音效分类来源当前已经抓到：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info
panel = audio
```

已知可直接横向切换的音效分类样例：

| 分类名 | `category_id` | `category_key` |
|---|---:|---|
| 热门 | `10892` | `10892` 或空字符串样例 |
| 最新 | `5914796` | `new` |
| 转场 | `10899` | `10899` |
| 网感口播 | `5914402` | `wanggan` |
| 热梗语录 | `5914764` | `regeng` |
| 笑声 | `10894` | `10894` |
| 尴尬 | `5914403` | `ganga` |
| 震惊 | `5914404` | `zhenjing` |
| 提示音 | `5914405` | `tishi` |
| 综艺感 | `10895` | `zongyi` |
| 机械 | `10896` | `10896` |
| BGM | `10897` | `10897` |
| 魔法 | `10901` | `10901` |
| 打斗 | `10902` | `10902` |
| 美食 | `10903` | `10903` |
| 动物 | `10904` | `10904` |
| 环境音 | `10905` | `10905` |
| 悬疑 | `10907` | `10907` |

所以：

- 热门音效第 2 页：
  - `panel = audio`
  - `category_id = 10892`
  - `offset = 50`
- 环境音第一页：
  - `panel = audio`
  - `category_id = 10905`
  - `category_key = 10905`
  - `offset = 0`

出处：
- 分类：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.json`
- 热门列表示例：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaokuremen.saz`

### 11.7 滤镜：已确认有分页，也已确认分类键参与横向切换

当前已抓到的滤镜列表示例是：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
panel = filter
category_id = 11568
category_key = chuntian
offset = 0
```

当前响应里明确有：

```json
{"has_more":true,"next_offset":50}
```

所以当前至少可以实锤：

- “春天”这个滤镜分类的第二页：
  - `panel = filter`
  - `category_id = 11568`
  - `category_key = chuntian`
  - `offset = 50`

这里已经可以看出：

- `category_id` 不是唯一分类控制字段
- `category_key` 也参与滤镜分类判断

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.saz`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/lvjing.json`

### 11.8 官方素材：分页已确认，横向分类仍需继续补

当前已抓到的官方素材列表示例是：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
panel = insert
category_id = 10231
category_key = 10231
offset = 0
```

响应里明确有：

```json
{"has_more":true,"next_offset":50}
```

所以当前能稳定确认：

- 官方素材当前这一个分类的第 2 页：
  - `panel = insert`
  - `category_id = 10231`
  - `category_key = 10231`
  - `offset = 50`

并且当前这个分类里已经同时混有：

- `effect_type = 9` 图片官方素材
- `effect_type = 5` 视频官方素材

这意味着继续横向翻页，很有机会再补到更多：

- 图片型素材
- 视频型素材
- 不同版权来源素材

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.json`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/guanfangsucai.saz`

### 11.9 模板库 / 营销模板：不是 `offset`，而是 `cursor`

模板体系的横向逻辑和 `artist/effect` 那套不一样。

模板分类入口是：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/replicate/get_collections
```

模板列表入口是：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates
```

#### 11.9.1 普通模板库

当前 `collection_type = 1` 已抓到的分类包括：

| `id` | `display_name` |
|---:|---|
| `10804` | 推荐 |
| `10807` | 风格大片 |
| `10808` | 片头片尾 |
| `10809` | 宣传 |
| `10814` | 纪念相册 |
| `11639` | 政企 |
| `10817` | 日常碎片 |
| `10812` | 旅行 |
| `10811` | 卡点 |
| `10810` | vlog |
| `10815` | 游戏 |
| `10816` | 美食 |

当前已抓到的模板列表请求样例是：

```json
{
  "count": 32,
  "cursor": "0",
  "id": 10804,
  "scene": "edit_page-Template",
  "filters": {
    "duration": [],
    "fragment_count": [],
    "is_commercial": 0,
    "screen_style": ["landscape", "portrait"],
    "sub_category_ids": []
  }
}
```

当前响应里明确有：

```json
{"new_cursor":"32","has_more":true}
```

所以：

- 模板库“推荐”第一页：
  - `id = 10804`
  - `cursor = "0"`
- 模板库“推荐”第二页：
  - `id = 10804`
  - 把 `cursor` 改成 `"32"`

也就是说，这套不是 `offset = 50` 这种规则，而是：

```text
cursor = 上一页响应返回的 new_cursor
```

出处：
- 分类：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.json`
- 列表：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.saz`
- 响应：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.json`

#### 11.9.2 营销模板

当前 `collection_type = 11` 已抓到的分类响应里，已经能看到：

- 一级行业分类
- 二级子分类
- 胶囊筛选项 `capsules`
- 筛选配置 `modal_config.filter_list`

也就是说，营销模板这套横向切换不只是“换一个 `id`”，还已经能确认存在更细的筛选层：

- `sub_category_ids`
- `fragments_range` / 片段数量
- `duration_range` / 模板时长
- `commercial_templates` / 可商用

当前已抓到的营销模板列表响应也明确有：

```json
{"new_cursor":"32","has_more":true}
```

所以营销模板至少能稳定确认：

- 同一个营销合集翻页：
  - 改 `cursor`
- 切不同营销行业 / 子类：
  - 先从 `get_collections(collection_type=11)` 里拿对应分类与筛选配置
  - 再把对应 `id` 或筛选参数带入 `get_collection_templates`

需要注意：

- 当前文件已经清楚展示了“有哪些行业分类、有哪些子分类、有哪些筛选胶囊”
- 但“点击某一个具体营销分类后，请求体最终把哪些 UI 选项映射成哪几个 `filters` 字段”这一步，最好再补一条点击抓包来完全坐实

出处：
- 分类：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiao.json`
- 列表：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.saz`
- 响应：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingxiaojingxuan.json`

### 11.10 现在最实用的横向查阅口诀

以后你再抓到一个“列表请求”，可以先按下面的方法判断：

1. 如果是：
   - `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collection_songs`
   - 那就优先看：
     - `id` 是否变了
     - `offset` 是否变了
2. 如果是：
   - `https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id`
   - 那就优先看：
     - `panel`
     - `category_id`
     - `category_key`
     - `offset`
3. 如果是：
   - `https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates`
   - 那就优先看：
     - `id`
     - `cursor`
     - `filters`

一句话总结：

```text
音乐看 id + offset
artist 素材看 panel + category_id/category_key + offset
模板体系看 id + cursor + filters
```

### 11.11 目前还缺哪几条最关键的横向抓包

如果你现在要把“纯音乐”“轻快”“其他分类页”彻底坐实，最值得补的只有下面几条：

1. 音乐页点击“纯音乐”
   - 目标：确认它到底是换了 `id`，还是走了另一条接口
   - 最想拿到的请求：
     - `get_collection_songs`
     - 或者音乐分类列表接口
2. 音乐页点击“轻快”
   - 目标：确认它到底映射成：
     - 另一个合集 `id`
     - 推荐词筛选
     - 还是搜索参数
3. 滤镜页从“春天”切到另一个具体分类
   - 目标：补齐更多 `category_id + category_key` 对照
4. 官方素材页切到另一个非 `10231` 的分类
   - 目标：补齐更多 `effect_type = 5` 视频样本和更多官方素材分类
5. 营销模板页点击一个具体行业，再点一个具体筛选胶囊
   - 目标：把 `yingxiao.json` 里的 `capsules` 彻底映射到最终请求体 `filters`

### 11.12 在线回放实测结果（2026-05-11 新增）

这一节和上面不一样。

上面很多结论是“根据抓到的原始请求/响应字段推断出来的规则”。
这一节是我直接拿你已经抓到的请求头、Cookie、请求体做在线重放，确认改分页字段或改分类字段后，服务器现在仍然会正常返回数据。

也就是说，这一节属于：

```text
不是只看抓包字段
而是已经实测能调通
```

#### 11.12.1 音乐推荐列表第 2 页：已在线验证

在线重放接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collection_songs
```

原始第一页请求体：

```json
{"count":50,"filter_commercial":false,"filter_paid_type":[],"id":6678556627852856076,"offset":0,"only_enterprise_commercial":false,"scene":0}
```

我做的改动：

- 保持 `id = 6678556627852856076` 不变
- 把 `offset` 从 `0` 改成 `50`

在线返回结果：

```json
{"has_more":true,"next_offset":100}
```

同时确实返回了新的 50 首歌，第一页和第二页不是同一批。

当前在线实测拿到的第 2 页样例首项：

```text
Chasing the Sky（纯音乐）
```

当前结论可以直接落地成：

- 推荐音乐第 1 页：`offset = 0`
- 推荐音乐第 2 页：`offset = 50`
- 推荐音乐第 3 页：`offset = 100`
- 更稳的写法：始终取上一页响应里的 `next_offset`

这说明：

1. 推荐音乐这条链路的分页规则已经不是“猜测”，而是在线验证成功
2. 当前推荐合集翻到第 2 页后，确实已经能出现明显“纯音乐”标题样本
3. 但这仍然不等于“纯音乐标签页”的请求规则已经被坐实

出处：
- 原始抓包请求：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianyinyue.txt`
- 原始抓包响应：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json`
- 在线回放使用的请求模板来源同上

#### 11.12.2 “纯音乐”目前能确认到哪一步

基于上面的在线结果，现在能更精确地说：

1. 推荐音乐第 2 页里已经出现了 `Chasing the Sky（纯音乐）`
2. 这说明“纯音乐曲目”本身会混在当前推荐合集里
3. 但这还不能证明界面上的“纯音乐”按钮只是把 `offset` 往后翻
4. 更大的可能仍然是：
   - 它会切到另一个音乐合集 `id`
   - 或者切到另一条音乐分类/筛选请求

所以：

```text
“推荐列表翻到后面能看到纯音乐”
已经成立

“点击纯音乐按钮后，请求一定怎么改”
目前仍未完全坐实
```

#### 11.12.3 “轻快”目前能确认到哪一步

当前还没有“点击轻快后第一条请求”的抓包，所以还不能把“轻快”直接写死成某个固定参数。

但现在已经可以把范围缩得更小：

1. `yinpin.txt` 里的 `general_config` 已明确给出推荐词候选：
   - `快乐`
   - `活力`
   - 以及其他风格词
2. 推荐音乐第一页与第二页里，已经能看到明显偏轻快/活力的歌曲：
   - `企业宣传片明亮轻快 成功时刻`
   - `愉快欢快的音乐  Be Happy`
   - `乐观活力  Upbeat Energetic`
   - `年轻律动 青春活力 积极阳光自信 商务展示`

所以当前最稳判断是：

- “轻快”大概率不是单纯翻下一页
- 更像是：
  - 推荐词下钻
  - 另一套合集 `id`
  - 或者某个隐藏筛选参数

如果你要彻底坐实“轻快怎么查”，最值钱的补包仍然是：

```text
音乐页点击“轻快”后的第一条请求
```

出处：
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinpin.txt`
- `C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yingjiancebian.json`
- 在线第 2 页回放结果来源同 11.12.1

#### 11.12.4 音效分类切换：已在线验证 3 个分类

在线重放接口：

```text
https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id
```

我直接把 `panel = audio` 保持不变，只改 `category_id` / `category_key`，已经在线验证成功以下分类：

1. 环境音

请求体核心：

```json
{"panel":"audio","category_id":10905,"category_key":"10905","offset":0,"count":50}
```

在线返回：

```json
{"has_more":true,"next_offset":50}
```

样例首项：

```text
春天的鸟鸣
```

2. 提示音

请求体核心：

```json
{"panel":"audio","category_id":5914405,"category_key":"tishi","offset":0,"count":50}
```

在线返回：

```json
{"has_more":true,"next_offset":50}
```

样例首项：

```text
工业喇叭鸣响24
```

3. BGM

请求体核心：

```json
{"panel":"audio","category_id":10897,"category_key":"10897","offset":0,"count":50}
```

在线返回：

```json
{"has_more":false,"next_offset":36}
```

样例首项：

```text
Gentle and pop marimba BGM(1040887)
```

这说明音效库横向切换规则已经可以写得很明确：

- 固定接口：`get_resources_by_category_id`
- 固定面板：`panel = audio`
- 换分类主要改：
  - `category_id`
  - `category_key`
- 翻页改：
  - `offset`

同时也能看出：

1. 不是每个分类都有下一页
2. `has_more` 和 `next_offset` 要按分类分别看
3. “音效库”和“BGM 音效分类”虽然都在 `panel=audio` 下，但业务内容可以差很多

出处：
- 分类清单来源：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaoku.json`
- 原始热门请求：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/yinxiaokuremen.saz`
- 在线回放使用的请求模板来源同上

#### 11.12.5 模板库第 2 页：已在线验证

在线重放接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates
```

原始第一页请求体核心：

```json
{"id":10804,"cursor":"0","count":32}
```

我做的改动：

- 保持 `id = 10804` 不变
- 把 `cursor` 从 `"0"` 改成 `"32"`

在线返回：

```json
{"new_cursor":"62","has_more":true}
```

并且确实拿到了下一批模板，不是第一页重复内容。

这说明模板库分页规则已经在线验证成功：

- 第 1 页：`cursor = "0"`
- 第 2 页：`cursor = "32"`
- 第 3 页：用上一页返回的 `new_cursor = "62"`

出处：
- 原始请求：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.saz`
- 原始响应：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.json`
- 分类来源：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.json`

#### 11.12.6 模板库切到“旅行”分类：已在线验证

同一个接口：

```text
https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates
```

我做的改动：

- 把合集 `id` 从推荐 `10804` 改成旅行 `10812`
- `cursor` 保持 `"0"`

在线返回正常，说明：

```text
模板库切大类
= 改合集 id

模板库同类翻页
= 改 cursor
```

这条规则现在也已经从“推断”升级成“在线验证成功”。

出处：
- 分类来源：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/muban.json`
- 请求模板来源：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianmuban.saz`

## 12. 本地 Cache 目录的素材缓存分类方式（2026-05-11 新增）

### 12.1 先说结论

我这次直接检查了：

- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\effect`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\music`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\image`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\resourcePanel`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template`

当前可以下一个很稳定的判断：

```text
剪映本地 Cache 的素材分类方式
不是按“热门 / 轻快 / 旅行 / 花字 / 贴纸”这种页面分类名直接建文件夹
而是更接近：

缓存域（资源类型）
-> 资源 ID 或实例 ID
-> 哈希目录 / 哈希文件
-> 具体素材内容
```

也就是说，本地缓存主要按“素材技术形态”分仓，而不是按“前端页面分类名”分仓。

### 12.2 顶层目录里，和素材最相关的几个缓存域

这次检查中，和素材下载最相关的目录主要是：

| 目录 | 当前判断 | 证据出处 |
|---|---|---|
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\ressdk_db` | 列表页 / 分类页 / 首屏响应的数据库缓存，是“素材库页面数据”的重要落盘位置 | `rp.db-wal` 中直接能搜到 `get_panel_info`、`get_resources_by_category_id`、`get_collection_songs` 等响应片段 |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect` | 高层素材包缓存，常见于花字、文字模板、贴纸、滤镜、转场、字幕模板、素材包等 | 目录结构与 `config.json / content.json / extra.json` |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\effect` | 低层运行时特效缓存，偏引擎资源 | 目录内有 `.lua / .frag / .vert / .material / .xshader / anim.prefab` |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\music` | 音乐/BGM/节拍文件缓存 | 目录内直接是哈希名 `.mp3 / .beat`，并有 `downLoadcfg` |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\image` | 封面图、预览图、缩略图缓存 | 绝大部分为无扩展名哈希文件，少量 `.svg` |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\resourcePanel` | 面板级配置与分块缓存，不是单个素材包目录 | 有若干 2MB/4MB 哈希块、`.crc`、`templates_config_*` |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template` | 模板工程/模板实例缓存，不是按模板分类名建目录 | 目录内有 `template.json`、`attachment_*`、`draft.extra` |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\importcache` | 本地导入媒体的旧索引缓存，不是素材库下载主目录 | 文件内直接能看到本地 `audio_record` 等路径信息 |
| `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\importcache3` | 本地导入媒体的新版媒资信息缓存，不是素材库下载主目录 | `mediainfo/*.json` 是音视频时长、码率、格式等信息 |

本轮目录数量概览：

- `artistEffect`：101 个一级目录
- `effect`：224 个一级目录
- `music`：348 个文件
- `image`：989 个文件

这些数量本身也说明：它更像“资源池缓存”，不像“热门/推荐/旅行”这种页面分类缓存。

出处：
- 根目录扫描：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache`
- 文件数量统计：同上

### 12.3 `artistEffect` 的分类方式：资源类型目录 -> 资源 ID -> 哈希目录

`artistEffect` 是这次最关键的目录。

它的典型结构是：

```text
artistEffect
└─ 资源ID
   ├─ 哈希目录
   └─ *_modity_time.txt
```

明确样例：

```text
C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590730429486026008
└─ 94d948d5ab86147e94d0f296f0daf6c6
```

其中 `7590730429486026008` 已经和前面文档里分析过的“文字模板主模板资源 ID”对上。

这个哈希目录内部实际内容：

- `config.json`
- `content.json`
- `extra.json`
- `js`
- `local`

其中：

- `config.json` 表明这是脚本模板型资源
- `extra.json` 里有 `depend_resource_list`
- `content.json` 里能看到它依赖别的字体、贴纸、花字、文字样式等资源 ID

我直接读到的主包配置样例：

文件：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590730429486026008\94d948d5ab86147e94d0f296f0daf6c6\config.json`

关键内容：

```json
{
  "effect": {
    "Link": [
      {
        "scriptPath": "js/template/template.js",
        "type": "ScriptInfoSticker"
      }
    ]
  }
}
```

依赖清单文件：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590730429486026008\94d948d5ab86147e94d0f296f0daf6c6\extra.json`

我实际读到的依赖资源示例包括：

- `7590511242821848382`
- `7590672052688899390`
- `7590727249989651736`

这三个依赖资源本身也各自落成独立目录：

- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590511242821848382`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590672052688899390`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590727249989651736`

并且它们内部 `config.json` 的类型分别是：

- `7590511242821848382` -> `InfoSticker`
- `7590672052688899390` -> `InfoSticker`
- `7590727249989651736` -> `TextStyle`

对应文件：

- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590511242821848382\b0115829b91201e57b4356ef0c7a58cb\config.json`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590672052688899390\0ff12979783b27cc6cd0bd0b8f43e564\config.json`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7590727249989651736\412387e2021b178c7136c52b96105d0e\config.json`

所以 `artistEffect` 当前最稳的解释是：

```text
它缓存的不是“热门花字”“轻快音乐”这种页面分类
而是“一个高层素材包，以及这个素材包依赖的多个子资源”
```

这也解释了为什么文字模板、花字、贴纸、字幕模板、滤镜、转场这类东西很容易在这里留下痕迹。

出处：
- 模板主资源分析来源：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/wenzimubanxiangqing.json`
- 本地缓存对应目录：上面列出的 `artistEffect` 路径

### 12.4 `effect` 的分类方式：运行时特效资源池

`effect` 目录的一级目录名同样是数字，但它表现出来的内容和 `artistEffect` 不同。

样例：

```text
C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\effect\1644341\ae803da2a5d2292e0f8be3c8ab3b3788
```

里面能看到：

- `anim.prefab`
- `BounceIn.lua`
- `config.json`
- `content.json`
- `rt.frag`
- `rt.material`
- `rt.vert`
- `rt.xshader`

这说明它更像底层运行时特效资源，偏引擎执行文件，而不是用户面板上的“单个素材业务包”。

所以当前更合理的分工是：

- `artistEffect`：高层素材包、组合素材、模板类素材
- `effect`：这些素材真正运行时要调用的底层效果资源

也就是说，很多图形类素材下载后，很可能会同时带动这两个目录变化。

出处：
- 路径：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\effect\1644341\ae803da2a5d2292e0f8be3c8ab3b3788`

### 12.5 `music` 的分类方式：哈希文件，不按歌曲名或分类名建目录

`music` 目录的落盘方式非常直接：

- 音频文件是哈希名 `.mp3`
- 节拍文件是哈希名 `.beat`
- 另外有一个下载映射文件：`downLoadcfg`

样例文件名：

- `0291b72047769e085e7595ce5d65dbd2.mp3`
- `068e10fa625c44db08b2f034a0cb0c6d.beat`
- `06eb05cbe43e3ce2a58479c3c9df455d.mp3`

配置文件：

`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\music\downLoadcfg`

其内容格式类似：

```json
{
  "date": "1714530956167",
  "hex": "1b1009b307d75f2c3ae499827fb09f6b",
  "path": "95fcf973d4327a81db68eea5fb62fdf1.mp3"
}
```

所以音乐缓存的规则也很清楚：

```text
不是：
music\轻快\xxx.mp3

而是：
music\哈希名.mp3
music\哈希名.beat
再由 downLoadcfg 维护映射
```

这和前面接口层的“合集 / 分类 / 分页”是两套逻辑：

- 接口层按 `collection id / category_id / offset` 组织
- 本地缓存层按哈希文件落盘

出处：
- 路径：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\music`
- 下载映射：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\music\downLoadcfg`
- 对应接口样本：`C:/Users/wu/Documents/Codex/2026-05-11/fiddler-v2rayn-10808/tuijianyinyue.txt`、`artist-v1-effect-mget_item.txt`、`686_Full.txt`

### 12.6 `image` 的分类方式：封面/缩略图哈希缓存

`image` 目录当前看到的规律是：

- 大量无扩展名哈希文件
- 少量 `.svg`
- 没有按素材业务分类名建子目录

扩展名统计结果：

- 无扩展名：978 个
- `.svg`：11 个

样例：

- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\image\0027a187108ad746a76678d702c04c07`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\image\01c6b3ee36a22bf594a6ddf478a9b6fc`

当前更像：

```text
封面图 / 静态图 / 缩略图 / 面板资源图
按哈希缓存
```

所以像官方素材、模板封面、音乐封面、特效封面，很可能都会共用这里，而不是各自建一个“花字图片”“滤镜图片”目录。

出处：
- 路径：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\image`

### 12.7 `resourcePanel` 的分类方式：面板配置 + 分块缓存

`resourcePanel` 目录里我看到的是：

- 多个哈希名大文件
- 配套 `.crc`
- `templates_config_3672830509584572`
- `specialCharacter` 子目录

典型文件：

- `a974bd116cadc3a695f95da1ad66e739`
- `a974bd116cadc3a695f95da1ad66e739.crc`
- `e770c092a61bc12b11ec18ddfd614f7a`
- `templates_config_3672830509584572`

其中 `templates_config_3672830509584572` 的内容很短：

```ini
[General]
panel_fetcher_feed_req_index=9
```

这更像“面板拉取状态 / 配置”，不是业务素材分类。

`specialCharacter` 目录这次检查为空，也没有看到它体现“素材分类名”的证据。

所以当前更稳的解释是：

```text
resourcePanel
= 面板级配置、预加载块、面板数据分块缓存
不等于具体素材下载目录
```

出处：
- 路径：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\resourcePanel`
- 配置文件：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\resourcePanel\templates_config_3672830509584572`

### 12.8 `template` 的分类方式：模板工程实例缓存，不按“推荐/旅行”分类

`template` 目录目前主要看到两部分：

- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template\04272f9fbb834200fa174bad5ed6dfec`
- `C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template\cache`

第一个目录内部有：

- `template.json`
- `attachment_pc_common.json`
- `draft.extra`
- `common_attachment`

第二个目录内部有：

- `7CC94161-EAFE-4279-B8A0-AF3BF8113111.zip`
- `attachment_editing.json`
- `common_attachment\attachment_script_video.json`

其中：

- `template.json` 是完整模板工程结构
- `attachment_editing.json` 是编辑态附加信息
- `attachment_script_video.json` 是脚本视频附件信息

这说明 `template` 更像：

```text
模板被下载/打开后
在本地还原成一个“可编辑模板工程”
```

而不是：

```text
template\推荐
template\旅行
template\电商
```

另外，`template.json` 内部虽然能看到个别 `category_id / category_name` 字段，但那是模板内部引用素材自己的业务属性，不代表本地目录按这些分类建仓。

出处：
- 模板实例目录：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template\04272f9fbb834200fa174bad5ed6dfec`
- 模板缓存目录：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template\cache`

### 12.9 一个特殊样例：`artistEffect` 里也会出现“接近模板工程”的大包

除了上面那个规则化很强的 `artistEffect\资源ID\哈希目录` 结构，这次还看到一个比较特殊的大包：

```text
C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7233797098666315040\5003e93364200ca8e0d43094972e1931
```

这个目录里有：

- `content.json`
- `content.json.bak`
- `draft_meta_info.json`
- `draft.extra`
- `template.tmp`
- `template-2.tmp`
- `attachment_pc_common.json`
- `common_attachment`

这说明有一部分高层素材包，实际上已经不是简单的单效果素材，而是“接近模板工程/组合工程”的结构。

所以在本地缓存层，可以把它理解为：

- 普通图形素材：更像单包
- 组合素材 / 模板类素材：更像工程包

这和前面接口层里分析过的：

- 文字模板
- 模板库
- 营销模板
- 素材包

这些链路，本身就比“单个音效、单个滤镜”更复杂，是一致的。

出处：
- 路径：`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect\7233797098666315040\5003e93364200ca8e0d43094972e1931`

### 12.10 这次没有找到“按页面分类名建目录”的证据

我额外做过一轮针对性检索，重点搜过这些线索：

- `热门`
- `轻快`
- `旅行`
- `category_id`
- `category_key`
- `panel=text-template`
- `panel=audio`

检查范围主要是：

- `artistEffect`
- `resourcePanel`
- `template`

结果是：

- 没有找到稳定的“目录名 = 页面分类名”证据
- 能看到的 `category_id / category_name` 多数出现在素材内容 JSON 内部
- 它们是素材属性，不是缓存仓位命名规则

所以目前最稳的落盘模型仍然是：

```text
页面层：
热门 / 轻快 / 旅行 / 推荐 / 风格

接口层：
panel / category_id / category_key / collection id / cursor / offset

缓存层：
资源类型目录 / 资源ID / 哈希目录 / 哈希文件
```

### 12.11 现在可以怎么用这套结论

如果你后面继续抓包、继续下载素材，可以按下面这套思路判断本地落盘位置：

1. 音乐 / BGM / beat
看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\music`

2. 图形类素材下载后有没有生成高层包
先看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\artistEffect`

3. 图形类素材有没有额外生成运行时底层效果
再看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\effect`

4. 模板库 / 营销模板 / 组合模板下载后有没有变成工程
看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\template`

5. 只是预览封面图变化
看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\image`

6. 面板切页、分类切换、首屏列表数据变化
先看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\ressdk_db`

7. 面板分块、局部预加载、面板配置变化
看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\resourcePanel`

8. 如果素材已经被插入工程，想看它作为“项目媒体”有没有落索引
看：
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\importcache`
和
`C:\Users\wu\AppData\Local\JianyingPro\User Data\Cache\importcache3`

### 12.12 目前仍然缺的实锤点

当前已经能稳定说明“缓存分类方式”，但还有几类素材的“最终落在哪个缓存域”没有完全逐类点名实锤：

- 官方素材下载后的最终本地落盘目录
- 官方视频素材下载后的最终本地落盘目录
- 个别模板库 / 营销模板下载时，是否一定同时写入 `artistEffect`
- 音效库是否除了 `music` 之外还会向别的目录写业务索引

也就是说：

- “缓存组织规则”已经很明确
- “每一种素材最终一定写哪个根目录”还可以继续逐类做一轮更细的对照实验

最省事的补法是：

1. 清空或记下当前几个关键目录的修改时间
2. 在剪映里只下载一种单一素材
3. 立刻比对这几个目录哪一个发生变化：
   - `ressdk_db`
   - `artistEffect`
   - `effect`
   - `music`
   - `image`
   - `template`
4. 这样很快就能把“某类素材 -> 本地缓存根目录”一一补齐

### 12.13 各类素材与本地缓存域对照表

下面这张表把当前最实用的判断汇总成“一类素材对应看哪些缓存目录”。

说明：

- `列表/分类缓存` 指你切页面、切分类、翻页时最容易变化的目录
- `下载后主缓存` 指素材真正下载到本地后最应该优先看的目录
- `辅助缓存` 指封面图、运行时依赖、项目导入索引等补充目录
- `证据等级`
  - `已实锤`：当前样本和本地缓存都能直接对应上
  - `高概率`：目录职责已经很清楚，但还没做“单类清洁环境下载对照实验”
  - `待实锤`：现在只能给出最可能路径，仍建议单独补一次对照抓取

| 素材类型 | 列表/分类缓存 | 下载后主缓存 | 辅助缓存 | 证据等级 | 当前判断 |
|---|---|---|---|---|---|
| 推荐音乐 / BGM | `ressdk_db` | `music` | `image` | `已实锤` | 列表响应会落数据库缓存，真正音频与 beat 落 `music`，封面图走 `image` |
| 音效 | `ressdk_db` | `music` | `image` | `已实锤` | 现在看起来和 BGM 一样，业务入口不同，但本地音频落盘方式一致 |
| 花字 | `ressdk_db`、`resourcePanel` | `artistEffect` | `effect`、`image` | `高概率` | 高层包更像落 `artistEffect`，复杂表现依赖可能继续落到 `effect` |
| 文字模板 | `ressdk_db` | `artistEffect` | `effect`、`image`、`template` | `已实锤` | 主模板资源 ID 已和 `artistEffect` 对上；如果继续还原成工程，还会看到 `template` |
| 贴纸 | `ressdk_db` | `artistEffect` | `effect`、`image` | `高概率` | 从接口形态和目录职责看，与花字/文字模板子资源同一路径最吻合 |
| 普通特效 | `ressdk_db`、`resourcePanel` | `artistEffect`、`effect` | `image` | `高概率` | 高层业务包和底层运行时资源大概率会同时参与 |
| 任务特效 / 人物特效 | `ressdk_db` | `artistEffect`、`effect` | `image` | `高概率` | 和普通特效同属图形/算法特效体系，只是业务面板不同 |
| 官方素材（图片） | `ressdk_db` | `待单项实测` | `image`、`importcache`、`importcache3` | `待实锤` | 预览图一定会进 `image`；真正图片素材更可能走项目媒体/导入链路，而不是 `artistEffect` |
| 官方素材（视频） | `ressdk_db` | `待单项实测` | `image`、`importcache3` | `待实锤` | 当前更像直接视频媒体，可能不走图形素材包目录，而是进入项目媒体索引链路 |
| 转场 | `ressdk_db` | `artistEffect` | `effect`、`image` | `高概率` | 业务上是单资源包，技术上更接近图形素材 |
| 字幕模板 | `ressdk_db` | `artistEffect` | `effect`、`image` | `高概率` | 更像模板化文字资源，主缓存路径应与花字/文字模板接近 |
| 滤镜 | `ressdk_db` | `artistEffect` | `effect`、`image` | `高概率` | 详情与下载形态接近特效类；运行时资源非常可能在 `effect` |
| 模板库 | `ressdk_db` | `template` | `artistEffect`、`image` | `高概率` | 下载或打开后更像模板工程实例；部分依赖包也可能在 `artistEffect` |
| 营销模板 | `ressdk_db` | `template` | `artistEffect`、`image` | `高概率` | 和模板库同一套 replicate 体系，本地形态预计一致 |
| 素材包 | `ressdk_db`、`resourcePanel` | `artistEffect` | `effect`、`image`、`template` | `高概率` | 组合型资源最像高层工程包；复杂包可能进一步表现为模板式结构 |

如果只想要一句最实用的判断法，可以直接记成：

```text
音乐 / 音效
看 music

花字 / 贴纸 / 文字模板 / 滤镜 / 转场 / 特效 / 字幕模板 / 素材包
先看 artistEffect
再看 effect

模板库 / 营销模板
先看 template
再看 artistEffect

官方图片 / 官方视频素材
先看 ressdk_db 和 image
真正媒体文件目前仍建议单独做一次下载对照实测
```

## 13. 搜索接口补充（2026-05-13 新增）

说明：
- 本章把新增搜索抓包正式并入总文档。
- 它和前面的“列表接口 / 详情接口 / 下载接口”不是对立关系，而是补充“如何通过搜索入口进入这些链路”。
- 如果后面要做搜索 crawler，优先看这一章。

### 13.1 先说结论

当前新增抓包里的搜索接口，可以稳定分成 4 组：

| 组别 | 主要接口 | 典型样本 | 结果主列表 | 分页字段 | 与本地代码关系 |
|---|---|---|---|---|---|
| 通用素材搜索 | `POST https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/search` | `search.json`、`search-effect.json`、`tiezhi.json` 等 | `data.effect_item_list` | `data.has_more` + `data.next_offset` | 可直接复用现有 `iter_effect_items`、`extract_common_attr`、`get_effect_item_identity` |
| 音乐搜索 | `POST https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/search/songs` | `search-song.json` | `response` 二次解析后的 `songs` | `has_more` + `next_offset` | 可直接复用现有 `iter_song_items` 和 `music.py` 的入库思路 |
| 模板搜索 | `POST https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/search/templates` | `search-muban.json` | `data.template_list` | `data.has_more` + `data.next_cursor` | 结构与现有模板详情链路接近，但当前项目还不能直接复用分页与列表解析 |
| 搜索词推荐 | `POST https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_search_words` | `search-zimumuban.json` | 无素材结果列表 | 无 | 这是联想词接口，不是字幕模板结果列表接口 |

核心结论：

- 大多数“素材搜索”都走 `artist/v1/effect/search`
- `search-song` 是独立音乐搜索接口
- `search-muban` 是独立模板搜索接口
- `search-zimumuban` 当前抓到的只是“字幕模板搜索联想词”，不是“字幕模板搜索结果”

### 13.2 与本地项目的直接映射

#### 13.2.1 已经可以直接复用的公共解析器

本地这些公共函数已经能直接吃掉大部分搜索响应：

- `jianying_crawler/crawlers/common.py`
- `unwrap_response_payload`
  - 对 `search-song.json` 这种“真正结果放在 `response` 字符串里”的情况已经兼容
  - 对 `search-effect.json` 这类“结果直接在 `data` 中”的情况也已经兼容
- `iter_effect_items`
  - 已适配 `effect_item_list`
- `iter_song_items`
  - 已适配 `songs`
- `extract_common_attr`
  - 可直接提取 `common_attr`
- `get_effect_item_identity`
  - 可直接从搜索结果里拿 `resource_id / effect_type / source`

#### 13.2.2 现有 crawler 的复用关系

| 搜索方向 | 抓包样本 | 本地 crawler | 复用程度 | 说明 |
|---|---|---|---|---|
| 音效搜索 | `search-effect.*` | `sound_effect.py` | 高 | 结果就是 `effect_type=3` 的音效项，后续详情仍可走 `mget_item` |
| 花字搜索 | `search-fllower.*` | `flower.py` | 高 | 结果是 `effect_type=1`，结构与现有花字列表一致 |
| 贴纸搜索 | `search-teizhi.saz` + `tiezhi.json` | `sticker.py` | 高 | 结果是 `effect_type=2`，项里有 `sticker` 子对象 |
| 普通特效搜索 | `search-texiao.*` | `effect.py` | 高 | 结果是 `effect_type=7`，项里有 `special_effect` |
| 人物特效搜索 | `search-rengwutexiao.*` | `task_effect.py` / `effect.py` | 中 | 抓包体里没有明显 `panel=face-prop` 之类的区分信息，结构上与普通特效搜索相同 |
| 转场搜索 | `search-zhuanchang.*` | `transition.py` | 高 | 结果是 `effect_type=19` |
| 花字模板搜索 | `search-huazimuban.*` | `text_template.py` | 高 | 结果是 `effect_type=6`，并带 `text_template` 子对象 |
| 滤镜搜索 | `search-lvjing.*` | `filter.py` | 高 | 结果是 `effect_type=12`，并带 `filter` 子对象 |
| 官方素材搜索 | `search.json` | `official_material.py` | 高 | 搜索请求用 `effect_type=201`，但返回项实际混合 `effect_type=5` 和 `9` |
| 音乐搜索 | `search-song.*` | `music.py` | 高 | 字段和现有音乐链路高度一致 |
| 模板搜索 | `search-muban.*` | `template.py` / `marketing_template.py` | 中 | 详情资源字段很像现有模板，但列表字段名和分页字段不同 |
| 字幕模板搜索 | `search-zimumuban.*` | `subtitle_template.py` | 低 | 只抓到联想词接口，没抓到真实结果列表 |

### 13.3 通用素材搜索：`artist/v1/effect/search`

#### 13.3.1 请求模式

接口：

```text
POST https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/search
```

共同特征：

- Query 中仍带完整设备信息、版本信息、`aid=3704`、`channel=jianyingpro_0`、`effect_sdk_version=21.2.0`
- Body 基本长这样：

```json
{
  "app_id": 3704,
  "count": 50,
  "effect_type": 7,
  "offset": 0,
  "query": "心形",
  "search_id": "",
  "need_recommend": false,
  "replicate_sdk_version": "",
  "search_option": {
    "aspect_ratio": "",
    "category_list": [],
    "effect_segment_type": null,
    "filter_uncommercial": false,
    "scene": "",
    "sticker_type": 0
  }
}
```

共同返回结构：

```json
{
  "ret": 0,
  "errmsg": "",
  "data": {
    "effect_item_list": [],
    "has_more": true,
    "next_offset": 50,
    "search_id": "2026...",
    "request_id": "2026...",
    "effect_type": 7,
    "related_words": []
  }
}
```

可以直接下的结论：

- 分页依赖 `next_offset`
- 会返回搜索态的 `search_id`
- 列表项和现有分类抓取里的 `effect_item_list` 基本同构

推断：

- 第二页请求会把首屏返回的 `data.search_id` 回填到下一次请求的 `search_id`
- 贴纸搜索第 2 页样本 `search-tiezhi2.saz` 已经实锤这一点
- 目前仍缺的是：其他搜索类型是否全部严格沿用同一翻页规则

#### 13.3.2 分类样本对照

| 样本 | 请求关键词 | 请求 `effect_type` | `search_option.scene` | 返回项里的核心子对象 | 返回项实际 `effect_type` | 本地建议映射 |
|---|---|---:|---|---|---:|---|
| `search-effect` | `欢呼` | 3 | `""` | `audio_effect` | 3 | `sound_effect` |
| `search-fllower` | `粉色` | 1 | `""` | `word_art` | 1 | `flower` |
| `search-teizhi` / `tiezhi.json` | `春天` | 2 | `""` | `sticker` | 2 | `sticker` |
| `search-texiao` | `心形` | 7 | `""` | `special_effect` | 7 | `effect` |
| `search-rengwutexiao` | `马赛克` | 7 | `""` | `special_effect` | 7 | `task_effect` 或 `effect` |
| `search-zhuanchang` | `旋转` | 19 | `""` | 无专门顶层子对象 | 19 | `transition` |
| `search-huazimuban` | `划重点` | 6 | `vimo_text-template` | `text_template` | 6 | `text_template` |
| `search-zimu` / `search-zimu2.json` | `手写` | 48 | `vimo_subtitle-template` | `subtitle_template` | 48 | `subtitle_template` |
| `search-lvjing` | `天空` | 12 | `""` | `filter` | 12 | `filter` |
| `search.json` | `天空` | 201 | `material_lib_c_v2` | `video` / `image` | 5、9 | `official_material` |

#### 13.3.3 各条链路的关键差异

音效搜索：
- 样本：`search-effect.saz` + `search-effect.json`
- 返回 `data.effect_item_list` 共有 50 条
- 项结构：`author` + `common_attr` + `audio_effect`
- 这条链路最接近现有 `sound_effect.py`

花字搜索：
- 样本：`search-fllower.saz` + `search-fllower.json`
- 返回 `effect_type=1`
- 项结构：`author` + `common_attr` + `word_art`
- 这条链路可直接复用 `flower.py` 的入库和详情补全

贴纸搜索：
- 样本：`search-teizhi.saz` + `tiezhi.json`
- 返回 `effect_type=2`
- 项结构：`author` + `common_attr` + `sticker`
- 与本地 `sticker.py` 的普通贴纸项结构一致

普通特效搜索：
- 样本：`search-texiao.saz` + `search-texiao.json`
- 返回 `effect_type=7`
- 项结构：`author` + `common_attr` + `special_effect`
- 与 `effect.py` 的特效列表项结构一致

人物 / 任务特效相关搜索：
- 老样本：`search-rengwutexiao.saz` + `search-rengwutexiao.json`
- 这组老样本返回 48 条，请求体表现为 `effect_type=7`
- 新增分页样本：
  - `renwutexiao1.saz` / `renwutexiao5.saz`：`effect_type=7` 第 1 / 2 页
  - `renwutexiao2.saz` / `renwutexiao4.saz` / `renwutexiao6.saz`：`effect_type=8` 第 1 / 2 / 3 页
- 两条分支的结果项结构都和普通特效搜索同构，都是 `author + common_attr + special_effect`

这一条现在的结论要更新为：
- 不能再简单视为“只是普通特效搜索的展示口径差异”
- 至少在搜索协议层，`effect_type=7` 和 `effect_type=8` 两条分支都真实存在
- 结合面板与分类在线回放，当前已经可以基本锁定：
  - `effects2` 面板 = 普通特效 = `effect_type=7`
  - `face-prop` 面板 = 人物 / 任务特效 = `effect_type=8`
  - 剩下没法 100% 静态证明的，只是 UI 文案里“人物特效”和“任务特效”是否是同一面板在不同版本下的命名差异

花字模板搜索：
- 样本：`search-huazimuban.saz` + `search-huazimuban.json`
- 请求里最有区分度的字段是：

```json
"effect_type": 6,
"search_option": {
  "scene": "vimo_text-template"
}
```

- 结果项里带 `text_template`
- `common_attr.sdk_extra` 中已经出现 `depend_resource_list`

这意味着：
- 仅靠搜索结果页就能知道它属于组合类文字模板
- 真正要补全子素材，仍建议复用本地 `text_template.py` 的详情与依赖展开逻辑

字幕模板搜索：
- 样本：`search-zimu.saz` + `search-zimu2.json`
- 请求里最有区分度的字段是：

```json
"effect_type": 48,
"search_option": {
  "scene": "vimo_subtitle-template"
}
```

- 结果项结构：
  - `author`
  - `common_attr`
  - `subtitle_template`
- `common_attr.sdk_extra` 中已经能看到 `depend_resource_list`

这说明：
- 字幕模板真实搜索结果页已经抓到了
- 它不是 `get_search_words`
- 它在协议层和花字模板搜索非常接近，只是 `effect_type` 和 `scene` 不同
- 后续依赖展开建议直接复用本地 `subtitle_template.py`

滤镜搜索：
- 样本：`search-lvjing.saz` + `search-lvjing.json`
- 返回 `effect_type=12`
- 项结构：`author` + `common_attr` + `filter`
- 与本地 `filter.py` 对应得很稳

官方素材搜索：
- 样本：`search.saz` + `search.json`
- 请求层是：

```json
"effect_type": 201,
"search_option": {
  "scene": "material_lib_c_v2"
}
```

- 但返回结果不是单一 `effect_type=201`
- 样本里实际返回：
  - `effect_type=5` 共 44 条
  - `effect_type=9` 共 5 条
- 结果项里会出现：
  - 视频素材：`video`
  - 图片素材：`image`

这说明：
- `201` 更像“素材库综合搜索域”而不是最终素材类型
- 本地最适合映射到 `official_material.py`
- 搜索结果可以直接沿用 `official_material.py` 里对 `video.origin_video`、`video.transcoded_video`、`download_info.url` 的下载链接提取思路

### 13.4 音乐搜索：`lv/v1/search/songs`

接口：

```text
POST https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/search/songs
```

样本：
- `search-song.saz`
- `search-song.json`

请求体：

```json
{
  "count": 50,
  "filter_paid_type": [],
  "keyword": "安静",
  "offset": 0,
  "scene": 0
}
```

结构特征：
- 顶层虽然有 `data`
- 但真正完整结果还会被塞进顶层字符串字段 `response`
- 本地 `unwrap_response_payload` 已能自动二次 JSON 解析

主要字段：

| 字段 | 说明 |
|---|---|
| `songs` | 主结果列表 |
| `has_more` | 是否还有下一页 |
| `next_offset` | 下一页偏移 |
| `search_id` | 搜索会话 ID |
| `source` | 当前样本值为 `search` |

单项字段与本地 `music.py` 的对齐度很高：

- `id` / `web_id`
- `title`
- `author`
- `preview_url`
- `cover_url`
- `beats`
- `business_info`
- `strategy_info`

当前结论：
- 音乐搜索几乎可以直接复用 `music.py` 的入库、去重、下载链接登记逻辑
- 这条链路和 `sound_effect` 不应混成一种搜索实现

### 13.5 模板搜索：`pc/search/templates`

接口：

```text
POST https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/search/templates
```

样本：
- `search-muban.saz`
- `search-muban.json`

请求体：

```json
{
  "channels": ["lv_template"],
  "count": 32,
  "cursor": 0,
  "extra": null,
  "filter_paid_template": false,
  "filters": {
    "duration": [],
    "fragment_count": [],
    "screen_style": ["landscape", "portrait"],
    "sub_category_ids": []
  },
  "keyword": "当年",
  "search_entrance": "pc_edit_page",
  "search_id": "",
  "search_source": "input",
  "sort_type": 0
}
```

响应主结构：

| 字段 | 说明 |
|---|---|
| `data.template_list` | 模板搜索结果列表 |
| `data.has_more` | 是否还有下一页 |
| `data.next_cursor` | 下一页 cursor，当前样本值是字符串 `"32"` |
| `data.search_id` | 搜索会话 ID |
| `data.channel` | 当前样本值为 `lv_template` |
| `data.filter_options` | 模板搜索筛选选项 |

和现有模板链路的关系：
- 结果项字段和 `template.py` / `marketing_template.py` 里的详情字段非常像
- 搜索结果里已经能直接看到：
  - `template_url`
  - `video_url`
  - `draft_package_url`
  - `template_json`
  - `origin_video_info`

这意味着模板搜索不一定要先跑 collection 才能拿下载链接。

但当前代码还不能直接无改动复用，原因有两个：

1. 本地 `iter_template_items` 只认：
   - `item_list`
   - `templates`
2. 本地 `get_new_cursor` 只认：
   - `new_cursor`

而模板搜索实际是：
- 列表字段：`template_list`
- 分页字段：`next_cursor`

所以模板搜索如果要接进项目，最少要补：
- 一个模板搜索专用列表解析器，或扩展 `iter_template_items`
- 一个能读取 `next_cursor` 的分页辅助函数

补充判断：
- 本次新增抓包只明确抓到了 `channels=["lv_template"]`
- 没有单独抓到 `marketing_template` 搜索请求
- 但从现有模板体系看，营销模板搜索很可能仍是同一接口族，只是 `channels`、筛选项或入口字段不同
- 这一句属于结构推断，不是本次抓包实锤

在线回放实测补充（2026-05-13）：
- 直接用普通 `post_json` 去打 `pc/search/templates`，会返回 `ret=1014`、`errmsg=system busy`
- 改用 replicate 风格请求头和签名后，`channels=["lv_template"]` 可以稳定返回结果
- 同样改用 replicate 风格请求头后：
  - `channels=["lv_marketing_template"]` 返回成功，但 `template_list=[]`
  - `channels=["marketing_template"]` 返回成功，但 `template_list=[]`
  - `channels=["lv_template","lv_marketing_template"]` 的结果仍等价于 `lv_template`
- 并且服务端返回的 `data.channel` 始终是 `lv_template`

这说明当前更稳的结论是：
- 模板搜索接口本身已经在线打通
- 它需要 replicate 体系请求头，而不是普通素材接口请求头
- 当前没有证据支持“营销模板存在独立搜索 channel”
- 更像是：模板搜索统一收敛到 `lv_template` 域，营销模板至少在这个搜索入口上没有表现出独立分支

### 13.6 字幕模板：当前只抓到联想词，不是结果页

接口：

```text
POST https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_search_words
```

样本：
- `search-zimumuban.saz`
- `search-zimumuban.json`

请求体：

```json
{
  "app_id": 3704,
  "effect_type": 48
}
```

响应里只有这些内容：
- `default_word`
- `recommend_words`
- `hot_words`
- `grey_words`
- `word_source`
- `task_id`

当前结论：
- 这不是字幕模板结果接口
- 这是搜索框推荐词 / 热词接口
- 它和本地 `subtitle_template.py` 的实际素材抓取链路不是一回事

目前能确认的是：
- `effect_type=48` 仍然对应字幕模板域
- 但现在已经有新的补抓样本证明：字幕模板真实搜索结果页实际走的是 `artist/v1/effect/search`

### 13.7 对本地项目的落地建议

如果后面把搜索能力接进当前项目，优先级建议是：

1. 先接通 `artist/v1/effect/search`
   - 一次就能覆盖音效、花字、贴纸、普通特效、转场、滤镜、花字模板、官方素材
   - 这些都能大量复用现有 `effect_item_list` 解析与详情补全逻辑
2. 再接 `search/songs`
   - 与 `music.py` 高度一致
3. 再接 `pc/search/templates`
   - 需要补模板搜索专用分页与列表适配
4. 最后补 `get_search_words`
   - 这是前端辅助接口，不是主抓取链路

补充说明：以上是当时的接入优先级建议。结合 2026-05-13 当前代码状态，这一层现在已经有了实际落地版本：

- 新增 `jianying_crawler/search_service.py`
- 新增 CLI 命令：
  - `python -m jianying_crawler.cli search <关键词>`
- 当前实际策略：
  - 先实时调用剪映搜索接口
  - 如果实时结果为空，再回退本地 SQLite / PostgreSQL
  - 如果传 `--downloaded-only`，则直接查本地库
- 当前已接入实时搜索的链路：
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
- 当前仍未接入实时搜索的：
  - `material_pack`
  - `get_search_words` 联想词接口未并入主搜索流程

### 13.8 这批新增搜索抓包里，哪些还没有完全跑透

当前仍然缺的点：

- UI 名称到搜索协议分支的精确映射还没最终锁定
  - 目前已经确认 `effect_type=7` 和 `effect_type=8` 两条人物 / 任务相关搜索分支都存在
  - 但还需要最终确认 UI 上“人物特效”“任务特效”“普通特效”各自对应哪条
- 营销模板独立搜索入口已经可以视为排除
  - 最新 `yingxiao.saz` 真实搜索样本仍是 `pc/search/templates` + `channels=["lv_template"]`
  - 在线回放 `lv_marketing_template` / `marketing_template` 仍为空
  - 结合你的确认，可以收口为“营销模板没有其他独立搜索入口”

### 13.9 在线回放实测结果（2026-05-13 新增）

#### 13.9.1 搜索翻页：已在线验证 3 类

我已经在线验证以下 3 类搜索都能正常翻到第 2 页，并且都会回填首屏 `search_id`：

- 贴纸搜索
  - `effect_type=2`
  - 关键词：`春天`
- 字幕模板搜索
  - `effect_type=48`
  - `scene=vimo_subtitle-template`
  - 关键词：`手写`
- 花字模板搜索
  - `effect_type=6`
  - `scene=vimo_text-template`
  - 关键词：`划重点`

当前结论：
- `effect/search` 这套搜索翻页机制已经可以稳定视为：
  - 首屏 `search_id=""`
  - 翻页时带回首屏返回的 `search_id`
  - 同时推进 `offset -> next_offset`

#### 13.9.2 模板搜索：已在线打通

我已经在线验证：

- `pc/search/templates` 可以打通
- 但要使用 replicate 体系请求头和签名
- 不能直接套普通 `post_json` 的请求头

当前结论：
- 模板搜索不是“接口没跑通”
- 而是“请求体系和普通素材搜索不同”

#### 13.9.3 营销模板搜索：最新真实样本仍回到 `lv_template`

最新这份 `E:/sucai/crawler_project/fiddler-v2rayn-10808/yingxiao.saz` 我已经拆开确认：

- 请求接口：`pc/search/templates`
- 关键词：`中秋`
- 请求体里的 `channels=["lv_template"]`
- 响应里的 `data.channel="lv_template"`
- 同时返回 `template_list`、`next_cursor`、`search_id`、`filter_options`

我另外在线尝试了这些 `channels`：

- `["lv_template"]`
- `["lv_marketing_template"]`
- `["marketing_template"]`
- `["lv_template","lv_marketing_template"]`

当前结果：

- 只有 `lv_template` 稳定返回结果
- 后 3 种都不会跑出独立营销模板结果
- 服务端返回的 `data.channel` 始终是 `lv_template`

当前结论：
- 营销模板搜索没有独立 search channel
- 最新真实抓包进一步说明：营销入口直接复用 `lv_template`

#### 13.9.4 人物 / 任务特效搜索：已确认 `effect_type=7 / 8` 双分支

新增抓包已经把这条线补得很清楚：

- `renwutexiao1.saz`：`effect_type=7`，第 1 页，`offset=0`
- `renwutexiao5.saz`：`effect_type=7`，第 2 页，`offset=50`，回填同一个 `search_id`
- `renwutexiao2.saz`：`effect_type=8`，第 1 页，`offset=0`
- `renwutexiao4.saz`：`effect_type=8`，第 2 页，`offset=50`
- `renwutexiao6.saz`：`effect_type=8`，第 3 页，`offset=100`

我也在线回放确认了 `effect_type=8`：

- 第 1 页返回 `effect_type=8`、`next_offset=50`
- 第 2 页继续返回 `effect_type=8`、`next_offset=100`
- 第 3 页继续返回 `effect_type=8`、`next_offset=150`
- 三页都沿用同一个 `search_id`

结合此前的手工对比：

- `effect_type=7` + `scene=""` 和 `scene="face-prop"` 仍无差异
- 强行给 `effect_type=7` 传 `category_list=[38389]` 仍是空结果

当前结论：

- 此前“只是展示口径差异”的结论已经不够用了
- 至少在搜索协议层，`effect_type=7` 和 `effect_type=8` 两条人物 / 任务相关搜索分支都真实存在
- 我又在线对照了面板和分类列表：
  - `get_panel_info(panel="effects2")` 返回普通特效分类，如 `热门 / 基础 / 动感 / 氛围 / 多屏`
  - `get_resources_by_category_id(panel="effects2", category_id=39654, category_key="rm")` 返回项全部是 `effect_type=7`
  - `get_panel_info(panel="face-prop")` 返回人物向分类，如 `热门 / 情绪 / 身体 / 挡脸 / 头饰 / 手部 / 形象 / 环绕 / 表情`
  - `get_resources_by_category_id(panel="face-prop", category_id=38389, category_key="hot")` 返回项全部是 `effect_type=8`
- 因此当前已经可以基本锁定：
  - 普通特效 UI 面板对应 `effects2` / `effect_type=7`
  - 人物 / 任务特效 UI 面板对应 `face-prop` / `effect_type=8`
  - 唯一还不能百分百静态证明的，是“人物特效”和“任务特效”这两个中文名是否只是同一面板在不同版本或不同入口下的命名差异
