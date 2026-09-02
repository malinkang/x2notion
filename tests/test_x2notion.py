import unittest
from unittest.mock import MagicMock, patch

from x2notion.client import XClient
from x2notion.errors import XAuthError, XError
from x2notion.models import XAuthor, XMedia, XPost
from x2notion.normalize import expand_text_urls, normalize_tweet
from x2notion.notion_writer import XNotionWriter
from x2notion.sync import run


class TestX2Notion(unittest.TestCase):
    def test_client_validation(self):
        with self.assertRaises(XAuthError):
            XClient(auth_token="", csrf_token="")

        with self.assertRaises(XAuthError):
            XClient(auth_token="auth", csrf_token="")

        client = XClient(auth_token="token_123", csrf_token="ct0_456", user_id="u=998877")
        self.assertEqual(client.auth_token, "token_123")
        self.assertEqual(client.csrf_token, "ct0_456")
        self.assertEqual(client.user_id, "998877")

    def test_expand_text_urls(self):
        text = "Check this out https://t.co/abc1234 and https://t.co/xyz"
        urls = [
            {"url": "https://t.co/abc1234", "expanded_url": "https://example.com/article"},
            {"url": "https://t.co/xyz", "expanded_url": "https://github.com"},
        ]
        expanded = expand_text_urls(text, urls)
        self.assertEqual(expanded, "Check this out https://example.com/article and https://github.com")

    def test_normalize_tweet(self):
        raw_tweet = {
            "id": "189000000000",
            "full_text": "Hello world #Notion #AI https://t.co/link",
            "created_at": "Sun Aug 30 10:00:00 +0000 2026",
            "user": {
                "id": "12345",
                "name": "Twitter User",
                "screen_name": "twuser",
                "profile_image_url_https": "https://pbs.twimg.com/avatar.jpg",
            },
            "entities": {
                "urls": [{"url": "https://t.co/link", "expanded_url": "https://openai.com"}],
                "hashtags": [{"text": "Notion"}, {"text": "AI"}],
            },
            "media": [
                {
                    "id": "m1",
                    "type": "photo",
                    "media_url_https": "https://pbs.twimg.com/media/photo.jpg",
                },
                {
                    "id": "m2",
                    "type": "video",
                    "video_info": {
                        "variants": [
                            {"content_type": "video/mp4", "bitrate": 832000, "url": "https://video.twimg.com/low.mp4"},
                            {"content_type": "video/mp4", "bitrate": 2176000, "url": "https://video.twimg.com/high.mp4"},
                        ]
                    },
                },
            ],
            "quoted_status": {
                "id": "188000000000",
                "text": "Quoted tweet text",
                "user": {"screen_name": "quoted_author"},
            },
        }

        post = normalize_tweet(raw_tweet, feed_type="posted")
        self.assertIsNotNone(post)
        self.assertEqual(post.post_id, "189000000000")
        self.assertEqual(post.url, "https://x.com/twuser/status/189000000000")
        self.assertEqual(post.text, "Hello world #Notion #AI https://openai.com")
        self.assertEqual(post.author.name, "Twitter User")
        self.assertEqual(post.author.handle, "twuser")
        self.assertEqual(post.tags, ["Notion", "AI"])
        self.assertEqual(len(post.media), 2)
        self.assertEqual(post.media[0].kind, "photo")
        self.assertEqual(post.media[0].url, "https://pbs.twimg.com/media/photo.jpg")
        self.assertEqual(post.media[1].kind, "video")
        self.assertEqual(post.media[1].url, "https://video.twimg.com/high.mp4")
        self.assertEqual(post.post_type, "引用")
        self.assertIsNotNone(post.quote)
        self.assertEqual(post.quote.handle, "quoted_author")
        self.assertEqual(post.quote.post_id, "188000000000")

    def test_notion_writer_mock(self):
        writer = XNotionWriter(
            notion_token="secret_token",
            posts_data_source_id="posts_db_id",
            relation_data_sources={"authors": "authors_db_id", "tag": "tags_db_id"},
        )
        writer._query_first = MagicMock(return_value=None)
        writer._author_cache["testuser"] = "author_page_123"

        mock_client = MagicMock()
        mock_client.pages.create.return_value = {"id": "page_new_123"}
        writer._client = mock_client
        writer._ensure_client = MagicMock(return_value=mock_client)

        post = XPost(
            post_id="999888777",
            url="https://x.com/testuser/status/999888777",
            text="Testing post sync",
            author=XAuthor(id="1", name="Test User", handle="testuser"),
            feed_types=["posted", "bookmark"],
        )

        res = writer.write_post(post)
        self.assertEqual(res["page_id"], "page_new_123")
        self.assertEqual(res["action"], "created")
        mock_client.pages.create.assert_called_once()

    def test_sync_runner(self):
        mock_client = MagicMock()
        mock_client.get_user_tweets.return_value = [
            {"id": "1", "full_text": "Post 1", "user": {"name": "User 1", "screen_name": "u1"}}
        ]
        mock_client.get_user_likes.return_value = [
            {"id": "1", "full_text": "Post 1", "user": {"name": "User 1", "screen_name": "u1"}},
            {"id": "2", "full_text": "Post 2", "user": {"name": "User 2", "screen_name": "u2"}},
        ]
        mock_client.get_bookmarks.return_value = []

        mock_writer = MagicMock()
        mock_writer.write_post.side_effect = [
            {"page_id": "p1", "action": "created"},
            {"page_id": "p2", "action": "created"},
        ]

        env = {
            "NOTION_TOKEN": "token",
            "POSTS_DATA_SOURCE_ID": "posts_id",
            "X_AUTH_TOKEN": "auth",
            "X_CT0": "ct0",
            "X_TWID": "123",
        }

        summary = run(env, client=mock_client, writer=mock_writer)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["created"], 2)
        self.assertEqual(summary["failed"], 0)


if __name__ == "__main__":
    unittest.main()
