from __future__ import annotations

import json
from typing import Any

def ensure_json(value: Any | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def unwrap_response_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}

    response_payload = data.get("response")
    if isinstance(response_payload, str) and response_payload.strip():
        try:
            parsed = json.loads(response_payload)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    inner = data.get("data")
    if isinstance(inner, dict):
        return inner

    return data


def iter_effect_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    if "effect_item_list" in payload:
        return payload.get("effect_item_list") or []
    return []


def iter_template_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    for key in ["item_list", "templates"]:
        items = payload.get(key)
        if isinstance(items, list):
            return items
    return []


def iter_aigc_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    items = payload.get("aigc_item_list")
    if isinstance(items, list):
        return items
    return []


def get_has_more(data: dict[str, Any]) -> bool:
    payload = unwrap_response_payload(data)
    return bool(payload.get("has_more"))


def get_next_offset(data: dict[str, Any]) -> int | None:
    payload = unwrap_response_payload(data)
    value = payload.get("next_offset")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_new_cursor(data: dict[str, Any]) -> str | None:
    payload = unwrap_response_payload(data)
    value = payload.get("new_cursor")
    if value is None:
        return None
    return str(value)


def extract_collection_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    collections = payload.get("collections")
    if isinstance(collections, list):
        return collections
    return []


def extract_categories(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    categories = payload.get("categories")
    if isinstance(categories, list):
        return categories
    return []


def extract_category_resources(data: dict[str, Any], category_id: str) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    mapping = payload.get("category_resources")
    if not isinstance(mapping, dict):
        return []
    bucket = mapping.get(str(category_id))
    if not isinstance(bucket, dict):
        return []
    items = bucket.get("effect_item_list")
    if isinstance(items, list):
        return items
    return []


def iter_song_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = unwrap_response_payload(data)
    songs = payload.get("songs")
    if isinstance(songs, list):
        return songs
    return []


def get_effect_item_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    common = item.get("common_attr") if isinstance(item, dict) else {}
    if not isinstance(common, dict):
        common = {}
    resource_id = str(common.get("id") or common.get("effect_id") or item.get("id") or "")
    effect_type = str(common.get("effect_type") or item.get("effect_type") or "")
    source = str(common.get("source") or item.get("source") or "")
    return resource_id, effect_type, source


def extract_common_attr(item: dict[str, Any]) -> dict[str, Any]:
    common = item.get("common_attr")
    if isinstance(common, dict):
        return common
    return {}


def extract_item_category_ids(item: dict[str, Any]) -> list[str]:
    common = extract_common_attr(item)
    values = common.get("category_ids")
    if not isinstance(values, list):
        values = item.get("category_ids")
    if not isinstance(values, list):
        return []

    category_ids: list[str] = []
    for value in values:
        if value is None:
            continue
        category_id = str(value).strip()
        if category_id:
            category_ids.append(category_id)
    return category_ids


def extract_recipe_material_items(detail_data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in iter_effect_items(detail_data):
        recipe = item.get("recipe")
        if not isinstance(recipe, dict):
            continue
        materials = recipe.get("materials") or []
        if isinstance(materials, list):
            results.extend(material for material in materials if isinstance(material, dict))
    return results


def extract_depend_resources(detail_data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    nodes = iter_effect_items(detail_data) + extract_recipe_material_items(detail_data)
    for item in nodes:
        for key in ["text_template", "subtitle_template"]:
            payload = item.get(key)
            if isinstance(payload, dict):
                depend_list = payload.get("depend_resource_list") or []
                if isinstance(depend_list, list):
                    results.extend(dep for dep in depend_list if isinstance(dep, dict))

        depend_list = item.get("depend_resource_list") or []
        if isinstance(depend_list, list):
            results.extend(dep for dep in depend_list if isinstance(dep, dict))

        common = extract_common_attr(item)
        sdk_extra = common.get("sdk_extra")
        if isinstance(sdk_extra, str) and sdk_extra.strip():
            try:
                parsed = json.loads(sdk_extra)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                nested = parsed.get("depend_resource_list") or []
                if isinstance(nested, list):
                    results.extend(dep for dep in nested if isinstance(dep, dict))

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for dep in results:
        dep_id = str(dep.get("resource_id") or "")
        dep_type = str(dep.get("type") or "")
        if dep_id:
            deduped[(dep_id, dep_type)] = dep
    return list(deduped.values())


def extract_recipe_downloads(detail_data: dict[str, Any]) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for item in iter_effect_items(detail_data):
        recipe = item.get("recipe")
        if not isinstance(recipe, dict):
            continue

        video = recipe.get("video")
        if isinstance(video, dict):
            for video_group_name, video_payload in video.items():
                if isinstance(video_payload, dict):
                    for key in ["video_url", "url", "play_url"]:
                        if video_payload.get(key):
                            results.append((f"recipe_video_{video_group_name}_{key}", str(video_payload[key])))
                elif video_group_name in {"url", "play_url", "video_url"} and video_payload:
                    results.append((f"recipe_video_{video_group_name}", str(video_payload)))

        materials = recipe.get("materials") or []
        for material in materials:
            if not isinstance(material, dict):
                continue
            common = extract_common_attr(material)
            material_id = str(common.get("id") or common.get("effect_id") or material.get("id") or "")
            for key in ["item_urls", "download_info"]:
                value = common.get(key)
                if key == "item_urls" and isinstance(value, list):
                    for index, url in enumerate(value):
                        if url:
                            prefix = material_id or "unknown"
                            results.append((f"recipe_material_{prefix}_item_url_{index}", str(url)))
                elif key == "download_info" and isinstance(value, dict) and value.get("url"):
                    prefix = material_id or "unknown"
                    results.append((f"recipe_material_{prefix}_download_info", str(value["url"])))
    return results
