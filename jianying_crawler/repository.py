from __future__ import annotations

import json
from typing import Any

from .config import AppConfig
from .db import connect


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        value = row.get(key, default)
        return default if value is None else value
    try:
        value = row[key]
    except Exception:
        return default
    return default if value is None else value


class Repository:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def upsert_item(
        self,
        crawler_name: str,
        resource_id: str,
        title: str = "",
        effect_type: str = "",
        panel: str = "",
        category_id: str = "",
        collection_id: str = "",
        source_kind: str = "",
        raw_list_path: str = "",
        raw_detail_path: str = "",
        item_json: Any | None = None,
        detail_json: Any | None = None,
        parent_resource_id: str | None = None,
    ) -> None:
        with connect(self.config) as conn:
            conn.execute(
                """
                INSERT INTO items (
                    crawler_name, resource_id, parent_resource_id, effect_type, title, panel,
                    category_id, collection_id, source_kind, raw_list_path, raw_detail_path,
                    item_json, detail_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(crawler_name, resource_id) DO UPDATE SET
                    parent_resource_id=excluded.parent_resource_id,
                    effect_type=excluded.effect_type,
                    title=excluded.title,
                    panel=excluded.panel,
                    category_id=excluded.category_id,
                    collection_id=excluded.collection_id,
                    source_kind=excluded.source_kind,
                    raw_list_path=excluded.raw_list_path,
                    raw_detail_path=excluded.raw_detail_path,
                    item_json=excluded.item_json,
                    detail_json=excluded.detail_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    crawler_name,
                    resource_id,
                    parent_resource_id,
                    effect_type,
                    title,
                    panel,
                    category_id,
                    collection_id,
                    source_kind,
                    raw_list_path,
                    raw_detail_path,
                    json.dumps(item_json, ensure_ascii=False) if item_json is not None else None,
                    json.dumps(detail_json, ensure_ascii=False) if detail_json is not None else None,
                ),
            )

    def upsert_category(
        self,
        crawler_name: str,
        category_id: str = "",
        category_key: str = "",
        category_name: str = "",
        collection_id: str = "",
        raw_json_path: str = "",
    ) -> None:
        with connect(self.config) as conn:
            conn.execute(
                """
                DELETE FROM categories
                WHERE crawler_name = ?
                  AND category_id = ?
                  AND category_key = ?
                  AND collection_id = ?
                """,
                (crawler_name, category_id, category_key, collection_id),
            )
            conn.execute(
                """
                INSERT INTO categories (
                    crawler_name, category_id, category_key, category_name, collection_id, raw_json_path
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (crawler_name, category_id, category_key, category_name, collection_id, raw_json_path),
            )

    def add_download(self, resource_id: str, url: str, url_kind: str, target_path: str = "") -> None:
        with connect(self.config) as conn:
            conn.execute(
                """
                INSERT INTO downloads (resource_id, url, url_kind, target_path)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(resource_id, url, url_kind) DO UPDATE SET
                    target_path=excluded.target_path,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (resource_id, url, url_kind, target_path),
            )

    def list_pending_downloads(
        self,
        crawler_name: str,
        limit: int = 50,
        resource_id: str | None = None,
        url_kind: str | None = None,
        include_auxiliary: bool = False,
    ) -> list[dict[str, Any]]:
        query = """
            WITH grouped AS (
                SELECT
                    resource_id,
                    url_kind,
                    MAX(CASE WHEN status IN ('pending', 'failed') THEN id ELSE NULL END) AS latest_id,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_count
                FROM downloads
                GROUP BY resource_id, url_kind
            )
            SELECT
                d.id,
                d.resource_id,
                d.url,
                d.url_kind,
                d.target_path,
                d.status,
                d.file_md5,
                COALESCE(i.title, '') AS title,
                COALESCE(i.parent_resource_id, '') AS parent_resource_id,
                COALESCE(i.source_kind, '') AS source_kind
            FROM downloads d
            JOIN grouped g
              ON g.latest_id = d.id
             AND g.done_count = 0
            JOIN items i
              ON i.resource_id = d.resource_id
             AND i.crawler_name = ?
            WHERE 1 = 1
        """
        params: list[Any] = [crawler_name]
        if resource_id:
            query += " AND d.resource_id = ?"
            params.append(resource_id)
        if url_kind:
            query += " AND d.url_kind = ?"
            params.append(url_kind)
        if not include_auxiliary:
            query += """
                AND (
                    d.url_kind IN (
                        'primary_asset_0', 'download_info', 'preview_audio', 'video_url',
                        'template_url', 'draft_package_url', 'template_json',
                        'origin_video_url', 'origin_watermark_video_url'
                    )
                    OR d.url_kind LIKE 'recipe_material_%'
                    OR d.url_kind LIKE 'origin_video_%'
                    OR d.url_kind LIKE 'transcoded_video_%'
                )
            """
        query += """
            ORDER BY
                CASE
                    WHEN d.url_kind = 'primary_asset_0' THEN 1
                    WHEN d.url_kind = 'download_info' THEN 2
                    WHEN d.url_kind = 'preview_audio' THEN 3
                    WHEN d.url_kind = 'video_url' THEN 4
                    WHEN d.url_kind = 'template_url' THEN 5
                    WHEN d.url_kind = 'draft_package_url' THEN 6
                    WHEN d.url_kind = 'template_json' THEN 7
                    WHEN d.url_kind LIKE 'recipe_material_%' THEN 8
                    WHEN d.url_kind LIKE 'transcoded_video_%' THEN 9
                    WHEN d.url_kind LIKE 'origin_%' THEN 10
                    ELSE 100
                END,
                d.id
        """
        query += " LIMIT ?"
        params.append(limit)

        with connect(self.config) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def cleanup_duplicate_downloads(self) -> dict[str, int]:
        with connect(self.config) as conn:
            before_count = int(conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0])
            duplicate_groups = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT resource_id, url_kind, COUNT(*) AS c
                        FROM downloads
                        GROUP BY resource_id, url_kind
                        HAVING COUNT(*) > 1
                    ) t
                    """
                ).fetchone()[0]
            )
            deleted_count = int(
                conn.execute(
                    """
                    DELETE FROM downloads
                    WHERE id NOT IN (
                        SELECT keep_id
                        FROM (
                            SELECT
                                resource_id,
                                url_kind,
                                COALESCE(
                                    MAX(CASE WHEN status = 'done' THEN id END),
                                    MAX(CASE WHEN status = 'pending' THEN id END),
                                    MAX(CASE WHEN status = 'failed' THEN id END)
                                ) AS keep_id
                            FROM downloads
                            GROUP BY resource_id, url_kind
                        ) kept
                    )
                    """
                ).rowcount
            )
            after_count = int(conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0])
        return {
            "before_count": before_count,
            "after_count": after_count,
            "deleted_count": deleted_count,
            "duplicate_groups": duplicate_groups,
        }

    def mark_download_status(
        self,
        download_id: int,
        status: str,
        target_path: str = "",
        file_md5: str = "",
    ) -> None:
        with connect(self.config) as conn:
            conn.execute(
                """
                UPDATE downloads
                SET status = ?,
                    target_path = CASE WHEN ? <> '' THEN ? ELSE target_path END,
                    file_md5 = CASE WHEN ? <> '' THEN ? ELSE file_md5 END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, target_path, target_path, file_md5, file_md5, download_id),
            )

    def add_dependency(
        self,
        parent_resource_id: str,
        child_resource_id: str,
        dependency_type: str = "",
        raw_json: Any | None = None,
    ) -> None:
        with connect(self.config) as conn:
            conn.execute(
                """
                INSERT INTO dependencies (
                    parent_resource_id, child_resource_id, dependency_type, raw_json
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(parent_resource_id, child_resource_id, dependency_type) DO UPDATE SET
                    raw_json=excluded.raw_json
                """,
                (
                    parent_resource_id,
                    child_resource_id,
                    dependency_type,
                    json.dumps(raw_json, ensure_ascii=False) if raw_json is not None else None,
                ),
            )

    def upsert_state(self, crawler_name: str, state_key: str, state_value: str) -> None:
        with connect(self.config) as conn:
            conn.execute(
                """
                INSERT INTO crawl_state (crawler_name, state_key, state_value)
                VALUES (?, ?, ?)
                ON CONFLICT(crawler_name, state_key) DO UPDATE SET
                    state_value=excluded.state_value,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (crawler_name, state_key, state_value),
            )

    def get_state(self, crawler_name: str, state_key: str) -> str | None:
        with connect(self.config) as conn:
            row = conn.execute(
                """
                SELECT state_value
                FROM crawl_state
                WHERE crawler_name = ? AND state_key = ?
                """,
                (crawler_name, state_key),
            ).fetchone()
        if row is None:
            return None
        return str(row["state_value"]) if row["state_value"] is not None else None

    def get_item_title(self, crawler_name: str, resource_id: str) -> str | None:
        with connect(self.config) as conn:
            row = conn.execute(
                """
                SELECT title
                FROM items
                WHERE crawler_name = ? AND resource_id = ?
                LIMIT 1
                """,
                (crawler_name, resource_id),
            ).fetchone()
        if row is None:
            return None
        value = row["title"] if hasattr(row, "__getitem__") else None
        if value is None:
            return None
        return str(value)

    def get_dashboard_summary(self) -> dict[str, Any]:
        with connect(self.config) as conn:
            item_rows = conn.execute(
                """
                SELECT
                    crawler_name,
                    COUNT(*) AS items_total,
                    MAX(updated_at) AS last_item_update
                FROM items
                GROUP BY crawler_name
                ORDER BY crawler_name
                """
            ).fetchall()
            category_rows = conn.execute(
                """
                SELECT
                    crawler_name,
                    COUNT(*) AS categories_total
                FROM categories
                GROUP BY crawler_name
                ORDER BY crawler_name
                """
            ).fetchall()
            download_rows = conn.execute(
                """
                SELECT
                    i.crawler_name AS crawler_name,
                    COUNT(*) AS downloads_total,
                    COALESCE(SUM(CASE WHEN d.status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_count,
                    COALESCE(SUM(CASE WHEN d.status = 'done' THEN 1 ELSE 0 END), 0) AS done_count,
                    COALESCE(SUM(CASE WHEN d.status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count,
                    MAX(d.updated_at) AS last_download_update
                FROM downloads d
                JOIN items i
                  ON i.resource_id = d.resource_id
                GROUP BY i.crawler_name
                ORDER BY i.crawler_name
                """
            ).fetchall()
            state_rows = conn.execute(
                """
                SELECT
                    crawler_name,
                    state_key,
                    state_value,
                    updated_at
                FROM crawl_state
                ORDER BY crawler_name, state_key
                """
            ).fetchall()

        enabled_crawlers = self.config.enabled_crawlers
        crawler_names = set(enabled_crawlers.keys())
        for row_group in [item_rows, category_rows, download_rows, state_rows]:
            for row in row_group:
                crawler_names.add(str(_row_get(row, "crawler_name", "")))

        summary: dict[str, dict[str, Any]] = {}
        for crawler_name in sorted(name for name in crawler_names if name):
            summary[crawler_name] = {
                "crawler_name": crawler_name,
                "enabled": bool(enabled_crawlers.get(crawler_name, False)),
                "items_total": 0,
                "categories_total": 0,
                "downloads_total": 0,
                "pending_count": 0,
                "done_count": 0,
                "failed_count": 0,
                "last_item_update": "",
                "last_download_update": "",
                "url_kind_breakdown": [],
                "crawl_state": [],
            }

        for row in item_rows:
            crawler_name = str(_row_get(row, "crawler_name", ""))
            if not crawler_name:
                continue
            summary.setdefault(crawler_name, {"crawler_name": crawler_name})
            summary[crawler_name]["items_total"] = int(_row_get(row, "items_total", 0) or 0)
            summary[crawler_name]["last_item_update"] = str(_row_get(row, "last_item_update", "") or "")

        for row in category_rows:
            crawler_name = str(_row_get(row, "crawler_name", ""))
            if not crawler_name:
                continue
            summary.setdefault(crawler_name, {"crawler_name": crawler_name})
            summary[crawler_name]["categories_total"] = int(_row_get(row, "categories_total", 0) or 0)

        for row in download_rows:
            crawler_name = str(_row_get(row, "crawler_name", ""))
            if not crawler_name:
                continue
            summary.setdefault(crawler_name, {"crawler_name": crawler_name})
            summary[crawler_name]["downloads_total"] = int(_row_get(row, "downloads_total", 0) or 0)
            summary[crawler_name]["pending_count"] = int(_row_get(row, "pending_count", 0) or 0)
            summary[crawler_name]["done_count"] = int(_row_get(row, "done_count", 0) or 0)
            summary[crawler_name]["failed_count"] = int(_row_get(row, "failed_count", 0) or 0)
            summary[crawler_name]["last_download_update"] = str(_row_get(row, "last_download_update", "") or "")

        for row in state_rows:
            crawler_name = str(_row_get(row, "crawler_name", ""))
            if not crawler_name:
                continue
            summary.setdefault(crawler_name, {"crawler_name": crawler_name})
            states = summary[crawler_name].setdefault("crawl_state", [])
            states.append(
                {
                    "state_key": str(_row_get(row, "state_key", "") or ""),
                    "state_value": str(_row_get(row, "state_value", "") or ""),
                    "updated_at": str(_row_get(row, "updated_at", "") or ""),
                }
            )

        crawler_list = [summary[name] for name in sorted(summary)]
        totals = {
            "crawler_count": len(crawler_list),
            "enabled_count": sum(1 for item in crawler_list if item.get("enabled")),
            "items_total": sum(int(item.get("items_total", 0) or 0) for item in crawler_list),
            "categories_total": sum(int(item.get("categories_total", 0) or 0) for item in crawler_list),
            "downloads_total": sum(int(item.get("downloads_total", 0) or 0) for item in crawler_list),
            "pending_count": sum(int(item.get("pending_count", 0) or 0) for item in crawler_list),
            "done_count": sum(int(item.get("done_count", 0) or 0) for item in crawler_list),
            "failed_count": sum(int(item.get("failed_count", 0) or 0) for item in crawler_list),
        }

        return {
            "totals": totals,
            "crawlers": crawler_list,
        }

    def search_items(
        self,
        query_text: str,
        crawler_names: list[str] | None = None,
        limit: int = 20,
        downloaded_only: bool = False,
    ) -> list[dict[str, Any]]:
        normalized_query = query_text.strip()
        if not normalized_query:
            return []

        like_value = f"%{normalized_query}%"
        query = """
            SELECT
                i.crawler_name,
                i.resource_id,
                COALESCE(i.title, '') AS title,
                COALESCE(i.effect_type, '') AS effect_type,
                COALESCE(i.panel, '') AS panel,
                COALESCE(i.category_id, '') AS category_id,
                COALESCE(i.collection_id, '') AS collection_id,
                COALESCE(i.source_kind, '') AS source_kind,
                COALESCE(i.parent_resource_id, '') AS parent_resource_id,
                COALESCE(i.updated_at, '') AS updated_at
            FROM items i
            WHERE (
                COALESCE(i.title, '') LIKE ?
                OR COALESCE(i.resource_id, '') LIKE ?
                OR COALESCE(i.category_id, '') LIKE ?
                OR COALESCE(i.collection_id, '') LIKE ?
            )
        """
        params: list[Any] = [like_value, like_value, like_value, like_value]

        if crawler_names:
            filtered_names = [name.strip() for name in crawler_names if name.strip()]
            if filtered_names:
                placeholders = ", ".join(["?"] * len(filtered_names))
                query += f" AND i.crawler_name IN ({placeholders})"
                params.extend(filtered_names)

        query += """
            ORDER BY
                CASE WHEN COALESCE(i.title, '') = ? THEN 0 ELSE 1 END,
                CASE WHEN COALESCE(i.title, '') LIKE ? THEN 0 ELSE 1 END,
                COALESCE(i.updated_at, '') DESC,
                i.crawler_name,
                i.resource_id
            LIMIT ?
        """
        params.extend([normalized_query, like_value, int(limit)])

        with connect(self.config) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            base_results = [dict(row) for row in rows]

            if not base_results:
                return []

            resource_ids = [str(_row_get(row, "resource_id", "") or "") for row in base_results]
            placeholders = ", ".join(["?"] * len(resource_ids))
            download_rows = conn.execute(
                f"""
                SELECT
                    d.resource_id,
                    SUM(CASE WHEN d.status = 'done' THEN 1 ELSE 0 END) AS any_done_count,
                    SUM(
                        CASE
                            WHEN d.status = 'done'
                             AND (
                                d.url_kind IN (
                                    'primary_asset_0',
                                    'download_info',
                                    'preview_audio',
                                    'video_url',
                                    'template_url',
                                    'draft_package_url',
                                    'template_json',
                                    'origin_video_url',
                                    'origin_watermark_video_url'
                                )
                                OR d.url_kind LIKE 'recipe_material_%'
                                OR d.url_kind LIKE 'origin_video_%'
                                OR d.url_kind LIKE 'transcoded_video_%'
                             )
                            THEN 1
                            ELSE 0
                        END
                    ) AS primary_done_count,
                    MAX(
                        CASE
                            WHEN d.status = 'done'
                             AND (
                                d.url_kind IN (
                                    'primary_asset_0',
                                    'download_info',
                                    'preview_audio',
                                    'video_url',
                                    'template_url',
                                    'draft_package_url',
                                    'template_json',
                                    'origin_video_url',
                                    'origin_watermark_video_url'
                                )
                                OR d.url_kind LIKE 'recipe_material_%'
                                OR d.url_kind LIKE 'origin_video_%'
                                OR d.url_kind LIKE 'transcoded_video_%'
                             )
                             AND COALESCE(d.target_path, '') <> ''
                            THEN d.target_path
                            ELSE ''
                        END
                    ) AS primary_target_path
                FROM downloads d
                WHERE d.resource_id IN ({placeholders})
                GROUP BY d.resource_id
                """,
                tuple(resource_ids),
            ).fetchall()

        download_map = {
            str(_row_get(row, "resource_id", "") or ""): dict(row)
            for row in download_rows
        }

        results: list[dict[str, Any]] = []
        for row in base_results:
            title = str(_row_get(row, "title", "") or "")
            effect_type = str(_row_get(row, "effect_type", "") or "")
            panel = str(_row_get(row, "panel", "") or "")
            crawler_name = str(_row_get(row, "crawler_name", "") or "")
            resource_id = str(_row_get(row, "resource_id", "") or "")
            download_meta = download_map.get(resource_id, {})
            primary_target_path = str(download_meta.get("primary_target_path") or "")
            primary_done_count = int(download_meta.get("primary_done_count") or 0)
            any_done_count = int(download_meta.get("any_done_count") or 0)

            if downloaded_only and any_done_count <= 0:
                continue

            results.append(
                {
                    "crawler_name": crawler_name,
                    "resource_id": resource_id,
                    "title": title,
                    "effect_type": effect_type,
                    "panel": panel,
                    "category_id": str(_row_get(row, "category_id", "") or ""),
                    "collection_id": str(_row_get(row, "collection_id", "") or ""),
                    "source_kind": str(_row_get(row, "source_kind", "") or ""),
                    "parent_resource_id": str(_row_get(row, "parent_resource_id", "") or ""),
                    "updated_at": str(_row_get(row, "updated_at", "") or ""),
                    "downloaded": any_done_count > 0,
                    "primary_downloaded": primary_done_count > 0,
                    "primary_target_path": primary_target_path,
                    "material_type": self._infer_material_type(crawler_name, effect_type, panel),
                }
            )
        return results[: int(limit)]

    @staticmethod
    def _infer_material_type(crawler_name: str, effect_type: str, panel: str) -> str:
        crawler_name = crawler_name.strip()
        effect_type = effect_type.strip()
        panel = panel.strip()

        if crawler_name in {"music", "sound_effect"}:
            return "audio"
        if crawler_name in {"template", "marketing_template", "text_template", "subtitle_template"}:
            return "template"
        if crawler_name == "material_pack":
            return "bundle"
        if crawler_name in {"sticker", "flower", "filter", "transition", "effect", "task_effect"}:
            return "effect"
        if crawler_name == "official_material":
            return "material"
        if effect_type in {"7", "8"}:
            return "effect"
        if panel in {"effects2", "face-prop"}:
            return "effect"
        return "unknown"
