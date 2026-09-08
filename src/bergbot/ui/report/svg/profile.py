"""Inline SVG elevation profile with exposed / hazard segments coloured, km ticks, hut and stop markers."""

from __future__ import annotations

from xml.sax.saxutils import escape

from bergbot.core.domain import Audit
from bergbot.i18n import Locale
from bergbot.ui.report.svg.map import SEG_COLOUR


def render_profile_svg(audit: Audit, L: Locale, width: int = 720, height: int = 220) -> str:
    prof = audit.route.profile or []
    if len(prof) < 2:
        return f'<p class="muted">{escape(L.t("report.labels.not_checked"))}</p>'
    pad_l, pad_r, pad_t, pad_b = 44, 12, 12, 26
    W, H = width - pad_l - pad_r, height - pad_t - pad_b
    kms = [p[0] for p in prof]
    eles = [p[1] for p in prof]
    k_max = kms[-1] or 1.0
    e_min, e_max = min(eles), max(eles)
    span = max(e_max - e_min, 100.0)
    e_lo = e_min - span * 0.08
    e_hi = e_max + span * 0.12

    def x(k: float) -> float:
        return pad_l + k / k_max * W

    def y(e: float) -> float:
        return pad_t + (e_hi - e) / (e_hi - e_lo) * H

    pts = " ".join(f"{x(k):.1f},{y(e):.1f}" for k, e in zip(kms, eles, strict=True))
    area = f"{x(0):.1f},{y(e_lo):.1f} {pts} {x(k_max):.1f},{y(e_lo):.1f}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(L.t("report.labels.elevation_profile"))}" class="profile">'
    ]
    parts.append(f'<rect width="{width}" height="{height}" fill="#fff"/>')
    # horizontal grid every 100/200/500 m
    step = 100 if span <= 600 else 200 if span <= 1500 else 500
    e = int(e_lo // step + 1) * step
    while e < e_hi:
        parts.append(
            f'<line x1="{pad_l}" y1="{y(e):.1f}" x2="{width - pad_r}" y2="{y(e):.1f}" stroke="#e5eaef" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 6}" y="{y(e) + 3:.1f}" font-size="10" text-anchor="end" fill="#667" font-family="system-ui,sans-serif">{e}</text>'
        )
        e += step
    parts.append(f'<polygon points="{area}" fill="#dbe7f7"/>')
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#1f6feb" stroke-width="2"/>')
    # coloured segments
    for seg in audit.route.segments:
        colour = SEG_COLOUR.get(seg.kind, "#e07b00")
        sub = [
            (k, e) for k, e in zip(kms, eles, strict=True) if seg.from_km - 0.013 <= k <= seg.to_km + 0.013
        ]
        if len(sub) >= 2:
            sp = " ".join(f"{x(k):.1f},{y(e):.1f}" for k, e in sub)
            parts.append(
                f'<polyline points="{sp}" fill="none" stroke="{colour}" stroke-width="4" stroke-linecap="round"><title>{escape(seg.label or seg.kind.value)}</title></polyline>'
            )
    # km ticks
    tick = 1 if k_max <= 12 else 2 if k_max <= 30 else 5
    k = 0
    while k <= k_max:
        parts.append(
            f'<line x1="{x(k):.1f}" y1="{pad_t + H}" x2="{x(k):.1f}" y2="{pad_t + H + 4}" stroke="#667"/>'
        )
        parts.append(
            f'<text x="{x(k):.1f}" y="{height - 8}" font-size="10" text-anchor="middle" fill="#667" font-family="system-ui,sans-serif">{k}</text>'
        )
        k += tick
    parts.append(
        f'<text x="{width - pad_r}" y="{height - 8}" font-size="10" text-anchor="end" fill="#667" font-family="system-ui,sans-serif">{escape(L.t("report.labels.km"))}</text>'
    )
    # markers for huts and stops on the profile
    for a in audit.amenities:
        if a.km is None or a.kind.value not in ("hut", "restaurant", "lift", "water"):
            continue
        ek = _ele_at(prof, a.km)
        colour = {"hut": "#8a5a1a", "restaurant": "#8a5a1a", "lift": "#444", "water": "#0b7285"}[a.kind.value]
        parts.append(
            f'<g><title>{escape(a.name)} km {a.km}</title><circle cx="{x(a.km):.1f}" cy="{y(ek):.1f}" r="4" fill="{colour}" stroke="#fff" stroke-width="1"/></g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _ele_at(prof: list[list[float]], km: float) -> float:
    for k, e in prof:
        if k >= km:
            return float(e)
    return float(prof[-1][1])
