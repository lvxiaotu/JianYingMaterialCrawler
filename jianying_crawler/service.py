from __future__ import annotations

from .base import CrawlContext
from .config import ensure_storage_dirs, load_config
from .db import init_db
from .http_client import JianyingHttpClient
from .repository import Repository


def build_context() -> CrawlContext:
    config = load_config()
    ensure_storage_dirs(config)
    init_db(config)
    client = JianyingHttpClient(config)
    repo = Repository(config)
    return CrawlContext(config=config, client=client, repo=repo)
