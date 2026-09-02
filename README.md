# x2notion: X (Twitter) to Notion Synchronization Runner

基于 [`twikit`](https://github.com/d60/twikit) 的 X（Twitter）推文、喜欢和书签同步到 Notion 的 Python Runner。

## 功能特性

1. **多数据流支持**：
   - 本人发布与回复（`posted`）
   - 我的喜欢列表（`liked`）
   - 我的书签列表（`bookmark`）
2. **多媒体下载与持久化**：
   - 自动提取并下载高清图片（`pbs.twimg.com`）和最高码率 MP4 视频（`video.twimg.com`）。
3. **富文本与关系建模**：
   - 展开 `t.co` 压缩短链为原始 URL。
   - 提取长推文（Note Tweet）、话题标签、引用（Quote Tweet）与回复链。
   - 自动在 Notion 模板中关联作者库、标签库、日期库与资源库。
4. **幂等写入与更新**：
   - 自动比对 `Post ID`，已同步推文仅更新属性，不重复建页。

## 环境变量配置

| 变量名 | 说明 | 必填 |
| :--- | :--- | :---: |
| `NOTION_TOKEN` | Notion API Integration Token | 是 |
| `X_POSTS_DATA_SOURCE_ID` | Notion 帖子数据库 ID | 是 |
| `X_AUTHORS_DATA_SOURCE_ID` | Notion 作者数据库 ID | 否 |
| `X_TAG_DATA_SOURCE_ID` | Notion 标签数据库 ID | 否 |
| `X_AUTH_TOKEN` | X 网页登录 Cookie `auth_token` | 是 |
| `X_CT0` | X 网页 CSRF Token `ct0` | 是 |
| `X_TWID` | X 数字用户 ID `u=...` | 是 |
| `SYNC_MODE` | 同步模式 (`incremental` / `full`) | 否 (默认 `incremental`) |
| `SYNC_STREAMS` | 同步流 (`posted,liked,bookmark`) | 否 (默认全部) |
| `DOWNLOAD_MEDIA` | 是否下载媒体资源 (`true` / `false`) | 否 (默认 `false`) |
| `HTTPS_PROXY` | 代理地址 (如 `http://127.0.0.1:7890`) | 否 |

## 本地测试与运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行单元测试
PYTHONPATH=. python -m unittest discover -s tests

# 执行同步
PYTHONPATH=. python -m x2notion.sync
```
