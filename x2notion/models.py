from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

XFeedType = Literal["posted", "liked", "bookmark"]


@dataclass
class XAuthor:
    id: str = ""
    name: str = ""
    handle: str = ""
    profile_url: str = ""
    avatar_url: str = ""


@dataclass
class XMedia:
    media_id: str = ""
    kind: Literal["photo", "video", "animated_gif", "link"] = "photo"
    url: str = ""
    alt_text: str = ""
    local_path: str = ""
    mime_type: str = ""
    size_bytes: int = 0


@dataclass
class XReference:
    post_id: str = ""
    handle: str = ""
    url: str = ""
    text: str = ""


@dataclass
class XPost:
    post_id: str
    url: str
    text: str
    author: XAuthor
    created_at: str | None = None
    saved_at: str | None = None
    feed_types: list[XFeedType] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    folders: list[str] = field(default_factory=list)
    media: list[XMedia] = field(default_factory=list)
    quote: XReference | None = None
    reply_to: XReference | None = None
    post_type: str = "原创"
    likes_count: int = 0
    retweets_count: int = 0
    replies_count: int = 0
    raw_dict: dict[str, Any] = field(default_factory=dict)
