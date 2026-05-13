from __future__ import annotations

from .common import extract_collection_items, get_has_more, get_new_cursor, iter_template_items
from ..base import BaseCrawler


class TemplateCrawler(BaseCrawler):
    crawler_name = "template"
    page_size = 32
    collection_endpoint_key = "replicate_get_collections_template"
    list_endpoint_key = "replicate_get_collection_templates_template"
    detail_endpoint_key = "replicate_multi_get_templates"

    def run(self) -> None:
        collections = self.fetch_collections()
        if not collections:
            return

        for collection in collections:
            collection_id = str(collection.get("id") or "")
            if not collection_id:
                continue
            self.crawl_collection(collection_id)

    def fetch_collections(self) -> list[dict]:
        payload = {
            "collection_type": "1",
            "sdk_version": "167.0.0",
        }
        response = self.client.post_replicate_json(
            "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/replicate/get_collections",
            payload=payload,
            endpoint_key=self.collection_endpoint_key,
        )
        data, raw_path = self.parse_response_or_save_raw(response, "template_collections.json")

        collections = extract_collection_items(data)
        for collection in collections:
            collection_id = str(collection.get("id") or "")
            if not collection_id:
                continue
            self.repo.upsert_category(
                crawler_name=self.crawler_name,
                collection_id=collection_id,
                category_name=str(collection.get("display_name") or ""),
                raw_json_path=str(raw_path),
            )
        return collections

    def crawl_collection(self, collection_id: str) -> None:
        cursor = self.repo.get_state(self.crawler_name, f"collection:{collection_id}:cursor") or "0"
        page_index = 1

        while True:
            payload = {
                "id": int(collection_id),
                "cursor": cursor,
                "count": self.page_size,
                "client_rcm_params": "",
                "client_tab": "",
                "daily_feed_recommend_req_index": 1,
                "enable_server_impression_dedup": False,
                "enter_from": "",
                "feed_recommend_req_index": 1,
                "filter_paid_template": 0,
                "scene": "edit_page-Template",
                "sdk_version": "167.0.0",
                "filters": {
                    "duration": [],
                    "fragment_count": [],
                    "is_commercial": 0,
                    "screen_style": ["landscape", "portrait"],
                    "sub_category_ids": [],
                },
                "from_group_id": "",
                "new_home_page": False,
            }
            response = self.client.post_replicate_json(
                "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/get_collection_templates",
                payload=payload,
                endpoint_key=self.list_endpoint_key,
            )
            raw_name = f"template_collection_{collection_id}_page_{page_index}.json"
            data, raw_path = self.parse_response_or_save_raw(response, raw_name)

            templates = iter_template_items(data)
            if not templates:
                break

            for template in templates:
                resource_id = str(template.get("template_id") or template.get("id") or "")
                if not resource_id:
                    continue
                self.repo.upsert_item(
                    crawler_name=self.crawler_name,
                    resource_id=resource_id,
                    title=str(template.get("title") or ""),
                    collection_id=collection_id,
                    source_kind="template",
                    raw_list_path=str(raw_path),
                    item_json=template,
                )
                self.add_downloads(resource_id, template)
                self.fetch_detail(resource_id=resource_id, raw_path=str(raw_path), collection_id=collection_id)

            if not get_has_more(data):
                self.repo.upsert_state(self.crawler_name, f"collection:{collection_id}:cursor", cursor)
                break
            new_cursor = get_new_cursor(data)
            if not new_cursor or new_cursor == cursor:
                self.repo.upsert_state(self.crawler_name, f"collection:{collection_id}:cursor", cursor)
                break
            self.repo.upsert_state(self.crawler_name, f"collection:{collection_id}:cursor", new_cursor)
            cursor = new_cursor
            page_index += 1

    def fetch_detail(self, resource_id: str, raw_path: str, collection_id: str) -> None:
        payload = {
            "id": [int(resource_id)],
            "sdk_version": "167.0.0",
        }
        response = self.client.post_replicate_json(
            "https://lv-pc-api-sinfonlineb.ulikecam.com/lv/v1/pc/replicate/multi_get_templates",
            payload=payload,
            endpoint_key=self.detail_endpoint_key,
        )
        raw_name = f"template_detail_{resource_id}.json"
        data, detail_raw_path = self.parse_response_or_save_raw(response, raw_name)

        for template in iter_template_items(data):
            detail_id = str(template.get("template_id") or template.get("id") or "")
            if detail_id != resource_id:
                continue
            self.repo.upsert_item(
                crawler_name=self.crawler_name,
                resource_id=detail_id,
                title=str(template.get("title") or ""),
                collection_id=collection_id,
                source_kind="template_detail",
                raw_list_path=raw_path,
                raw_detail_path=str(detail_raw_path),
                item_json=template,
                detail_json=template,
            )
            self.add_downloads(detail_id, template)

    def add_downloads(self, resource_id: str, template: dict) -> None:
        for key in ["template_url", "video_url", "draft_package_url", "template_json"]:
            value = template.get(key)
            if value:
                self.repo.add_download(resource_id, str(value), key)
        origin_video_info = template.get("origin_video_info") or {}
        if isinstance(origin_video_info, dict):
            for key in ["video_url", "watermark_video_url"]:
                if origin_video_info.get(key):
                    self.repo.add_download(resource_id, str(origin_video_info[key]), f"origin_{key}")
