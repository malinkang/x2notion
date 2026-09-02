from __future__ import annotations

import json
import os
import sys
from typing import Any, Mapping

from .client import XClient
from .errors import XAuthError, XError
from .media import download_post_media
from .models import XFeedType, XPost
from .normalize import normalize_tweet
from .notion_writer import XNotionWriter


def _get_first(source: Mapping[str, str], *names: str) -> str:
    for name in names:
        val = str(source.get(name) or "").strip()
        if val:
            return val
    return ""


def run(env: Mapping[str, str] | None = None, *, client: Any = None, writer: Any = None) -> dict[str, Any]:
    source = env or os.environ

    notion_token = _get_first(source, "NOTION_TOKEN", "NOTION_API_KEY")
    posts_ds = _get_first(source, "X_POSTS_DATA_SOURCE_ID", "POSTS_DATA_SOURCE_ID", "X_DATA_SOURCE_ID")
    authors_ds = _get_first(source, "X_AUTHORS_DATA_SOURCE_ID", "AUTHORS_DATA_SOURCE_ID", "AUTHOR_DATA_SOURCE_ID")
    tag_ds = _get_first(source, "X_TAG_DATA_SOURCE_ID", "TAG_DATA_SOURCE_ID", "TAGS_DATA_SOURCE_ID")

    auth_token = _get_first(source, "X_AUTH_TOKEN", "AUTH_TOKEN")
    csrf_token = _get_first(source, "X_CT0", "CT0", "CSRF_TOKEN")
    user_id = _get_first(source, "X_TWID", "TWID", "X_USER_ID", "USER_ID")

    sync_mode = _get_first(source, "SYNC_MODE", "REQUESTED_SYNC_MODE").lower() or "incremental"
    streams_str = _get_first(source, "SYNC_STREAMS", "X_SYNC_STREAMS") or "posted,liked,bookmark"
    streams = [s.strip().lower() for s in streams_str.split(",") if s.strip()]
    download_media = _get_first(source, "DOWNLOAD_MEDIA", "X_DOWNLOAD_MEDIA").lower() in ("true", "1", "yes")

    if not notion_token:
        raise XError("缺少 NOTION_TOKEN。")
    if not posts_ds:
        raise XError("缺少 POSTS_DATA_SOURCE_ID 或 X_DATA_SOURCE_ID。")

    x_client = client or XClient(
        auth_token=auth_token,
        csrf_token=csrf_token,
        user_id=user_id,
        proxy=_get_first(source, "HTTPS_PROXY", "TWIKIT_PROXY"),
    )
    notion_writer = writer or XNotionWriter(
        notion_token=notion_token,
        posts_data_source_id=posts_ds,
        relation_data_sources={"authors": authors_ds, "tag": tag_ds},
    )

    max_pages = 10 if sync_mode == "full" else 2
    post_map: dict[str, XPost] = {}

    print(f"[*] 开始 X 同步 (模式: {sync_mode}, 流: {streams})...")

    if "posted" in streams:
        try:
            print("[*] 正在获取本人发布推文...")
            posted_raw = x_client.get_user_tweets(user_id=user_id, count=20, max_pages=max_pages)
            for raw in posted_raw:
                post = normalize_tweet(raw, feed_type="posted")
                if post:
                    if post.post_id in post_map:
                        if "posted" not in post_map[post.post_id].feed_types:
                            post_map[post.post_id].feed_types.append("posted")
                    else:
                        post_map[post.post_id] = post
            print(f"[+] 获取到 {len(posted_raw)} 条本人发布推文。")
        except Exception as e:
            print(f"[!] 获取本人发布推文失败: {e}", file=sys.stderr)

    if "liked" in streams:
        try:
            print("[*] 正在获取我的喜欢推文...")
            liked_raw = x_client.get_user_likes(user_id=user_id, count=20, max_pages=max_pages)
            for raw in liked_raw:
                post = normalize_tweet(raw, feed_type="liked")
                if post:
                    if post.post_id in post_map:
                        if "liked" not in post_map[post.post_id].feed_types:
                            post_map[post.post_id].feed_types.append("liked")
                    else:
                        post_map[post.post_id] = post
            print(f"[+] 获取到 {len(liked_raw)} 条喜欢推文。")
        except Exception as e:
            print(f"[!] 获取喜欢推文失败: {e}", file=sys.stderr)

    if "bookmark" in streams:
        try:
            print("[*] 正在获取我的书签推文...")
            bookmarks_raw = x_client.get_bookmarks(count=20, max_pages=max_pages)
            for raw in bookmarks_raw:
                post = normalize_tweet(raw, feed_type="bookmark")
                if post:
                    if post.post_id in post_map:
                        if "bookmark" not in post_map[post.post_id].feed_types:
                            post_map[post.post_id].feed_types.append("bookmark")
                    else:
                        post_map[post.post_id] = post
            print(f"[+] 获取到 {len(bookmarks_raw)} 条书签推文。")
        except Exception as e:
            print(f"[!] 获取书签推文失败: {e}", file=sys.stderr)

    all_posts = list(post_map.values())
    print(f"[*] 去重合并后共有 {len(all_posts)} 条推文待同步至 Notion。")

    if download_media and all_posts:
        print("[*] 正在下载多媒体资源...")
        download_post_media(all_posts)

    created_count = 0
    updated_count = 0
    failed_count = 0

    for idx, post in enumerate(all_posts, 1):
        try:
            res = notion_writer.write_post(post)
            action = res.get("action", "created")
            if action == "created":
                created_count += 1
            else:
                updated_count += 1
            print(f"  [{idx}/{len(all_posts)}] [{action.upper()}] {post.post_id} - {post.author.name}: {post.text[:30]}...")
        except Exception as e:
            failed_count += 1
            print(f"  [{idx}/{len(all_posts)}] [FAIL] {post.post_id} 写入失败: {e}", file=sys.stderr)

    summary = {
        "status": "success" if failed_count == 0 else "partial",
        "total": len(all_posts),
        "created": created_count,
        "updated": updated_count,
        "failed": failed_count,
    }
    print(f"[✓] 同步结束: 新建 {created_count}, 更新 {updated_count}, 失败 {failed_count}")
    return summary


def cli() -> None:
    try:
        run()
    except Exception as e:
        print(f"[x2notion ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
