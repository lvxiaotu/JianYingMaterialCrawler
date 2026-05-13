from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from inspect import stack
from typing import Any
from urllib.parse import urlencode

import requests

from .config import AppConfig
from .request_logging import append_request_log


@dataclass
class ApiResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    json_data: Any | None


class ResponseParseError(RuntimeError):
    def __init__(self, message: str, response: "ApiResponse") -> None:
        super().__init__(message)
        self.response = response


class JianyingHttpClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.trust_env = False

    def build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = self.config.default_headers
        auth = self.config.auth
        replicate_auth = self.config.replicate_auth

        if auth.get("cookie"):
            headers["Cookie"] = auth["cookie"]
        elif replicate_auth.get("cookie"):
            headers["Cookie"] = str(replicate_auth["cookie"])
        if auth.get("sign"):
            headers["sign"] = auth["sign"]
        if auth.get("x_ss_stub"):
            headers["x-ss-stub"] = auth["x_ss_stub"]
        if auth.get("x_tt_trace_id"):
            headers["x-tt-trace-id"] = auth["x_tt_trace_id"]
        if auth.get("x_helios"):
            headers["X-Helios"] = auth["x_helios"]
        if auth.get("x_medusa"):
            headers["X-Medusa"] = auth["x_medusa"]
        if auth.get("business_sign_version"):
            headers["Business-Sign-Version"] = auth["business_sign_version"]

        headers["device-time"] = str(int(time.time()))

        if extra_headers:
            headers.update(extra_headers)
        return headers

    def build_replicate_headers(
        self,
        payload: dict[str, Any],
        endpoint_key: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        replicate_auth = self.config.replicate_auth
        headers = self.config.default_headers

        headers.setdefault("Content-Type", "application/json")
        headers["App-Sdk-Version"] = str(replicate_auth.get("app_sdk_version") or "167.0.0")
        headers["appid"] = str(replicate_auth.get("appid") or "3704")
        headers["appvr"] = str(replicate_auth.get("appvr") or headers.get("appvr") or "10.5.0")
        headers["ch"] = str(replicate_auth.get("channel_header") or "jianyingpro_0")
        headers["lan"] = str(replicate_auth.get("lan") or headers.get("lan") or "zh-hans")
        headers["loc"] = str(replicate_auth.get("loc") or headers.get("loc") or "cn")
        headers["pf"] = str(replicate_auth.get("pf") or headers.get("pf") or "4")
        headers["sign-ver"] = str(replicate_auth.get("sign_ver") or headers.get("sign-ver") or "1")
        headers["tdid"] = str(replicate_auth.get("tdid") or headers.get("tdid") or "")
        headers["X-SS-DP"] = str(replicate_auth.get("x_ss_dp") or headers.get("X-SS-DP") or "3704")
        headers["User-Agent"] = str(replicate_auth.get("user_agent") or headers.get("User-Agent") or "")
        headers["Accept-Encoding"] = str(replicate_auth.get("accept_encoding") or headers.get("Accept-Encoding") or "gzip, deflate")
        headers["X-Neptune"] = str(replicate_auth.get("x_neptune") or "")

        cookie = replicate_auth.get("cookie") or self.config.auth.get("cookie") or ""
        if cookie:
            headers["Cookie"] = str(cookie)

        device_time_map = replicate_auth.get("device_time_by_endpoint") or {}
        default_device_time = replicate_auth.get("device_time")
        device_time = device_time_map.get(endpoint_key, default_device_time)
        if device_time:
            headers["device-time"] = str(device_time)
        else:
            headers["device-time"] = str(int(time.time()))

        trace_map = replicate_auth.get("x_tt_trace_id_by_endpoint") or {}
        trace_id = trace_map.get(endpoint_key)
        if not trace_id:
            trace_id = self._generate_trace_id()
        headers["x-tt-trace-id"] = str(trace_id)

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["x-ss-stub"] = self.compute_stub(body)

        sign_map = replicate_auth.get("sign_by_endpoint") or {}
        sign = sign_map.get(endpoint_key) or replicate_auth.get("sign")
        if sign:
            headers["sign"] = str(sign)

        if extra_headers:
            headers.update(extra_headers)
        return headers

    def build_url(self, base_url: str, query: dict[str, Any] | None = None) -> str:
        merged = self.config.default_query.copy()
        if query:
            merged.update({k: v for k, v in query.items() if v is not None})
        return f"{base_url}?{urlencode(merged, doseq=True)}"

    def post_json(
        self,
        base_url: str,
        payload: dict[str, Any],
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        log_context: dict[str, Any] | None = None,
    ) -> ApiResponse:
        url = self.build_url(base_url, query)
        response = None
        last_error: Exception | None = None
        resolved_log_context = self._resolve_log_context(log_context, url, payload)

        for attempt in range(self.config.retry_count + 1):
            started_at = time.perf_counter()
            self._log_request_event(
                event="request_start",
                log_context=resolved_log_context,
                method="POST",
                endpoint=base_url,
                url=url,
                attempt=attempt + 1,
                max_attempts=self.config.retry_count + 1,
            )
            try:
                response = self.session.post(
                    url,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers=self.build_headers(headers),
                    timeout=self.config.request_timeout_seconds,
                )
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._log_request_event(
                    event="request_success",
                    log_context=resolved_log_context,
                    method="POST",
                    endpoint=base_url,
                    url=url,
                    attempt=attempt + 1,
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    response_bytes=len(response.content or b""),
                )
                break
            except Exception as exc:
                last_error = exc
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                if attempt >= self.config.retry_count:
                    self._log_request_event(
                        event="request_failed",
                        log_context=resolved_log_context,
                        method="POST",
                        endpoint=base_url,
                        url=url,
                        attempt=attempt + 1,
                        elapsed_ms=elapsed_ms,
                        error=str(exc),
                    )
                    raise
                self._log_request_event(
                    event="request_retry",
                    log_context=resolved_log_context,
                    method="POST",
                    endpoint=base_url,
                    url=url,
                    attempt=attempt + 1,
                    elapsed_ms=elapsed_ms,
                    retry_backoff_seconds=self.config.retry_backoff_seconds,
                    error=str(exc),
                )
                time.sleep(self.config.retry_backoff_seconds)

        if response is None and last_error:
            raise last_error

        json_data = None
        try:
            json_data = response.json()
        except Exception:
            json_data = None

        return ApiResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response.text,
            json_data=json_data,
        )

    def post_replicate_json(
        self,
        base_url: str,
        payload: dict[str, Any],
        endpoint_key: str,
        headers: dict[str, str] | None = None,
        log_context: dict[str, Any] | None = None,
    ) -> ApiResponse:
        response = None
        last_error: Exception | None = None
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        resolved_log_context = self._resolve_log_context(log_context, base_url, payload, endpoint_key=endpoint_key)

        for attempt in range(self.config.retry_count + 1):
            started_at = time.perf_counter()
            self._log_request_event(
                event="request_start",
                log_context=resolved_log_context,
                method="POST",
                endpoint=endpoint_key,
                url=base_url,
                attempt=attempt + 1,
                max_attempts=self.config.retry_count + 1,
            )
            try:
                response = self.session.post(
                    base_url,
                    data=body,
                    headers=self.build_replicate_headers(payload, endpoint_key, headers),
                    timeout=self.config.request_timeout_seconds,
                )
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._log_request_event(
                    event="request_success",
                    log_context=resolved_log_context,
                    method="POST",
                    endpoint=endpoint_key,
                    url=base_url,
                    attempt=attempt + 1,
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    response_bytes=len(response.content or b""),
                )
                break
            except Exception as exc:
                last_error = exc
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                if attempt >= self.config.retry_count:
                    self._log_request_event(
                        event="request_failed",
                        log_context=resolved_log_context,
                        method="POST",
                        endpoint=endpoint_key,
                        url=base_url,
                        attempt=attempt + 1,
                        elapsed_ms=elapsed_ms,
                        error=str(exc),
                    )
                    raise
                self._log_request_event(
                    event="request_retry",
                    log_context=resolved_log_context,
                    method="POST",
                    endpoint=endpoint_key,
                    url=base_url,
                    attempt=attempt + 1,
                    elapsed_ms=elapsed_ms,
                    retry_backoff_seconds=self.config.retry_backoff_seconds,
                    error=str(exc),
                )
                time.sleep(self.config.retry_backoff_seconds)

        if response is None and last_error:
            raise last_error

        json_data = None
        try:
            json_data = response.json()
        except Exception:
            json_data = None

        return ApiResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response.text,
            json_data=json_data,
        )

    @staticmethod
    def compute_stub(body: bytes) -> str:
        import hashlib

        return hashlib.md5(body).hexdigest()

    @staticmethod
    def _generate_trace_id() -> str:
        chars = "0123456789abcdef"
        token = "".join(random.choice(chars) for _ in range(32))
        return f"00-{token}-{token[:16]}01"

    def _resolve_log_context(
        self,
        log_context: dict[str, Any] | None,
        url: str,
        payload: dict[str, Any],
        endpoint_key: str = "",
    ) -> dict[str, Any]:
        resolved = dict(log_context or {})
        resolved.setdefault("crawler_name", self._guess_crawler_name())
        resolved.setdefault("request_name", self._guess_request_name())
        resolved.setdefault("endpoint_key", endpoint_key)
        resolved.setdefault("payload_summary", self._summarize_payload(payload))
        resolved.setdefault("url_path", url)
        return resolved

    def _log_request_event(
        self,
        event: str,
        log_context: dict[str, Any],
        **fields: object,
    ) -> None:
        crawler_name = str(log_context.get("crawler_name") or "_unknown")
        merged_fields = dict(log_context)
        merged_fields.update(fields)
        merged_fields.pop("crawler_name", None)
        append_request_log(
            self.config,
            scope="crawl",
            crawler_name=crawler_name,
            event=event,
            **merged_fields,
        )

    def _guess_crawler_name(self) -> str:
        for frame in stack():
            instance = frame.frame.f_locals.get("self")
            crawler_name = getattr(instance, "crawler_name", "")
            if isinstance(crawler_name, str) and crawler_name:
                return crawler_name
        return "_unknown"

    def _guess_request_name(self) -> str:
        for frame in stack():
            instance = frame.frame.f_locals.get("self")
            crawler_name = getattr(instance, "crawler_name", "")
            if isinstance(crawler_name, str) and crawler_name:
                return frame.function
        return "unknown_request"

    def _summarize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "keys": sorted(payload.keys()),
        }
        for key in ("category_id", "category_key", "offset", "count", "cursor", "collection_id", "panel", "scene"):
            if key in payload:
                summary[key] = payload.get(key)
        items = payload.get("items")
        if isinstance(items, list):
            summary["items_count"] = len(items)
        return summary


def validate_response_json(response: ApiResponse) -> dict[str, Any]:
    if response.status_code >= 400:
        raise ResponseParseError(f"HTTP {response.status_code}", response)

    data = response.json_data if isinstance(response.json_data, dict) else {}
    if not data:
        raise ResponseParseError("Response JSON parse failed", response)

    ret = data.get("ret")
    if ret is not None and str(ret) not in {"0", "success"}:
        errmsg = str(data.get("errmsg") or data.get("message") or f"ret={ret}")
        raise ResponseParseError(f"API error: {errmsg}", response)

    response_payload = data.get("response")
    if isinstance(response_payload, str) and response_payload.strip():
        try:
            parsed = json.loads(response_payload)
        except json.JSONDecodeError as exc:
            raise ResponseParseError(f"Inner response JSON parse failed: {exc}", response) from exc
        if not isinstance(parsed, dict):
            raise ResponseParseError("Inner response is not a JSON object", response)

    return data
