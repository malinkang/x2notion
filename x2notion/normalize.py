from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from .models import XAuthor, XFeedType, XMedia, XPost, XReference

SHANGHAI = ZoneInfo("Asia/Shanghai")


def expand_text_urls(text: str, urls: list[dict[str, Any]] | None) -> str:
    if not text or not urls:
        return text or ""
    result = text
    for item in urls:
        short_url = item.get("url")
        expanded_url = item.get("expanded_url") or item.get("unwound_url")
        if short_url and expanded_url:
            result = result.replace(short_url, expanded_url)
    return result


def parse_iso_datetime(value: Any) -> str | None:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = date_parser.parse(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def extract_media_from_tweet(tweet: Any) -> list[XMedia]:
    media_list: list[XMedia] = []
    raw_media = getattr(tweet, "media", None)
    if not raw_media and isinstance(tweet, dict):
        raw_media = tweet.get("media") or tweet.get("extended_entities", {}).get("media") or []
    if not raw_media:
        raw_media = []

    if isinstance(raw_media, list):
        for item in raw_media:
            if isinstance(item, dict):
                m_type = item.get("type", "photo")
                m_url = item.get("media_url_https") or item.get("url") or ""
                if m_type in ("video", "animated_gif"):
                    variants = item.get("video_info", {}).get("variants", [])
                    mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
                    if mp4s:
                        mp4s.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
                        m_url = mp4s[0].get("url") or m_url
                if m_url:
                    media_list.append(
                        XMedia(
                            media_id=str(item.get("id") or ""),
                            kind="video" if m_type in ("video", "animated_gif") else "photo",
                            url=m_url,
                            alt_text=item.get("alt_text") or "",
                        )
                    )
            elif hasattr(item, "media_url_https") or hasattr(item, "url"):
                m_url = getattr(item, "media_url_https", None) or getattr(item, "url", "")
                m_type = getattr(item, "type", "photo")
                if m_url:
                    media_list.append(
                        XMedia(
                            media_id=str(getattr(item, "id", "")),
                            kind="video" if m_type in ("video", "animated_gif") else "photo",
                            url=m_url,
                        )
                    )
    return media_list


def normalize_tweet(tweet: Any, feed_type: XFeedType = "posted") -> XPost | None:
    if not tweet:
        return None

    post_id = str(getattr(tweet, "id", None) or getattr(tweet, "rest_id", None) or (tweet.get("id") if isinstance(tweet, dict) else "")).strip()
    if not post_id:
        return None

    user_obj = getattr(tweet, "user", None) or (tweet.get("user") if isinstance(tweet, dict) else None)
    author_id = ""
    author_name = "X User"
    author_handle = ""
    avatar_url = ""

    if user_obj:
        author_id = str(getattr(user_obj, "id", None) or getattr(user_obj, "rest_id", None) or (user_obj.get("id") if isinstance(user_obj, dict) else "") or "")
        author_name = str(getattr(user_obj, "name", None) or (user_obj.get("name") if isinstance(user_obj, dict) else "") or author_name)
        author_handle = str(getattr(user_obj, "screen_name", None) or getattr(user_obj, "username", None) or (user_obj.get("screen_name") if isinstance(user_obj, dict) else "") or "").replace("@", "")
        avatar_url = str(getattr(user_obj, "profile_image_url_https", None) or getattr(user_obj, "avatar_url", None) or (user_obj.get("profile_image_url_https") if isinstance(user_obj, dict) else "") or "")

    raw_text = str(getattr(tweet, "full_text", None) or getattr(tweet, "text", None) or (tweet.get("full_text") if isinstance(tweet, dict) else "") or "")
    entities = getattr(tweet, "entities", None) or (tweet.get("entities") if isinstance(tweet, dict) else {}) or {}
    urls_entity = entities.get("urls", []) if isinstance(entities, dict) else []
    text = expand_text_urls(raw_text, urls_entity)

    hashtags: list[str] = []
    if isinstance(entities, dict) and "hashtags" in entities:
        for tag_item in entities.get("hashtags", []):
            tag_text = tag_item.get("text") if isinstance(tag_item, dict) else str(tag_item)
            if tag_text:
                hashtags.append(tag_text)
    if not hashtags:
        hashtags = list(set(re.findall(r"#([\w\u4e00-\u9fa5]+)", text)))

    created_at_raw = getattr(tweet, "created_at", None) or (tweet.get("created_at") if isinstance(tweet, dict) else None)
    created_at = parse_iso_datetime(created_at_raw)
    saved_at = datetime.now(timezone.utc).isoformat()

    media = extract_media_from_tweet(tweet)

    quote_ref = None
    quoted_tweet = getattr(tweet, "quoted_tweet", None) or (tweet.get("quoted_status") if isinstance(tweet, dict) else None)
    if quoted_tweet:
        q_id = str(getattr(quoted_tweet, "id", "") or (quoted_tweet.get("id") if isinstance(quoted_tweet, dict) else ""))
        q_user = getattr(quoted_tweet, "user", None) or (quoted_tweet.get("user") if isinstance(quoted_tweet, dict) else None)
        q_handle = str(getattr(q_user, "screen_name", "") or (q_user.get("screen_name") if isinstance(q_user, dict) else "")).replace("@", "")
        if q_id:
            quote_ref = XReference(
                post_id=q_id,
                handle=q_handle,
                url=f"https://x.com/{q_handle or 'i'}/status/{q_id}",
                text=str(getattr(quoted_tweet, "text", "") or (quoted_tweet.get("text") if isinstance(quoted_tweet, dict) else "")),
            )

    reply_ref = None
    in_reply_to_id = getattr(tweet, "in_reply_to_status_id_str", None) or (tweet.get("in_reply_to_status_id_str") if isinstance(tweet, dict) else None)
    in_reply_to_screen_name = getattr(tweet, "in_reply_to_screen_name", None) or (tweet.get("in_reply_to_screen_name") if isinstance(tweet, dict) else None)
    if in_reply_to_id:
        r_handle = str(in_reply_to_screen_name or "").replace("@", "")
        reply_ref = XReference(
            post_id=str(in_reply_to_id),
            handle=r_handle,
            url=f"https://x.com/{r_handle or 'i'}/status/{in_reply_to_id}",
        )

    post_type = "回复" if reply_ref else ("引用" if quote_ref else "原创")
    canonical_url = f"https://x.com/{author_handle or 'i'}/status/{post_id}"

    author = XAuthor(
        id=author_id,
        name=author_name,
        handle=author_handle,
        profile_url=f"https://x.com/{author_handle}" if author_handle else "",
        avatar_url=avatar_url,
    )

    return XPost(
        post_id=post_id,
        url=canonical_url,
        text=text,
        author=author,
        created_at=created_at,
        saved_at=saved_at,
        feed_types=[feed_type],
        tags=hashtags,
        media=media,
        quote=quote_ref,
        reply_to=reply_ref,
        post_type=post_type,
        likes_count=int(getattr(tweet, "favorite_count", 0) or 0),
        retweets_count=int(getattr(tweet, "retweet_count", 0) or 0),
        replies_count=int(getattr(tweet, "reply_count", 0) or 0),
    )
