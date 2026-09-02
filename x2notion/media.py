from __future__ import annotations

import os
import re
import tempfile
from typing import Sequence
from urllib.parse import unquote, urlparse

import requests

from .models import XMedia, XPost


def download_media_file(url: str, output_dir: str | None = None, timeout: int = 30) -> tuple[str, int] | None:
    if not url or not url.startswith("http"):
        return None
    out_dir = output_dir or tempfile.gettempdir()
    os.makedirs(out_dir, exist_ok=True)

    parsed_path = unquote(urlparse(url).path)
    base_name = parsed_path.rsplit("/", 1)[-1]
    safe_name = re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|]', "_", base_name)
    if not safe_name:
        safe_name = "x_media_file"

    local_path = os.path.join(out_dir, safe_name)

    try:
        response = requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return None
        size = 0
        with open(local_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    file.write(chunk)
                    size += len(chunk)
        return local_path, size
    except Exception:
        return None


def download_post_media(posts: Sequence[XPost], output_dir: str | None = None) -> None:
    for post in posts:
        for media_item in post.media:
            if media_item.url:
                res = download_media_file(media_item.url, output_dir=output_dir)
                if res:
                    media_item.local_path, media_item.size_bytes = res
