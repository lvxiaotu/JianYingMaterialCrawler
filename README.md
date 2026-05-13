# JianYing Material Crawler

这是一个围绕剪映素材接口的爬虫项目，当前已经具备：

- 统一管理配置、请求头、Cookie 和存储目录
- 支持元数据抓取、详情补全、下载任务入库
- 支持断点续跑
- 支持从 SQLite 迁移到 PostgreSQL
- 支持本地 Web 控制台
- 支持 `crawl` / `download` 请求日志实时查看

## 默认存储目录

- `E:\sucai`

默认会在该目录下生成：

- `raw`
  - 仅在解析失败或接口异常时保存原始响应
- `meta`
  - 元数据和辅助信息
- `downloads`
  - 下载到本地的素材文件
- `logs`
  - 下载日志、请求日志
- `state`
  - 数据库、状态文件
- `structure`
  - 资源结构报告

## 数据库模式

项目支持两种数据库后端。

1. SQLite
   - 使用 `config/settings.json` 里的 `database_path`
   - 适合单机、单进程、轻并发调试

2. PostgreSQL
   - 使用 `config/settings.json` 里的 `database_url`
   - 或环境变量 `JY_DATABASE_URL`
   - 推荐用于长期跑全量、增量和更稳定的数据管理

示例：

```json
{
  "database_path": "E:\\sucai\\state\\crawler.db",
  "database_url": "postgresql://postgres:postgres@127.0.0.1:5432/jianying_crawler"
}
```

当 `database_url` 非空时，程序优先使用 PostgreSQL。

## 安装与启动

1. 安装依赖

```powershell
pip install -r requirements.txt
```

2. 启动 Web 控制台

```powershell
python -m jianying_crawler.webapp
```

默认打开：

- [http://127.0.0.1:8765](http://127.0.0.1:8765)

3. 初始化数据库

```powershell
python -m jianying_crawler.cli init-db
```

4. 如果要把已有 SQLite 数据迁移到 PostgreSQL

先配置好 `database_url`，再执行：

```powershell
python -m jianying_crawler.cli migrate-sqlite
```

如果 SQLite 文件不在默认位置：

```powershell
python -m jianying_crawler.cli migrate-sqlite --sqlite-path E:\sucai\state\crawler.db
```

## Web 控制台

控制台现在包含这些分栏：

- `总览`
  - 查看全局抓取、下载、待下载统计
- `命令执行`
  - 使用下拉分类选择命令
  - 自动展示命令说明
  - 自动填充到命令输入框
- `任务输出`
  - 查看最近 CLI 任务输出
- `实时请求`
  - 实时查看 `crawl` 和 `download` 请求日志
- `链路状态`
  - 查看每条链路的 items、downloads、pending、分页状态
- `配置认证`
  - 修改 Cookie、签名和完整配置 JSON

### 命令来源说明

控制台中的命令预设不再只依赖 `README` 示例，而是由两部分合并生成：

1. 项目内置默认命令
   - 包括数据库命令
   - 包括全部已接入 crawler 的抓取命令
   - 包括全部已接入 crawler 的下载命令

2. `README` 中显式写出的命令示例

因此，只要某条 crawler 已经接入 `CRAWLER_MAP`，它就会自动出现在控制台命令下拉里。

## 抓取链路

当前已接入的抓取链路：

```text
effect
filter
flower
marketing_template
material_pack
music
official_material
sound_effect
sticker
subtitle_template
task_effect
template
text_template
transition
```

对应抓取命令：

```powershell
python -m jianying_crawler.cli crawl effect
python -m jianying_crawler.cli crawl filter
python -m jianying_crawler.cli crawl flower
python -m jianying_crawler.cli crawl marketing_template
python -m jianying_crawler.cli crawl material_pack
python -m jianying_crawler.cli crawl music
python -m jianying_crawler.cli crawl official_material
python -m jianying_crawler.cli crawl sound_effect
python -m jianying_crawler.cli crawl sticker
python -m jianying_crawler.cli crawl subtitle_template
python -m jianying_crawler.cli crawl task_effect
python -m jianying_crawler.cli crawl template
python -m jianying_crawler.cli crawl text_template
python -m jianying_crawler.cli crawl transition
```

## 下载命令

### 下载前说明

- 下载默认目录是 `E:\sucai\downloads`
- 下载日志目录是 `E:\sucai\logs\downloads`
- 统一请求日志目录是 `E:\sucai\logs\requests`
- 下载间隔默认读取 `config/settings.json` 里的 `download_interval_seconds`
- `--limit` 表示每一批最多处理多少条下载记录，不是页数
- 不加 `--until-empty` 时，只跑一批
- 加上 `--until-empty` 时，会一直跑到当前链路没有待下载资源为止
- 模板类链路如果要连依赖资源一起下载，需要额外加 `--include-auxiliary`

### 清理重复下载记录

这条命令清理的是数据库里的重复下载记录，不会删除磁盘上已经存在的文件：

```powershell
python -m jianying_crawler.cli cleanup-downloads
```

### 单批下载示例

```powershell
python -m jianying_crawler.cli download sound_effect --limit 50
python -m jianying_crawler.cli download music --limit 50
python -m jianying_crawler.cli download effect --limit 50
```

### 一条命令跑到当前链路清空

```powershell
python -m jianying_crawler.cli download sound_effect --limit 50 --until-empty
python -m jianying_crawler.cli download music --limit 50 --until-empty
python -m jianying_crawler.cli download effect --limit 50 --until-empty
```

### 全部主链路下载命令

这些命令默认只下载主资源：

```powershell
python -m jianying_crawler.cli download effect --limit 50 --until-empty
python -m jianying_crawler.cli download filter --limit 50 --until-empty
python -m jianying_crawler.cli download flower --limit 50 --until-empty
python -m jianying_crawler.cli download marketing_template --limit 50 --until-empty
python -m jianying_crawler.cli download material_pack --limit 50 --until-empty
python -m jianying_crawler.cli download music --limit 50 --until-empty
python -m jianying_crawler.cli download official_material --limit 50 --until-empty
python -m jianying_crawler.cli download sound_effect --limit 50 --until-empty
python -m jianying_crawler.cli download sticker --limit 50 --until-empty
python -m jianying_crawler.cli download subtitle_template --limit 50 --until-empty
python -m jianying_crawler.cli download task_effect --limit 50 --until-empty
python -m jianying_crawler.cli download template --limit 50 --until-empty
python -m jianying_crawler.cli download text_template --limit 50 --until-empty
python -m jianying_crawler.cli download transition --limit 50 --until-empty
```

### 模板和组合链路下载全部资源

下面这些链路如果要把依赖资源一起下载，要加 `--include-auxiliary`：

```powershell
python -m jianying_crawler.cli download marketing_template --limit 50 --include-auxiliary --until-empty
python -m jianying_crawler.cli download material_pack --limit 50 --include-auxiliary --until-empty
python -m jianying_crawler.cli download subtitle_template --limit 50 --include-auxiliary --until-empty
python -m jianying_crawler.cli download template --limit 50 --include-auxiliary --until-empty
python -m jianying_crawler.cli download text_template --limit 50 --include-auxiliary --until-empty
```

### 临时覆盖下载间隔

如果只想针对某一次下载临时改间隔，可以手动覆盖：

```powershell
python -m jianying_crawler.cli download sound_effect --limit 50 --until-empty --interval-seconds 1.0
python -m jianying_crawler.cli download sound_effect --limit 50 --until-empty --interval-seconds 2.0
python -m jianying_crawler.cli download sound_effect --limit 50 --until-empty --interval-seconds 0
```

## 请求日志

项目现在支持统一请求日志。

### 覆盖范围

- `crawl` 阶段接口请求
- `download` 阶段资源请求
- 解析失败时的异常响应

### 日志目录

- `E:\sucai\logs\requests\crawl\_all`
- `E:\sucai\logs\requests\crawl\<crawler_name>`
- `E:\sucai\logs\requests\download\_all`
- `E:\sucai\logs\requests\download\<crawler_name>`

### Web 接口

控制台内部会调用：

```text
/api/request-logs?scope=all&crawler=_all&limit=120
```

支持参数：

- `scope`
  - `all`
  - `crawl`
  - `download`
- `crawler`
  - `_all`
  - 或具体 crawler 名称
- `limit`
  - 返回最近多少条日志

## 原始响应保存策略

当前策略已经调整为：

- 请求成功并可正常解析时，不保存 `raw`
- 只有在解析失败或接口异常时，才保存原始响应到 `raw`

这样可以避免正常抓取时大量写入 JSON 文件。

## 当前覆盖

当前已覆盖：

- 推荐音乐 / BGM
- 音效
- 花字
- 文字模板
- 贴纸
- 普通特效
- 任务特效
- 官方素材
- 转场
- 字幕模板
- 滤镜
- 模板库
- 营销模板
- 素材包

## 注意

- 当前项目默认不内置签名算法
- 你需要先在配置页里填入可用的 Cookie 和常用 Header
- 某些接口的 `sign`、`x-ss-stub`、`X-Helios`、`X-Medusa` 仍可能需要按抓包更新
- PostgreSQL 已经接入，但你本机仍需要准备数据库服务本体
