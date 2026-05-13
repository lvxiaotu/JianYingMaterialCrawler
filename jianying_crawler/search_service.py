from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import CrawlContext
from .crawlers.common import (
    extract_common_attr,
    get_effect_item_identity,
    get_has_more,
    get_new_cursor,
    get_next_offset,
    get_search_id,
    iter_effect_items,
    iter_song_items,
    iter_template_items,
)
from .http_client import ApiResponse, validate_response_json


EFFECT_SEARCH_URL = "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/search"
SONG_SEARCH_URL = "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/search/songs"
TEMPLATE_SEARCH_URL = "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/search/templates"
TEMPLATE_SEARCH_ENDPOINT_KEY = "replicate_get_collection_templates_template"

DEFAULT_SEARCH_ORDER = [
    "sound_effect",
    "music",
    "sticker",
    "flower",
    "effect",
    "task_effect",
    "transition",
    "filter",
    "text_template",
    "subtitle_template",
    "template",
    "marketing_template",
    "official_material",
]

SUPPORTED_LIVE_CRAWLERS = set(DEFAULT_SEARCH_ORDER)


@dataclass(frozen=True)
class EffectSearchSpec:
    crawler_name: str
    effect_type: int
    panel: str
    scene: str = ""
    source_kind: str = "live_search"
    material_type: str = "effect"


EFFECT_SEARCH_SPECS: dict[str, EffectSearchSpec] = {
    "sound_effect": EffectSearchSpec(
        crawler_name="sound_effect",
        effect_type=3,
        panel="audio",
        material_type="audio",
    ),
    "flower": EffectSearchSpec(
        crawler_name="flower",
        effect_type=1,
        panel="flower",
        material_type="effect",
    ),
    "sticker": EffectSearchSpec(
        crawler_name="sticker",
        effect_type=2,
        panel="sticker",
        material_type="effect",
    ),
    "effect": EffectSearchSpec(
        crawler_name="effect",
        effect_type=7,
        panel="effects2",
        material_type="effect",
    ),
    "task_effect": EffectSearchSpec(
        crawler_name="task_effect",
        effect_type=8,
        panel="face-prop",
        material_type="effect",
    ),
    "transition": EffectSearchSpec(
        crawler_name="transition",
        effect_type=19,
        panel="transitions",
        material_type="effect",
    ),
    "filter": EffectSearchSpec(
        crawler_name="filter",
        effect_type=12,
        panel="filter",
        material_type="effect",
    ),
    "text_template": EffectSearchSpec(
        crawler_name="text_template",
        effect_type=6,
        panel="text-template",
        scene="vimo_text-template",
        material_type="template",
    ),
    "subtitle_template": EffectSearchSpec(
        crawler_name="subtitle_template",
        effect_type=48,
        panel="subtitle-template",
        scene="vimo_subtitle-template",
        material_type="template",
    ),
    "official_material": EffectSearchSpec(
        crawler_name="official_material",
        effect_type=201,
        panel="insert",
        scene="material_lib_c_v2",
        material_type="material",
    ),
}


def _build_effect_search_payload(query_text: str, spec: EffectSearchSpec, offset: int, search_id: str) -> dict[str, Any]:
    return {
        "app_id": 3704,
        "count": 50,
        "effect_type": spec.effect_type,
        "need_recommend": False,
        "offset": offset,
        "pack_optional": {
            "fav_scene": None,
            "image_pack_param": None,
            "large_image_formats": [],
            "need_collection_id": False,
            "need_contract": True,
            "need_favorite_info": False,
            "need_operation_tag": False,
            "need_parent_tag": False,
            "need_tag": False,
            "need_thumb": False,
            "only_commercial": False,
            "tag_one_level": None,
        },
        "query": query_text,
        "replicate_sdk_version": "",
        "search_id": search_id,
        "search_option": {
            "aspect_ratio": "",
            "category_list": None,
            "effect_segment_type": None,
            "filter_uncommercial": False,
            "scene": spec.scene,
            "sticker_type": 0,
        },
        "statistics_optional": {
            "need_add_count": False,
            "need_favorite_count": False,
            "need_usage_count": False,
        },
    }


def _build_song_search_payload(query_text: str, offset: int) -> dict[str, Any]:
    return {
        "count": 50,
        "filter_paid_type": [],
        "keyword": query_text,
        "offset": offset,
        "scene": 0,
    }


def _build_template_search_payload(query_text: str, cursor: int, search_id: str) -> dict[str, Any]:
    return {
        "channels": ["lv_template"],
        "count": 32,
        "cursor": cursor,
        "extra": None,
        "filter_paid_template": False,
        "filters": {
            "duration": [],
            "fragment_count": [],
            "screen_style": ["landscape", "portrait"],
            "sub_category_ids": [],
        },
        "keyword": query_text,
        "search_entrance": "pc_edit_page",
        "search_id": search_id,
        "search_source": "input",
        "sort_type": 0,
    }


def _safe_validate_json(response: ApiResponse) -> dict[str, Any]:
    return validate_response_json(response)


def _choose_title(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


class SearchService:
    def __init__(self, context: CrawlContext) -> None:
        self.context = context

    @property
    def client(self):
        return self.context.client

    @property
    def repo(self):
        return self.context.repo

    def search_hybrid(
        self,
        query_text: str,
        crawler_names: list[str] | None = None,
        limit: int = 20,
        downloaded_only: bool = False,
    ) -> dict[str, Any]:
        normalized_query = query_text.strip()
        if not normalized_query:
            return {
                "query": query_text,
                "count": 0,
                "results": [],
                "search_mode": "empty_query",
                "source": "none",
            }

        if downloaded_only:
            sql_results = self.repo.search_items(
                query_text=normalized_query,
                crawler_names=crawler_names,
                limit=limit,
                downloaded_only=True,
            )
            return {
                "query": normalized_query,
                "count": len(sql_results),
                "results": sql_results,
                "search_mode": "sql_downloaded_only",
                "source": "sql",
            }

        live_results = self.search_live(
            query_text=normalized_query,
            crawler_names=crawler_names,
            limit=limit,
        )
        if live_results:
            return {
                "query": normalized_query,
                "count": len(live_results),
                "results": live_results,
                "search_mode": "live_only",
                "source": "live_search",
            }

        sql_results = self.repo.search_items(
            query_text=normalized_query,
            crawler_names=crawler_names,
            limit=limit,
            downloaded_only=downloaded_only,
        )
        return {
            "query": normalized_query,
            "count": len(sql_results),
            "results": sql_results,
            "search_mode": "sql_fallback",
            "source": "sql",
        }

    def search_live(
        self,
        query_text: str,
        crawler_names: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        ordered_crawlers = self._resolve_crawler_names(crawler_names)
        results: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        for crawler_name in ordered_crawlers:
            if len(results) >= limit:
                break
            remaining = limit - len(results)
            try:
                batch = self._search_one_live(crawler_name, query_text, remaining)
            except Exception:
                continue
            for item in batch:
                key = (str(item.get("crawler_name") or ""), str(item.get("resource_id") or ""))
                if not key[0] or not key[1] or key in seen_keys:
                    continue
                seen_keys.add(key)
                results.append(item)
                if len(results) >= limit:
                    break

        return results[:limit]

    def _resolve_crawler_names(self, crawler_names: list[str] | None) -> list[str]:
        if crawler_names:
            resolved: list[str] = []
            for crawler_name in crawler_names:
                normalized = str(crawler_name or "").strip()
                if not normalized or normalized not in SUPPORTED_LIVE_CRAWLERS:
                    continue
                if normalized not in resolved:
                    resolved.append(normalized)
            return resolved
        return list(DEFAULT_SEARCH_ORDER)

    def _search_one_live(self, crawler_name: str, query_text: str, limit: int) -> list[dict[str, Any]]:
        if crawler_name in EFFECT_SEARCH_SPECS:
            return self._search_effect_live(EFFECT_SEARCH_SPECS[crawler_name], query_text, limit)
        if crawler_name == "music":
            return self._search_music_live(query_text, limit)
        if crawler_name in {"template", "marketing_template"}:
            return self._search_template_live(crawler_name, query_text, limit)
        return []

    def _search_effect_live(self, spec: EffectSearchSpec, query_text: str, limit: int) -> list[dict[str, Any]]:
        offset = 0
        search_id = ""
        results: list[dict[str, Any]] = []

        while len(results) < limit:
            payload = _build_effect_search_payload(query_text, spec, offset=offset, search_id=search_id)
            response = self.client.post_json(
                EFFECT_SEARCH_URL,
                payload=payload,
                log_context={
                    "crawler_name": spec.crawler_name,
                    "request_name": "search_live",
                    "search_query": query_text,
                },
            )
            data = _safe_validate_json(response)
            items = iter_effect_items(data)
            if not items:
                break

            for item in items:
                results.append(self._map_effect_item(spec, item))
                if len(results) >= limit:
                    break

            if len(results) >= limit or not get_has_more(data):
                break

            next_offset = get_next_offset(data)
            next_search_id = get_search_id(data)
            if next_offset is None or next_offset <= offset:
                break
            offset = next_offset
            if next_search_id:
                search_id = next_search_id

        return results[:limit]

    def _search_music_live(self, query_text: str, limit: int) -> list[dict[str, Any]]:
        offset = 0
        results: list[dict[str, Any]] = []

        while len(results) < limit:
            payload = _build_song_search_payload(query_text, offset=offset)
            response = self.client.post_json(
                SONG_SEARCH_URL,
                payload=payload,
                headers={"Business-Sign-Version": "v2"},
                log_context={
                    "crawler_name": "music",
                    "request_name": "search_live",
                    "search_query": query_text,
                },
            )
            data = _safe_validate_json(response)
            songs = iter_song_items(data)
            if not songs:
                break

            for song in songs:
                results.append(self._map_song_item(song))
                if len(results) >= limit:
                    break

            if len(results) >= limit or not get_has_more(data):
                break

            next_offset = get_next_offset(data)
            if next_offset is None or next_offset <= offset:
                break
            offset = next_offset

        return results[:limit]

    def _search_template_live(self, crawler_name: str, query_text: str, limit: int) -> list[dict[str, Any]]:
        cursor = 0
        search_id = ""
        results: list[dict[str, Any]] = []

        while len(results) < limit:
            payload = _build_template_search_payload(query_text, cursor=cursor, search_id=search_id)
            response = self.client.post_replicate_json(
                TEMPLATE_SEARCH_URL,
                payload=payload,
                endpoint_key=TEMPLATE_SEARCH_ENDPOINT_KEY,
                log_context={
                    "crawler_name": crawler_name,
                    "request_name": "search_live",
                    "search_query": query_text,
                },
            )
            data = _safe_validate_json(response)
            items = iter_template_items(data)
            if not items:
                break

            for item in items:
                results.append(self._map_template_item(crawler_name, item))
                if len(results) >= limit:
                    break

            if len(results) >= limit or not get_has_more(data):
                break

            next_cursor = get_new_cursor(data)
            next_search_id = get_search_id(data)
            if not next_cursor:
                break
            try:
                next_cursor_int = int(next_cursor)
            except ValueError:
                break
            if next_cursor_int <= cursor:
                break
            cursor = next_cursor_int
            if next_search_id:
                search_id = next_search_id

        return results[:limit]

    def _map_effect_item(self, spec: EffectSearchSpec, item: dict[str, Any]) -> dict[str, Any]:
        common = extract_common_attr(item)
        resource_id, effect_type, _ = get_effect_item_identity(item)
        title = _choose_title(
            common.get("title"),
            item.get("title"),
            item.get("name"),
        )
        category_ids = common.get("category_ids")
        category_id = ""
        if isinstance(category_ids, list) and category_ids:
            category_id = str(category_ids[0] or "")

        return {
            "crawler_name": spec.crawler_name,
            "resource_id": resource_id,
            "title": title,
            "effect_type": effect_type or str(spec.effect_type),
            "panel": spec.panel,
            "category_id": category_id,
            "collection_id": "",
            "source_kind": spec.source_kind,
            "parent_resource_id": "",
            "updated_at": "",
            "downloaded": False,
            "primary_downloaded": False,
            "primary_target_path": "",
            "material_type": spec.material_type,
        }

    def _map_song_item(self, song: dict[str, Any]) -> dict[str, Any]:
        resource_id = str(song.get("id") or song.get("web_id") or "")
        title = _choose_title(song.get("title"), song.get("name"))
        return {
            "crawler_name": "music",
            "resource_id": resource_id,
            "title": title,
            "effect_type": "4",
            "panel": "music_search",
            "category_id": "",
            "collection_id": "",
            "source_kind": "live_search",
            "parent_resource_id": "",
            "updated_at": "",
            "downloaded": False,
            "primary_downloaded": False,
            "primary_target_path": "",
            "material_type": "audio",
        }

    def _map_template_item(self, crawler_name: str, item: dict[str, Any]) -> dict[str, Any]:
        resource_id = str(item.get("template_id") or item.get("id") or "")
        title = _choose_title(item.get("title"), item.get("name"))
        collection_id = str(item.get("collection_id") or item.get("group_id") or "")
        return {
            "crawler_name": crawler_name,
            "resource_id": resource_id,
            "title": title,
            "effect_type": "",
            "panel": "lv_template",
            "category_id": "",
            "collection_id": collection_id,
            "source_kind": "live_search",
            "parent_resource_id": "",
            "updated_at": "",
            "downloaded": False,
            "primary_downloaded": False,
            "primary_target_path": "",
            "material_type": "template",
        }
