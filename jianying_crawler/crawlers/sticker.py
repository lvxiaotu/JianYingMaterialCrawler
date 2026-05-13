from __future__ import annotations

from .common import extract_categories, extract_common_attr, get_effect_item_identity, get_has_more, get_next_offset, iter_aigc_items, iter_effect_items
from ..base import BaseCrawler


class StickerCrawler(BaseCrawler):
    crawler_name = "sticker"
    panel = "sticker"
    extra_categories = [
        {"category_id": "11128", "category_key": "", "category_name": "detail_inferred_11128"},
        {"category_id": "10515", "category_key": "", "category_name": "detail_inferred_10515"},
    ]
    aigc_models = [
        "high_aes_scheduler_svr:sticker_cartoon_v2.0",
        "high_aes_scheduler_svr:sticker_real_v2.0",
        "text2image_high_aes_sticker_3d",
        "text2image_high_aes_sticker_outline",
        "text2image_high_aes_sticker_pixel",
        "text2image_high_aes_sticker_crayon",
        "text2image_high_aes_sticker_oil",
    ]
    page_size = 50

    def run(self) -> None:
        categories = self.fetch_categories()
        categories = self.merge_extra_categories(categories)
        for category in categories:
            category_id = str(category.get("category_id") or "")
            if not category_id:
                continue
            category_key = str(category.get("category_key") or "")
            self.crawl_category(category_id=category_id, category_key=category_key)
        self.fetch_aigc_items()
        self.fetch_aigc_prompts()

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
        raw_name = "sticker_panel.json"
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

    def merge_extra_categories(self, categories: list[dict]) -> list[dict]:
        existing = {
            (str(category.get("category_id") or ""), str(category.get("category_key") or ""))
            for category in categories
        }
        merged = list(categories)
        for category in self.extra_categories:
            key = (str(category.get("category_id") or ""), str(category.get("category_key") or ""))
            if key in existing:
                continue
            merged.append(category)
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                category_id=key[0],
                category_key=key[1],
                category_name=str(category.get("category_name") or ""),
            )
        return merged

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
            raw_name = f"sticker_{category_id}_page_{page_index}.json"
            data, raw_path = self.parse_response_or_save_raw(response, raw_name)

            items = iter_effect_items(data)
            if not items:
                break

            for item in items:
                resource_id, effect_type, _ = get_effect_item_identity(item)
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
                    source_kind="sticker",
                    raw_list_path=str(raw_path),
                    item_json=item,
                )
                self.add_downloads(resource_id, common, item)
                self.fetch_detail(
                    resource_id=resource_id,
                    raw_path=str(raw_path),
                    category_id=category_id,
                    effect_type=effect_type or "35",
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
        effect_type: str = "35",
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
        raw_name = f"sticker_detail_{resource_id}.json"
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
                source_kind="sticker_detail",
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=common,
                detail_json=item,
            )
            self.add_downloads(detail_id, common, item)

    def add_downloads(self, resource_id: str, common: dict, item: dict) -> None:
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

        sticker = item.get("sticker") or {}
        if isinstance(sticker, dict):
            track_thumbnail = sticker.get("track_thumbnail")
            if track_thumbnail:
                self.repo.add_download(resource_id, str(track_thumbnail), "track_thumbnail")
            large_image = sticker.get("large_image") or {}
            if isinstance(large_image, dict) and large_image.get("image_url"):
                self.repo.add_download(resource_id, str(large_image["image_url"]), "large_image")

    def fetch_aigc_items(self) -> None:
        payload = {
            "count": self.page_size,
            "effect_type": 2,
            "offset": 0,
        }
        response = self.client.post_json(
            "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/user_aigc_list",
            payload=payload,
        )
        raw_name = "sticker_aigc_page_1.json"
        data, raw_path = self.parse_response_or_save_raw(response, raw_name)

        for item in iter_aigc_items(data):
            resource_id, effect_type, _ = get_effect_item_identity(item)
            if not resource_id:
                continue
            common = extract_common_attr(item)
            self.repo.upsert_item(
                crawler_name=self.crawler_name,
                resource_id=resource_id,
                title=str(common.get("title") or item.get("title") or ""),
                effect_type=effect_type or "2",
                panel="aigc_sticker",
                source_kind="sticker_aigc",
                raw_list_path=str(raw_path),
                item_json=item,
            )
            self.add_downloads(resource_id, common, item)

        self.repo.upsert_state(self.crawler_name, "aigc:offset", "0")

    def fetch_aigc_prompts(self) -> None:
        payload = {
            "model_list": self.aigc_models,
            "scene": 1,
        }
        response = self.client.post_json(
            "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/aigc_effect/random_prompt",
            payload=payload,
        )
        raw_name = "sticker_aigc_prompts.json"
        self.parse_response_or_save_raw(response, raw_name)
        self.repo.upsert_state(self.crawler_name, "aigc:prompt_models", str(len(self.aigc_models)))
