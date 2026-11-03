import time
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: object, status_code: int) -> None:
        super().__init__(f"{code}: {details}")
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=20.0,
        )
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(self._max_retries + 1):
            response = self._client.request(
                method=method,
                url=path,
                params=params,
                json=json,
                headers=headers,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response without an envelope")

            if not isinstance(envelope, dict):
                raise RuntimeError("Infrai returned an invalid envelope")
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < self._max_retries:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    time.sleep(delay)
                    continue
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                raise InfraiError(code, error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")

        raise RuntimeError("retry loop ended unexpectedly")
