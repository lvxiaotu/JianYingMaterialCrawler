from __future__ import annotations

from .common import extract_common_attr, get_effect_item_identity, get_has_more, get_next_offset, iter_effect_items
from ..base import BaseCrawler


class OfficialMaterialCrawler(BaseCrawler):
    crawler_name = "official_material"
    panel = "insert"
    category_id = "10231"
    category_key = "10231"
    page_size = 50

    def run(self) -> None:
        self.repo.upsert_category(
            crawler_name=self.crawler_name,
            category_id=self.category_id,
            category_key=self.category_key,
            category_name="insert",
        )
        self.crawl_category(category_id=self.category_id, category_key=self.category_key)

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
            raw_name = f"official_material_{category_id}_page_{page_index}.json"
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
                    source_kind="official_material",
                    raw_list_path=str(raw_path),
                    item_json=item,
                )
                self.add_downloads(resource_id, common, item)
                self.fetch_detail(
                    resource_id=resource_id,
                    raw_path=str(raw_path),
                    category_id=category_id,
                    effect_type=effect_type,
                )

            self.repo.upsert_state(self.crawler_name, f"category:{category_id}:offset", str(offset))

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
        effect_type: str = "",
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
        raw_name = f"official_material_detail_{resource_id}.json"
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
                source_kind="official_material_detail",
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

        video = item.get("video") or {}
        if isinstance(video, dict):
            origin_video = video.get("origin_video") or {}
            if isinstance(origin_video, dict):
                for key in ["video_url", "url", "play_url"]:
                    if origin_video.get(key):
                        self.repo.add_download(resource_id, str(origin_video[key]), f"origin_video_{key}")

            transcoded_video = video.get("transcoded_video") or {}
            if isinstance(transcoded_video, dict):
                for definition, payload in transcoded_video.items():
                    if not isinstance(payload, dict):
                        continue
                    for key in ["video_url", "url", "play_url"]:
                        if payload.get(key):
                            self.repo.add_download(
                                resource_id,
                                str(payload[key]),
                                f"transcoded_video_{definition}_{key}",
                            )
