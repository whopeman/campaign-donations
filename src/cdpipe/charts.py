"""
src/cdpipe/charts.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Server-side SVG charts that do not rely on colour alone. Every
          series gets a colour from the Okabe-Ito colour-blind-safe palette
          AND a distinct fill pattern (hatching, dots, cross-hatch), plus a
          text legend with the amount and percentage.
Usage   : pie_svg([Slice("Support", 750, "support"), ...], title="...", uid="c1")
          stacked_bars_svg([Bar("2024", [Slice(...), ...]), ...], title="...", uid="c2")
Change log:
  2026-10-26  0.1.0  Initial version: pie and stacked bars.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from xml.sax.saxutils import escape

from cdpipe.format import pct, usd

SVG_NS = "http://www.w3.org/2000/svg"

# Okabe & Ito (2008) palette, chosen to stay distinct for the common forms of
# colour blindness. Patterns carry the meaning when colour cannot.
_STYLES: dict[str, tuple[str, str]] = {
    "support": ("#0072B2", "diag"),
    "oppose": ("#D55E00", "cross"),
    "DEM": ("#56B4E9", "dots"),
    "REP": ("#E69F00", "horiz"),
    "IND": ("#009E73", "vert"),
    "LIB": ("#F0E442", "rdiag"),
    "GRE": ("#009E73", "grid"),
    "OTHER": ("#999999", "solid"),
    "indiv": ("#009E73", "dots"),
    "unitemized": ("#F0E442", "rdiag"),
    "pac": ("#CC79A7", "grid"),
}
_FALLBACK = [
    ("#CC79A7", "diag"),
    ("#009E73", "dots"),
    ("#F0E442", "cross"),
    ("#56B4E9", "horiz"),
    ("#999999", "vert"),
    ("#000000", "solid"),
]


@dataclass(frozen=True)
class Slice:
    label: str
    amount: float
    kind: str


@dataclass(frozen=True)
class Bar:
    label: str
    parts: list[Slice]


def _style(kind: str, order: int) -> tuple[str, str]:
    return _STYLES.get(kind) or _FALLBACK[order % len(_FALLBACK)]


def _pattern(pid: str, color: str, kind: str) -> str:
    ink = "#000000" if color in {"#F0E442", "#E69F00", "#56B4E9"} else "#FFFFFF"
    marks = {
        "diag": f'<path d="M0,8 L8,0" stroke="{ink}" stroke-width="2"/>',
        "rdiag": f'<path d="M0,0 L8,8" stroke="{ink}" stroke-width="2"/>',
        "cross": f'<path d="M0,8 L8,0 M0,0 L8,8" stroke="{ink}" stroke-width="1.5"/>',
        "horiz": f'<path d="M0,4 L8,4" stroke="{ink}" stroke-width="2"/>',
        "vert": f'<path d="M4,0 L4,8" stroke="{ink}" stroke-width="2"/>',
        "grid": f'<path d="M4,0 L4,8 M0,4 L8,4" stroke="{ink}" stroke-width="1"/>',
        "dots": f'<circle cx="4" cy="4" r="1.6" fill="{ink}"/>',
        "solid": "",
    }[kind]
    return (
        f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="8" height="8">'
        f'<rect width="8" height="8" fill="{color}"/>{marks}</pattern>'
    )


def _defs(uid: str, kinds: list[str]) -> tuple[str, dict[str, str]]:
    ids: dict[str, str] = {}
    out = []
    for i, k in enumerate(kinds):
        if k in ids:
            continue
        pid = f"{uid}-p{len(ids)}"
        color, shape = _style(k, i)
        ids[k] = pid
        out.append(_pattern(pid, color, shape))
    return "<defs>" + "".join(out) + "</defs>", ids


def _open(width: int, height: int, title: str) -> str:
    return (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 {width} {height}" role="img" '
        f'class="chart"><title>{escape(title)}</title>'
    )


def _legend(slices: list[Slice], ids: dict[str, str], total: float, x: int, y: int) -> str:
    rows = []
    for i, s in enumerate(slices):
        ty = y + i * 26
        rows.append(
            f'<rect x="{x}" y="{ty}" width="18" height="18" fill="url(#{ids[s.kind]})" '
            f'stroke="#333"/>'
            f'<text x="{x + 26}" y="{ty + 14}">{escape(s.label)}: {usd(s.amount)} '
            f"({pct(s.amount, total)})</text>"
        )
    return "".join(rows)


def pie_svg(slices: list[Slice], title: str, uid: str = "pie") -> str:
    slices = [s for s in slices if s.amount > 0]
    total = sum(s.amount for s in slices)
    height = max(200, 30 + 26 * len(slices))
    head = _open(620, height, title)
    if not slices:
        return head + '<text x="10" y="100">No reported spending</text></svg>'

    defs, ids = _defs(uid, [s.kind for s in slices])
    cx, cy, r = 100, 100, 90
    parts = []
    if len(slices) == 1:
        s = slices[0]
        parts.append(
            f'<circle class="slice" cx="{cx}" cy="{cy}" r="{r}" fill="url(#{ids[s.kind]})" '
            f'stroke="#333"><title>{escape(s.label)}: {usd(s.amount)} (100.0%)</title></circle>'
        )
    else:
        angle = -math.pi / 2
        for s in slices:
            sweep = 2 * math.pi * s.amount / total
            x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
            angle += sweep
            x2, y2 = cx + r * math.cos(angle), cy + r * math.sin(angle)
            large = 1 if sweep > math.pi else 0
            d = f"M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 {large} 1 {x2:.2f},{y2:.2f} Z"
            tip = f"{escape(s.label)}: {usd(s.amount)} ({pct(s.amount, total)})"
            parts.append(
                f'<path class="slice" d="{d}" fill="url(#{ids[s.kind]})" stroke="#333" '
                f'stroke-width="1"><title>{tip}</title></path>'
            )
    legend = _legend(slices, ids, total, 210, 20)
    return head + defs + "".join(parts) + legend + "</svg>"


def stacked_bars_svg(bars: list[Bar], title: str, uid: str = "bars") -> str:
    """One horizontal bar per row (e.g. per cycle), split by kind (e.g. party)."""
    bars = [Bar(b.label, [p for p in b.parts if p.amount > 0]) for b in bars]
    bars = [b for b in bars if b.parts]
    kinds: list[str] = []
    labels: dict[str, str] = {}
    for b in bars:
        for p in b.parts:
            if p.kind not in kinds:
                kinds.append(p.kind)
                labels[p.kind] = p.label
    height = 40 + 34 * len(bars) + 26 * len(kinds)
    head = _open(640, height, title)
    if not bars:
        return head + '<text x="10" y="30">No reported contributions</text></svg>'

    defs, ids = _defs(uid, kinds)
    peak = max(sum(p.amount for p in b.parts) for b in bars)
    x0, width = 70, 420
    rows = []
    for i, b in enumerate(bars):
        y = 10 + i * 34
        total = sum(p.amount for p in b.parts)
        rows.append(f'<text x="0" y="{y + 18}">{escape(b.label)}</text>')
        x = float(x0)
        for p in b.parts:
            w = width * p.amount / peak
            tip = f"{escape(b.label)} {escape(p.label)}: {usd(p.amount)} ({pct(p.amount, total)})"
            rows.append(
                f'<rect class="seg" x="{x:.2f}" y="{y}" width="{w:.2f}" height="24" '
                f'fill="url(#{ids[p.kind]})" stroke="#333"><title>{tip}</title></rect>'
            )
            x += w
        rows.append(f'<text x="{x + 6:.2f}" y="{y + 18}">{usd(total)}</text>')
    ly = 20 + 34 * len(bars)
    key = []
    for i, k in enumerate(kinds):
        ty = ly + i * 26
        key.append(
            f'<rect x="{x0}" y="{ty}" width="18" height="18" fill="url(#{ids[k]})" stroke="#333"/>'
            f'<text x="{x0 + 26}" y="{ty + 14}">{escape(labels[k])}</text>'
        )
    return head + defs + "".join(rows) + "".join(key) + "</svg>"
