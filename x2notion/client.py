from __future__ import annotations

import asyncio
import os
from typing import Any, Sequence

try:
    from twikit import Client as TwikitClient
    from twikit.errors import Forbidden, TooManyRequests, Unauthorized, UserNotFound
except ImportError:
    TwikitClient = None  # type: ignore
    Unauthorized = Exception  # type: ignore
    Forbidden = Exception  # type: ignore
    TooManyRequests = Exception  # type: ignore
    UserNotFound = Exception  # type: ignore

from .errors import XAuthError, XError, XRateLimitError


class XClient:
    """Wrapper around twikit.Client for fetching X timeline feeds."""

    def __init__(
        self,
        auth_token: str,
        csrf_token: str,
        user_id: str = "",
        proxy: str | None = None,
        language: str = "zh-CN",
    ) -> None:
        self.auth_token = str(auth_token or "").strip()
        self.csrf_token = str(csrf_token or "").strip()
        self.user_id = str(user_id or "").replace("u=", "").strip()
        self.proxy = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("TWIKIT_PROXY") or None
        self.language = language

        if not self.auth_token or not self.csrf_token:
            raise XAuthError("缺少 X_AUTH_TOKEN 或 X_CT0 凭据。")

        if TwikitClient is None:
            self._client = None
        else:
            self._client = TwikitClient(language=self.language, proxy=self.proxy)
            twid_val = f"u={self.user_id}" if self.user_id else ""
            cookies = {
                "auth_token": self.auth_token,
                "ct0": self.csrf_token,
            }
            if twid_val:
                cookies["twid"] = twid_val
            self._client.set_cookies(cookies)

    def _ensure_client(self) -> Any:
        if self._client is None:
            raise XError("Twikit 依赖未安装，请执行 pip install twikit>=2.2.0。")
        return self._client

    async def _async_get_user_tweets(self, user_id: str, count: int = 20, max_pages: int = 3) -> list[Any]:
        client = self._ensure_client()
        tweets_list: list[Any] = []
        try:
            target_id = user_id or self.user_id
            if not target_id:
                raise XAuthError("未指定 X User ID。")
            tweets = await client.get_user_tweets(target_id, tweet_type="TweetsAndReplies", count=count)
            while tweets and len(tweets_list) < (count * max_pages):
                tweets_list.extend(tweets)
                if not hasattr(tweets, "next") or not tweets.next:
                    break
                tweets = await tweets.next()
            return tweets_list
        except (Unauthorized, Forbidden) as exc:
            raise XAuthError(f"X 鉴权失败：{exc}") from exc
        except TooManyRequests as exc:
            raise XRateLimitError(f"X 请求频率超限：{exc}") from exc
        except Exception as exc:
            raise XError(f"获取推文失败：{exc}") from exc

    async def _async_get_user_likes(self, user_id: str, count: int = 20, max_pages: int = 3) -> list[Any]:
        client = self._ensure_client()
        likes_list: list[Any] = []
        try:
            target_id = user_id or self.user_id
            if not target_id:
                raise XAuthError("未指定 X User ID。")
            likes = await client.get_user_likes(target_id, count=count)
            while likes and len(likes_list) < (count * max_pages):
                likes_list.extend(likes)
                if not hasattr(likes, "next") or not likes.next:
                    break
                likes = await likes.next()
            return likes_list
        except (Unauthorized, Forbidden) as exc:
            raise XAuthError(f"X 鉴权失败：{exc}") from exc
        except TooManyRequests as exc:
            raise XRateLimitError(f"X 请求频率超限：{exc}") from exc
        except Exception as exc:
            raise XError(f"获取喜欢列表失败：{exc}") from exc

    async def _async_get_bookmarks(self, count: int = 20, max_pages: int = 3) -> list[Any]:
        client = self._ensure_client()
        bookmarks_list: list[Any] = []
        try:
            bookmarks = await client.get_bookmarks(count=count)
            while bookmarks and len(bookmarks_list) < (count * max_pages):
                bookmarks_list.extend(bookmarks)
                if not hasattr(bookmarks, "next") or not bookmarks.next:
                    break
                bookmarks = await bookmarks.next()
            return bookmarks_list
        except (Unauthorized, Forbidden) as exc:
            raise XAuthError(f"X 鉴权失败：{exc}") from exc
        except TooManyRequests as exc:
            raise XRateLimitError(f"X 请求频率超限：{exc}") from exc
        except Exception as exc:
            raise XError(f"获取书签失败：{exc}") from exc

    def get_user_tweets(self, user_id: str = "", count: int = 20, max_pages: int = 3) -> list[Any]:
        return asyncio.run(self._async_get_user_tweets(user_id or self.user_id, count, max_pages))

    def get_user_likes(self, user_id: str = "", count: int = 20, max_pages: int = 3) -> list[Any]:
        return asyncio.run(self._async_get_user_likes(user_id or self.user_id, count, max_pages))

    def get_bookmarks(self, count: int = 20, max_pages: int = 3) -> list[Any]:
        return asyncio.run(self._async_get_bookmarks(count, max_pages))
