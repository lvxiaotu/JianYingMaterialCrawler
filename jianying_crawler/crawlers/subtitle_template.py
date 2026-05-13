from __future__ import annotations

from .common import extract_common_attr, extract_depend_resources, extract_item_category_ids, get_effect_item_identity, get_has_more, get_next_offset, iter_effect_items
from ..base import BaseCrawler


class SubtitleTemplateCrawler(BaseCrawler):
    crawler_name = "subtitle_template"
    panel = "subtitle-template"
    panel_aliases = [
        "subtitle-template",
        "subtitle",
        "captions",
        "caption",
        "zimu",
        "subtitle_template",
    ]
    seed_category_id = "5913895"
    seed_category_key = "5913895"
    page_size = 50

    def run(self) -> None:
        categories = self.discover_categories()
        if not categories:
            categories = {
                self.seed_category_id: {
                    "category_id": self.seed_category_id,
                    "category_key": self.seed_category_key,
                    "category_name": "热门",
                }
            }

        for category in categories.values():
            category_id = str(category.get("category_id") or "")
            category_key = str(category.get("category_key") or category_id)
            if not category_id:
                continue
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                category_id=category_id,
                category_key=category_key,
                category_name=str(category.get("category_name") or ""),
                raw_json_path=str(category.get("raw_json_path") or ""),
            )
            self.crawl_category(category_id=category_id, category_key=category_key)

    def discover_categories(self) -> dict[str, dict]:
        discovered: dict[str, dict] = {}

        for panel in self.panel_aliases:
            payload = {
                "app_id": 3704,
                "category_id": int(self.seed_category_id),
                "category_key": self.seed_category_key,
                "count": self.page_size,
                "filter_optional": {
                    "filter_paid_type": [],
                    "filter_uncommercial": False,
                    "no_copyrighted": False,
                    "no_tuchong_order": False,
                    "only_enterprise_commercial": False,
                },
                "full_count": False,
                "offset": 0,
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
                "panel": panel,
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
            raw_name = f"subtitle_template_discover_{panel.replace('-', '_')}.json"
            data, raw_path = self.parse_response_or_save_raw(response, raw_name)

            items = iter_effect_items(data)
            if not items:
                continue

            discovered.setdefault(
                self.seed_category_id,
                {
                    "category_id": self.seed_category_id,
                    "category_key": self.seed_category_key,
                    "category_name": "热门",
                    "raw_json_path": str(raw_path),
                },
            )
            self.repo.upsert_state(self.crawler_name, f"panel_alias:{panel}", "ok")

            for item in items:
                for category_id in extract_item_category_ids(item):
                    discovered.setdefault(
                        category_id,
                        {
                            "category_id": category_id,
                            "category_key": category_id,
                            "category_name": "",
                            "raw_json_path": str(raw_path),
                        },
                    )
        return discovered

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
            raw_name = f"subtitle_template_{category_id}_page_{page_index}.json"
            data, raw_path = self.parse_response_or_save_raw(response, raw_name)

            items = iter_effect_items(data)
            if not items:
                self.repo.upsert_state(self.crawler_name, f"category:{category_id}:status", "empty_or_unsupported")
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
                    source_kind="subtitle_template",
                    raw_list_path=str(raw_path),
                    item_json=item,
                )
                self.add_downloads(resource_id, common, item)
                self.fetch_detail(
                    resource_id=resource_id,
                    raw_path=str(raw_path),
                    category_id=category_id,
                    effect_type=effect_type or "48",
                    source=source or "1",
                )
                self.upsert_item_categories(item=item, raw_json_path=str(raw_path))

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
        effect_type: str = "48",
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
        raw_name = f"subtitle_template_detail_{resource_id}.json"
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
                source_kind="subtitle_template_detail",
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=common,
                detail_json=item,
            )
            self.add_downloads(detail_id, common, item)
            self.add_dependencies(parent_resource_id=detail_id, detail_data=data, raw_path=raw_path)
            self.upsert_item_categories(item=item, raw_json_path=str(detail_raw_path))

    def add_dependencies(self, parent_resource_id: str, detail_data: dict, raw_path: str) -> None:
        for dep in extract_depend_resources(detail_data):
            dep_id = str(dep.get("resource_id") or "")
            dep_type = str(dep.get("type") or "")
            dep_source = str(dep.get("source") or "1")
            if not dep_id:
                continue
            self.repo.upsert_item(
                crawler_name=self.crawler_name,
                resource_id=dep_id,
                title="",
                effect_type="",
                source_kind="subtitle_template_dependency",
                parent_resource_id=parent_resource_id,
            )
            self.repo.add_dependency(
                parent_resource_id=parent_resource_id,
                child_resource_id=dep_id,
                dependency_type=dep_type,
                raw_json=dep,
            )
            self.fetch_dependency_detail(
                parent_resource_id=parent_resource_id,
                resource_id=dep_id,
                dependency_type=dep_type,
                source=dep_source,
                raw_path=raw_path,
            )

    def fetch_dependency_detail(
        self,
        parent_resource_id: str,
        resource_id: str,
        dependency_type: str,
        source: str,
        raw_path: str,
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
        raw_name = f"subtitle_template_dependency_{resource_id}.json"
        data, detail_raw_path = self.parse_response_or_save_raw(response, raw_name)

        for item in iter_effect_items(data):
            detail_id, effect_type, detail_source = get_effect_item_identity(item)
            if detail_id != resource_id:
                continue
            common = extract_common_attr(item)
            self.repo.upsert_item(
                crawler_name=self.crawler_name,
                resource_id=detail_id,
                title=str(common.get("title") or ""),
                effect_type=effect_type,
                source_kind="subtitle_template_dependency_detail",
                parent_resource_id=parent_resource_id,
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=common,
                detail_json=item,
            )
            self.repo.add_dependency(
                parent_resource_id=parent_resource_id,
                child_resource_id=detail_id,
                dependency_type=dependency_type or detail_source or source,
                raw_json=item,
            )
            self.add_downloads(detail_id, common, item)
            self.upsert_item_categories(item=item, raw_json_path=str(detail_raw_path))

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

    def upsert_item_categories(self, item: dict, raw_json_path: str) -> None:
        for category_id in extract_item_category_ids(item):
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                category_id=category_id,
                category_key=category_id,
                category_name="",
                raw_json_path=raw_json_path,
            )
