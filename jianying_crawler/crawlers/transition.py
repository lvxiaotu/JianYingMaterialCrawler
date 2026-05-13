from __future__ import annotations

from .common import extract_categories, extract_common_attr, get_effect_item_identity, get_has_more, get_next_offset, iter_effect_items
from ..base import BaseCrawler


class TransitionCrawler(BaseCrawler):
    crawler_name = "transition"
    panel = "transitions"
    fallback_category_id = "39663"
    fallback_category_key = "hot"
    page_size = 50

    def run(self) -> None:
        categories = self.fetch_categories()
        if not categories:
            categories = [
                {
                    "category_id": self.fallback_category_id,
                    "category_key": self.fallback_category_key,
                    "category_name": "热门",
                }
            ]
        for category in categories:
            category_id = str(category.get("category_id") or "")
            category_key = str(category.get("category_key") or "")
            if not category_id:
                continue
            self.crawl_category(category_id=category_id, category_key=category_key)

    def fetch_categories(self) -> list[dict]:
        payload = {
            "category_status": 1,
            "full_count": False,
            "only_commercial": False,
            "panel": self.panel,
        }
        response = self.client.post_json(
            "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info",
            payload=payload,
        )
        raw_name = "transition_panel.json"
        data, raw_path = self.parse_response_or_save_raw(response, raw_name)

        categories = extract_categories(data)
        for category in categories:
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                category_id=str(category.get("category_id") or ""),
                category_key=str(category.get("category_key") or ""),
                category_name=str(category.get("category_name") or ""),
                raw_json_path=str(raw_path),
            )
        return categories

    def crawl_category(self, category_id: str, category_key: str) -> None:
        state_key = f"category:{category_id}:offset"
        saved_offset = self.repo.get_state(self.crawler_name, state_key)
        offset = int(saved_offset) if saved_offset and saved_offset.isdigit() else 0
        page_index = offset // self.page_size + 1
        self.repo.upsert_state(self.crawler_name, state_key, str(offset))

        while True:
            payload = {
                "app_id": 3704,
                "category_id": int(category_id),
                "category_key": category_key,
                "count": self.page_size,
                "filter_optional": {
                    "filter_paid_type": [],
                    "filter_uncommercial": False,
                    "no_copyrighted": False,
                    "no_tuchong_order": False,
                    "only_enterprise_commercial": False,
                },
                "full_count": False,
                "offset": offset,
                "pack_optional": {
                    "fav_scene": None,
                    "image_pack_param": None,
                    "large_image_formats": [],
                    "need_collection_id": False,
                    "need_contract": True,
                    "need_favorite_info": True,
                    "need_operation_tag": False,
                    "need_parent_tag": False,
                    "need_tag": False,
                    "need_thumb": False,
                    "only_commercial": False,
                    "tag_one_level": None,
                },
                "panel": self.panel,
                "panel_source": "heycan",
                "replicate_sdk_version": "",
                "request_id": "",
                "statistics_optional": {
                    "need_add_count": False,
                    "need_favorite_count": False,
                    "need_usage_count": False,
                },
            }
            response = self.client.post_json(
                "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/get_resources_by_category_id",
                payload=payload,
            )
            raw_name = f"transition_{category_id}_page_{page_index}.json"
            data, raw_path = self.parse_response_or_save_raw(response, raw_name)

            items = iter_effect_items(data)
            if not items:
                break

            for item in items:
                resource_id, effect_type, source = get_effect_item_identity(item)
                if not resource_id:
                    continue
                common = extract_common_attr(item)
                self.repo.upsert_item(
                    crawler_name=self.crawler_name,
                    resource_id=resource_id,
                    title=str(common.get("title") or ""),
                    effect_type=effect_type,
                    panel=self.panel,
                    category_id=category_id,
                    source_kind="transition",
                    raw_list_path=str(raw_path),
                    item_json=item,
                )
                self.add_downloads(resource_id, common)
                self.fetch_detail(
                    resource_id=resource_id,
                    raw_path=str(raw_path),
                    category_id=category_id,
                    effect_type=effect_type or "19",
                    source=source or "1",
                )

            self.repo.upsert_state(self.crawler_name, state_key, str(offset))

            if not get_has_more(data):
                break
            next_offset = get_next_offset(data)
            if next_offset is None or next_offset <= offset:
                break
            offset = next_offset
            page_index += 1

    def fetch_detail(
        self,
        resource_id: str,
        raw_path: str,
        category_id: str,
        effect_type: str = "19",
        source: str = "1",
    ) -> None:
        payload = {
            "app_id": 3704,
            "id_list": [resource_id],
            "pack_optional": {
                "fav_scene": None,
                "image_pack_param": None,
                "large_image_formats": [],
                "need_collection_id": False,
                "need_contract": True,
                "need_favorite_info": True,
                "need_operation_tag": False,
                "need_parent_tag": False,
                "need_tag": False,
                "need_thumb": False,
                "only_commercial": False,
                "tag_one_level": None,
            },
            "replicate_sdk_version": "",
            "scene": "",
        }
        response = self.client.post_json(
            "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_artist_item",
            payload=payload,
        )
        raw_name = f"transition_detail_{resource_id}.json"
        data, detail_raw_path = self.parse_response_or_save_raw(response, raw_name)

        for item in iter_effect_items(data):
            detail_id, detail_effect_type, _ = get_effect_item_identity(item)
            if detail_id != resource_id:
                continue
            common = extract_common_attr(item)
            self.repo.upsert_item(
                crawler_name=self.crawler_name,
                resource_id=detail_id,
                title=str(common.get("title") or ""),
                effect_type=detail_effect_type or effect_type,
                panel=self.panel,
                category_id=category_id,
                source_kind="transition_detail",
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=common,
                detail_json=item,
            )
            self.add_downloads(detail_id, common)

    def add_downloads(self, resource_id: str, common: dict) -> None:
        for index, url in enumerate(common.get("item_urls", []) or []):
            if url:
                self.repo.add_download(resource_id, str(url), f"item_url_{index}")

        download_info = common.get("download_info") or {}
        if isinstance(download_info, dict) and download_info.get("url"):
            self.repo.add_download(resource_id, str(download_info["url"]), "download_info")

        cover = common.get("cover_url") or {}
        if isinstance(cover, dict):
            for key, url in cover.items():
                if url:
                    self.repo.add_download(resource_id, str(url), f"cover_{key}")
