"""HTTP fetching with an on-disk cache, offline mode and fixture replay.

Boundary: the only place that performs network I/O for adapters. Every adapter receives a `Fetcher`;
production uses `HttpFetcher` (httpx + disk cache + TTL), tests use `FixtureFetcher` (recorded responses).
Offline mode (`BERGBOT_OFFLINE=1` or `offline=True`) serves cache only and raises `SourceUnavailable`
otherwise — never a silent empty result (FR-D5).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from bergbot import __version__
from bergbot.paths import cache_dir
from bergbot.sources.base import SourceUnavailable

USER_AGENT = f"bergbot/{__version__} (+https://github.com/suchipizza/BergBot)"


@dataclass
class FetchResult:
    data: Any
    retrieved_ts: datetime
    from_cache: bool
    url: str
    latency_ms: int = 0
    raw: bytes | None = None


class Fetcher(Protocol):
    def get_json(
        self,
        source_id: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        *,
        ttl_s: int = 0,
        method: str = "GET",
        data: str | None = None,
        what: str = "data",
    ) -> FetchResult: ...

    def get_bytes(self, source_id: str, url: str, *, ttl_s: int = 0, what: str = "bytes") -> FetchResult: ...


def _key(url: str, params: Mapping[str, Any] | None, data: str | None) -> str:
    canon = json.dumps(
        [url, sorted((params or {}).items(), key=lambda kv: kv[0]), data], ensure_ascii=False, default=str
    )
    return hashlib.sha256(canon.encode()).hexdigest()[:32]


def is_offline() -> bool:
    return os.environ.get("BERGBOT_OFFLINE", "") not in ("", "0", "false")


@dataclass
class HttpFetcher:
    """Live fetcher with per-source disk cache. `record_to` writes every response into a fixture file."""

    offline: bool = False
    timeout_s: float = 30.0
    record_to: Path | None = None
    _client: httpx.Client | None = field(default=None, repr=False)
    _recorded: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def _cache_path(self, source_id: str, key: str) -> Path:
        d = cache_dir() / source_id
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{key}.json"

    def _client_or_new(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout_s, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            )
        return self._client

    def _read_cache(self, path: Path, ttl_s: int, allow_stale: bool) -> FetchResult | None:
        if not path.exists():
            return None
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        age = time.time() - doc["ts"]
        if age <= ttl_s or allow_stale:
            return FetchResult(
                data=doc["data"],
                retrieved_ts=datetime.fromtimestamp(doc["ts"], tz=UTC),
                from_cache=True,
                url=doc["url"],
            )
        return None

    def _write_cache(self, path: Path, url: str, data: Any) -> None:
        try:
            path.write_text(
                json.dumps({"ts": time.time(), "url": url, "data": data}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _record(
        self, source_id: str, url: str, params: Mapping[str, Any] | None, data_body: str | None, data: Any
    ) -> None:
        if self.record_to is None:
            return
        self._recorded.append(
            {
                "source_id": source_id,
                "url": url,
                "params": dict(params or {}),
                "data": data_body,
                "response": data,
            }
        )
        self.record_to.parent.mkdir(parents=True, exist_ok=True)
        self.record_to.write_text(json.dumps(self._recorded, ensure_ascii=False, indent=1), encoding="utf-8")

    def get_json(
        self,
        source_id: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        *,
        ttl_s: int = 0,
        method: str = "GET",
        data: str | None = None,
        what: str = "data",
    ) -> FetchResult:
        key = _key(url, params, data)
        path = self._cache_path(source_id, key)
        offline = self.offline or is_offline()
        cached = self._read_cache(path, ttl_s, allow_stale=offline)
        if cached is not None:
            self._record(source_id, url, params, data, cached.data)
            return cached
        if offline:
            raise SourceUnavailable(source_id, what)
        t0 = time.monotonic()
        try:
            if method == "POST":
                resp = self._client_or_new().post(
                    url,
                    params=params,
                    content=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                resp = self._client_or_new().get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            stale = self._read_cache(path, ttl_s, allow_stale=True)
            if stale is not None:
                return stale
            raise SourceUnavailable(source_id, what, e) from e
        latency = int((time.monotonic() - t0) * 1000)
        if ttl_s > 0:
            self._write_cache(path, str(resp.url), payload)
        self._record(source_id, url, params, data, payload)
        return FetchResult(
            data=payload,
            retrieved_ts=datetime.now(tz=UTC),
            from_cache=False,
            url=str(resp.url),
            latency_ms=latency,
        )

    def get_bytes(self, source_id: str, url: str, *, ttl_s: int = 0, what: str = "bytes") -> FetchResult:
        key = _key(url, None, None)
        path = self._cache_path(source_id, key).with_suffix(".bin")
        offline = self.offline or is_offline()
        if path.exists() and (offline or time.time() - path.stat().st_mtime <= ttl_s):
            return FetchResult(
                data=None,
                raw=path.read_bytes(),
                retrieved_ts=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                from_cache=True,
                url=url,
            )
        if offline:
            raise SourceUnavailable(source_id, what)
        t0 = time.monotonic()
        try:
            resp = self._client_or_new().get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceUnavailable(source_id, what, e) from e
        if ttl_s > 0:
            try:
                path.write_bytes(resp.content)
            except OSError:
                pass
        return FetchResult(
            data=None,
            raw=resp.content,
            retrieved_ts=datetime.now(tz=UTC),
            from_cache=False,
            url=url,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )


@dataclass
class FixtureFetcher:
    """Replays responses recorded by `HttpFetcher(record_to=...)`. Unknown requests raise SourceUnavailable,
    which is exactly what the graceful-degradation path must handle."""

    entries: list[dict[str, Any]]
    strict: bool = True

    @staticmethod
    def _load(path: Path) -> list[dict[str, Any]]:
        if path.suffix == ".gz":
            import gzip

            with gzip.open(path, "rt", encoding="utf-8") as fh:
                return list(json.load(fh))
        return list(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_file(cls, path: Path) -> FixtureFetcher:
        return cls(entries=cls._load(path))

    @classmethod
    def from_files(cls, *paths: Path) -> FixtureFetcher:
        entries: list[dict[str, Any]] = []
        for p in paths:
            if p.exists():
                entries.extend(cls._load(p))
        return cls(entries=entries)

    def _match(self, url: str, params: Mapping[str, Any] | None, data: str | None) -> Any:
        want = _key(url, params, data)
        for e in self.entries:
            if _key(e["url"], e.get("params"), e.get("data")) == want:
                return e["response"]
        if self.strict:
            raise KeyError(url)
        # loose: same url and same layer set (GeoAdmin identify), else same url
        layers = (params or {}).get("layers")
        for e in self.entries:
            if e["url"] == url and (layers is None or e.get("params", {}).get("layers") == layers):
                return e["response"]
        raise KeyError(url)

    def get_json(
        self,
        source_id: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        *,
        ttl_s: int = 0,
        method: str = "GET",
        data: str | None = None,
        what: str = "data",
    ) -> FetchResult:
        try:
            payload = self._match(url, params, data)
        except KeyError as e:
            raise SourceUnavailable(source_id, what, e) from e
        return FetchResult(
            data=payload, retrieved_ts=datetime(2026, 9, 8, 20, 0, tzinfo=UTC), from_cache=True, url=url
        )

    def get_bytes(self, source_id: str, url: str, *, ttl_s: int = 0, what: str = "bytes") -> FetchResult:
        raise SourceUnavailable(source_id, what)


_default: HttpFetcher | None = None


def default_fetcher() -> HttpFetcher:
    global _default
    if _default is None:
        _default = HttpFetcher()
    return _default
