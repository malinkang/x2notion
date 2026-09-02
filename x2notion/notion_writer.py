from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

try:
    from notion_client import Client as NotionClient
    from notion_client.errors import APIResponseError
except ImportError:
    NotionClient = None  # type: ignore
    APIResponseError = Exception  # type: ignore

from .errors import XError, XSchemaError
from .models import XAuthor, XMedia, XPost

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _rich(text: str, size: int = 1800) -> list[dict[str, Any]]:
    value = str(text or "")
    if not value:
        return [{"type": "text", "text": {"content": ""}}]
    return [
        {"type": "text", "text": {"content": value[i : i + size]}}
        for i in range(0, len(value), size)
    ]


def _paragraph(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich(text)}}


class XNotionWriter:
    """Writes normalized X posts to Notion database adhering to NotionHub template contracts."""

    def __init__(
        self,
        notion_token: str,
        posts_data_source_id: str,
        relation_data_sources: Mapping[str, str] | None = None,
    ) -> None:
        self.notion_token = str(notion_token or "").strip()
        self.posts_data_source_id = str(posts_data_source_id or "").strip()
        self.relations = dict(relation_data_sources or {})
        self._authors_ds = self.relations.get("authors") or self.relations.get("author") or ""
        self._tag_ds = self.relations.get("tag") or self.relations.get("tags") or ""
        self._resources_ds = self.relations.get("resources") or self.relations.get("resource") or ""
        self._day_ds = self.relations.get("day") or ""
        self._month_ds = self.relations.get("month") or ""
        self._year_ds = self.relations.get("year") or ""

        if not self.notion_token:
            raise XError("缺少 NOTION_TOKEN。")
        if not self.posts_data_source_id:
            raise XError("缺少 POSTS_DATA_SOURCE_ID 或 X_DATA_SOURCE_ID。")

        if NotionClient is None:
            self._client = None
        else:
            self._client = NotionClient(auth=self.notion_token)

        self._posts_schema: dict[str, Any] | None = None
        self._authors_schema: dict[str, Any] | None = None
        self._author_cache: dict[str, str] = {}
        self._tag_cache: dict[str, str] = {}
        self._resource_cache: dict[str, str] = {}
        self._date_cache: dict[str, str] = {}

    def _ensure_client(self) -> Any:
        if self._client is None:
            raise XError("notion-client 依赖未安装，请执行 pip install notion-client>=3.0.0。")
        return self._client

    def _get_schema(self, data_source_id: str) -> dict[str, Any]:
        client = self._ensure_client()
        try:
            return client.databases.retrieve(database_id=data_source_id)
        except Exception:
            return {}

    def _query_first(self, data_source_id: str, property_name: str, property_type: str, value: str) -> str | None:
        if not data_source_id or not value:
            return None
        client = self._ensure_client()
        try:
            filter_payload: dict[str, Any] = {}
            if property_type == "rich_text":
                filter_payload = {"property": property_name, "rich_text": {"equals": value}}
            elif property_type == "title":
                filter_payload = {"property": property_name, "title": {"equals": value}}
            elif property_type == "url":
                filter_payload = {"property": property_name, "url": {"equals": value}}
            
            res = client.databases.query(database_id=data_source_id, filter=filter_payload, page_size=1)
            results = res.get("results", [])
            if results:
                return results[0].get("id")
        except Exception:
            pass
        return None

    def upsert_author(self, author: XAuthor) -> str | None:
        if not self._authors_ds or not author.handle:
            return None
        cache_key = author.handle.lower()
        if cache_key in self._author_cache:
            return self._author_cache[cache_key]

        page_id = self._query_first(self._authors_ds, "Handle", "rich_text", author.handle) or \
                  self._query_first(self._authors_ds, "用户名", "rich_text", author.handle)
        
        if not page_id:
            client = self._ensure_client()
            props = {
                "标题": {"title": _rich(author.name or author.handle)},
                "Handle": {"rich_text": _rich(author.handle)},
            }
            if author.profile_url:
                props["主页"] = {"url": author.profile_url}
            try:
                page = client.pages.create(
                    parent={"database_id": self._authors_ds},
                    properties=props,
                )
                page_id = page.get("id")
            except Exception:
                pass

        if page_id:
            self._author_cache[cache_key] = page_id
        return page_id

    def upsert_tag(self, tag_name: str) -> str | None:
        if not self._tag_ds or not tag_name:
            return None
        if tag_name in self._tag_cache:
            return self._tag_cache[tag_name]

        page_id = self._query_first(self._tag_ds, "标题", "title", tag_name) or \
                  self._query_first(self._tag_ds, "Name", "title", tag_name)
        
        if not page_id:
            client = self._ensure_client()
            try:
                page = client.pages.create(
                    parent={"database_id": self._tag_ds},
                    properties={"标题": {"title": _rich(tag_name)}},
                )
                page_id = page.get("id")
            except Exception:
                pass

        if page_id:
            self._tag_cache[tag_name] = page_id
        return page_id

    def write_post(self, post: XPost) -> dict[str, Any]:
        client = self._ensure_client()

        # Check existing by Post ID
        existing_page_id = self._query_first(self.posts_data_source_id, "Post ID", "rich_text", post.post_id) or \
                            self._query_first(self.posts_data_source_id, "帖子 ID", "rich_text", post.post_id)

        author_page_id = self.upsert_author(post.author)
        tag_page_ids = [pid for tag in post.tags if (pid := self.upsert_tag(tag))]

        feed_type_labels = {
            "posted": "本人发布",
            "liked": "喜欢",
            "bookmark": "书签",
        }
        feed_types_selected = [{"name": feed_type_labels.get(ft, ft)} for ft in post.feed_types]

        properties: dict[str, Any] = {
            "Post ID": {"rich_text": _rich(post.post_id)},
            "原文链接": {"url": post.url},
            "来源": {"select": {"name": "X"}},
            "收录类型": {"multi_select": feed_types_selected},
            "帖子类型": {"select": {"name": post.post_type}},
            "最后同步时间": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        }

        if post.created_at:
            properties["发布时间"] = {"date": {"start": post.created_at}}

        if author_page_id:
            properties["作者"] = {"relation": [{"id": author_page_id}]}

        if tag_page_ids and not existing_page_id:
            properties["标签"] = {"relation": [{"id": pid} for pid in tag_page_ids]}

        # Build blocks
        title_text = (post.text.split("\n")[0].strip() or f"{post.author.name} 的帖子")[:80]
        properties["标题"] = {"title": _rich(title_text)}

        blocks: list[dict[str, Any]] = []
        if post.text:
            for para in re.split(r"\n{2,}", post.text):
                if para.strip():
                    blocks.append(_paragraph(para.strip()))

        blocks.append({"object": "block", "type": "bookmark", "bookmark": {"url": post.url}})

        if post.quote and post.quote.url:
            blocks.append({
                "object": "block",
                "type": "bookmark",
                "bookmark": {"url": post.quote.url, "caption": _rich(f"引用 @{post.quote.handle}: {post.quote.text[:100]}")}
            })

        for media in post.media[:10]:
            if media.kind == "photo" and media.url:
                blocks.append({
                    "object": "block",
                    "type": "image",
                    "image": {"type": "external", "external": {"url": media.url}}
                })
            elif media.kind == "video" and media.url:
                blocks.append({
                    "object": "block",
                    "type": "bookmark",
                    "bookmark": {"url": media.url, "caption": _rich("视频直链")}
                })

        if existing_page_id:
            client.pages.update(page_id=existing_page_id, properties=properties)
            return {"page_id": existing_page_id, "action": "updated", "post_id": post.post_id}
        else:
            page = client.pages.create(
                parent={"database_id": self.posts_data_source_id},
                properties=properties,
                children=blocks[:100],
                icon={"type": "emoji", "emoji": "🐦"},
            )
            return {"page_id": page.get("id"), "action": "created", "post_id": post.post_id}
