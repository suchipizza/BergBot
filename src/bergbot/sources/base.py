"""Adapter contract shared by every data source (work order §3).

Boundary: adapters normalise external data into `Record`s carrying both timestamps. They never interpret
safety, never guess open/closed, and never bundle data whose licence is not recorded in docs/data-licences.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Query(BaseModel):
    """Generic adapter query. Adapters document which fields they read."""

    kind: str
    text: str | None = None
    bbox: tuple[float, float, float, float] | None = Field(
        default=None, description="minlon,minlat,maxlon,maxlat WGS84"
    )
    geometry: dict[str, Any] | None = Field(default=None, description="GeoJSON geometry (WGS84)")
    date: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    time_window: tuple[str, str] | None = Field(default=None, description="ISO datetimes (start, end)")
    params: dict[str, Any] = Field(default_factory=dict)


class Record(BaseModel):
    """One normalised item from a source. `source_ts` = when the source says the data is from;
    `retrieved_ts` = when Bergbot fetched it. Both are mandatory (SR-1)."""

    source_id: str
    kind: str
    payload: dict[str, Any]
    source_ts: datetime | None = Field(
        default=None, description="None only when the source publishes no timestamp"
    )
    retrieved_ts: datetime = Field(default_factory=utcnow)
    url: str | None = None
    original_span: str | None = Field(default=None, description="verbatim source text, ≤ 15 words")
    licence_note: str | None = None


class Freshness(BaseModel):
    source_ts: datetime | None
    retrieved_ts: datetime | None
    ttl_s: int


class Licence(BaseModel):
    name: str
    redistribution: bool
    attribution: str
    url: str | None = None


class Health(BaseModel):
    ok: bool
    latency_ms: int | None = None
    last_success_ts: datetime | None = None
    note: str | None = None
    cache_age_s: int | None = None


@runtime_checkable
class SourceAdapter(Protocol):
    id: str  # e.g. "ch.meteoswiss"
    kinds: ClassVar[tuple[str, ...]]  # query kinds this adapter answers

    def fetch(self, query: Query) -> list[Record]: ...
    def freshness(self) -> Freshness: ...
    def licence(self) -> Licence: ...
    def health(self) -> Health: ...


class SourceUnavailable(RuntimeError):
    """Raised when a source cannot be reached and no cache exists. Callers turn this into
    a 'could not verify X' finding (FR-D5) — never into silence."""

    def __init__(self, source_id: str, what: str, cause: BaseException | None = None) -> None:
        super().__init__(f"{source_id}: could not fetch {what}" + (f" ({cause})" if cause else ""))
        self.source_id = source_id
        self.what = what
        self.cause = cause
