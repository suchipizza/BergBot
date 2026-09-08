"""Pydantic models for Bergbot. See package docstring. Geometry is GeoJSON (WGS84 lon/lat[/ele])."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Lang = Literal["en", "fr", "de", "it"]


# ---------- enums ----------


class Activity(StrEnum):
    hiking = "hiking"
    alpine_hiking = "alpine_hiking"
    winter_hiking = "winter_hiking"
    snowshoe = "snowshoe"
    ski_touring = "ski_touring"
    mtb = "mtb"
    trail_running = "trail_running"
    climbing = "climbing"
    unknown = "unknown"


class DifficultySystem(StrEnum):
    sac_t = "sac_t"
    none = "none"


class EvidenceClass(StrEnum):
    A = "A"  # official fact
    B = "B"  # derived fact
    C = "C"  # forecast
    D = "D"  # interpretation
    E = "E"  # judgment required


class Severity(StrEnum):
    critical = "critical"
    important = "important"
    note = "note"


class WarningType(StrEnum):
    trail_closure = "trail_closure"
    diversion = "diversion"
    fire_restriction = "fire_restriction"
    fire_danger = "fire_danger"
    shooting_activity = "shooting_activity"
    shooting_zone = "shooting_zone"
    wildlife_quiet_zone = "wildlife_quiet_zone"
    protected_area = "protected_area"
    guardian_dogs = "guardian_dogs"
    exposed_wind = "exposed_wind"
    thunderstorm = "thunderstorm"
    heavy_precipitation = "heavy_precipitation"
    heat = "heat"
    cold = "cold"
    natural_hazard = "natural_hazard"
    avalanche_context = "avalanche_context"
    snow_context = "snow_context"
    lift_unverified = "lift_unverified"
    lift_closed = "lift_closed"
    hut_unverified = "hut_unverified"
    transport_no_return = "transport_no_return"
    transport_tight_return = "transport_tight_return"
    source_unavailable = "source_unavailable"
    difficulty_above_ceiling = "difficulty_above_ceiling"
    exposed_terrain = "exposed_terrain"
    long_day = "long_day"


# Warning types that force the serious register regardless of severity (FR-R2).
SERIOUS_WARNING_TYPES: frozenset[WarningType] = frozenset(
    {
        WarningType.trail_closure,
        WarningType.fire_restriction,
        WarningType.shooting_activity,
        WarningType.avalanche_context,
        WarningType.exposed_wind,
    }
)


class AmenityKind(StrEnum):
    hut = "hut"
    restaurant = "restaurant"
    lift = "lift"
    water = "water"
    shelter = "shelter"
    stop = "stop"
    webcam = "webcam"
    poi = "poi"
    parking = "parking"


class AmenityStatus(StrEnum):
    open = "open"
    closed = "closed"
    unverified = "unverified"
    conflicting = "conflicting"


class PlaceKind(StrEnum):
    address = "address"
    locality = "locality"
    municipality = "municipality"
    stop = "stop"
    lift_station = "lift_station"
    hut = "hut"
    summit = "summit"
    coordinates = "coordinates"
    route_point = "route_point"
    unknown = "unknown"


class SegmentKind(StrEnum):
    exposed = "exposed"
    steep = "steep"
    hazard = "hazard"
    closure = "closure"
    zone = "zone"
    flat = "flat"


class Intent(str, Enum):  # noqa: UP042 — str.find would clash with StrEnum member checks
    find = "find"  # type: ignore[assignment]
    around = "around"
    audit = "audit"
    check = "check"
    export = "export"
    media = "media"
    help = "help"
    chat = "chat"
    emergency = "emergency"
    select = "select"
    modify = "modify"


class QuestionKind(StrEnum):
    none = "none"
    safety = "safety"
    logistics = "logistics"
    terrain = "terrain"
    general = "general"


class Register(StrEnum):
    playful = "playful"
    serious = "serious"


# ---------- evidence ----------


class Evidence(BaseModel):
    """One piece of evidence. `original_span` ≤ 15 words verbatim from the source (FR-D4)."""

    model_config = ConfigDict(extra="forbid")

    cls: EvidenceClass = Field(alias="class")
    source: str = Field(description="Adapter id or source name, e.g. 'ch.closures'")
    url: str | None = None
    source_ts: datetime | None = Field(default=None, description="When the source says the data is from")
    retrieved_ts: datetime = Field(description="When Bergbot fetched it")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    original_span: str | None = None
    original_lang: str | None = None
    translated_summary: str | None = None
    verification: Literal["verified", "unverified", "conflicting", "n/a"] = "n/a"

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("original_span")
    @classmethod
    def _span_short(cls, v: str | None) -> str | None:
        if v is not None and len(v.split()) > 15:
            raise ValueError("original_span must be ≤ 15 words")
        return v


class Segment(BaseModel):
    """A km range on the route, in route distance."""

    model_config = ConfigDict(extra="forbid")

    from_km: float = Field(ge=0)
    to_km: float = Field(ge=0)
    kind: SegmentKind = SegmentKind.hazard
    label: str | None = None
    slope_pct: float | None = None
    aspect_deg: float | None = None

    @model_validator(mode="after")
    def _ordered(self) -> Segment:
        if self.to_km < self.from_km:
            raise ValueError("to_km < from_km")
        return self


class Warning(BaseModel):
    """A safety-relevant finding. Presentation via locales/*/warnings.yaml[type] with `params`."""

    model_config = ConfigDict(extra="forbid")

    type: WarningType
    severity: Severity
    evidence: list[Evidence] = Field(min_length=1)
    affected_segment: Segment | None = None
    params: dict[str, Any] = Field(default_factory=dict, description="Placeholders for the locale template")
    original_text: str | None = Field(default=None, description="Verbatim source text, original language")
    original_lang: str | None = None

    @property
    def forces_serious(self) -> bool:
        return self.severity in (Severity.critical, Severity.important) or self.type in SERIOUS_WARNING_TYPES


# ---------- places & routes ----------


class Place(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: PlaceKind = PlaceKind.unknown
    lon: float
    lat: float
    elevation_m: float | None = None
    canton: str | None = Field(default=None, description="Two-letter code, lower-case (gl, vs, ti…)")
    municipality: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    source: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class Difficulty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: DifficultySystem = DifficultySystem.none
    grade: str | None = Field(default=None, description="T1..T6 for sac_t")
    source: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.0)

    @field_validator("grade")
    @classmethod
    def _grade(cls, v: str | None) -> str | None:
        if v is not None and v not in {"T1", "T2", "T3", "T4", "T5", "T6"}:
            raise ValueError("grade must be T1..T6")
        return v

    @property
    def rank(self) -> int:
        return int(self.grade[1]) if self.grade else 0


class RouteIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    official_id: str | None = None
    network: str | None = Field(default=None, description="e.g. 'ch.swisstopo.swisstlm3d-wanderwege'")
    overlap_pct: float | None = Field(default=None, ge=0, le=100)
    famous: bool = False
    famous_reason: str | None = None


class RouteStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_km: float
    ascent_m: float
    descent_m: float
    duration_min: int
    duration_method: str = "sac"
    min_elevation_m: float | None = None
    max_elevation_m: float | None = None
    n_points: int = 0


class Route(BaseModel):
    """Geometry is a GeoJSON LineString in WGS84 with optional elevation as the third coordinate."""

    model_config = ConfigDict(extra="forbid")

    geometry: dict[str, Any]
    identity: RouteIdentity = Field(default_factory=RouteIdentity)
    activity: Activity = Activity.hiking
    difficulty: Difficulty = Field(default_factory=Difficulty)
    stats: RouteStats | None = None
    segments: list[Segment] = Field(default_factory=list)
    start: Place | None = None
    end: Place | None = None
    is_loop: bool = False
    source_file: str | None = None
    network_member: bool = Field(
        default=False, description="True when every part lies on the official network"
    )
    profile: list[list[float]] | None = Field(default=None, description="[[km, elevation_m], …] every 25 m")

    @field_validator("geometry")
    @classmethod
    def _linestring(cls, g: dict[str, Any]) -> dict[str, Any]:
        if g.get("type") != "LineString":
            raise ValueError("geometry must be a GeoJSON LineString")
        coords = g.get("coordinates") or []
        if len(coords) < 2:
            raise ValueError("LineString needs ≥ 2 coordinates")
        return g

    @property
    def coords(self) -> list[list[float]]:
        return list(self.geometry["coordinates"])

    @property
    def name(self) -> str:
        return self.identity.name or "route"


# ---------- conditions & logistics ----------


class WeatherHour(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: datetime
    km: float | None = Field(default=None, description="Route km the sample applies to")
    elevation_m: float | None = None
    temp_c: float | None = None
    precip_mm: float | None = None
    precip_prob: float | None = None
    wind_kmh: float | None = None
    gust_kmh: float | None = None
    thunder_prob: float | None = None
    summary: str | None = Field(
        default=None, description="Neutral condition code: clear, cloudy, rain, snow, storm…"
    )


class ConditionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime
    hours: list[WeatherHour] = Field(default_factory=list)
    hazards: list[dict[str, Any]] = Field(default_factory=list)
    fire_danger_level: int | None = None
    fire_restrictions: list[dict[str, Any]] = Field(default_factory=list)
    slf_region: str | None = None
    slf_level: int | None = None
    snow_line_m: float | None = None
    sunset: datetime | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list, description="Sources that could not be reached")


class TransportLeg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_stop: str
    to_stop: str
    departure: datetime
    arrival: datetime
    products: list[str] = Field(default_factory=list)
    changes: int = 0
    url: str | None = None


class TransportPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbound: TransportLeg | None = None
    last_return: TransportLeg | None = None
    origin: str | None = None
    start_stop: str | None = None
    end_stop: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    unavailable: bool = False


class Amenity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AmenityKind
    name: str
    lon: float
    lat: float
    km: float | None = None
    distance_m: float | None = None
    status: AmenityStatus = AmenityStatus.unverified
    verification: Literal["verified", "unverified", "conflicting"] = "unverified"
    evidence: list[Evidence] = Field(default_factory=list)
    url: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _status_needs_verification(self) -> Amenity:
        """SR-3: open/closed only when verified evidence exists; never inferred."""
        if self.status in (AmenityStatus.open, AmenityStatus.closed):
            if self.verification != "verified" or not self.evidence:
                raise ValueError("open/closed status requires verification='verified' and evidence")
        if self.status is AmenityStatus.conflicting and self.verification != "conflicting":
            raise ValueError("conflicting status requires verification='conflicting'")
        return self


class Webcam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    lon: float
    lat: float
    distance_m: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class Media(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    type: Literal["official", "gallery", "trip_report", "video", "article"]
    date: str | None = None
    description: str | None = None
    third_party: bool = True


# ---------- constraints & candidates ----------


class Constraint(BaseModel):
    """Structured user constraints (FR-C2). All optional; None = unconstrained."""

    model_config = ConfigDict(extra="forbid")

    region: str | None = Field(default=None, description="Canton code or free text region")
    place: str | None = None
    date: str | None = Field(default=None, description="YYYY-MM-DD")
    start_time: str | None = Field(default=None, description="HH:MM")
    end_time: str | None = None
    max_ascent_m: float | None = None
    max_descent_m: float | None = None
    max_distance_km: float | None = None
    min_distance_km: float | None = None
    max_duration_min: int | None = None
    max_grade: str | None = Field(default=None, description="T1..T6 ceiling")
    origin: str | None = Field(default=None, description="Transport origin, e.g. 'Zürich HB'")
    max_travel_min: int | None = None
    transport_required: bool | None = None
    hut: bool | None = None
    restaurant: bool | None = None
    water: bool | None = None
    dog: bool | None = None
    bivouac: bool | None = None
    kids: bool | None = None
    seniors: bool | None = None
    loop: bool | None = None
    start_place: str | None = None
    end_place: str | None = None
    activity: Activity = Activity.hiking
    lang: Lang | None = None
    free_text: str | None = None

    @field_validator("max_grade")
    @classmethod
    def _grade(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in {"T1", "T2", "T3", "T4", "T5", "T6"}:
            raise ValueError("max_grade must be T1..T6")
        return v.upper() if v else v


class RouteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    warnings: list[Warning] = Field(default_factory=list)
    weather_summary: str | None = None
    transport_summary: str | None = None
    why: dict[str, Any] = Field(default_factory=dict, description="Neutral reasons for the LLM to phrase")


class CandidateSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    constraints: Constraint
    place: Place | None = None
    candidates: list[RouteCandidate]
    lang: Lang = "en"
    unavailable: list[str] = Field(default_factory=list)
    generated_at: datetime


# ---------- audit ----------


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    known: list[str] = Field(default_factory=list)
    inferred: list[str] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)
    checked: list[str] = Field(default_factory=list)


class Audit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    date: str
    start_time: str = "09:00"
    lang: Lang = "en"
    warnings: list[Warning] = Field(default_factory=list)
    conditions: ConditionSnapshot | None = None
    transport: TransportPlan | None = None
    amenities: list[Amenity] = Field(default_factory=list)
    webcams: list[Webcam] = Field(default_factory=list)
    escape_points: list[Place] = Field(default_factory=list)
    zones: list[dict[str, Any]] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    generated_at: datetime
    offline: bool = False
    version: str = "0.1.0"

    @model_validator(mode="after")
    def _warnings_sorted(self) -> Audit:
        order = {Severity.critical: 0, Severity.important: 1, Severity.note: 2}
        self.warnings.sort(key=lambda w: order[w.severity])
        return self

    @property
    def max_severity(self) -> Severity | None:
        return self.warnings[0].severity if self.warnings else None


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    name: str
    date: str
    status: AmenityStatus = AmenityStatus.unverified
    verification: Literal["verified", "unverified", "conflicting"] = "unverified"
    evidence: list[Evidence] = Field(default_factory=list)
    web_verification_spec: dict[str, Any] = Field(default_factory=dict)
    lang: Lang = "en"
    generated_at: datetime


# ---------- conversation ----------


class RegisterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Register
    reasons: list[str] = Field(default_factory=list)
    mascot_allowed: bool
    media_offer_allowed: bool
    emoji_allowed: bool
    severity: Severity | None = None

    @property
    def register(self) -> Register:
        return self.mode

    @property
    def serious(self) -> bool:
        return self.mode is Register.serious


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    lines: list[str]
    lang: Lang
    mode: Register
    attachments: list[str] = Field(default_factory=list)
    buttons: list[str] = Field(default_factory=list)
    intent: Intent = Intent.audit

    @model_validator(mode="after")
    def _twelve(self) -> ChatMessage:
        if len(self.lines) > 12:
            raise ValueError("chat message exceeds 12 lines (FR-M1)")
        return self


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    kind: Intent
    months: list[int] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)


# ---------- schema export ----------

SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    Place,
    Route,
    Difficulty,
    ConditionSnapshot,
    Constraint,
    Amenity,
    Webcam,
    Media,
    Evidence,
    Warning,
    Audit,
    RegisterDecision,
    ChatMessage,
    Suggestion,
    CandidateSet,
    CheckResult,
    TransportPlan,
)


def export_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in SCHEMA_MODELS:
        path = out_dir / f"{model.__name__}.json"
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written
