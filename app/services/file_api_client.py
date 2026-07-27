from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


class FileApiError(RuntimeError):
    pass


class RateLimitError(FileApiError):
    def __init__(self, status_code: int, retry_after_seconds: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class FileApiClient:
    def __init__(self, base_url: str, candidate_id: str = "", timeout_seconds: int = 30) -> None:
        if not base_url:
            raise FileApiError("EXTERNAL_API_BASE_URL is not configured")

        headers = {}
        if candidate_id:
            headers["X-Candidate-Id"] = candidate_id

        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def get_names(self) -> list[str]:
        response = self._client.get("/api/files/names")
        self._raise_for_response(response)
        data = response.json()
        if isinstance(data, list):
            return [str(item) for item in data]
        if isinstance(data, dict):
            for key in ("names", "files", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return [str(item) for item in value]
        raise FileApiError("names endpoint returned an unsupported response shape")

    def download(self, names: list[str]) -> bytes:
        response = self._post_with_payload_fallback("/api/files/download", names)
        return response.content

    def mark_downloaded(self, names: list[str]) -> None:
        self._post_with_payload_fallback("/api/files/downloaded", names)

    def _post_with_payload_fallback(self, path: str, names: list[str]) -> httpx.Response:
        attempts: list[Callable[[], httpx.Response]] = [
            lambda: self._client.post(path, json={"names": names}),
            lambda: self._client.post(path, json=names),
        ]

        last_response: httpx.Response | None = None
        for attempt in attempts:
            response = attempt()
            if response.status_code not in (400, 422):
                self._raise_for_response(response)
                return response
            last_response = response

        assert last_response is not None
        self._raise_for_response(last_response)
        return last_response

    def _raise_for_response(self, response: httpx.Response) -> None:
        if response.status_code in (429, 403):
            retry_after = _retry_after_seconds(response.headers.get("Retry-After"), response.status_code)
            raise RateLimitError(
                response.status_code,
                retry_after,
                f"external API returned {response.status_code}; retry after {retry_after} seconds",
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _response_detail(response)
            raise FileApiError(f"external API request failed: {response.status_code} {detail}") from exc


def _retry_after_seconds(header_value: str | None, status_code: int) -> int:
    if not header_value:
        return 1800 if status_code == 403 else 10

    if header_value.isdigit():
        return max(1, int(header_value))

    try:
        retry_at = parsedate_to_datetime(header_value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(1, int((retry_at - datetime.now(timezone.utc)).total_seconds()))
    except (TypeError, ValueError):
        return 1800 if status_code == 403 else 10


def _response_detail(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]
