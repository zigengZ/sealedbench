"""Small HTTP fetcher that counts downloaded bytes."""

from __future__ import annotations

import urllib.error
import urllib.request


class Fetcher:
    def __init__(self, user_agent: str = "sealedbench/0.1.0"):
        self.user_agent = user_agent
        self.downloaded = 0
        self.calls = 0

    def get(self, url: str, headers: dict | None = None, timeout: float = 90, data: bytes | None = None):
        hdrs = {"User-Agent": self.user_agent}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs)
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                self.downloaded += len(body)
                return resp.status, {k: v for k, v in resp.headers.items()}, body
        except urllib.error.HTTPError as err:
            body = err.read() if err.fp is not None else b""
            self.downloaded += len(body)
            return err.code, {k: v for k, v in err.headers.items()}, body
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            # A refused connection or a timeout is an observation failure.
            # Callers treat HTTP 0 as UNKNOWN, not as a hash mismatch.
            return 0, {"error": str(err)}, b""

    def get_json(self, url: str, timeout: float = 90):
        import json

        status, headers, body = self.get(url, timeout=timeout)
        parsed = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = None
        return status, headers, parsed, body
