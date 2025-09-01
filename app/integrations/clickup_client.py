from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


class ClickUpError(Exception):
    """Raised when ClickUp API calls fail after retries."""


class ClickUpClient:
    """
    Minimal ClickUp API wrapper for creating tasks and subtasks.

    - Uses personal token auth: `Authorization: <token>` (no 'Bearer' prefix).
    - Retries on network errors and 5xx responses with backoff.
    - Returns parsed JSON (dict) on success.
    """

    BASE_URL = "https://api.clickup.com/api/v2"

    def __init__(self, token: str, list_id: str, default_status: Optional[str] = None,
                 timeout: float = 10.0, max_retries: int = 3) -> None:
        self.token = (token or "").strip()
        self.list_id = (list_id or "").strip()
        self.default_status = (default_status or "").strip() or None
        self.timeout = timeout
        self.max_retries = max_retries

    @classmethod
    def from_settings(cls) -> "ClickUpClient":
        s = get_settings()
        return cls(
            token=s.CLICKUP_TOKEN,
            list_id=s.CLICKUP_LIST_ID,
            default_status=s.CLICKUP_DEFAULT_STATUS,
        )

    def is_configured(self) -> bool:
        return bool(self.token and self.list_id)

    # -------------------------------
    # Public API
    # -------------------------------

    def create_task(
        self,
        name: str,
        description: Optional[str] = None,
        due_date_ms: Optional[int] = None,
        parent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a task in the configured List. If `parent` is provided, ClickUp will create a subtask.

        Returns the ClickUp task object (dict) on success.
        Raises ClickUpError on failure (after retries).
        """
        if not self.is_configured():
            log.info("tm_skipped", reason="missing_token_or_list_id")
            return {"skipped": True, "reason": "missing_token_or_list_id"}

        payload: Dict[str, Any] = {
            "name": name,
        }
        if description:
            payload["description"] = description
        if due_date_ms is not None:
            payload["due_date"] = due_date_ms
        if parent:
            payload["parent"] = parent
        if self.default_status:
            # Optional: set initial status if your List allows it
            payload["status"] = self.default_status

        path = f"/list/{self.list_id}/task"
        data = self._post_with_retries(path, json=payload)
        return data

    def create_subtask(
        self,
        parent_task_id: str,
        name: str,
        description: Optional[str] = None,
        due_date_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Convenience wrapper to create a subtask under an existing parent task."""
        return self.create_task(
            name=name,
            description=description,
            due_date_ms=due_date_ms,
            parent=parent_task_id,
        )

    # -------------------------------
    # Internal helpers
    # -------------------------------

    def _headers(self) -> Dict[str, str]:
        # Personal token style: no 'Bearer' prefix
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }

    def _post_with_retries(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:
        """POST with basic retry/backoff on network/5xx errors."""
        url = f"{self.BASE_URL}{path}"
        backoffs = [0.5, 2.0, 5.0]

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=self._headers(), json=json)
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    log.info("tm_post_ok", url=url, status=resp.status_code)
                    return data

                # Retry on 429/5xx; log 4xx as errors without retry except 429
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    log.warning(
                        "tm_post_retryable_http_error",
                        url=url,
                        status=resp.status_code,
                        body=_safe_text(resp),
                        attempt=attempt,
                    )
                else:
                    log.error(
                        "tm_post_http_error",
                        url=url,
                        status=resp.status_code,
                        body=_safe_text(resp),
                        attempt=attempt,
                    )
                    break  # do not retry non-retryable 4xx

            except httpx.HTTPError as exc:
                last_exc = exc
                log.warning(
                    "tm_post_network_error",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )

            # Backoff before next attempt (if any)
            if attempt < self.max_retries:
                time.sleep(backoffs[min(attempt - 1, len(backoffs) - 1)])

        # If we reach here, we failed all attempts
        message = f"ClickUp POST failed after {self.max_retries} attempts"
        if last_exc:
            message += f": {last_exc}"
        raise ClickUpError(message)


def _safe_text(resp: httpx.Response) -> str:
    try:
        return resp.text
    except Exception:
        return "<unreadable>"
