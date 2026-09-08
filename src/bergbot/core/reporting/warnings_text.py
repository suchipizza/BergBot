"""Turn a `Warning` into localised (title, body) using locales/*/warnings.yaml. Unknown placeholders render as
'—' rather than raising, so a partially filled finding still surfaces (FR-D5)."""

from __future__ import annotations

from string import Formatter
from typing import Any

from bergbot.core.domain import Warning
from bergbot.i18n import Locale


class _Safe(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "—"


class _Fmt(Formatter):
    def get_value(self, key: int | str, args: Any, kwargs: Any) -> Any:
        if isinstance(key, str):
            return kwargs.get(key, "—")
        return super().get_value(key, args, kwargs)

    def format_field(self, value: Any, format_spec: str) -> Any:
        try:
            return super().format_field(value, format_spec)
        except (ValueError, TypeError):
            return str(value)


_fmt = _Fmt()


def format_warning(w: Warning, L: Locale) -> tuple[str, str]:
    title = L.t(f"warnings.{w.type.value}.title")
    body_tpl = L.get(f"warnings.{w.type.value}.body", "")
    params = dict(w.params)
    if w.type.value == "avalanche_context" and "text" not in params:
        lvl = params.get("level")
        label = L.get(f"safety.danger_levels.{lvl}", "") if lvl else ""
        params["text"] = L.t(
            "safety.terms.avalanche_not_interpreted", level=lvl if lvl is not None else "—", label=label
        )
    if w.type.value == "fire_danger" and "label" in params and not params.get("label"):
        params["label"] = L.get(f"safety.danger_levels.{params.get('level')}", "")
    for k, v in list(params.items()):
        if isinstance(v, float):
            params[k] = f"{v:g}"
    body = _fmt.vformat(str(body_tpl), (), _Safe(params))
    return title, body


def severity_marker(w: Warning, L: Locale) -> str:
    return L.t(f"ui.severity_marker.{w.severity.value}")


def severity_label(w: Warning, L: Locale) -> str:
    return L.t(f"ui.severity.{w.severity.value}")
