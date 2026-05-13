from __future__ import annotations

from .common import extract_categories, extract_common_attr, extract_depend_resources, extract_recipe_downloads, get_effect_item_identity, get_has_more, get_next_offset, iter_effect_items
from ..base import BaseCrawler


class MaterialPackCrawler(BaseCrawler):
    crawler_name = "material_pack"
    panel = "composition"
    category_id = "10536"
    category_key = "10536"
    page_size = 50

    def run(self) -> None:
        categories = self.fetch_categories()
        if not categories:
            categories = [
                {
                    "category_id": self.category_id,
                    "category_key": self.category_key,
                    "category_name": "热门",
                }
            ]
        for category in categories:
            category_id = str(category.get("category_id") or "")
            if not category_id:
                continue
            category_key = str(category.get("category_key") or "")
            self.crawl_category(
                category_id=category_id,
                category_key=category_key,
            )

    def fetch_categories(self) -> list[dict]:
        payload = {
            "panel": "recipe",
            "get_resource": True,
            "resource_count": self.page_size,
        }
        response = self.client.post_json(
            "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/panel/get_panel_info",
            payload=payload,
        )
        data, raw_path = self.parse_response_or_save_raw(response, "material_pack_panel.json")

        for category in extract_categories(data):
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                category_id=str(category.get("category_id") or ""),
                category_key=str(category.get("category_key") or ""),
                category_name=str(category.get("category_name") or ""),
                raw_json_path=str(raw_path),
            )
        return extract_categories(data)

    def crawl_category(self, category_id: str, category_key: str) -> None:
        offset = 0
        page_index = 1

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
                    "need_contract": False,
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
            raw_name = f"material_pack_page_{page_index}.json"
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
                    source_kind="material_pack",
                    raw_list_path=str(raw_path),
                    item_json=item,
                )
                self.add_downloads(resource_id, common)
                self.fetch_detail(resource_id, raw_path=str(raw_path), category_id=category_id)

            self.repo.upsert_state(self.crawler_name, f"category:{category_id}:offset", str(offset))

            if not get_has_more(data):
                break
            next_offset = get_next_offset(data)
            if next_offset is None or next_offset <= offset:
                break
            offset = next_offset
            page_index += 1

    def fetch_detail(self, resource_id: str, raw_path: str, category_id: str) -> None:
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
        raw_name = f"material_pack_detail_{resource_id}.json"
        data, detail_raw_path = self.parse_response_or_save_raw(response, raw_name)

        for item in iter_effect_items(data):
            detail_id, effect_type, _ = get_effect_item_identity(item)
            if detail_id != resource_id:
                continue
            common = extract_common_attr(item)
            self.repo.upsert_item(
                crawler_name=self.crawler_name,
                resource_id=detail_id,
                title=str(common.get("title") or ""),
                effect_type=effect_type,
                panel=self.panel,
                category_id=category_id,
                source_kind="material_pack_detail",
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=common,
                detail_json=item,
            )
            self.add_downloads(detail_id, common)
            for url_kind, url in extract_recipe_downloads(data):
                self.repo.add_download(detail_id, url, url_kind)
            for dep in extract_depend_resources(data):
                dep_id = str(dep.get("resource_id") or "")
                dep_type = str(dep.get("type") or "")
                if not dep_id:
                    continue
                self.repo.upsert_item(
                    crawler_name=self.crawler_name,
                    resource_id=dep_id,
                    title="",
                    source_kind="material_pack_dependency",
                    parent_resource_id=detail_id,
                )
                self.repo.add_dependency(
                    parent_resource_id=detail_id,
                    child_resource_id=dep_id,
                    dependency_type=dep_type,
                    raw_json=dep,
                )

    def add_downloads(self, resource_id: str, common: dict) -> None:
        for index, url in enumerate(common.get("item_urls", []) or []):
            if url:
                self.repo.add_download(resource_id, str(url), f"item_url_{index}")
        download_info = common.get("download_info") or {}
        if isinstance(download_info, dict) and download_info.get("url"):
            self.repo.add_download(resource_id, str(download_info["url"]), "download_info")
