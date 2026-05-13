from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import AppConfig


SQLITE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawler_name TEXT NOT NULL,
    category_id TEXT,
    category_key TEXT,
    category_name TEXT,
    collection_id TEXT,
    raw_json_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawler_name TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    parent_resource_id TEXT,
    effect_type TEXT,
    title TEXT,
    panel TEXT,
    category_id TEXT,
    collection_id TEXT,
    source_kind TEXT,
    raw_list_path TEXT,
    raw_detail_path TEXT,
    item_json TEXT,
    detail_json TEXT,
    status TEXT DEFAULT 'discovered',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crawler_name, resource_id)
);

CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT NOT NULL,
    url TEXT NOT NULL,
    url_kind TEXT NOT NULL,
    target_path TEXT,
    file_md5 TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(resource_id, url, url_kind)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_resource_id TEXT NOT NULL,
    child_resource_id TEXT NOT NULL,
    dependency_type TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_resource_id, child_resource_id, dependency_type)
);

CREATE TABLE IF NOT EXISTS crawl_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawler_name TEXT NOT NULL,
    state_key TEXT NOT NULL,
    state_value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crawler_name, state_key)
);
"""


POSTGRES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    crawler_name TEXT NOT NULL,
    category_id TEXT,
    category_key TEXT,
    category_name TEXT,
    collection_id TEXT,
    raw_json_path TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id BIGSERIAL PRIMARY KEY,
    crawler_name TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    parent_resource_id TEXT,
    effect_type TEXT,
    title TEXT,
    panel TEXT,
    category_id TEXT,
    collection_id TEXT,
    source_kind TEXT,
    raw_list_path TEXT,
    raw_detail_path TEXT,
    item_json TEXT,
    detail_json TEXT,
    status TEXT DEFAULT 'discovered',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crawler_name, resource_id)
);

CREATE TABLE IF NOT EXISTS downloads (
    id BIGSERIAL PRIMARY KEY,
    resource_id TEXT NOT NULL,
    url TEXT NOT NULL,
    url_kind TEXT NOT NULL,
    target_path TEXT,
    file_md5 TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(resource_id, url, url_kind)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id BIGSERIAL PRIMARY KEY,
    parent_resource_id TEXT NOT NULL,
    child_resource_id TEXT NOT NULL,
    dependency_type TEXT,
    raw_json TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_resource_id, child_resource_id, dependency_type)
);

CREATE TABLE IF NOT EXISTS crawl_state (
    id BIGSERIAL PRIMARY KEY,
    crawler_name TEXT NOT NULL,
    state_key TEXT NOT NULL,
    state_value TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crawler_name, state_key)
);

CREATE INDEX IF NOT EXISTS idx_downloads_resource_url_kind
ON downloads(resource_id, url, url_kind);

CREATE INDEX IF NOT EXISTS idx_items_crawler_resource
ON items(crawler_name, resource_id);

CREATE INDEX IF NOT EXISTS idx_items_resource
ON items(resource_id);

CREATE INDEX IF NOT EXISTS idx_dependencies_parent_child_type
ON dependencies(parent_resource_id, child_resource_id, dependency_type);

CREATE INDEX IF NOT EXISTS idx_crawl_state_crawler_key
ON crawl_state(crawler_name, state_key);

CREATE INDEX IF NOT EXISTS idx_categories_crawler
ON categories(crawler_name);

CREATE INDEX IF NOT EXISTS idx_downloads_resource_status_kind
ON downloads(resource_id, status, url_kind);
"""


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def connect_postgres(database_url: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row)


def init_db(config: AppConfig) -> None:
    if config.use_postgres:
        init_postgres(config.database_url)
        return
    init_sqlite(config.database_path)


def init_sqlite(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SQLITE_SCHEMA_SQL)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_downloads_resource_url_kind
            ON downloads(resource_id, url, url_kind)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_items_crawler_resource
            ON items(crawler_name, resource_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_items_resource
            ON items(resource_id)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dependencies_parent_child_type
            ON dependencies(parent_resource_id, child_resource_id, dependency_type)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_crawl_state_crawler_key
            ON crawl_state(crawler_name, state_key)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_categories_crawler
            ON categories(crawler_name)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_downloads_resource_status_kind
            ON downloads(resource_id, status, url_kind)
            """
        )
        conn.commit()
    finally:
        conn.close()


def init_postgres(database_url: str) -> None:
    with connect_postgres(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_SCHEMA_SQL)
        conn.commit()


@contextmanager
def connect(config: AppConfig) -> Iterator[Any]:
    if config.use_postgres:
        conn = connect_postgres(config.database_url)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
        return

    conn = connect_sqlite(config.database_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
