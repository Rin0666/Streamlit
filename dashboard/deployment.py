"""Small client for the separate, host-side deployment service."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DeploymentClientError(RuntimeError):
    pass


class DeploymentClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: int = 10):
        self.base_url = (base_url or os.environ.get("DEPLOYMENT_SERVICE_URL", "")).rstrip("/")
        self.token = token or os.environ.get("DEPLOYMENT_SERVICE_TOKEN", "")
        self.timeout = timeout
        if not self.base_url or not self.token:
            raise DeploymentClientError("Application updates are not configured on this server.")

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path, data=body, method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
                if not isinstance(result, dict):
                    raise ValueError
                return result
        except HTTPError as error:
            if error.code == 409:
                raise DeploymentClientError("Another deployment is already running.") from None
            raise DeploymentClientError("The deployment service rejected the request.") from None
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            raise DeploymentClientError("The deployment service is unavailable or returned an invalid response.") from None

    def version(self) -> dict:
        return self._request("GET", "/version")

    def deploy(self, requested_by: str) -> dict:
        return self._request("POST", "/deploy", {"requested_by": requested_by})

    def status(self, deployment_id: str) -> dict:
        return self._request("GET", f"/deploy/{deployment_id}")
