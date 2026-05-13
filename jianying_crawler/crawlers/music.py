from __future__ import annotations

from .common import extract_categories, extract_collection_items, extract_common_attr, get_effect_item_identity, get_has_more, get_next_offset, iter_effect_items, iter_song_items
from ..base import BaseCrawler


class MusicCrawler(BaseCrawler):
    crawler_name = "music"
    panel = "audio"
    page_size = 50

    def run(self) -> None:
        collections = self.fetch_collections()
        for collection in collections:
            collection_id = str(collection.get("id") or "")
            if not collection_id:
                continue
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                collection_id=collection_id,
                category_name=str(collection.get("display_name") or collection.get("name") or ""),
            )
            self.crawl_collection(collection_id)

        categories = self.fetch_audio_categories()
        for category in categories:
            category_id = str(category.get("category_id") or "")
            if not category_id:
                continue
            category_key = str(category.get("category_key") or "")
            self.crawl_audio_category(category_id=category_id, category_key=category_key)

    def fetch_collections(self) -> list[dict]:
        payload = {"scene": 0}
        response = self.client.post_json(
            "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collections",
            payload=payload,
            headers={"Business-Sign-Version": "v2"},
        )
        data, raw_path = self.parse_response_or_save_raw(response, "music_collections.json")

        collections = extract_collection_items(data)
        for collection in collections:
            collection_id = str(collection.get("id") or "")
            if not collection_id:
                continue
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                collection_id=collection_id,
                category_name=str(collection.get("display_name") or collection.get("name") or ""),
                raw_json_path=str(raw_path),
            )
        return collections

    def fetch_audio_categories(self) -> list[dict]:
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
        data, raw_path = self.parse_response_or_save_raw(response, "music_audio_panel.json")

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

    def crawl_collection(self, collection_id: str) -> None:
        offset = 0
        page_index = 1

        while True:
            payload = {
                "count": self.page_size,
                "filter_commercial": False,
                "filter_paid_type": [],
                "id": int(collection_id),
                "offset": offset,
                "only_enterprise_commercial": False,
                "scene": 0,
            }
            response = self.client.post_json(
                "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/get_collection_songs",
                payload=payload,
                headers={"Business-Sign-Version": "v2"},
            )
            raw_name = f"collection_{collection_id}_page_{page_index}.json"
            data, raw_path = self.parse_response_or_save_raw(response, raw_name)

            songs = iter_song_items(data)
            if not songs:
                break

            for song in songs:
                resource_id = str(song.get("id") or song.get("web_id") or "")
                if not resource_id:
                    continue
                self.repo.upsert_item(
                    crawler_name=self.crawler_name,
                    resource_id=resource_id,
                    title=str(song.get("title") or ""),
                    collection_id=collection_id,
                    effect_type="4",
                    panel="music_collection",
                    source_kind="music_song",
                    raw_list_path=str(raw_path),
                    item_json=song,
                )
                self.add_song_downloads(resource_id, song)
                self.fetch_detail(
                    resource_id=resource_id,
                    raw_path=str(raw_path),
                    collection_id=collection_id,
                    effect_type="4",
                    source="3",
                )

            self.repo.upsert_state(self.crawler_name, f"collection:{collection_id}:offset", str(offset))

            if not get_has_more(data):
                break
            next_offset = get_next_offset(data)
            if next_offset is None or next_offset <= offset:
                break
            offset = next_offset
            page_index += 1

    def crawl_audio_category(self, category_id: str, category_key: str) -> None:
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
            raw_name = f"music_audio_{category_id}_page_{page_index}.json"
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
                    effect_type=effect_type or "4",
                    panel=self.panel,
                    category_id=category_id,
                    source_kind="music_audio_category",
                    raw_list_path=str(raw_path),
                    item_json=item,
                )
                self.add_common_downloads(resource_id, common)
                self.fetch_detail(
                    resource_id=resource_id,
                    raw_path=str(raw_path),
                    category_id=category_id,
                    effect_type=effect_type or "4",
                    source=source or "1",
                )

            self.repo.upsert_state(self.crawler_name, f"audio_category:{category_id}:offset", str(offset))

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
        collection_id: str = "",
        category_id: str = "",
        effect_type: str = "4",
        source: str = "3",
    ) -> None:
        payload = {
            "app_id": 3704,
            "items": [
                {
                    "effect_type": int(effect_type or "4"),
                    "id": resource_id,
                    "source": int(source or "3"),
                }
            ],
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
            "https://lv-api-sinfonlineb.ulikecam.com/artist/v1/effect/mget_item",
            payload=payload,
        )
        raw_name = f"music_detail_{resource_id}.json"
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
                collection_id=collection_id,
                category_id=category_id,
                source_kind="music_song_detail",
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=common,
                detail_json=item,
            )
            self.add_common_downloads(detail_id, common)

            song = item.get("song") or {}
            if isinstance(song, dict):
                self.add_song_downloads(detail_id, song)

    def add_song_downloads(self, resource_id: str, song: dict) -> None:
        preview_url = song.get("preview_url")
        if preview_url:
            self.repo.add_download(resource_id, str(preview_url), "preview_audio")
        beats = song.get("beats") or {}
        if isinstance(beats, dict):
            for key in ["beat_url", "melody_url"]:
                if beats.get(key):
                    self.repo.add_download(resource_id, str(beats[key]), key)

    def add_common_downloads(self, resource_id: str, common: dict) -> None:
        for index, url in enumerate(common.get("item_urls", []) or []):
            if url:
                self.repo.add_download(resource_id, str(url), f"primary_asset_{index}")
        download_info = common.get("download_info") or {}
        if isinstance(download_info, dict) and download_info.get("url"):
            self.repo.add_download(resource_id, str(download_info["url"]), "download_info")
